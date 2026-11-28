import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

/// Помилка запиту до API з повідомленням, яке можна показати користувачу.
class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  /// Перетворює помилку Dio на зрозуміле повідомлення.
  /// FastAPI повертає текст помилки в полі `detail`.
  factory ApiException.fromDio(DioException error) {
    // У режимі розробки виводимо справжню причину в консоль `flutter run`.
    debugPrint(
      'API error [${error.type.name}] ${error.requestOptions.method} '
      '${error.requestOptions.uri} → ${error.response?.statusCode}: '
      '${error.error ?? error.message}',
    );

    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return const ApiException(
          'Немає зв\'язку з сервером. Перевірте інтернет і спробуйте ще раз.',
        );
      default:
        break;
    }

    final response = error.response;
    final statusCode = response?.statusCode;
    final data = response?.data;

    if (data is Map && data['detail'] is String) {
      return ApiException(data['detail'] as String, statusCode: statusCode);
    }
    if (statusCode == 422) {
      return ApiException('Перевірте правильність введених даних.',
          statusCode: statusCode);
    }
    if (statusCode != null && statusCode >= 500) {
      return ApiException('Помилка сервера. Спробуйте пізніше.',
          statusCode: statusCode);
    }
    return ApiException('Сталася помилка. Спробуйте ще раз.',
        statusCode: statusCode);
  }

  @override
  String toString() => message;
}
