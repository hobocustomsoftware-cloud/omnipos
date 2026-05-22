import '../../data/models/user_profile_model.dart';

/// Successful restoration of a signed-in session (profile loaded).
class AuthSession {
  const AuthSession({required this.profile});

  final UserProfileModel profile;
}
