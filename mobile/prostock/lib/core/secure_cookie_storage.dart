import 'package:cookie_jar/cookie_jar.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Сховище cookie у захищеному сховищі пристрою (Android Keystore / iOS Keychain).
///
/// Бекенд кладе refresh-токен у httpOnly cookie. Зберігаючи cookie тут,
/// застосунок пам'ятає сесію після перезапуску, а токен не лежить відкритим
/// текстом у файлах.
class SecureCookieStorage implements Storage {
  SecureCookieStorage([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  static const _prefix = 'cookie_';
  final FlutterSecureStorage _storage;

  @override
  Future<void> init(bool persistSession, bool ignoreExpires) async {}

  @override
  Future<String?> read(String key) => _storage.read(key: '$_prefix$key');

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: '$_prefix$key', value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: '$_prefix$key');

  @override
  Future<void> deleteAll(List<String> keys) async {
    for (final key in keys) {
      await delete(key);
    }
  }
}
