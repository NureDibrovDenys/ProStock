// Контракт даних між веб-панеллю та бекендом.
// Імена полів і значення enum узгоджені з backend/app/*/models.py та backend/app/core/enums.py.
// Повний опис ендпоінтів - у frontend/API.md.

// ── Enum-и (backend/app/core/enums.py) ─────────────────────────────────────

export type RoleName = 'root' | 'administrator' | 'warehouse_manager' | 'storekeeper';
export type UserStatus = 'active' | 'inactive' | 'blocked';
export type ZoneType = 'inbound_dock' | 'storage_area' | 'outbound_dock';
export type ObstacleType = 'column' | 'pillar' | 'niche' | 'restricted_zone' | 'other';
export type PointType = 'inbound' | 'outbound' | 'general_entry';
export type ShelfStatus = 'active' | 'occupied' | 'inactive';
export type InactiveReason = 'damaged' | 'maintenance' | 'stocktaking' | 'quality_control' | 'other';

// ── Склад ─────────────────────────────────────────────────────────────────

export interface Warehouse {
  warehouse_id: number;
  warehouse_name: string;
  warehouse_address: string | null;
  total_warehouse_area: number;
}

/** Тіло POST / PATCH /warehouses - бекенд приймає інші імена полів, ніж віддає. */
export interface WarehouseInput {
  name: string;
  address: string | null;
  /** Площа, м² (> 0). */
  total_area: number;
}

// ── Мапа складу ───────────────────────────────────────────────────────────
// Усі координати й розміри - у метрах. coord_x / coord_y - центр об'єкта.
// length - розмір уздовж власної осі X об'єкта (до повороту), width - уздовж осі Y.
// rotation_angle - поворот у градусах за годинниковою стрілкою.

/**
 * Вершина контуру приміщення (WarehouseWall). Вершини - по внутрішній грані стіни,
 * полігон простий (без самоперетинів), знакова площа за vertex_order додатна.
 */
export interface WallVertex {
  vertex_order: number;
  coord_x: number;
  coord_y: number;
}

/**
 * Внутрішня перегородка (WarehousePartition) - відрізок по осьовій лінії стіни.
 * height: null - до стелі.
 */
export interface MapPartition {
  partition_id?: number;
  start_x: number;
  start_y: number;
  end_x: number;
  end_y: number;
  thickness: number;
  height: number | null;
}

export interface MapRack {
  rack_id?: number;
  rack_code: string;
  coord_x: number;
  coord_y: number;
  length: number;
  width: number;
  rotation_angle: number;
  shelves_count: number;
}

export interface MapObstacle {
  obstacle_id?: number;
  obstacle_name: string | null;
  obstacle_type: ObstacleType;
  coord_x: number;
  coord_y: number;
  length: number;
  width: number;
  rotation_angle: number;
  max_height: number | null;
}

export interface MapZone {
  zone_id?: number;
  zone_name: string;
  zone_type: ZoneType;
  coord_x: number;
  coord_y: number;
  length: number;
  width: number;
  rotation_angle: number;
  max_capacity_m3: number | null;
}

export interface MapEntryPoint {
  point_id?: number;
  point_name: string;
  point_type: PointType;
  coord_x: number;
  coord_y: number;
}

export interface WarehouseMap {
  walls: WallVertex[];
  partitions: MapPartition[];
  racks: MapRack[];
  obstacles: MapObstacle[];
  zones: MapZone[];
  entry_points: MapEntryPoint[];
}

// ── Стелажі та полиці ─────────────────────────────────────────────────────

export interface RackSummary {
  rack_id: number;
  rack_code: string;
  shelves_count: number;
  fill_percent: number;
  volume_fill_percent: number;
  weight_fill_percent: number;
  used_volume_m3: number;
  total_volume_m3: number;
  used_weight_kg: number;
  total_max_weight_kg: number;
  shelves_used: number;
  overloaded: boolean;
}

export interface ShelfInfo {
  shelf_id: number;
  shelf_code: string;
  product_name: string | null;
  occupied: number;
  capacity: number;
  shelf_status: ShelfStatus;
}

export interface RackDetails {
  rack_id: number;
  rack_code: string;
  zone_name: string | null;
  updated_at: string;
  shelves: ShelfInfo[];
}

/**
 * Повні дані полиці - GET /api/v1/warehouses/{id}/racks/{code}/shelves[/{shelf_id}]
 * (backend: ShelfResponse).
 */
export interface Shelf {
  shelf_id: number;
  shelf_code: string;
  /** QR формується на бекенді як «R{rack_code}-{shelf_code}». */
  qr: string;
  rack_id: number;
  /** Ширина, м (> 0). */
  width: string;
  /** Довжина, м (> 0). */
  length: string;
  /** Висота, м (> 0). */
  height: string;
  /** Максимальне навантаження, кг (> 0). */
  max_weight: string;
  is_occupied: boolean;
  status: ShelfStatus;
  inactive_reason: InactiveReason | null;
  volume_m3: number;
  used_volume_m3: number;
  used_weight_kg: number;
  volume_fill_percent: number;
  weight_fill_percent: number;
  free_volume_m3: number;
  free_weight_kg: number;
  items_count: number;
  overloaded: boolean;
}

/**
 * Тіло POST .../shelves - створення полиці (backend: ShelfCreate).
 * Статус «occupied» вручну встановити не можна - його визначають складські операції.
 */
export interface ShelfInput {
  /** Код полиці, унікальний у стелажі (макс. 50 символів). Зміна коду PATCH-ем не передбачена. */
  code: string;
  width: number;
  length: number;
  height: number;
  max_weight: number;
  status: 'active' | 'inactive';
  /** Обовʼязковий, якщо status === 'inactive'. */
  inactive_reason: InactiveReason | null;
}

/** Тіло PATCH .../shelves/{shelf_id} - лише змінені поля (backend: ShelfUpdate, без code). */
export type ShelfPatch = Partial<Omit<ShelfInput, 'code'>>;

// ── Дашборд ───────────────────────────────────────────────────────────────

export interface Operation {
  log_id: number;
  timestamp: string;
  action: string;
}

export interface DashboardStats {
  racks_count: number;
  zones_count: number;
  fill_percent: number;
  fill_change_week: number;
  on_shift: number;
  employees_total: number;
  free_area_m2: number;
  total_area_m2: number;
  updated_at: string;
  rack_fill: Array<Pick<RackSummary, 'rack_id' | 'rack_code' | 'fill_percent'>>;
  recent_operations: Operation[];
}

// ── Користувачі ───────────────────────────────────────────────────────────

export interface User {
  user_id: number;
  user_email: string;
  first_name: string;
  last_name: string;
  role: RoleName;
  status: UserStatus;
  warehouse_id: number | null;
  /** Посада для відображення ("Водій навантажувача"). null - показується назва ролі. */
  position: string | null;
  on_shift: boolean;
  created_at: string;
}

export interface UserList {
  items: User[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface NewUser {
  first_name: string;
  last_name: string;
  user_email: string;
  password: string;
  role: RoleName;
  warehouse_id: number | null;
}

/** Дані комірника від менеджера: роль і склад бекенд призначає сам. */
export type NewStorekeeper = Omit<NewUser, 'role' | 'warehouse_id'>;

// ── Товари ────────────────────────────────────────────────────────────────

export type UnitOfMeasure = 'pcs' | 'kg' | 'pound' | 'box' | 'pallet' | 'other';

export const UNIT_LABELS: Record<UnitOfMeasure, string> = {
  pcs: 'шт',
  kg: 'кг',
  pound: 'фунт',
  box: 'коробка',
  pallet: 'палета',
  other: 'інше',
};

export interface Category {
  category_id: number;
  name: string;
  description: string | null;
  products_count: number;
}

export interface Product {
  product_id: number;
  sku_code: string;
  name: string;
  category_id: number;
  category_name: string | null;
  unit_of_measure: UnitOfMeasure;
  width: string;
  length: string;
  height: string;
  weight: string;
  min_stock_level: string | null;
}

export interface ProductList {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/** Тіло запиту на створення / оновлення товару. */
export interface ProductPayload {
  sku_code: string;
  name: string;
  category_id: number;
  unit_of_measure: UnitOfMeasure;
  width: number;
  length: number;
  height: number;
  weight: number;
  min_stock_level: number | null;
}

export type ProductSortField = 'product_id' | 'sku_code' | 'name' | 'weight' | 'min_stock_level';

export interface ProductQuery {
  search?: string;
  category_id?: number;
  unit_of_measure?: UnitOfMeasure;
  sort_by?: ProductSortField;
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

export interface ImportRowError {
  row: number;
  sku_code: string | null;
  field: string | null;
  message: string;
}

export interface ImportReport {
  filename: string;
  total: number;
  created: number;
  updated: number;
  failed: number;
  categories_created: number;
  errors: ImportRowError[];
}

// ── Довідники: постачальники та одержувачі ────────────────────────────────

export type CounterpartyKind = 'suppliers' | 'recipients';
export type CounterpartyStatus = 'active' | 'inactive' | 'blocked';

/** Постачальник або одержувач - поля спільні (моделі Supplier і Recipient). */
export interface Counterparty {
  id: number;
  company_name: string;
  /** ЄДРПОУ (8 цифр) або ІПН (10 цифр). */
  tax_id: string | null;
  contact_person: string | null;
  phone_number: string | null;
  email: string | null;
  /** Для одержувача - адреса доставки (обов'язкова). */
  address: string | null;
  status: CounterpartyStatus;
}

export type CounterpartyInput = Omit<Counterparty, 'id' | 'status'>;

// ── Накладні (backend/app/orders/schemas.py) ──────────────────────────────

export type OrderStatus = 'draft' | 'in_progress' | 'ready' | 'completed' | 'canceled';

/** Варіант пакування позиції (поле package_type, рядок до 30 символів). */
export type PackageType = 'box' | 'pallet';

export interface InboundOrderItem {
  item_id: number;
  product_id: number;
  /** Decimal приходить рядком, наприклад "120.00". */
  quantity: string;
  package_type: string;
}

export interface InboundOrder {
  inbound_order_id: number;
  supplier_id: number;
  warehouse_id: number;
  /** № супровідного документа постачальника (унікальний). */
  invoice_number: string;
  expected_delivery_date: string;
  order_status: OrderStatus;
  created_by_user_id: number;
  created_at: string;
  items: InboundOrderItem[];
}

export interface InboundOrderItemPayload {
  product_id: number;
  quantity: number;
  package_type: PackageType;
}

export interface InboundOrderPayload {
  supplier_id: number;
  warehouse_id: number;
  invoice_number: string;
  expected_delivery_date: string;
  items: InboundOrderItemPayload[];
}

/**
 * Вихідна накладна (модель OutboundOrder). API ще немає - контракт запропонований фронтендом:
 * поля як у прихідній, але одержувач замість постачальника, а invoice_number присвоює бекенд.
 */
export interface OutboundOrder {
  outbound_order_id: number;
  recipient_id: number;
  warehouse_id: number;
  /** Номер накладної, присвоєний автоматично (унікальний). */
  invoice_number: string;
  planned_shipment_date: string;
  order_status: OrderStatus;
  created_by_user_id: number;
  created_at: string;
  items: OutboundOrderItem[];
}

/** Рядок вихідної накладної - та сама форма, що й у прихідної. */
export type OutboundOrderItem = InboundOrderItem;
export type OutboundOrderItemPayload = InboundOrderItemPayload;

export interface OutboundOrderPayload {
  recipient_id: number;
  warehouse_id: number;
  planned_shipment_date: string;
  items: OutboundOrderItemPayload[];
}

export type OrderType = 'inbound' | 'outbound';

export interface OrderListItem {
  order_type: OrderType;
  order_id: number;
  number: string;
  invoice_number: string;
  counterparty_id: number;
  counterparty_name: string;
  warehouse_id: number;
  order_status: OrderStatus;
  date: string;
  items_count: number;
  total_quantity: string;
}

export interface OrderListResponse {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Shortage {
  product_id: number;
  product_name: string;
  sku_code: string;
  requested: string;
  available: string;
  shortage: string;
}

export interface CapacityShortage {
  product_id: number;
  product_name: string;
  sku_code: string;
  requested: string;
  placed: string;
  unplaced: string;
  reason: string;
}

export interface PostOrderResult {
  order_id: number;
  order_type: OrderType;
  order_status: OrderStatus;
  posted_at: string;
  items_count: number;
  total_quantity: string;
  processed_quantity: string;
}

/** Доступний залишок товару на поточному складі, в одиницях виміру товару. */
export interface StockLevel {
  product_id: number;
  /** Decimal рядком, наприклад "340.00". */
  available: string;
}

/** Результат перевірки вміщуваності партії (FR-4.9, FR-4.10). */
export interface CapacityCheck {
  fits: boolean;
  /** Об'єм партії, м³. */
  required_m3: number;
  /** Вільний об'єм полиць складу зараз, м³. */
  free_m3: number;
  /** Загальна місткість полиць складу, м³. */
  total_m3: number;
}

// ── Авторизація ───────────────────────────────────────────────────────────

export type Permission =
  | 'products_read'
  | 'products_write'
  | 'products_delete'
  | 'products_import'
  | 'products_export'
  | 'users_manage'
  /** Менеджер складу: створення комірників свого складу. */
  | 'storekeepers_manage'
  | 'warehouse_map_write'
  /** Адміністратор і менеджер складу: довідники постачальників та одержувачів. */
  | 'directories_manage'
  /** Адміністратор і менеджер складу: прихідні та вихідні накладні. */
  | 'orders_manage'
  /** Адміністратор і менеджер складу: створення / редагування / видалення полиць. */
  | 'shelves_manage';

export interface AuthUser {
  user_id: number;
  user_email: string;
  first_name: string;
  last_name: string;
  role: RoleName | 'guest';
  status: UserStatus;
  /** ID складу, до якого прив'язаний обліковий запис. null - не прив'язаний (адміністратор). */
  warehouse_id: number | null;
  permissions: Record<Permission, boolean>;
}

export interface Profile extends AuthUser {
  created_at: string;
}

/** Клієнтська сесія: access-токен зберігається лише в памʼяті модуля. */
export interface Session {
  user: AuthUser;
  /** Момент (ms), коли access-токен перестане діяти. */
  expiresAt: number;
}
