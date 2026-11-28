import 'package:dio/dio.dart';

import '../../core/api_client.dart';
import '../../core/api_exception.dart';
import 'auth_user.dart';

/// Запити до `/api/v1/auth/*`.
class AuthRepository {
  AuthRepository(this._api);

  final ApiClient _api;

  ApiClient get api => _api;

  Future<AuthUser> login(String email, String password) async {
    try {
      final response = await _api.dio.post<Map<String, dynamic>>(
        '/auth/login',
        data: {'email': email, 'password': password},
      );
      final data = response.data!;
      _api.accessToken = data['access_token'] as String;
      return AuthUser.fromJson(data['user'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Відновлює сесію за збереженим refresh-cookie.
  /// Повертає `null`, якщо сесії немає або вона прострочена.
  Future<AuthUser?> restoreSession() async {
    try {
      final data = await _api.refresh();
      return AuthUser.fromJson(data['user'] as Map<String, dynamic>);
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        await _api.clearSession();
      }
      return null;
    }
  }

  Future<void> logout() async {
    try {
      await _api.dio.post<void>('/auth/logout');
    } on DioException {
      // Навіть якщо сервер недоступний, локально виходимо.
    } finally {
      await _api.clearSession();
    }
  }
}
