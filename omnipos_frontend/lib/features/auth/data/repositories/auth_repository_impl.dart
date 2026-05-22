import 'package:dio/dio.dart';

import '../../../../core/data/network/api_config.dart';
import '../../../../core/data/network/token_vault.dart';
import '../../domain/auth_exception.dart';
import '../../domain/entities/auth_session.dart';
import '../../domain/repositories/auth_repository.dart';
import '../models/user_profile_model.dart';

class AuthRepositoryImpl implements AuthRepository {
  AuthRepositoryImpl({
    required Dio dio,
    required TokenVault vault,
  })  : _dio = dio,
        _vault = vault;

  final Dio _dio;
  final TokenVault _vault;

  @override
  Future<UserProfileModel> login({
    required String username,
    required String password,
    required String apiBaseUrl,
  }) async {
    final base = ApiConfig.normalizeUserInput(apiBaseUrl);
    _dio.options.baseUrl = base;
    await _vault.saveApiBaseUrl(base);

    try {
      final res = await _dio.post<Map<String, dynamic>>(
        ApiPaths.tokenObtain,
        data: <String, dynamic>{
          'username': username,
          'password': password,
        },
        options: Options(extra: {'skipAuthRefresh': true}),
      );
      final data = res.data;
      if (data == null) {
        throw AuthException('Empty token response');
      }
      String? access;
      String? refresh;
      if (data.containsKey('access')) {
        access = data['access'] as String?;
        refresh = data['refresh'] as String?;
      } else if (data.containsKey('token')) {
        access = data['token'] as String?;
      } else {
        throw AuthException('No access token in response');
      }
      if (access == null || access.isEmpty) {
        throw AuthException('Invalid access token');
      }
      await _vault.saveTokens(accessToken: access, refreshToken: refresh);
    } on DioException catch (e) {
      throw AuthException(_dioErrorMessage(e));
    }

    return fetchProfile();
  }

  @override
  Future<UserProfileModel> fetchProfile() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(ApiPaths.userProfile);
      final data = res.data;
      if (data == null) {
        throw AuthException('Empty profile response');
      }
      return UserProfileModel.fromJson(data);
    } on DioException catch (e) {
      throw AuthException(_dioErrorMessage(e));
    }
  }

  @override
  Future<void> logout({bool clearApiBase = false}) async {
    if (clearApiBase) {
      await _vault.clearAll();
    } else {
      await _vault.clearTokens();
    }
  }

  @override
  Future<AuthSession?> tryRestoreSession() async {
    final base = await _vault.readApiBaseUrl();
    final access = await _vault.readAccessToken();
    if (base == null || base.isEmpty || access == null || access.isEmpty) {
      return null;
    }
    _dio.options.baseUrl = base;
    try {
      final profile = await fetchProfile();
      return AuthSession(profile: profile);
    } on AuthException {
      await logout();
      return null;
    }
  }

  static String _dioErrorMessage(DioException e) {
    final data = e.response?.data;
    if (data is Map<String, dynamic>) {
      final detail = data['detail'];
      if (detail is String) {
        return detail;
      }
      final nonField = data['non_field_errors'];
      if (nonField is List && nonField.isNotEmpty) {
        return nonField.first.toString();
      }
    }
    return e.message ?? 'Network error';
  }
}
