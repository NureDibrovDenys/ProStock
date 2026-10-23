// Модель об'єктів конструктора та перетворення до/з формату API (WarehouseMap).
import type { ObstacleType, PointType, WarehouseMap, ZoneType } from '../../api/types';
import { boundsOf, corners, intersects, pointInPolygon, type Bounds, type Point } from './geometry';

export type ShapeKind = 'rack' | 'obst' | 'zin' | 'zstore' | 'zout' | 'entry';

export interface ShapeObject {
  id: string;
  t: ShapeKind;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  a: number;
  /** id запису на бекенді — щоб при збереженні оновити, а не створити заново. */
  serverId?: number;
  shelves?: number;
  cap?: number | null;
  obstacleType?: ObstacleType;
  maxHeight?: number | null;
  pointType?: PointType;
}

export interface RoomObject {
  id: string;
  t: 'room';
  pts: Point[];
}

export type MapObject = ShapeObject | RoomObject;

export const isShape = (o: MapObject): o is ShapeObject => o.t !== 'room';

let counter = 100;
export const nextId = () => `o${counter++}`;

export const ZONE_KIND_TO_TYPE: Record<'zin' | 'zstore' | 'zout', ZoneType> = {
  zin: 'inbound_dock',
  zstore: 'storage_area',
  zout: 'outbound_dock',
};
const ZONE_TYPE_TO_KIND: Record<ZoneType, 'zin' | 'zstore' | 'zout'> = {
  inbound_dock: 'zin',
  storage_area: 'zstore',
  outbound_dock: 'zout',
};

export const DEFAULT_NAMES: Record<ShapeKind, string> = {
  rack: 'R',
  obst: 'Колона',
  zin: 'Зона приймання',
  zstore: 'Зона зберігання',
  zout: 'Зона відвантаження',
  entry: 'Вхід',
};

export const OBSTACLE_TYPES: Array<{ value: ObstacleType; label: string }> = [
  { value: 'column', label: 'Колона' },
  { value: 'pillar', label: 'Стовп' },
  { value: 'niche', label: 'Ніша' },
  { value: 'restricted_zone', label: 'Зона обмеженого доступу' },
  { value: 'other', label: 'Інша перешкода' },
];

export const POINT_TYPES: Array<{ value: PointType; label: string }> = [
  { value: 'general_entry', label: 'Основний вхід' },
  { value: 'inbound', label: 'Точка приймання' },
  { value: 'outbound', label: 'Точка відвантаження' },
];

/** Пресети стелажів: w — довжина, h — глибина (м), s — кількість полиць. */
export const RACK_PRESETS = [
  { n: 'Полицевий легкий', w: 2, h: 0.6, s: 5 },
  { n: 'Фронтальний палетний', w: 2.7, h: 1.1, s: 3 },
  { n: 'Глибинний палетний', w: 2.7, h: 2.2, s: 3 },
  { n: 'Довгий стелаж', w: 6, h: 0.8, s: 4 },
  { n: 'Консольний', w: 4, h: 1, s: 3 },
];

const r2 = (n: number) => Math.round(n * 100) / 100;

export function fromApi(map: WarehouseMap): MapObject[] {
  const objs: MapObject[] = [];
  if (map.walls.length >= 3) {
    const pts = [...map.walls]
      .sort((a, b) => a.vertex_order - b.vertex_order)
      .map((v): Point => [Number(v.coord_x), Number(v.coord_y)]);
    objs.push({ id: nextId(), t: 'room', pts });
  }
  for (const r of map.racks) {
    objs.push({
      id: nextId(),
      t: 'rack',
      serverId: r.rack_id,
      name: r.rack_code,
      x: Number(r.coord_x),
      y: Number(r.coord_y),
      w: Number(r.length),
      h: Number(r.width),
      a: Number(r.rotation_angle ?? 0),
      shelves: r.shelves_count,
    });
  }
  for (const o of map.obstacles) {
    objs.push({
      id: nextId(),
      t: 'obst',
      serverId: o.obstacle_id,
      name: o.obstacle_name ?? DEFAULT_NAMES.obst,
      x: Number(o.coord_x),
      y: Number(o.coord_y),
      w: Number(o.length),
      h: Number(o.width),
      a: Number(o.rotation_angle ?? 0),
      obstacleType: o.obstacle_type,
      maxHeight: o.max_height,
    });
  }
  for (const z of map.zones) {
    objs.push({
      id: nextId(),
      t: ZONE_TYPE_TO_KIND[z.zone_type] ?? 'zstore',
      serverId: z.zone_id,
      name: z.zone_name,
      x: Number(z.coord_x),
      y: Number(z.coord_y),
      w: Number(z.length),
      h: Number(z.width),
      a: Number(z.rotation_angle ?? 0),
      cap: z.max_capacity_m3,
    });
  }
  for (const p of map.entry_points) {
    objs.push({
      id: nextId(),
      t: 'entry',
      serverId: p.point_id,
      name: p.point_name,
      x: Number(p.coord_x),
      y: Number(p.coord_y),
      w: 1,
      h: 1,
      a: 0,
      pointType: p.point_type,
    });
  }
  return objs;
}

export function toApi(objs: MapObject[]): WarehouseMap {
  const map: WarehouseMap = { walls: [], racks: [], obstacles: [], zones: [], entry_points: [] };
  for (const o of objs) {
    if (o.t === 'room') {
      map.walls = o.pts.map(([x, y], i) => ({ vertex_order: i + 1, coord_x: r2(x), coord_y: r2(y) }));
      continue;
    }
    const geo = { coord_x: r2(o.x), coord_y: r2(o.y), length: r2(o.w), width: r2(o.h), rotation_angle: r2(o.a) };
    switch (o.t) {
      case 'rack':
        map.racks.push({ rack_id: o.serverId, rack_code: o.name.trim(), ...geo, shelves_count: o.shelves ?? 1 });
        break;
      case 'obst':
        map.obstacles.push({
          obstacle_id: o.serverId,
          obstacle_name: o.name.trim() || null,
          obstacle_type: o.obstacleType ?? 'column',
          ...geo,
          max_height: o.maxHeight ?? null,
        });
        break;
      case 'entry':
        map.entry_points.push({
          point_id: o.serverId,
          point_name: o.name.trim() || DEFAULT_NAMES.entry,
          point_type: o.pointType ?? 'general_entry',
          coord_x: geo.coord_x,
          coord_y: geo.coord_y,
        });
        break;
      default:
        map.zones.push({
          zone_id: o.serverId,
          zone_name: o.name.trim() || DEFAULT_NAMES[o.t],
          zone_type: ZONE_KIND_TO_TYPE[o.t],
          ...geo,
          max_capacity_m3: o.cap ?? null,
        });
    }
  }
  return map;
}

/** Стелажі, що перетинаються з іншими стелажами / перешкодами або виходять за контур. */
export function findConflicts(objs: MapObject[]): Set<string> {
  const bad = new Set<string>();
  const room = objs.find((o): o is RoomObject => o.t === 'room');
  const shapes = objs.filter(isShape);
  const racks = shapes.filter((o) => o.t === 'rack');
  const blockers = shapes.filter((o) => o.t === 'rack' || o.t === 'obst');
  for (const r of racks) {
    const C = corners(r);
    if (room && !C.every((p) => pointInPolygon(p, room.pts))) bad.add(r.id);
    for (const o of blockers) {
      if (o.id !== r.id && intersects(C, corners(o))) {
        bad.add(r.id);
        bad.add(o.id);
      }
    }
  }
  return bad;
}

export function mapBounds(objs: MapObject[]): Bounds | null {
  const pts: Point[] = [];
  for (const o of objs) {
    if (o.t === 'room') pts.push(...o.pts);
    else pts.push(...corners(o));
  }
  return boundsOf(pts);
}
