import 'package:flutter/foundation.dart';

/// Central API configuration. Override at build time:
/// `flutter build apk --dart-define=API_BASE_URL=https://api.example.com/`
class ApiConfig {
  ApiConfig._();

  /// Default OmniPOS dev server (django-tenants: use hostname that resolves to a tenant).
  static String get defaultBaseUrl {
    const fromEnv = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: '',
    );
    if (fromEnv.isNotEmpty) {
      return _normalizeBaseUrl(fromEnv);
    }
    if (kIsWeb) {
      // Same host as Flutter web app is often wrong for API; devs should set API_BASE_URL.
      return 'http://localhost:8000/';
    }
    return 'http://127.0.0.1:8000/';
  }

  static String _normalizeBaseUrl(String raw) {
    var s = raw.trim();
    if (s.isEmpty) {
      return 'http://127.0.0.1:8000/';
    }
    if (!s.endsWith('/')) {
      s = '$s/';
    }
    if (!s.startsWith(RegExp(r'https?://'))) {
      s = 'http://$s';
    }
    return s;
  }

  /// Login field: accepts ``127.0.0.1:8000`` or full ``https://api.shop/``.
  static String normalizeUserInput(String? raw) {
    final input = (raw ?? '').trim();
    if (input.isEmpty) {
      return defaultBaseUrl;
    }
    return _normalizeBaseUrl(input);
  }
}

/// Relative paths appended to [Dio.options.baseUrl].
class ApiPaths {
  ApiPaths._();

  static const userProfile = 'api/accounts/user/profile/';
  static const tokenObtain = 'api/token/';
  static const tokenRefresh = 'api/token/refresh/';
}
