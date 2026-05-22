import '../entities/auth_session.dart';
import '../../data/models/user_profile_model.dart';

/// Login, profile hydration, and secure session lifecycle (implements app auth rules).
abstract class AuthRepository {
  Future<UserProfileModel> login({
    required String username,
    required String password,
    required String apiBaseUrl,
  });

  Future<UserProfileModel> fetchProfile();

  /// Clears tokens; optional full reset of remembered API host.
  Future<void> logout({bool clearApiBase = false});

  /// When access + API base exist in [TokenVault], validates by fetching profile.
  Future<AuthSession?> tryRestoreSession();
}
