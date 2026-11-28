/// Налаштування застосунку, які залежать від середовища.
///
/// Адресу бекенду можна змінити під час запуску:
///   flutter run --dart-define=API_BASE_URL=http://192.168.0.10:8000
///
/// За замовчуванням — `10.0.2.2`: так емулятор Android бачить `localhost`
/// комп'ютера, на якому запущено бекенд.
const String apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

/// Ролі, яким дозволено входити в мобільний застосунок.
const Set<String> allowedRoles = {'storekeeper'};
