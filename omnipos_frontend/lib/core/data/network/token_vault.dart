import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persists access / refresh credentials using platform keychains / encrypted prefs.
class TokenVault {
  TokenVault({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _kAccess = 'omnipos.jwt.access';
  static const _kRefresh = 'omnipos.jwt.refresh';
  static const _kApiBase = 'omnipos.api_base_url';

  Future<void> saveTokens({
    required String accessToken,
    String? refreshToken,
  }) async {
    await _storage.write(key: _kAccess, value: accessToken);
    if (refreshToken != null && refreshToken.isNotEmpty) {
      await _storage.write(key: _kRefresh, value: refreshToken);
    } else {
      await _storage.delete(key: _kRefresh);
    }
  }

  Future<void> saveApiBaseUrl(String baseUrl) {
    return _storage.write(key: _kApiBase, value: baseUrl);
  }

  Future<String?> readAccessToken() => _storage.read(key: _kAccess);

  Future<String?> readRefreshToken() => _storage.read(key: _kRefresh);

  Future<String?> readApiBaseUrl() => _storage.read(key: _kApiBase);

  Future<void> clearTokens() async {
    await _storage.delete(key: _kAccess);
    await _storage.delete(key: _kRefresh);
  }

  /// Full sign-out (tokens + remembered host).
  Future<void> clearAll() async {
    await clearTokens();
    await _storage.delete(key: _kApiBase);
  }
}
