import 'package:flutter/foundation.dart';

import '../../core/api_exception.dart';
import '../../core/config.dart';
import 'auth_repository.dart';
import 'auth_user.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

/// Стан авторизації всього застосунку. Екрани підписуються на нього
/// і перемикаються між входом та основною частиною.
class AuthController extends ChangeNotifier {
  AuthController(this._repository) {
    _repository.api.onSessionExpired = _onSessionExpired;
  }

  final AuthRepository _repository;

  AuthStatus _status = AuthStatus.unknown;
  AuthUser? _user;

  AuthStatus get status => _status;
  AuthUser? get user => _user;

  /// Під час запуску пробуємо відновити попередню сесію.
  Future<void> restoreSession() async {
    final user = await _repository.restoreSession();
    if (user != null && allowedRoles.contains(user.role)) {
      _setUser(user);
    } else {
      if (user != null) await _repository.logout();
      _setUser(null);
    }
  }

  /// Кидає [ApiException] з повідомленням для користувача.
  Future<void> login(String email, String password) async {
    final user = await _repository.login(email.trim(), password);
    if (!allowedRoles.contains(user.role)) {
      await _repository.logout();
      throw const ApiException(
        'Мобільний застосунок призначений для комірників. '
        'Скористайтеся веб-версією ProStock.',
      );
    }
    _setUser(user);
  }

  Future<void> logout() async {
    await _repository.logout();
    _setUser(null);
  }

  void _onSessionExpired() => _setUser(null);

  void _setUser(AuthUser? user) {
    _user = user;
    _status =
        user == null ? AuthStatus.unauthenticated : AuthStatus.authenticated;
    notifyListeners();
  }
}
