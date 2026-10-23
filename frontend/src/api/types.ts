// Контракт даних між веб-панеллю та бекендом.
// Імена полів і значення enum узгоджені з backend/app/*/models.py та backend/app/core/enums.py.
// Повний опис ендпоінтів — у frontend/API.md.

// ── Enum-и (backend/app/core/enums.py) ─────────────────────────────────────

export type RoleName = 'root' | 'administrator' | 'warehouse_manager' | 'storekeeper';
export type UserStatus = 'active' | 'inactive' | 'blocked';
export type ZoneType = 'inbound_dock' | 'storage_area' | 'outbound_dock';
export type ObstacleType = 'column' | 'pillar' | 'niche' | 'restricted_zone' | 'other';
export type PointType = 'inbound' | 'outbound' | 'general_entry';
export type ShelfStatus = 'active' | 'occupied' | 'inactive';

// ── Склад ─────────────────────────────────────────────────────────────────

export interface Warehouse {
  warehouse_id: number;
  warehouse_name: string;
  warehouse_address: string | null;
  total_warehouse_area: number;
}

// ── Мапа складу ───────────────────────────────────────────────────────────
// Усі координати й розміри — у метрах. coord_x / coord_y — центр об'єкта.
// length — розмір уздовж власної осі X об'єкта (до повороту), width — уздовж осі Y.
// rotation_angle — поворот у градусах за годинниковою стрілкою.

/** Вершина контуру приміщення (WarehouseWalls). */
export interface WallVertex {
  vertex_order: number;
  coord_x: number;
  coord_y: number;
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
  /** Посада для відображення ("Водій навантажувача"). null — показується назва ролі. */
  position: string | null;
  on_shift: boolean;
  created_at: string;
}

export interface NewUser {
  first_name: string;
  last_name: string;
  user_email: string;
  password: string;
  role: RoleName;
  warehouse_id: number;
}

// ── Авторизація ───────────────────────────────────────────────────────────

export interface Session {
  token: string;
  email: string;
  role: string;
  expiresAt: number;
}
