// Конструктор складу (2D-мапа). Перенесено з прототипу тіммейта на React + TypeScript:
// контур приміщення полігоном (з редагуванням вершин), внутрішні перегородки, стелажі з поворотом
// і пресетами, перешкоди, зони, точки входу, перевірка колізій і виходу за контур, undo/redo.
// Збереження — PUT /warehouses/{id}/map.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState, type ChangeEvent, type MouseEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'react-toastify';
import type { ObstacleType, PointType, WarehouseMap } from '../api/types';
import { getWarehouseMap, saveWarehouseMap } from '../api/warehouse';
import { MapLayers } from '../components/map/MapLayers';
import { ZoomControls } from '../components/map/ZoomControls';
import mapStyles from '../components/map/map.module.css';
import {
  FINE_STEP,
  angleToEdge,
  closestPointOnSegment,
  corners,
  dist,
  isSimplePolygon,
  movePolygonEdge,
  normalizeAngle,
  pointAtEdgeAngle,
  polygonArea,
  polygonSignedArea,
  segmentsTouch,
  snap,
  snapAngle,
  snapFine,
  withLength,
  type EdgeAngle,
  type Point,
} from '../components/map/geometry';
import {
  DEFAULT_NAMES,
  DEFAULT_PARTITION_THICKNESS,
  MIN_PARTITION_LENGTH,
  OBSTACLE_TYPES,
  POINT_TYPES,
  RACK_PRESETS,
  findConflicts,
  fromApi,
  isPartition,
  isRoom,
  isShape,
  mapBounds,
  nextId,
  toApi,
  validateMap,
  type MapObject,
  type PartitionObject,
  type ShapeKind,
  type ShapeObject,
} from '../components/map/model';
import { LoadingState } from '../components/ui';
import { WAREHOUSE_ID } from '../config';
import { useViewport } from '../hooks/useViewport';
import { useWarehouseName } from '../hooks/useWarehouse';
import { cx } from '../lib/cx';
import styles from './MapEditorPage.module.css';

type Tool = 'select' | 'pan' | 'wall' | 'partition' | ShapeKind;

const TOOLS: Array<{ id: Tool; key: string; name: string; icon: string }> = [
  { id: 'pan', key: 'H', name: 'Рука', icon: '✥' },
  { id: 'select', key: 'V', name: 'Вибір', icon: '↖' },
  { id: 'wall', key: 'W', name: 'Контур', icon: '⬡' },
  { id: 'partition', key: 'P', name: 'Перегор.', icon: '┃' },
  { id: 'rack', key: 'R', name: 'Стелаж', icon: '▤' },
  { id: 'obst', key: 'O', name: 'Перешкода', icon: '▧' },
  { id: 'zin', key: 'I', name: 'Прийман.', icon: '⇩' },
  { id: 'zstore', key: 'S', name: 'Зберіган.', icon: '▦' },
  { id: 'zout', key: 'U', name: 'Відвант.', icon: '⇧' },
  { id: 'entry', key: 'E', name: 'Вхід', icon: '➜' },
];

const HINTS: Record<Tool, string> = {
  select:
    'Клік — вибір · Shift+клік — додати до виділення · Shift+рамка — виділити кілька · Ctrl+A — усе · перетягування — переміщення · ⟳ над об’єктом — поворот (Shift — без кроку 15°) · контур: тягніть вершину, «+» — нова вершина, ребро — зсув · Del — видалити · Ctrl+Z — скасувати',
  pan: 'Перетягуйте, щоб рухати полотно (також: середня кнопка або Пробіл)',
  wall: 'Клік — вершина контуру · Shift — кут 45°/90° · Backspace — прибрати останню · Enter або клік на першу точку — замкнути · Esc — скасувати',
  partition:
    'Клік — початок, клік — кінець (далі ланцюжком) · без сітки, з прив’язкою до стін і вершин · біля стіни показано кут до неї · Shift — кут 45°/90° · Enter — новий ланцюжок · Esc — вийти',
  rack: 'Клік — поставити стелаж за пресетом · потягніть — власний розмір (кількість полиць із пресету)',
  obst: 'Затисніть і потягніть, щоб додати перешкоду (колона, ніша, техзона)',
  zin: 'Затисніть і потягніть, щоб задати зону приймання',
  zstore: 'Затисніть і потягніть, щоб задати зону зберігання',
  zout: 'Затисніть і потягніть, щоб задати зону відвантаження',
  entry: 'Клік — поставити точку входу/виходу',
};

/** Масштаб, що відповідає 100% (пікселів на метр). */
const BASE_SCALE = 22;
/** Радіус прив'язки до вершин і стін, пікселі екрана. */
const MAGNET_PX = 10;
/** Скільки кроків зберігає undo. */
const HISTORY_LIMIT = 100;

const round2 = (n: number) => Math.round(n * 100) / 100;
/** Ручне введення — не більше 3 знаків після коми. */
const round3 = (n: number) => Math.round(n * 1000) / 1000;
/** Поворот ручкою: крок 15°, із Shift — 0,5°. */
const ROTATE_STEP = 15;

export function MapEditorPage() {
  const query = useQuery({
    queryKey: ['map', WAREHOUSE_ID],
    queryFn: () => getWarehouseMap(WAREHOUSE_ID),
    // Редагуємо знімок мапи — фонове оновлення не повинно перезатирати зміни
    refetchOnWindowFocus: false,
    retry: false,
  });

  if (query.isPending) {
    return (
      <div className={styles.loading}>
        <LoadingState label="Завантаження мапи…" />
      </div>
    );
  }
  return (
    <Editor
      initial={query.data ? fromApi(query.data) : []}
      loadError={query.isError ? query.error : null}
      onRetry={() => query.refetch()}
    />
  );
}

type Draft = { t: ShapeKind; x0: number; y0: number; x1: number; y1: number };
type WallDrag = { edgeIndex: number; start: Point; initialPoints: Point[]; normal: Point };
type PartitionDrag = { id: string; mode: 'start' | 'end' };
/**
 * Перетягування виділення: початкові точки кожного об'єкта (центр фігури або кінці перегородки).
 * До сітки прилипає об'єкт під курсором (anchor), решта зсуваються на той самий вектор.
 */
type GroupDrag = { anchor: string; origin: Point; starts: Map<string, Point[]>; delta: Point; moved: boolean };
/** Рамка виділення; base — що було виділено до неї (рамка додає до виділення). */
type Marquee = { from: Point; to: Point; base: string[] };
/** record — окремий крок історії; drag — один крок на весь жест перетягування. */
type HistoryMode = 'record' | 'drag';
/** Що не враховувати під час прив'язки (сам об'єкт, який зараз тягнуть). */
type MagnetExclude = { roomVertex?: number; partitionId?: string };

function Editor({ initial, loadError, onRetry }: { initial: MapObject[]; loadError: Error | null; onRetry: () => void }) {
  const queryClient = useQueryClient();
  const warehouseName = useWarehouseName();

  const [objs, setObjsRaw] = useState<MapObject[]>(initial);
  const [tool, setTool] = useState<Tool>('pan');
  // Виділення: один об'єкт — панель властивостей і ручки, кілька — групові дії
  const [selIds, setSelIds] = useState<string[]>([]);
  const sel = selIds.length === 1 ? selIds[0] : null;
  const setSel = (id: string | null) => setSelIds(id ? [id] : []);
  const [marquee, setMarquee] = useState<Marquee | null>(null);
  const [selVertex, setSelVertex] = useState<number | null>(null);
  const [poly, setPoly] = useState<Point[]>([]);
  const [chainStart, setChainStart] = useState<Point | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [cur, setCur] = useState<Point>([0, 0]);
  const [preset, setPreset] = useState(1);
  const [msg, setMsg] = useState('');
  const [dirty, setDirty] = useState(false);
  const [errorDismissed, setErrorDismissed] = useState(false);
  const [hoveredWall, setHoveredWall] = useState<number | null>(null);

  const vp = useViewport();
  const k = vp.viewport.scale;
  const groupDrag = useRef<GroupDrag | null>(null);
  const wallDrag = useRef<WallDrag | null>(null);
  const vertexDrag = useRef<number | null>(null);
  const partDrag = useRef<PartitionDrag | null>(null);
  const rotateDrag = useRef<string | null>(null);
  const space = useRef(false);
  const msgTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const importInput = useRef<HTMLInputElement>(null);

  // Історія для undo/redo: знімки масиву об'єктів (вони незмінні, тож копіювати не треба)
  const past = useRef<MapObject[][]>([]);
  const future = useRef<MapObject[][]>([]);
  const pendingCheckpoint = useRef(false);
  const objsRef = useRef(objs);
  objsRef.current = objs;
  const saveRef = useRef<() => void>(() => undefined);

  const room = objs.find(isRoom);
  const activeVertex =
    room && sel === room.id && selVertex !== null && selVertex < room.pts.length ? selVertex : null;

  // Актуальний стан для глобальних слухачів клавіатури
  const S = useRef({ tool, sel, selIds, poly, chainStart, vertex: activeVertex });
  S.current = { tool, sel, selIds, poly, chainStart, vertex: activeVertex };

  const pushHistory = () => {
    past.current.push(objsRef.current);
    if (past.current.length > HISTORY_LIMIT) past.current.shift();
    future.current = [];
  };

  const setObjs = (updater: (prev: MapObject[]) => MapObject[], mode: HistoryMode = 'record') => {
    if (mode === 'record' || pendingCheckpoint.current) {
      pushHistory();
      pendingCheckpoint.current = false;
    }
    setObjsRaw(updater);
    setDirty(true);
  };

  const undo = () => {
    const prev = past.current.pop();
    if (!prev) return;
    future.current.push(objsRef.current);
    setObjsRaw(prev);
    setDirty(true);
  };

  const redo = () => {
    const next = future.current.pop();
    if (!next) return;
    past.current.push(objsRef.current);
    setObjsRaw(next);
    setDirty(true);
  };

  const flash = (text: string) => {
    setMsg(text);
    clearTimeout(msgTimer.current);
    msgTimer.current = setTimeout(() => setMsg(''), 4000);
  };

  // Вписати наявну мапу у полотно при відкритті
  useEffect(() => {
    vp.fitTo(mapBounds(initial));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pick = (t: Tool) => {
    setTool(t);
    setPoly([]);
    setChainStart(null);
    setDraft(null);
  };

  const closePoly = () => {
    const p = S.current.poly;
    if (p.length < 3) return;
    if (!isSimplePolygon(p)) return flash('Стіни контуру не можуть перетинатися');
    setObjs((os) => [...os.filter((o) => o.t !== 'room'), { id: nextId(), t: 'room', pts: p }]);
    setPoly([]);
    setTool('select');
  };

  const upd = (id: string, patch: Partial<ShapeObject>, mode: HistoryMode = 'record') =>
    setObjs((os) => os.map((o) => (o.id === id && isShape(o) ? { ...o, ...patch } : o)), mode);

  const updPartition = (id: string, patch: Partial<PartitionObject>, mode: HistoryMode = 'record') =>
    setObjs((os) => os.map((o) => (o.id === id && isPartition(o) ? { ...o, ...patch } : o)), mode);

  /** Змінює контур, лише якщо результат — простий полігон (без самоперетинів). */
  const tryRoomPts = (pts: Point[], mode: HistoryMode = 'record', error?: string) => {
    if (!isSimplePolygon(pts)) {
      if (error) flash(error);
      return false;
    }
    setObjs((os) => os.map((o) => (isRoom(o) ? { ...o, pts } : o)), mode);
    return true;
  };

  const remove = (...ids: string[]) => {
    setObjs((os) => os.filter((o) => !ids.includes(o.id)));
    setSel(null);
    setSelVertex(null);
  };

  /** Повертає виділені фігури й перегородки навколо спільного центру (центр — на сітці, щоб 90° не збивали крок). */
  const rotateGroup = (ids: string[], deg: number) => {
    const items = objsRef.current.filter((o) => ids.includes(o.id));
    const pts = items.flatMap((o) => (isShape(o) ? corners(o) : isPartition(o) ? [o.start, o.end] : []));
    if (!pts.length) return;
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    const c: Point = [snap((Math.min(...xs) + Math.max(...xs)) / 2), snap((Math.min(...ys) + Math.max(...ys)) / 2)];
    const r = (deg * Math.PI) / 180;
    const turn = ([x, y]: Point): Point => [
      round2(c[0] + (x - c[0]) * Math.cos(r) - (y - c[1]) * Math.sin(r)),
      round2(c[1] + (x - c[0]) * Math.sin(r) + (y - c[1]) * Math.cos(r)),
    ];
    setObjs((os) =>
      os.map((o) => {
        if (!ids.includes(o.id)) return o;
        if (isShape(o)) {
          const [x, y] = turn([o.x, o.y]);
          return { ...o, x, y, a: normalizeAngle(o.a + deg) };
        }
        return isPartition(o) ? { ...o, start: turn(o.start), end: turn(o.end) } : o;
      }),
    );
  };

  const startGroupDrag = (anchor: string, origin: Point, ids: string[]) => {
    const starts = new Map<string, Point[]>();
    for (const o of objs) {
      if (!ids.includes(o.id)) continue;
      if (isShape(o)) starts.set(o.id, [[o.x, o.y]]);
      else if (isPartition(o)) starts.set(o.id, [o.start, o.end]);
    }
    groupDrag.current = { anchor, origin, starts, delta: [0, 0], moved: false };
    pendingCheckpoint.current = true;
  };

  const removeVertex = (index: number) => {
    const r = objsRef.current.find(isRoom);
    if (!r) return;
    if (r.pts.length <= 3) return flash('У контурі має бути щонайменше 3 вершини');
    const pts = r.pts.filter((_, i) => i !== index);
    if (tryRoomPts(pts, 'record', 'Без цієї вершини контур перетне сам себе')) setSelVertex(null);
  };

  const setEdgeLength = (index: number, len: number) => {
    if (!room || len < MIN_PARTITION_LENGTH) return;
    const next = (index + 1) % room.pts.length;
    const end = withLength(room.pts[index], room.pts[next], len);
    tryRoomPts(
      room.pts.map((v, i) => (i === next ? end : v)),
      'record',
      'З такою довжиною стіни контур перетне сам себе',
    );
  };

  const setVertex = (index: number, p: Point) => {
    if (!room) return;
    tryRoomPts(
      room.pts.map((v, i) => (i === index ? p : v)),
      'record',
      'Вершина в цьому місці перетне контур',
    );
  };

  // ── Прив'язка ────────────────────────────────────────────────────────────

  const magnetVertices = (ex: MagnetExclude): Point[] => {
    const out: Point[] = [...poly];
    room?.pts.forEach((p, i) => {
      if (i !== ex.roomVertex) out.push(p);
    });
    for (const o of objs) if (isPartition(o) && o.id !== ex.partitionId) out.push(o.start, o.end);
    return out;
  };

  const magnetEdges = (ex: MagnetExclude): Array<[Point, Point]> => {
    const out: Array<[Point, Point]> = [];
    room?.pts.forEach((a, i) => out.push([a, room.pts[(i + 1) % room.pts.length]]));
    for (const o of objs) if (isPartition(o) && o.id !== ex.partitionId) out.push([o.start, o.end]);
    return out;
  };

  /**
   * Пріоритет: вершини та кінці перегородок → кут від попередньої точки (Shift) → стіни →
   * вирівнювання по осях з вершинами → сітка (або 1 см, якщо fine — для перегородок).
   */
  const snapPoint = (
    raw: Point,
    opts: { from?: Point | null; ortho?: boolean; edges?: boolean; align?: boolean; fine?: boolean; ex?: MagnetExclude } = {},
  ): Point => {
    const ex = opts.ex ?? {};
    const grid = opts.fine ? snapFine : snap;
    let best: Point | null = null;
    let bestDist = MAGNET_PX / k;
    for (const v of magnetVertices(ex)) {
      const d = dist(v, raw);
      if (d < bestDist) {
        best = v;
        bestDist = d;
      }
    }
    if (best) return best;
    if (opts.ortho && opts.from) return snapAngle(opts.from, raw, 45, opts.fine ? FINE_STEP : undefined);
    if (opts.edges) {
      for (const [a, b] of magnetEdges(ex)) {
        const c = closestPointOnSegment(raw, a, b);
        const d = dist(c, raw);
        if (d < bestDist) {
          best = c;
          bestDist = d;
        }
      }
      if (best) return best;
    }
    if (opts.align) {
      // Кожна вісь окремо: x/y притягується до найближчої вершини, що лежить на тій самій вертикалі/горизонталі
      const aligned: [number | null, number | null] = [null, null];
      for (const axis of [0, 1] as const) {
        let bestAxis = MAGNET_PX / k;
        for (const v of magnetVertices(ex)) {
          const d = Math.abs(v[axis] - raw[axis]);
          if (d < bestAxis) {
            aligned[axis] = v[axis];
            bestAxis = d;
          }
        }
      }
      return [aligned[0] ?? grid(raw[0]), aligned[1] ?? grid(raw[1])];
    }
    return [grid(raw[0]), grid(raw[1])];
  };

  /** Пунктирні напрямні від найближчих вершин, з якими точка лежить на одній вертикалі/горизонталі. */
  const alignGuides = (p: Point): Array<[Point, Point]> => {
    const out: Array<[Point, Point]> = [];
    for (const axis of [0, 1] as const) {
      let near: Point | null = null;
      for (const v of magnetVertices({})) {
        if (Math.abs(v[axis] - p[axis]) > 1e-6 || dist(v, p) < 1e-6) continue;
        if (!near || dist(v, p) < dist(near, p)) near = v;
      }
      if (near) out.push([near, p]);
    }
    return out;
  };

  /** Точка під курсором з урахуванням прив'язки поточного інструмента. */
  const toolPoint = (raw: Point, shift: boolean): Point => {
    if (tool === 'wall') return snapPoint(raw, { from: poly[poly.length - 1], ortho: shift, align: true });
    if (tool === 'partition') return snapPoint(raw, { from: chainStart, ortho: shift, edges: true, align: true, fine: true });
    return [snap(raw[0]), snap(raw[1])];
  };

  const beginWallDrag = (edgeIndex: number, start: Point, points: Point[], pointerId: number) => {
    const edgeStart = points[edgeIndex];
    const edgeEnd = points[(edgeIndex + 1) % points.length];
    const dx = edgeEnd[0] - edgeStart[0];
    const dy = edgeEnd[1] - edgeStart[1];
    const length = Math.hypot(dx, dy);
    if (length === 0) return;

    const direction = polygonSignedArea(points) >= 0 ? 1 : -1;
    wallDrag.current = {
      edgeIndex,
      start,
      initialPoints: points,
      normal: [(direction * dy) / length, (-direction * dx) / length],
    };
    pendingCheckpoint.current = true;
    setSel(room?.id ?? null);
    setSelVertex(null);
    vp.svgRef.current?.setPointerCapture(pointerId);
  };

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.code === 'KeyS') {
        e.preventDefault();
        saveRef.current();
        return;
      }
      if (/INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName)) return;
      const s = S.current;
      const key = e.key;
      // e.code — щоб Ctrl+Z працював і в українській розкладці
      if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyZ' || e.code === 'KeyY')) {
        e.preventDefault();
        return e.code === 'KeyY' || e.shiftKey ? redo() : undo();
      }
      if ((e.ctrlKey || e.metaKey) && e.code === 'KeyA') {
        // Усе, крім контуру приміщення
        e.preventDefault();
        pick('select');
        setSelVertex(null);
        setSelIds(objsRef.current.filter((o) => !isRoom(o)).map((o) => o.id));
        return;
      }
      if (key === ' ') {
        space.current = true;
        e.preventDefault();
        return;
      }
      if (key === 'Escape') {
        if (s.tool === 'select') setSelIds([]);
        return pick('select');
      }
      if (key === 'Enter') return s.tool === 'partition' ? setChainStart(null) : closePoly();
      if (key === 'Delete' || key === 'Backspace') {
        if (s.tool === 'wall' && s.poly.length) {
          e.preventDefault();
          return setPoly((p) => p.slice(0, -1));
        }
        if (s.tool === 'partition' && s.chainStart) {
          e.preventDefault();
          return setChainStart(null);
        }
        if (s.vertex !== null) {
          e.preventDefault();
          return removeVertex(s.vertex);
        }
        if (s.selIds.length) {
          e.preventDefault();
          return remove(...s.selIds);
        }
        return;
      }
      const lower = key.toLowerCase();
      if (lower === 'q' && s.selIds.length > 1) return rotateGroup(s.selIds, e.shiftKey ? -15 : 15);
      if (lower === 'q' && s.sel) {
        const step = e.shiftKey ? -15 : 15;
        setObjs((os) => os.map((o) => (o.id === s.sel && isShape(o) ? { ...o, a: normalizeAngle(o.a + step) } : o)));
        return;
      }
      const t = TOOLS.find((x) => x.key.toLowerCase() === lower);
      if (t && !e.ctrlKey && !e.metaKey) pick(t.id);
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.key === ' ') space.current = false;
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Попередження браузера при закритті вкладки з незбереженими змінами
  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);

  // ── Події вказівника ─────────────────────────────────────────────────────

  const down = (e: ReactPointerEvent) => {
    if (e.button === 2) return;
    const p = vp.toWorld(e.clientX, e.clientY);

    if (e.button === 1 || tool === 'pan' || space.current) return vp.startPan(e);

    const sp = toolPoint(p, e.shiftKey);
    const target = e.target as Element;
    const capture = () => vp.svgRef.current?.setPointerCapture(e.pointerId);

    if (tool === 'select') {
      // Ручки редагування: вершини контуру, «+» на ребрі, кінці перегородки
      const handle = target.closest('[data-handle]') as HTMLElement | SVGElement | null;
      if (handle) {
        const kind = handle.dataset.handle;
        const index = Number(handle.dataset.index);
        pendingCheckpoint.current = true;
        if (kind === 'vertex' && room) {
          setSelVertex(index);
          vertexDrag.current = index;
        } else if (kind === 'insert' && room) {
          const a = room.pts[index];
          const b = room.pts[(index + 1) % room.pts.length];
          const mid: Point = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
          tryRoomPts([...room.pts.slice(0, index + 1), mid, ...room.pts.slice(index + 1)], 'drag');
          setSelVertex(index + 1);
          vertexDrag.current = index + 1;
        } else if ((kind === 'start' || kind === 'end') && handle.dataset.part) {
          partDrag.current = { id: handle.dataset.part, mode: kind };
        } else if (kind === 'rotate' && sel) {
          rotateDrag.current = sel;
        }
        capture();
        return;
      }

      const wallEl = target.closest('[data-wall-index]') as HTMLElement | SVGElement | null;
      const wallIndex = wallEl ? Number(wallEl.dataset.wallIndex) : NaN;
      if (room && Number.isInteger(wallIndex)) {
        beginWallDrag(wallIndex, p, room.pts, e.pointerId);
        return;
      }

      const el = target.closest('[data-id]') as HTMLElement | SVGElement | null;
      const id = el?.dataset.id;
      const o = id ? objs.find((x) => x.id === id) : undefined;
      const additive = e.shiftKey || e.ctrlKey || e.metaKey;
      setSelVertex(null);
      // Shift/Ctrl по порожньому місці або підлозі приміщення — рамка виділення
      if (additive && (!o || isRoom(o))) {
        setMarquee({ from: p, to: p, base: selIds });
        capture();
        return;
      }
      if (!id) {
        // Порожнє місце: зняти виділення й рухати полотно
        setSel(null);
        return vp.startPan(e);
      }
      if (additive && o) {
        // Додати або прибрати об'єкт; контур у групове виділення не входить
        const base = selIds.filter((x) => x !== room?.id);
        setSelIds(base.includes(id) ? base.filter((x) => x !== id) : [...base, id]);
        return;
      }
      // Клік по вже виділеному об'єкту тягне всю групу
      const group = selIds.includes(id) ? selIds : [id];
      if (!selIds.includes(id)) setSel(id);
      if (o && !isRoom(o)) {
        startGroupDrag(id, p, group);
        capture();
      }
      return;
    }

    if (tool === 'wall') {
      const last = poly[poly.length - 1];
      if (poly.length > 2 && dist(sp, poly[0]) < 1e-6) return closePoly();
      if (last && dist(sp, last) < 1e-6) return;
      // Новий відрізок не може зачіпати попередні (крім сусіднього, з яким має спільну вершину)
      if (last && poly.slice(0, -2).some((a, i) => segmentsTouch(a, poly[i + 1], last, sp))) {
        return flash('Стіни контуру не можуть перетинатися');
      }
      setPoly([...poly, sp]);
      return;
    }

    if (tool === 'partition') {
      if (!chainStart) return setChainStart(sp);
      if (dist(chainStart, sp) < MIN_PARTITION_LENGTH) return;
      const id = nextId();
      setObjs((os) => [
        ...os,
        { id, t: 'partition', start: chainStart, end: sp, thickness: DEFAULT_PARTITION_THICKNESS, height: null },
      ]);
      setChainStart(sp);
      return;
    }

    if (tool === 'entry') {
      const id = nextId();
      setObjs((os) => [
        ...os,
        { id, t: 'entry', name: DEFAULT_NAMES.entry, x: sp[0], y: sp[1], w: 1, h: 1, a: 0, pointType: 'general_entry' },
      ]);
      setSel(id);
      return;
    }

    setDraft({ t: tool, x0: sp[0], y0: sp[1], x1: sp[0], y1: sp[1] });
    capture();
  };

  const move = (e: ReactPointerEvent) => {
    const p = vp.toWorld(e.clientX, e.clientY);
    const sp = toolPoint(p, e.shiftKey);
    setCur(sp);

    if (tool === 'select' && !wallDrag.current) {
      const wall = (e.target as Element).closest('[data-wall-index]') as HTMLElement | SVGElement | null;
      setHoveredWall(wall ? Number(wall.dataset.wallIndex) : null);
    }

    if (vp.movePan(e)) return;

    if (marquee) {
      setMarquee({ ...marquee, to: p });
      return;
    }

    const g = groupDrag.current;
    if (g) {
      const a0 = g.starts.get(g.anchor)?.[0];
      const anchor = objs.find((o) => o.id === g.anchor);
      if (!a0 || !anchor) return;
      const raw: Point = [p[0] - g.origin[0], p[1] - g.origin[1]];
      // Перегородка рухається з кроком 1 см, фігура прилипає центром до сітки
      const delta: Point = isPartition(anchor)
        ? [snapFine(raw[0]), snapFine(raw[1])]
        : [snap(a0[0] + raw[0]) - a0[0], snap(a0[1] + raw[1]) - a0[1]];
      if (delta[0] === g.delta[0] && delta[1] === g.delta[1]) return;
      g.delta = delta;
      g.moved = true;
      const shift = ([x, y]: Point): Point => [round2(x + delta[0]), round2(y + delta[1])];
      setObjs(
        (os) =>
          os.map((o) => {
            const s = g.starts.get(o.id);
            if (!s) return o;
            if (isShape(o)) {
              const [x, y] = shift(s[0]);
              return { ...o, x, y };
            }
            return isPartition(o) ? { ...o, start: shift(s[0]), end: shift(s[1]) } : o;
          }),
        'drag',
      );
      return;
    }

    const rid = rotateDrag.current;
    if (rid) {
      const o = objs.find((x) => x.id === rid);
      if (!o || !isShape(o)) return;
      // Ручка стоїть над об'єктом (локальна вісь -Y), тож кут рахуємо від вертикалі
      const raw = (Math.atan2(p[0] - o.x, o.y - p[1]) * 180) / Math.PI;
      const a = normalizeAngle(e.shiftKey ? Math.round(raw * 2) / 2 : Math.round(raw / ROTATE_STEP) * ROTATE_STEP);
      if (a !== o.a) upd(rid, { a }, 'drag');
      return;
    }

    const wall = wallDrag.current;
    if (wall && room) {
      const distance = snap((p[0] - wall.start[0]) * wall.normal[0] + (p[1] - wall.start[1]) * wall.normal[1]);
      // Крок, після якого контур перетне сам себе, просто не застосовується
      tryRoomPts(movePolygonEdge(wall.initialPoints, wall.edgeIndex, distance), 'drag');
      return;
    }

    const vi = vertexDrag.current;
    if (vi !== null && room) {
      const prev = room.pts[(vi - 1 + room.pts.length) % room.pts.length];
      const q = snapPoint(p, { from: prev, ortho: e.shiftKey, align: true, ex: { roomVertex: vi } });
      if (dist(q, room.pts[vi]) > 1e-9) tryRoomPts(room.pts.map((v, i) => (i === vi ? q : v)), 'drag');
      setCur(q);
      return;
    }

    const pd = partDrag.current;
    if (pd) {
      const part = objs.find((o) => o.id === pd.id);
      if (!part || !isPartition(part)) return;
      const other = pd.mode === 'start' ? part.end : part.start;
      const q = snapPoint(p, {
        from: other,
        ortho: e.shiftKey,
        edges: true,
        align: true,
        fine: true,
        ex: { partitionId: pd.id },
      });
      if (dist(q, other) >= MIN_PARTITION_LENGTH) updPartition(pd.id, pd.mode === 'start' ? { start: q } : { end: q }, 'drag');
      setCur(q);
      return;
    }

    if (draft) setDraft({ ...draft, x1: sp[0], y1: sp[1] });
  };

  const up = (e: ReactPointerEvent) => {
    vp.endPan(e);
    const g = groupDrag.current;
    // Клік без перетягування по об'єкту з групи — залишити виділеним лише його
    if (g && !g.moved && selIds.length > 1) setSel(g.anchor);
    groupDrag.current = null;
    if (marquee) {
      const inside = objectsInRect(objs, marquee.from, marquee.to);
      setSelIds([...new Set([...marquee.base.filter((id) => id !== room?.id), ...inside])]);
      setMarquee(null);
    }
    wallDrag.current = null;
    vertexDrag.current = null;
    partDrag.current = null;
    rotateDrag.current = null;
    pendingCheckpoint.current = false;
    if (!draft) return;

    let w = Math.abs(draft.x1 - draft.x0);
    let h = Math.abs(draft.y1 - draft.y0);
    const P = RACK_PRESETS[preset];
    const click = draft.t === 'rack' && (w < 0.5 || h < 0.5);
    if (click) {
      w = P.w;
      h = P.h;
    }
    if (w >= 0.5 && h >= 0.5) {
      const id = nextId();
      const base: ShapeObject = {
        id,
        t: draft.t,
        name: DEFAULT_NAMES[draft.t],
        x: click ? draft.x0 : (draft.x0 + draft.x1) / 2,
        y: click ? draft.y0 : (draft.y0 + draft.y1) / 2,
        w,
        h,
        a: 0,
      };
      if (draft.t === 'rack') Object.assign(base, { name: nextRackCode(objs), shelves: P.s });
      if (draft.t === 'obst') base.obstacleType = 'column';
      if (draft.t === 'zin' || draft.t === 'zstore' || draft.t === 'zout') base.cap = null;
      setObjs((os) => [...os, base]);
      setSel(id);
    }
    setDraft(null);
  };

  // ── Збереження ───────────────────────────────────────────────────────────

  const conflicts = useMemo(() => findConflicts(objs), [objs]);
  const selected = objs.find((o) => o.id === sel) ?? null;
  const selSet = useMemo(() => new Set(selIds), [selIds]);
  const racksCount = objs.filter((o) => o.t === 'rack').length;

  const mutation = useMutation({
    mutationFn: (map: WarehouseMap) => saveWarehouseMap(WAREHOUSE_ID, map),
    onSuccess: (saved, sent) => {
      // Бекенд повертає мапу з id нових об'єктів; якщо ні — кешуємо надіслане
      queryClient.setQueryData(['map', WAREHOUSE_ID], saved ?? sent);
      queryClient.invalidateQueries({ queryKey: ['racks', WAREHOUSE_ID] });
      setDirty(false);
    },
    onError: (err) => toast.error(`Не вдалося зберегти: ${err.message}`),
  });

  const save = () => {
    const errors = validateMap(objs);
    if (errors.length) return void toast.error(errors.join(' · '));
    const codes = objs.filter((o): o is ShapeObject => o.t === 'rack').map((o) => o.name.trim());
    if (codes.some((c) => !c)) return void toast.error('У кожного стелажа має бути назва (код)');
    if (new Set(codes).size !== codes.length) return void toast.error('Назви стелажів повторюються');
    const conflictCount = conflicts.size;
    if (conflictCount && !window.confirm(`На мапі є конфлікти (${conflictCount}). Зберегти все одно?`)) return;
    mutation.mutate(toApi(objs), {
      onSuccess: () => {
        if (!conflictCount) return void toast.success('Мапу збережено');
        toast.warning(
          `Мапу збережено з конфліктами (${conflictCount}): є перетини стелажів або вихід за межі приміщення`,
        );
      },
    });
  };
  saveRef.current = save;

  const exportJson = () => {
    const data = {
      format: 'prostock-warehouse-map',
      version: 1,
      unit: 'm',
      warehouse_id: WAREHOUSE_ID,
      saved_at: new Date().toISOString(),
      ...toApi(objs),
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `warehouse-${WAREHOUSE_ID}-map.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importJson = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    try {
      const imported = JSON.parse(await file.text()) as Partial<WarehouseMap> & {
        format?: string;
        warehouse_id?: number;
      };
      if (imported.warehouse_id !== undefined && imported.warehouse_id !== WAREHOUSE_ID) {
        throw new Error(`Файл призначений для складу №${imported.warehouse_id}`);
      }
      const collections = ['walls', 'partitions', 'obstacles', 'entry_points', 'racks', 'zones'] as const;
      if (collections.some((collection) => !Array.isArray(imported[collection]))) {
        throw new Error('Файл не містить коректної карти складу');
      }

      const next = fromApi(imported as WarehouseMap);
      if (dirty && !window.confirm('Є незбережені зміни. Замінити їх імпортованою картою?')) return;
      setObjs(() => next);
      setSel(null);
      setSelVertex(null);
      setPoly([]);
      setChainStart(null);
      setDraft(null);
      setTool('select');
      vp.fitTo(mapBounds(next));
      flash('Карту імпортовано. Натисніть Ctrl+S для збереження');
    } catch (error) {
      flash(`Не вдалося імпортувати JSON: ${error instanceof Error ? error.message : 'некоректний файл'}`);
    }
  };

  const goBack = (e: MouseEvent) => {
    if (dirty && !window.confirm('Є незбережені зміни. Вийти з конструктора?')) e.preventDefault();
  };

  // ── Кут перегородки до стіни ─────────────────────────────────────────────

  /** Кут до стіни біля початку перегородки, а якщо початок вільний — біля кінця. */
  const partitionWallAngle = (p: PartitionObject): { end: 'start' | 'end'; info: EdgeAngle } | null => {
    const edges = magnetEdges({ partitionId: p.id });
    const atStart = angleToEdge(p.start, p.end, edges);
    if (atStart) return { end: 'start', info: atStart };
    const atEnd = angleToEdge(p.end, p.start, edges);
    return atEnd ? { end: 'end', info: atEnd } : null;
  };

  /** Повертає перегородку навколо кінця, прикріпленого до стіни, зберігаючи довжину. */
  const setPartitionWallAngle = (p: PartitionObject, deg: number) => {
    const wa = partitionWallAngle(p);
    if (!wa) return;
    const pivot = p[wa.end];
    const other = pointAtEdgeAngle(pivot, wa.info.edge, Math.min(180, Math.max(0, deg)), wa.info.side, dist(p.start, p.end));
    updPartition(p.id, wa.end === 'start' ? { end: other } : { start: other });
  };

  // ── Рендер ───────────────────────────────────────────────────────────────

  const selectedWallAngle = selected && isPartition(selected) ? partitionWallAngle(selected) : null;
  const chainWallAngle =
    tool === 'partition' && chainStart && dist(chainStart, cur) > 1e-6 ? angleToEdge(chainStart, cur, magnetEdges({})) : null;

  const dw = draft ? Math.abs(draft.x1 - draft.x0) : 0;
  const dh = draft ? Math.abs(draft.y1 - draft.y0) : 0;
  const sw = (n: number) => n / k;
  const P = RACK_PRESETS[preset];
  const cursor = tool === 'pan' ? 'grab' : tool === 'select' ? 'default' : 'crosshair';
  const roomDirection = room && polygonSignedArea(room.pts) >= 0 ? 1 : -1;

  return (
    <div className={styles.app}>
      <header className={styles.top}>
        <Link to="/warehouse" className={styles.back} onClick={goBack}>
          ← До складу
        </Link>
        <b>ProStock</b>
        <span className={styles.subtitle}>Конструктор складу · {warehouseName}</span>
        <div className={styles.topActions}>
          <button
            type="button"
            className={styles.topGhost}
            onClick={undo}
            disabled={!past.current.length}
            title="Скасувати (Ctrl+Z)"
            aria-label="Скасувати"
          >
            ↶
          </button>
          <button
            type="button"
            className={styles.topGhost}
            onClick={redo}
            disabled={!future.current.length}
            title="Повторити (Ctrl+Shift+Z)"
            aria-label="Повторити"
          >
            ↷
          </button>
          <button type="button" className={styles.topGhost} onClick={exportJson}>
            Експорт JSON
          </button>
          <input
            ref={importInput}
            type="file"
            accept=".json,application/json"
            className={styles.fileInput}
            onChange={importJson}
            aria-label="Імпорт JSON"
          />
          <button type="button" className={styles.topGhost} onClick={() => importInput.current?.click()}>
            Імпорт JSON
          </button>
          <button
            type="button"
            className={styles.topSave}
            onClick={save}
            disabled={mutation.isPending}
            title="Зберегти (Ctrl+S)"
          >
            {mutation.isPending ? 'Збереження…' : dirty ? 'Зберегти •' : 'Зберегти'}
          </button>
        </div>
      </header>

      <div className={styles.main}>
        <div className={styles.tools}>
          {TOOLS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={cx(styles.tb, tool === t.id && styles.tbOn)}
              title={`${t.name} (${t.key})`}
              onClick={() => pick(t.id)}
            >
              <i>{t.icon}</i>
              <small>{t.name}</small>
            </button>
          ))}
        </div>

        <div className={styles.cv}>
          <svg
            ref={vp.bindSvg}
            className={cx(mapStyles.svg, vp.isPanning() && mapStyles.panning)}
            style={{ cursor: vp.isPanning() ? undefined : cursor }}
            onPointerDown={down}
            onPointerMove={move}
            onPointerUp={up}
            onPointerCancel={up}
            onPointerLeave={() => setHoveredWall(null)}
            onContextMenu={(e) => e.preventDefault()}
          >
            <MapLayers objs={objs} viewport={vp.viewport} size={vp.size} selectedIds={selSet} conflicts={conflicts}>
              {tool === 'select' && room && (
                <g aria-label="Редагування стін">
                  {room.pts.map((start, index) => {
                    const end = room.pts[(index + 1) % room.pts.length];
                    return (
                      <g key={index}>
                        <line
                          data-wall-index={index}
                          x1={start[0]}
                          y1={start[1]}
                          x2={end[0]}
                          y2={end[1]}
                          stroke="transparent"
                          strokeWidth={sw(1.5)}
                          strokeLinecap="round"
                          pointerEvents="stroke"
                          style={{ cursor: 'move' }}
                        />
                        {hoveredWall === index && (
                          <line
                            x1={start[0]}
                            y1={start[1]}
                            x2={end[0]}
                            y2={end[1]}
                            stroke="var(--map-wall-hover)"
                            strokeWidth={sw(0.2)}
                            strokeLinecap="round"
                            pointerEvents="none"
                          />
                        )}
                      </g>
                    );
                  })}
                </g>
              )}
              {tool === 'select' && room && sel === room.id && (
                <g aria-label="Вершини контуру">
                  {room.pts.map((a, i) => {
                    const b = room.pts[(i + 1) % room.pts.length];
                    const len = dist(a, b);
                    const mid: Point = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
                    // Підпис довжини — із зовнішнього боку стіни
                    const off = 14 / k / (len || 1);
                    const lx = mid[0] + roomDirection * (b[1] - a[1]) * off;
                    const ly = mid[1] - roomDirection * (b[0] - a[0]) * off;
                    return (
                      <g key={`e${i}`}>
                        <text
                          x={lx}
                          y={ly}
                          fontSize={11 / k}
                          textAnchor="middle"
                          dominantBaseline="central"
                          fill="var(--map-ink)"
                          pointerEvents="none"
                        >
                          {len.toFixed(2)} м
                        </text>
                        {len * k > 40 && (
                          <g data-handle="insert" data-index={i} style={{ cursor: 'copy' }}>
                            <title>Додати вершину</title>
                            <circle cx={mid[0]} cy={mid[1]} r={sw(6)} fill="#fff" stroke="var(--map-acc)" strokeWidth={sw(1.5)} />
                            <path
                              d={`M${mid[0] - sw(3)} ${mid[1]}H${mid[0] + sw(3)}M${mid[0]} ${mid[1] - sw(3)}V${mid[1] + sw(3)}`}
                              stroke="var(--map-ink)"
                              strokeWidth={sw(1.5)}
                              pointerEvents="none"
                            />
                          </g>
                        )}
                      </g>
                    );
                  })}
                  {room.pts.map((v, i) => (
                    <circle
                      key={`v${i}`}
                      data-handle="vertex"
                      data-index={i}
                      cx={v[0]}
                      cy={v[1]}
                      r={sw(activeVertex === i ? 7 : 5)}
                      fill={activeVertex === i ? 'var(--map-acc)' : '#fff'}
                      stroke="var(--map-pri)"
                      strokeWidth={sw(2)}
                      style={{ cursor: 'move' }}
                    />
                  ))}
                </g>
              )}
              {tool === 'select' && selected && isPartition(selected) && (
                <g aria-label="Кінці перегородки">
                  <text
                    x={(selected.start[0] + selected.end[0]) / 2}
                    y={(selected.start[1] + selected.end[1]) / 2 - selected.thickness / 2 - 10 / k}
                    fontSize={11 / k}
                    textAnchor="middle"
                    fill="var(--map-ink)"
                    pointerEvents="none"
                  >
                    {dist(selected.start, selected.end).toFixed(2)} м
                  </text>
                  {selectedWallAngle && (
                    <AngleMark
                      at={selected[selectedWallAngle.end]}
                      to={selected[selectedWallAngle.end === 'start' ? 'end' : 'start']}
                      info={selectedWallAngle.info}
                      k={k}
                    />
                  )}
                  {(['start', 'end'] as const).map((end) => (
                    <circle
                      key={end}
                      data-handle={end}
                      data-part={selected.id}
                      cx={selected[end][0]}
                      cy={selected[end][1]}
                      r={sw(6)}
                      fill="#fff"
                      stroke="var(--map-acc)"
                      strokeWidth={sw(2)}
                      style={{ cursor: 'move' }}
                    />
                  ))}
                </g>
              )}
              {(tool === 'wall' ||
                tool === 'partition' ||
                vertexDrag.current !== null ||
                partDrag.current !== null) && (
                <g pointerEvents="none">
                  {alignGuides(cur).map(([a, b], i) => (
                    <line
                      key={i}
                      x1={a[0]}
                      y1={a[1]}
                      x2={b[0]}
                      y2={b[1]}
                      stroke="var(--map-acc)"
                      strokeWidth={sw(1)}
                      strokeDasharray={`${sw(5)} ${sw(4)}`}
                    />
                  ))}
                </g>
              )}
              {poly.length > 0 && (
                <g pointerEvents="none">
                  <polyline
                    points={[...poly, cur].map((p) => p.join(',')).join(' ')}
                    fill="none"
                    stroke="var(--map-acc)"
                    strokeWidth={sw(2.5)}
                  />
                  {poly.map((p, i) => (
                    <circle
                      key={i}
                      cx={p[0]}
                      cy={p[1]}
                      r={sw(i === 0 ? 7 : 4)}
                      fill={i === 0 ? 'var(--map-ok)' : 'var(--map-acc)'}
                    />
                  ))}
                  <text x={cur[0] + 0.4} y={cur[1] - 0.4} fontSize={12 / k} fill="var(--map-ink)">
                    {Math.hypot(cur[0] - poly[poly.length - 1][0], cur[1] - poly[poly.length - 1][1]).toFixed(1)} м
                  </text>
                </g>
              )}
              {tool === 'partition' && chainStart && (
                <g pointerEvents="none">
                  <line
                    x1={chainStart[0]}
                    y1={chainStart[1]}
                    x2={cur[0]}
                    y2={cur[1]}
                    stroke="var(--map-acc)"
                    strokeOpacity=".8"
                    strokeWidth={DEFAULT_PARTITION_THICKNESS}
                    strokeLinecap="square"
                  />
                  <circle cx={chainStart[0]} cy={chainStart[1]} r={sw(4)} fill="var(--map-acc)" />
                  <text x={cur[0] + 0.4} y={cur[1] - 0.4} fontSize={12 / k} fill="var(--map-ink)">
                    {dist(chainStart, cur).toFixed(2)} м
                  </text>
                  {chainWallAngle && <AngleMark at={chainStart} to={cur} info={chainWallAngle} k={k} />}
                </g>
              )}
              {tool === 'select' && selected && isShape(selected) && selected.t !== 'entry' && (
                <RotateHandle o={selected} k={k} />
              )}
              {marquee && (
                <rect
                  x={Math.min(marquee.from[0], marquee.to[0])}
                  y={Math.min(marquee.from[1], marquee.to[1])}
                  width={Math.abs(marquee.to[0] - marquee.from[0])}
                  height={Math.abs(marquee.to[1] - marquee.from[1])}
                  fill="var(--map-acc)"
                  fillOpacity=".1"
                  stroke="var(--map-acc)"
                  strokeWidth={sw(1)}
                  strokeDasharray={`${sw(4)} ${sw(3)}`}
                  pointerEvents="none"
                />
              )}
              {draft && (
                <g pointerEvents="none">
                  <rect
                    x={Math.min(draft.x0, draft.x1)}
                    y={Math.min(draft.y0, draft.y1)}
                    width={dw}
                    height={dh}
                    fill="var(--map-acc)"
                    fillOpacity=".25"
                    stroke="var(--map-acc)"
                    strokeWidth={sw(2)}
                  />
                  <text
                    x={Math.max(draft.x0, draft.x1) + 0.3}
                    y={Math.min(draft.y0, draft.y1) - 0.3}
                    fontSize={12 / k}
                    fill="var(--map-ink)"
                  >
                    {dw.toFixed(1)} × {dh.toFixed(1)} м
                  </text>
                </g>
              )}
              {tool === 'rack' && !draft && (
                <rect
                  x={cur[0] - P.w / 2}
                  y={cur[1] - P.h / 2}
                  width={P.w}
                  height={P.h}
                  fill="var(--map-pri)"
                  fillOpacity=".22"
                  stroke="var(--map-pri)"
                  strokeWidth={sw(1.5)}
                  strokeDasharray={`${sw(5)} ${sw(3)}`}
                  pointerEvents="none"
                />
              )}
              {tool !== 'select' && tool !== 'pan' && (
                <path
                  d={`M${cur[0] - 0.6} ${cur[1]}H${cur[0] + 0.6}M${cur[0]} ${cur[1] - 0.6}V${cur[1] + 0.6}`}
                  stroke="var(--map-ink)"
                  strokeWidth={sw(1)}
                  pointerEvents="none"
                />
              )}
            </MapLayers>
          </svg>

          {loadError && !errorDismissed && (
            <div className={styles.banner} role="alert">
              <span>Не вдалося завантажити мапу: {loadError.message}</span>
              <span className={styles.bannerActions}>
                <button type="button" onClick={onRetry}>
                  Повторити
                </button>
                <button type="button" onClick={() => setErrorDismissed(true)}>
                  Почати з порожньої
                </button>
              </span>
            </div>
          )}
          {!loadError && objs.length === 0 && (
            <div className={styles.emptyTip}>Почніть з контуру приміщення: інструмент «Контур» (W)</div>
          )}
          <div className={styles.hint}>{HINTS[tool]}</div>
          <ZoomControls
            scale={k / BASE_SCALE}
            onZoomIn={() => vp.zoomBy(1.25)}
            onZoomOut={() => vp.zoomBy(0.8)}
            onReset={vp.reset}
          />
        </div>

        <aside className={styles.panel}>
          {selIds.length > 1 ? (
            <GroupProperties
              items={objs.filter((o) => selSet.has(o.id))}
              conflicts={selIds.filter((id) => conflicts.has(id)).length}
              onRotate={(deg) => rotateGroup(selIds, deg)}
              onClear={() => setSel(null)}
              onDelete={() => remove(...selIds)}
            />
          ) : selected && isShape(selected) ? (
            <Properties
              o={selected}
              conflict={conflicts.has(selected.id)}
              onChange={(patch) => upd(selected.id, patch)}
              onDelete={() => remove(selected.id)}
            />
          ) : selected && isPartition(selected) ? (
            <PartitionProperties
              p={selected}
              wallAngle={selectedWallAngle?.info.angle ?? null}
              conflict={conflicts.has(selected.id)}
              onChange={(patch) => updPartition(selected.id, patch)}
              onWallAngle={(deg) => setPartitionWallAngle(selected, deg)}
              onDelete={() => remove(selected.id)}
            />
          ) : selected && isRoom(selected) ? (
            <RoomProperties
              pts={selected.pts}
              vertex={activeVertex}
              onVertexChange={setVertex}
              onVertexDelete={removeVertex}
              onEdgeLength={setEdgeLength}
              onDelete={() => remove(selected.id)}
            />
          ) : (
            <>
              <h4>Об'єкти</h4>
              <p className={styles.muted}>Оберіть об'єкт на мапі, щоб змінити параметри.</p>
            </>
          )}

          <h4 className={styles.section}>Пресети стелажів</h4>
          {RACK_PRESETS.map((p, i) => (
            <button
              key={p.n}
              type="button"
              className={cx(styles.btn, styles.btnPreset, preset === i && styles.btnOn)}
              onClick={() => {
                setPreset(i);
                if (selected && selected.t === 'rack') upd(selected.id, { w: p.w, h: p.h, shelves: p.s });
                else pick('rack');
              }}
            >
              {p.n}
              <br />
              <small>
                {p.w} × {p.h} м · {p.s} пол.
              </small>
            </button>
          ))}

          <h4 className={styles.section}>Умовні позначення</h4>
          <Legend />
        </aside>
      </div>

      <footer className={styles.st}>
        <span>
          X: {cur[0].toFixed(1)} м · Y: {cur[1].toFixed(1)} м
        </span>
        <span>Масштаб: {((k / BASE_SCALE) * 100).toFixed(0)}%</span>
        <span>Крок: {tool === 'partition' || (selected && isPartition(selected)) ? '1 см' : '0,5 м'}</span>
        {msg && <span className={styles.msg}>{msg}</span>}
        <span>Стелажів: {racksCount}</span>
        {room && <span>Площа: {polygonArea(room.pts).toFixed(0)} м²</span>}
        <span className={conflicts.size ? styles.bad : undefined}>Конфліктів: {conflicts.size}</span>
      </footer>
    </div>
  );
}

/** Ручка повороту над виділеним об'єктом (у його локальних координатах, тож обертається разом з ним). */
function RotateHandle({ o, k }: { o: ShapeObject; k: number }) {
  const sw = (n: number) => n / k;
  // Вище за підпис стелажа, щоб його не перекривати
  const cy = -o.h / 2 - sw(34);
  return (
    <g transform={`translate(${o.x} ${o.y}) rotate(${o.a})`}>
      <g data-handle="rotate" style={{ cursor: 'grab' }}>
        <title>Поворот (Shift — без кроку 15°)</title>
        <circle cy={cy} r={sw(10)} fill="#fff" stroke="var(--map-acc)" strokeWidth={sw(2)} />
        <text
          y={cy}
          fontSize={sw(14)}
          textAnchor="middle"
          dominantBaseline="central"
          fill="var(--map-ink)"
          pointerEvents="none"
        >
          ⟳
        </text>
      </g>
    </g>
  );
}

/** Дуга й підпис кута між стіною (від її напрямку a → b) і перегородкою, що виходить із точки at. */
function AngleMark({ at, to, info, k }: { at: Point; to: Point; info: EdgeAngle; k: number }) {
  const r = 26 / k;
  const [a, b] = info.edge;
  const base = Math.atan2(b[1] - a[1], b[0] - a[0]);
  const end = Math.atan2(to[1] - at[1], to[0] - at[0]);
  const mid = base + (info.side * info.angle * Math.PI) / 360;
  const p1: Point = [at[0] + Math.cos(base) * r, at[1] + Math.sin(base) * r];
  const p2: Point = [at[0] + Math.cos(end) * r, at[1] + Math.sin(end) * r];
  const tr = r + 16 / k;
  return (
    <g pointerEvents="none">
      <path
        d={`M${at[0]} ${at[1]}L${p1[0]} ${p1[1]}A${r} ${r} 0 0 ${info.side > 0 ? 1 : 0} ${p2[0]} ${p2[1]}Z`}
        fill="var(--map-acc)"
        fillOpacity=".25"
        stroke="var(--map-acc)"
        strokeWidth={1.5 / k}
      />
      <text
        x={at[0] + Math.cos(mid) * tr}
        y={at[1] + Math.sin(mid) * tr}
        fontSize={11 / k}
        textAnchor="middle"
        dominantBaseline="central"
        fill="var(--map-ink)"
      >
        {info.angle.toFixed(1)}°
      </text>
    </g>
  );
}

/** Об'єкти (крім контуру), що повністю лежать у прямокутнику рамки виділення. */
function objectsInRect(objs: MapObject[], a: Point, b: Point): string[] {
  const [x0, x1] = [Math.min(a[0], b[0]), Math.max(a[0], b[0])];
  const [y0, y1] = [Math.min(a[1], b[1]), Math.max(a[1], b[1])];
  const inside = ([x, y]: Point) => x >= x0 && x <= x1 && y >= y0 && y <= y1;
  return objs
    .filter((o) => {
      if (isPartition(o)) return inside(o.start) && inside(o.end);
      if (!isShape(o)) return false;
      // Точка входу — за центром, решта — усіма кутами з урахуванням повороту
      return o.t === 'entry' ? inside([o.x, o.y]) : corners(o).every(inside);
    })
    .map((o) => o.id);
}

const GROUP_LABELS: Record<Exclude<MapObject['t'], 'room'>, string> = {
  rack: 'Стелажі',
  partition: 'Перегородки',
  obst: 'Перешкоди',
  zin: 'Зони приймання',
  zstore: 'Зони зберігання',
  zout: 'Зони відвантаження',
  entry: 'Точки входу',
};

function GroupProperties({
  items,
  conflicts,
  onRotate,
  onClear,
  onDelete,
}: {
  items: MapObject[];
  conflicts: number;
  onRotate: (deg: number) => void;
  onClear: () => void;
  onDelete: () => void;
}) {
  const counts = new Map<string, number>();
  for (const o of items) if (!isRoom(o)) counts.set(GROUP_LABELS[o.t], (counts.get(GROUP_LABELS[o.t]) ?? 0) + 1);
  return (
    <>
      <h4>Виділено об'єктів: {items.length}</h4>
      {[...counts].map(([label, n]) => (
        <p key={label} className={styles.muted}>
          {label}: {n}
        </p>
      ))}
      <p className={styles.muted}>Перетягніть будь-який із них, щоб посунути всю групу.</p>
      <div className={styles.row}>
        <button type="button" className={styles.btn} title="Повернути групу на 90° проти годинникової стрілки" onClick={() => onRotate(-90)}>
          ⟲ 90°
        </button>
        <button type="button" className={styles.btn} title="Повернути групу на 90° за годинниковою стрілкою" onClick={() => onRotate(90)}>
          ⟳ 90°
        </button>
      </div>
      {conflicts > 0 && <div className={styles.conflict}>⚠ Колізії у виділенні: {conflicts}</div>}
      <button type="button" className={styles.btn} onClick={onClear}>
        Зняти виділення
      </button>
      <button type="button" className={cx(styles.btn, styles.btnDanger)} onClick={onDelete}>
        Видалити всі ({items.length})
      </button>
    </>
  );
}

function nextRackCode(objs: MapObject[]): string {
  const used = new Set(objs.filter((o): o is ShapeObject => o.t === 'rack').map((o) => o.name));
  for (let n = 1; ; n++) if (!used.has(`R-${n}`)) return `R-${n}`;
}

function Properties({
  o,
  conflict,
  onChange,
  onDelete,
}: {
  o: ShapeObject;
  conflict: boolean;
  onChange: (patch: Partial<ShapeObject>) => void;
  onDelete: () => void;
}) {
  const isZone = o.t === 'zin' || o.t === 'zstore' || o.t === 'zout';
  return (
    <>
      <h4>Властивості</h4>
      <TextField label={o.t === 'rack' ? 'Код стелажа' : 'Назва'} value={o.name} onChange={(name) => onChange({ name })} />
      {o.t !== 'entry' && (
        <>
          <NumField label="Довжина (X), м" value={o.w} step={0.1} min={0.5} onChange={(w) => onChange({ w: Math.max(0.5, w) })} />
          <NumField label="Ширина (Y), м" value={o.h} step={0.1} min={0.5} onChange={(h) => onChange({ h: Math.max(0.5, h) })} />
        </>
      )}
      <NumField label="X, м" value={o.x} step={0.1} onChange={(x) => onChange({ x })} />
      <NumField label="Y, м" value={o.y} step={0.1} onChange={(y) => onChange({ y })} />
      {o.t !== 'entry' && (
        <>
          <NumField label="Кут, °" value={o.a} step={0.5} onChange={(a) => onChange({ a: normalizeAngle(a) })} />
          <div className={styles.row}>
            <button
              type="button"
              className={styles.btn}
              title="Повернути на 90° проти годинникової стрілки"
              onClick={() => onChange({ a: normalizeAngle(o.a - 90) })}
            >
              ⟲ 90°
            </button>
            <button
              type="button"
              className={styles.btn}
              title="Повернути на 90° за годинниковою стрілкою"
              onClick={() => onChange({ a: normalizeAngle(o.a + 90) })}
            >
              ⟳ 90°
            </button>
          </div>
        </>
      )}
      {o.t === 'rack' && (
        <NumField
          label="Полиць"
          value={o.shelves ?? 1}
          step={1}
          min={1}
          onChange={(n) => onChange({ shelves: Math.max(1, Math.round(n)) })}
        />
      )}
      {isZone && (
        <NumField
          label="Місткість, м³"
          value={o.cap ?? ''}
          step={1}
          min={0}
          onChange={(cap) => onChange({ cap: Math.max(0, cap) })}
          onClear={() => onChange({ cap: null })}
        />
      )}
      {o.t === 'obst' && (
        <>
          <SelectField
            label="Тип"
            value={o.obstacleType ?? 'column'}
            options={OBSTACLE_TYPES}
            onChange={(v) => onChange({ obstacleType: v as ObstacleType })}
          />
          <NumField
            label="Макс. висота, м"
            value={o.maxHeight ?? ''}
            step={0.1}
            min={0}
            onChange={(maxHeight) => onChange({ maxHeight: Math.max(0, maxHeight) })}
            onClear={() => onChange({ maxHeight: null })}
          />
        </>
      )}
      {o.t === 'entry' && (
        <SelectField
          label="Тип"
          value={o.pointType ?? 'general_entry'}
          options={POINT_TYPES}
          onChange={(v) => onChange({ pointType: v as PointType })}
        />
      )}
      {conflict && <div className={styles.conflict}>⚠ Колізія або вихід за межі приміщення</div>}
      <button type="button" className={cx(styles.btn, styles.btnDanger)} onClick={onDelete}>
        Видалити
      </button>
    </>
  );
}

function RoomProperties({
  pts,
  vertex,
  onVertexChange,
  onVertexDelete,
  onEdgeLength,
  onDelete,
}: {
  pts: Point[];
  vertex: number | null;
  onVertexChange: (index: number, p: Point) => void;
  onVertexDelete: (index: number) => void;
  onEdgeLength: (index: number, len: number) => void;
  onDelete: () => void;
}) {
  return (
    <>
      <h4>Контур приміщення</h4>
      <p className={styles.muted}>
        Площа: {polygonArea(pts).toFixed(1)} м² · вершин: {pts.length}
      </p>
      {vertex !== null && (
        <>
          <h4 className={styles.section}>Вершина {vertex + 1}</h4>
          <CommitNumField
            label="X, м"
            value={round2(pts[vertex][0])}
            step={0.1}
            onCommit={(x) => onVertexChange(vertex, [x, pts[vertex][1]])}
          />
          <CommitNumField
            label="Y, м"
            value={round2(pts[vertex][1])}
            step={0.1}
            onCommit={(y) => onVertexChange(vertex, [pts[vertex][0], y])}
          />
          <button type="button" className={styles.btn} onClick={() => onVertexDelete(vertex)} disabled={pts.length <= 3}>
            Видалити вершину
          </button>
        </>
      )}
      <h4 className={styles.section}>Довжини стін</h4>
      {pts.map((a, i) => (
        <CommitNumField
          key={i}
          label={`Стіна ${i + 1}, м`}
          value={round2(dist(a, pts[(i + 1) % pts.length]))}
          step={0.1}
          min={MIN_PARTITION_LENGTH}
          onCommit={(len) => onEdgeLength(i, len)}
        />
      ))}
      <p className={styles.muted}>Зміна довжини рухає кінцеву вершину стіни.</p>
      <button type="button" className={cx(styles.btn, styles.btnDanger)} onClick={onDelete}>
        Видалити контур
      </button>
    </>
  );
}

function PartitionProperties({
  p,
  wallAngle,
  conflict,
  onChange,
  onWallAngle,
  onDelete,
}: {
  p: PartitionObject;
  /** Кут до стіни, до якої прикріплена перегородка; null — не прикріплена. */
  wallAngle: number | null;
  conflict: boolean;
  onChange: (patch: Partial<PartitionObject>) => void;
  onWallAngle: (deg: number) => void;
  onDelete: () => void;
}) {
  return (
    <>
      <h4>Перегородка</h4>
      <CommitNumField
        label="Довжина, м"
        value={round2(dist(p.start, p.end))}
        step={0.1}
        min={MIN_PARTITION_LENGTH}
        onCommit={(len) => len >= MIN_PARTITION_LENGTH && onChange({ end: withLength(p.start, p.end, len) })}
      />
      {wallAngle !== null ? (
        <CommitNumField
          label="Кут до стіни, °"
          value={Math.round(wallAngle * 10) / 10}
          step={0.5}
          min={0}
          onCommit={onWallAngle}
        />
      ) : (
        <p className={styles.muted}>Прикріпіть кінець до стіни, щоб задати кут до неї.</p>
      )}
      <CommitNumField
        label="Товщина, м"
        value={p.thickness}
        step={0.05}
        min={0.05}
        onCommit={(t) => onChange({ thickness: Math.min(1, Math.max(0.05, t)) })}
      />
      <CommitNumField
        label="Висота, м"
        value={p.height ?? ''}
        step={0.1}
        min={0}
        onCommit={(h) => onChange({ height: h > 0 ? h : null })}
        onClear={() => onChange({ height: null })}
      />
      <p className={styles.muted}>Порожня висота — перегородка до стелі.</p>
      {conflict && <div className={styles.conflict}>⚠ Перетин зі стелажем або вихід за межі приміщення</div>}
      <button type="button" className={cx(styles.btn, styles.btnDanger)} onClick={onDelete}>
        Видалити
      </button>
    </>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className={styles.f}>
      <span>{label}</span>
      <input type="text" value={value} maxLength={100} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function NumField({
  label,
  value,
  step,
  min,
  onChange,
  onClear,
}: {
  label: string;
  value: number | '';
  step: number;
  min?: number;
  onChange: (v: number) => void;
  onClear?: () => void;
}) {
  return (
    <label className={styles.f}>
      <span>{label}</span>
      <input
        type="number"
        step={step}
        min={min}
        value={value}
        onChange={(e) => {
          if (e.target.value === '' && onClear) return onClear();
          const n = parseFloat(e.target.value);
          if (!Number.isNaN(n)) onChange(round3(n));
        }}
      />
    </label>
  );
}

/**
 * Числове поле, що застосовує значення лише на Enter або при втраті фокусу. Для геометрії
 * стін: проміжні значення під час набору («1» на шляху до «12») могли б зламати контур.
 */
function CommitNumField({
  label,
  value,
  step,
  min,
  onCommit,
  onClear,
}: {
  label: string;
  value: number | '';
  step: number;
  min?: number;
  onCommit: (v: number) => void;
  onClear?: () => void;
}) {
  const [text, setText] = useState<string | null>(null);
  const commit = () => {
    if (text === null) return;
    setText(null);
    if (text.trim() === '') return onClear?.();
    const n = parseFloat(text);
    if (!Number.isNaN(n)) onCommit(round3(n));
  };
  return (
    <label className={styles.f}>
      <span>{label}</span>
      <input
        type="number"
        step={step}
        min={min}
        value={text ?? value}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') setText(null);
        }}
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (v: string) => void;
}) {
  return (
    <label className={styles.f}>
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Legend() {
  return (
    <>
      <div className={styles.lg}>
        <s style={{ background: 'var(--map-pri)' }} />
        Стелаж
      </div>
      <div className={styles.lg}>
        <s className={styles.lgWall} />
        Перегородка
      </div>
      <div className={styles.lg}>
        <s style={{ background: 'var(--map-bad)' }} />
        Колізія
      </div>
      <div className={styles.lg}>
        <s style={{ background: 'var(--map-acc)', opacity: 0.5 }} />
        Зона приймання
      </div>
      <div className={styles.lg}>
        <s style={{ background: 'var(--map-store)', opacity: 0.5 }} />
        Зона зберігання
      </div>
      <div className={styles.lg}>
        <s style={{ background: 'var(--map-okd)', opacity: 0.5 }} />
        Зона відвантаження
      </div>
      <div className={styles.lg}>
        <s style={{ background: 'var(--map-ok)', borderRadius: '50%' }} />
        Точка входу
      </div>
    </>
  );
}
