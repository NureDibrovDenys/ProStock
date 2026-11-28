import 'package:cookie_jar/cookie_jar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:prostock/core/api_client.dart';
import 'package:prostock/features/auth/auth_controller.dart';
import 'package:prostock/features/auth/auth_repository.dart';
import 'package:prostock/features/auth/login_screen.dart';

void main() {
  late AuthController auth;

  setUp(() {
    final api = ApiClient(cookieJar: CookieJar());
    auth = AuthController(AuthRepository(api));
  });

  Future<void> pumpLogin(WidgetTester tester) =>
      tester.pumpWidget(MaterialApp(home: LoginScreen(auth: auth)));

  testWidgets('екран входу показує поля і кнопку', (tester) async {
    await pumpLogin(tester);

    expect(find.text('Вхід до системи'), findsOneWidget);
    expect(find.text('Пошта'), findsOneWidget);
    expect(find.text('Пароль'), findsOneWidget);
    expect(find.text('Увійти'), findsOneWidget);
  });

  testWidgets('порожня форма не відправляється', (tester) async {
    await pumpLogin(tester);

    await tester.tap(find.text('Увійти'));
    await tester.pump();

    expect(find.text('Введіть пошту'), findsOneWidget);
    expect(find.text('Введіть пароль'), findsOneWidget);
  });

  testWidgets('перевіряється формат пошти', (tester) async {
    await pumpLogin(tester);

    await tester.enterText(find.byType(TextFormField).first, 'not-an-email');
    await tester.enterText(find.byType(TextFormField).last, 'secret');
    await tester.tap(find.text('Увійти'));
    await tester.pump();

    expect(find.text('Невірний формат пошти'), findsOneWidget);
  });

  testWidgets('кнопка показує або ховає пароль', (tester) async {
    await pumpLogin(tester);

    expect(find.byIcon(Icons.visibility_outlined), findsOneWidget);
    await tester.tap(find.byIcon(Icons.visibility_outlined));
    await tester.pump();
    expect(find.byIcon(Icons.visibility_off_outlined), findsOneWidget);
  });
}
