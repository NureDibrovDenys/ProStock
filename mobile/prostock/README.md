# ProStock — мобільний застосунок комірника

Flutter-застосунок для комірників складу. Працює з тим самим бекендом, що й веб-версія (`/api/v1`).

## Вимоги

- **Flutter 3.50.x** (stable). Перевірити: `flutter --version`, оновити: `flutter upgrade`.
- Android Studio з Android SDK, **Android SDK Command-line Tools** та емулятором.
- На Windows — увімкнений **Developer Mode** (потрібен для плагінів).

`flutter doctor` має показувати «No issues found» для Flutter і Android toolchain.

## Запуск

1. Запустити бекенд з кореня репозиторію: `docker compose up`.
2. Запустити емулятор Android.
3. У цій папці:

   ```bash
   flutter pub get
   flutter run
   ```

За замовчуванням застосунок звертається до `http://10.0.2.2:8000` — так емулятор бачить `localhost` комп'ютера.
Для фізичного телефону вкажіть IP комп'ютера в локальній мережі:

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.0.10:8000
```

> Після додавання пакетів або змін у `android/` hot reload не допоможе —
> зупиніть застосунок (`q`) і виконайте `flutter run` знову.

## Вхід

У мобільний застосунок можуть увійти лише **комірники** (роль `storekeeper`).
Стартовий обліковий запис: `worker@prostock.com` / `Worker12345`.

## Структура

```
lib/
  main.dart              точка входу
  app.dart               MaterialApp і перемикання «вхід ↔ головний екран»
  core/
    config.dart          адреса API, дозволені ролі
    theme.dart           кольори й тема (токени з веб-фронтенду)
    api_client.dart      Dio: access-токен у заголовку, автооновлення через /auth/refresh
    api_exception.dart   помилки API → повідомлення для користувача
    secure_cookie_storage.dart  refresh-cookie у захищеному сховищі пристрою
  features/
    auth/                модель користувача, запити /auth/*, стан входу, екран входу
    home/                головний екран (тимчасовий)
```

## Тести

```bash
flutter test
```
