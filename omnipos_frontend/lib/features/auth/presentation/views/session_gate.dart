import 'package:flutter/material.dart';

import '../../data/models/user_profile_model.dart';
import '../../domain/entities/auth_session.dart';
import '../../domain/repositories/auth_repository.dart';
import '../../../pos/presentation/views/pos_counter_view.dart';
import 'login_view.dart';
import 'saas_super_admin_view.dart';

/// Chooses landing screen after bootstrap / login using [UserProfileModel.isSuperuser].
class SessionGate extends StatefulWidget {
  const SessionGate({super.key, required this.repository});

  final AuthRepository repository;

  @override
  State<SessionGate> createState() => _SessionGateState();
}

enum _Screen { booting, login, superAdmin, pos }

class _SessionGateState extends State<SessionGate> {
  _Screen _screen = _Screen.booting;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    final session = await widget.repository.tryRestoreSession();
    if (!mounted) {
      return;
    }
    if (session == null) {
      setState(() => _screen = _Screen.login);
      return;
    }
    _applySession(session);
  }

  void _applySession(AuthSession session) {
    setState(() {
      _screen = session.profile.isSuperuser ? _Screen.superAdmin : _Screen.pos;
    });
  }

  Future<void> _logout() async {
    await widget.repository.logout();
    if (!mounted) {
      return;
    }
    setState(() => _screen = _Screen.login);
  }

  void _onLoginSuccess(UserProfileModel profile) {
    _applySession(AuthSession(profile: profile));
  }

  @override
  Widget build(BuildContext context) {
    switch (_screen) {
      case _Screen.booting:
        return const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        );
      case _Screen.login:
        return LoginView(
          repository: widget.repository,
          onLoginSuccess: _onLoginSuccess,
        );
      case _Screen.superAdmin:
        return SaasSuperAdminView(
          onSignOut: _logout,
        );
      case _Screen.pos:
        return PosCounterView(
          onSignOut: _logout,
        );
    }
  }
}
