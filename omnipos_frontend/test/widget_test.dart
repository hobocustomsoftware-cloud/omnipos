import 'package:flutter_test/flutter_test.dart';

import 'package:omnipos_frontend/features/auth/data/models/user_profile_model.dart';
import 'package:omnipos_frontend/features/auth/domain/entities/auth_session.dart';
import 'package:omnipos_frontend/features/auth/domain/repositories/auth_repository.dart';
import 'package:omnipos_frontend/main.dart';

class _FakeAuthRepository implements AuthRepository {
  @override
  Future<UserProfileModel> fetchProfile() async {
    throw UnimplementedError();
  }

  @override
  Future<UserProfileModel> login({
    required String username,
    required String password,
    required String apiBaseUrl,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<void> logout({bool clearApiBase = false}) async {}

  @override
  Future<AuthSession?> tryRestoreSession() async => null;
}

void main() {
  testWidgets('Login shell shows OmniPOS title', (WidgetTester tester) async {
    await tester.pumpWidget(OmniPosApp(authRepository: _FakeAuthRepository()));
    await tester.pumpAndSettle();
    expect(find.text('OmniPOS'), findsOneWidget);
    expect(find.text('Staff sign in'), findsOneWidget);
  });
}
