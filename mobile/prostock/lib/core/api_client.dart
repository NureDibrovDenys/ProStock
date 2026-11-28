import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';

import 'config.dart';
import 'secure_cookie_storage.dart';

/// HTTP-клієнт для бекенду ProStock.
///
/// - access-токен тримається в пам'яті й додається до кожного запиту;
/// - refresh-токен живе в cookie (його ставить бекенд), cookie зберігаються
///   у захищеному сховищі;
/// - коли access-токен прострочився (401), клієнт один раз оновлює його
///   через `/auth/refresh` і повторює запит.
class ApiClient {
  ApiClient({CookieJar? cookieJar})
      : cookieJar =
            cookieJar ?? PersistCookieJar(storage: SecureCookieStorage()) {
    final options = BaseOptions(
      baseUrl: '$apiBaseUrl/api/v1',
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      contentType: Headers.jsonContentType,
      responseType: ResponseType.json,
    );

    dio = Dio(options);
    // Окремий клієнт для оновлення токена, щоб не зациклити перехоплювач.
    _refreshDio = Dio(options);

    final cookies = CookieManager(this.cookieJar);
    dio.interceptors.addAll([cookies, _AuthInterceptor(this)]);
    _refreshDio.interceptors.add(cookies);
  }

  final CookieJar cookieJar;
  late final Dio dio;
  late final Dio _refreshDio;

  /// Поточний access-токен (лише в пам'яті).
  String? accessToken;

  /// Викликається, коли сесію не вдалося відновити — треба увійти знову.
  void Function()? onSessionExpired;

  Future<Map<String, dynamic>>? _refreshing;

  /// Оновлює access-токен за refresh-cookie. Паралельні виклики чекають
  /// на один і той самий запит, бо бекенд робить ротацію refresh-токена.
  Future<Map<String, dynamic>> refresh() {
    return _refreshing ??= () async {
      try {
        final response =
            await _refreshDio.post<Map<String, dynamic>>('/auth/refresh');
        final data = response.data!;
        accessToken = data['access_token'] as String;
        return data;
      } finally {
        _refreshing = null;
      }
    }();
  }

  /// Скидає сесію локально: токен у пам'яті та всі cookie.
  Future<void> clearSession() async {
    accessToken = null;
    await cookieJar.deleteAll();
  }
}

class _AuthInterceptor extends Interceptor {
  _AuthInterceptor(this._client);

  final ApiClient _client;
  static const _retriedKey = 'auth_retried';

  bool _isAuthPath(RequestOptions options) =>
      options.path.startsWith('/auth/login') ||
      options.path.startsWith('/auth/refresh');

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final token = _client.accessToken;
    if (token != null && !_isAuthPath(options)) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final options = err.requestOptions;
    final canRetry = err.response?.statusCode == 401 &&
        !_isAuthPath(options) &&
        options.extra[_retriedKey] != true;

    if (!canRetry) {
      return handler.next(err);
    }

    try {
      await _client.refresh();
    } on DioException {
      await _client.clearSession();
      _client.onSessionExpired?.call();
      return handler.next(err);
    }

    try {
      options.extra[_retriedKey] = true;
      options.headers['Authorization'] = 'Bearer ${_client.accessToken}';
      final response = await _client.dio.fetch<dynamic>(options);
      handler.resolve(response);
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }
}
