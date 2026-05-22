/// Thrown when login / token exchange fails or the payload is invalid.
class AuthException implements Exception {
  AuthException(this.message);

  final String message;

  @override
  String toString() => 'AuthException: $message';
}
