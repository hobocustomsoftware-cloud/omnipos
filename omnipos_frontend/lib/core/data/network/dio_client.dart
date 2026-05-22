import 'package:dio/dio.dart';

import 'api_config.dart';
import 'token_vault.dart';

typedef SessionExpiredCallback = void Function();

/// Builds a configured [Dio] instance with Bearer injection and optional JWT refresh.
Dio createAuthenticatedDio({
  required TokenVault vault,
  SessionExpiredCallback? onSessionExpired,
  String? initialBaseUrl,
}) {
  final dio = Dio(
    BaseOptions(
      baseUrl: initialBaseUrl ?? ApiConfig.defaultBaseUrl,
      connectTimeout: const Duration(seconds: 20),
      receiveTimeout: const Duration(seconds: 30),
      sendTimeout: const Duration(seconds: 20),
      headers: <String, dynamic>{
        Headers.acceptHeader: Headers.jsonContentType,
        Headers.contentTypeHeader: Headers.jsonContentType,
      },
    ),
  );

  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await vault.readAccessToken();
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (err, handler) async {
        final response = err.response;
        final requestOptions = err.requestOptions;
        if (response?.statusCode != 401) {
          handler.next(err);
          return;
        }
        if (requestOptions.extra['skipAuthRefresh'] == true) {
          handler.next(err);
          return;
        }
        final path = requestOptions.uri.path;
        if (path.contains(ApiPaths.tokenObtain) || path.contains(ApiPaths.tokenRefresh)) {
          handler.next(err);
          return;
        }

        final refresh = await vault.readRefreshToken();
        if (refresh == null || refresh.isEmpty) {
          await vault.clearTokens();
          onSessionExpired?.call();
          handler.next(err);
          return;
        }

        if (requestOptions.extra['_retried'] == true) {
          await vault.clearTokens();
          onSessionExpired?.call();
          handler.next(err);
          return;
        }

        try {
          final refreshDio = Dio(
            BaseOptions(
              baseUrl: requestOptions.baseUrl,
              headers: {
                Headers.acceptHeader: Headers.jsonContentType,
                Headers.contentTypeHeader: Headers.jsonContentType,
              },
            ),
          );
          final tokenRes = await refreshDio.post<Map<String, dynamic>>(
            ApiPaths.tokenRefresh,
            data: <String, dynamic>{'refresh': refresh},
            options: Options(extra: {'skipAuthRefresh': true}),
          );
          final data = tokenRes.data;
          final newAccess = data is Map<String, dynamic> ? data['access'] as String? : null;
          if (newAccess == null || newAccess.isEmpty) {
            await vault.clearTokens();
            onSessionExpired?.call();
            handler.next(err);
            return;
          }
          await vault.saveTokens(accessToken: newAccess, refreshToken: refresh);
          final opts = requestOptions.copyWith(
            extra: Map<String, dynamic>.from(requestOptions.extra)..['_retried'] = true,
          );
          opts.headers['Authorization'] = 'Bearer $newAccess';
          final clone = await dio.fetch<dynamic>(opts);
          handler.resolve(clone);
        } catch (_) {
          await vault.clearTokens();
          onSessionExpired?.call();
          handler.next(err);
        }
      },
    ),
  );

  return dio;
}
