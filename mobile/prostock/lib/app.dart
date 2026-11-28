import 'package:flutter/material.dart';

import 'core/theme.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/login_screen.dart';
import 'features/home/home_screen.dart';

class ProStockApp extends StatelessWidget {
  const ProStockApp({super.key, required this.auth});

  final AuthController auth;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ProStock',
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      home: AuthGate(auth: auth),
    );
  }
}

/// Показує вхід або основну частину залежно від стану авторизації.
class AuthGate extends StatelessWidget {
  const AuthGate({super.key, required this.auth});

  final AuthController auth;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: auth,
      builder: (context, _) => switch (auth.status) {
        AuthStatus.unknown => const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          ),
        AuthStatus.unauthenticated => LoginScreen(auth: auth),
        AuthStatus.authenticated => HomeScreen(auth: auth),
      },
    );
  }
}
