import 'package:flutter/material.dart';

import 'core/data/network/api_config.dart';
import 'core/data/network/dio_client.dart';
import 'core/data/network/token_vault.dart';
import 'features/auth/data/repositories/auth_repository_impl.dart';
import 'features/auth/domain/repositories/auth_repository.dart';
import 'features/auth/presentation/views/session_gate.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final vault = TokenVault();
  final savedBase = await vault.readApiBaseUrl();
  final dio = createAuthenticatedDio(
    vault: vault,
    initialBaseUrl: (savedBase != null && savedBase.isNotEmpty) ? savedBase : ApiConfig.defaultBaseUrl,
  );
  final AuthRepository authRepository = AuthRepositoryImpl(dio: dio, vault: vault);

  runApp(OmniPosApp(authRepository: authRepository));
}

class OmniPosApp extends StatelessWidget {
  const OmniPosApp({super.key, required this.authRepository});

  final AuthRepository authRepository;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'OmniPOS',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF991B1B)),
        useMaterial3: true,
      ),
      home: SessionGate(repository: authRepository),
    );
  }
}
