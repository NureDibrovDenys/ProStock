import 'package:flutter/material.dart';

import 'app.dart';
import 'core/api_client.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/auth_repository.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  final api = ApiClient();
  final auth = AuthController(AuthRepository(api));

  runApp(ProStockApp(auth: auth));
  auth.restoreSession();
}
