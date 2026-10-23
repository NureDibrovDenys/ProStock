// Конструктор складу (2D-мапа). Перенесено з прототипу тіммейта на React + TypeScript:
// контур приміщення полігоном, стелажі з поворотом і пресетами, перешкоди, зони, точки входу,
// перевірка колізій і виходу за контур. Збереження — PUT /warehouses/{id}/map.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState, type MouseEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { Link } from 'react-router-dom';
import type { ObstacleType, PointType, WarehouseMap } from '../api/types';
import { getWarehouseMap, saveWarehouseMap } from '../api/warehouse';
import { MapLayers } from '../components/map/MapLayers';
import { ZoomControls } from '../components/map/ZoomControls';
import mapStyles from '../components/map/map.module.css';
import { movePolygonEdge, polygonArea, polygonSignedArea, snap, type Point } from '../components/map/geometry';
import {
  DEFAULT_NAMES,
  OBSTACLE_TYPES,
  POINT_TYPES,
  RACK_PRESETS,
  findConflicts,
  fromApi,
  isShape,
  mapBounds,
  nextId,
  toApi,
  type MapObject,
  type ShapeKind,
  type ShapeObject,
} from '../components/map/model';
import { LoadingState } from '../components/ui';
import { WAREHOUSE_ID } from '../config';
import { useViewport } from '../hooks/useViewport';
import { useWarehouseName } from '../hooks/useWarehouse';
import { cx } from '../lib/cx';
import styles from './MapEditorPage.module.css';

type Tool = 'select' | 'pan' | 'wall' | ShapeKind;

const TOOLS: Array<{ id: Tool; key: string; name: string; icon: string }> = [
  { id: 'select', key: 'V', name: 'Вибір', icon: '↖' },
  { id: 'pan', key: 'H', name: 'Рука', icon: '✥' },
  { id: 'wall', key: 'W', name: 'Контур', icon: '⬡' },
  { id: 'rack', key: 'R', name: 'Стелаж', icon: '▤' },
  { id: 'obst', key: 'O', name: 'Перешкода', icon: '▧' },
  { id: 'zin', key: 'I', name: 'Прийман.', icon: '⇩' },
  { id: 'zstore', key: 'S', name: 'Зберіган.', icon: '▦' },
  { id: 'zout', key: 'U', name: 'Відвант.', icon: '⇧' },
  { id: 'entry', key: 'E', name: 'Вхід', icon: '➜' },
];

const HINTS: Record<Tool, string> = {
  select: 'Клік — вибір · перетягування — переміщення · стіна — зсув по нормалі · Q — поворот · Del — видалити',
  pan: 'Перетягуйте, щоб рухати полотно (також: середня кнопка або Пробіл)',
  wall: 'Клік — вершина контуру · Enter або клік на першу точку — замкнути · Esc — скасувати',
  rack: 'Клік — поставити стелаж за пресетом · потягніть — власний розмір (кількість полиць із пресету)',
  obst: 'Затисніть і потягніть, щоб додати перешкоду (колона, ніша, техзона)',
  zin: 'Затисніть і потягніть, щоб задати зону приймання',
  zstore: 'Затисніть і потягніть, щоб задати зону зберігання',
  zout: 'Затисніть і потягніть, щоб задати зону відвантаження',
  entry: 'Клік — поставити точку входу/виходу',
};

/** Масштаб, що відповідає 100% (пікселів на метр). */
const BASE_SCALE = 22;

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

function Editor({ initial, loadError, onRetry }: { initial: MapObject[]; loadError: Error | null; onRetry: () => void }) {
  const queryClient = useQueryClient();
  const warehouseName = useWarehouseName();

  const [objs, setObjsRaw] = useState<MapObject[]>(initial);
  const [tool, setTool] = useState<Tool>('select');
  const [sel, setSel] = useState<string | null>(null);
  const [poly, setPoly] = useState<Point[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [cur, setCur] = useState<Point>([0, 0]);
  const [preset, setPreset] = useState(1);
  const [msg, setMsg] = useState('');
  const [dirty, setDirty] = useState(false);
  const [errorDismissed, setErrorDismissed] = useState(false);
  const [hoveredWall, setHoveredWall] = useState<number | null>(null);

  const vp = useViewport();
  const k = vp.viewport.scale;
  const drag = useRef<{ id: string; dx: number; dy: number } | null>(null);
  const wallDrag = useRef<WallDrag | null>(null);
  const space = useRef(false);
  const msgTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Актуальний стан для глобальних слухачів клавіатури
  const S = useRef({ tool, sel, poly });
  S.current = { tool, sel, poly };

  const setObjs = (updater: (prev: MapObject[]) => MapObject[]) => {
    setObjsRaw(updater);
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
    setDraft(null);
  };

  const closePoly = () => {
    const p = S.current.poly;
    if (p.length < 3) return;
    setObjs((os) => [...os.filter((o) => o.t !== 'room'), { id: nextId(), t: 'room', pts: p }]);
    setPoly([]);
    setTool('select');
  };

  const upd = (id: string, patch: Partial<ShapeObject>) =>
    setObjs((os) => os.map((o) => (o.id === id && isShape(o) ? { ...o, ...patch } : o)));

  const remove = (id: string) => {
    setObjs((os) => os.filter((o) => o.id !== id));
    setSel(null);
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
    setSel(room?.id ?? null);
    vp.svgRef.current?.setPointerCapture(pointerId);
  };

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (/INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName)) return;
      const s = S.current;
      const key = e.key;
      if (key === ' ') {
        space.current = true;
        e.preventDefault();
        return;
      }
      if (key === 'Escape') return pick('select');
      if (key === 'Enter') return closePoly();
      if ((key === 'Delete' || key === 'Backspace') && s.sel) {
        e.preventDefault();
        return remove(s.sel);
      }
      const lower = key.toLowerCase();
      if (lower === 'q' && s.sel) {
        const step = e.shiftKey ? -15 : 15;
        setObjs((os) => os.map((o) => (o.id === s.sel && isShape(o) ? { ...o, a: (o.a + step + 360) % 360 } : o)));
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
    const sp: Point = [snap(p[0]), snap(p[1])];

    if (e.button === 1 || tool === 'pan' || space.current) return vp.startPan(e);

    if (tool === 'select') {
      const el = (e.target as Element).closest('[data-id]') as HTMLElement | SVGElement | null;
      const wallEl = (e.target as Element).closest('[data-wall-index]') as HTMLElement | SVGElement | null;
      const wallIndex = wallEl ? Number(wallEl.dataset.wallIndex) : NaN;
      if (room?.t === 'room' && Number.isInteger(wallIndex)) {
        beginWallDrag(wallIndex, p, room.pts, e.pointerId);
        return;
      }
      const id = el?.dataset.id;
      if (!id) {
        // Порожнє місце: зняти виділення й рухати полотно
        setSel(null);
        return vp.startPan(e);
      }
      setSel(id);
      const o = objs.find((x) => x.id === id);
      if (o && isShape(o)) {
        drag.current = { id, dx: o.x - p[0], dy: o.y - p[1] };
        vp.svgRef.current?.setPointerCapture(e.pointerId);
      }
      return;
    }

    if (tool === 'wall') {
      if (poly.length > 2 && Math.hypot(sp[0] - poly[0][0], sp[1] - poly[0][1]) < 0.01) closePoly();
      else setPoly([...poly, sp]);
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
    vp.svgRef.current?.setPointerCapture(e.pointerId);
  };

  const move = (e: ReactPointerEvent) => {
    const p = vp.toWorld(e.clientX, e.clientY);
    const sp: Point = [snap(p[0]), snap(p[1])];
    setCur(sp);

    if (tool === 'select' && !wallDrag.current) {
      const wall = (e.target as Element).closest('[data-wall-index]') as HTMLElement | SVGElement | null;
      setHoveredWall(wall ? Number(wall.dataset.wallIndex) : null);
    }

    if (vp.movePan(e)) return;
    const wall = wallDrag.current;
    if (wall && room?.t === 'room') {
      const distance = snap((p[0] - wall.start[0]) * wall.normal[0] + (p[1] - wall.start[1]) * wall.normal[1]);
      const points = movePolygonEdge(wall.initialPoints, wall.edgeIndex, distance);
      setObjs((os) => os.map((o) => (o.t === 'room' ? { ...o, pts: points } : o)));
      return;
    }
    const d = drag.current;
    if (d) upd(d.id, { x: snap(p[0] + d.dx), y: snap(p[1] + d.dy) });
    else if (draft) setDraft({ ...draft, x1: sp[0], y1: sp[1] });
  };

  const up = (e: ReactPointerEvent) => {
    vp.endPan(e);
    drag.current = null;
    wallDrag.current = null;
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
  const room = objs.find((o) => o.t === 'room');
  const selected = objs.find((o) => o.id === sel) ?? null;
  const racksCount = objs.filter((o) => o.t === 'rack').length;

  const mutation = useMutation({
    mutationFn: (map: WarehouseMap) => saveWarehouseMap(WAREHOUSE_ID, map),
    onSuccess: (saved, sent) => {
      // Бекенд повертає мапу з id нових об'єктів; якщо ні — кешуємо надіслане
      queryClient.setQueryData(['map', WAREHOUSE_ID], saved ?? sent);
      queryClient.invalidateQueries({ queryKey: ['racks', WAREHOUSE_ID] });
      setDirty(false);
      flash('Збережено');
    },
    onError: (err) => flash(`Не вдалося зберегти: ${err.message}`),
  });

  const save = () => {
    const codes = objs.filter((o): o is ShapeObject => o.t === 'rack').map((o) => o.name.trim());
    if (codes.some((c) => !c)) return flash('У кожного стелажа має бути назва (код)');
    if (new Set(codes).size !== codes.length) return flash('Назви стелажів повторюються');
    if (conflicts.size && !window.confirm(`На мапі є конфлікти (${conflicts.size}). Зберегти все одно?`)) return;
    mutation.mutate(toApi(objs));
  };

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

  const goBack = (e: MouseEvent) => {
    if (dirty && !window.confirm('Є незбережені зміни. Вийти з конструктора?')) e.preventDefault();
  };

  // ── Рендер ───────────────────────────────────────────────────────────────

  const dw = draft ? Math.abs(draft.x1 - draft.x0) : 0;
  const dh = draft ? Math.abs(draft.y1 - draft.y0) : 0;
  const sw = (n: number) => n / k;
  const P = RACK_PRESETS[preset];
  const cursor = tool === 'pan' ? 'grab' : tool === 'select' ? 'default' : 'crosshair';

  return (
    <div className={styles.app}>
      <header className={styles.top}>
        <Link to="/warehouse" className={styles.back} onClick={goBack}>
          ← До складу
        </Link>
        <b>ProStock</b>
        <span className={styles.subtitle}>Конструктор складу · {warehouseName}</span>
        <div className={styles.topActions}>
          <button type="button" className={styles.topGhost} onClick={exportJson}>
            Експорт JSON
          </button>
          <button type="button" className={styles.topSave} onClick={save} disabled={mutation.isPending}>
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
            <MapLayers objs={objs} viewport={vp.viewport} size={vp.size} selectedId={sel} conflicts={conflicts}>
              {tool === 'select' && room?.t === 'room' && (
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
          {selected && isShape(selected) ? (
            <Properties
              o={selected}
              conflict={conflicts.has(selected.id)}
              onChange={(patch) => upd(selected.id, patch)}
              onDelete={() => remove(selected.id)}
            />
          ) : (
            <>
              <h4>{selected ? 'Контур приміщення' : "Об'єкти"}</h4>
              {selected ? (
                <>
                  {room?.t === 'room' && <p className={styles.muted}>Площа: {polygonArea(room.pts).toFixed(1)} м²</p>}
                  <button type="button" className={cx(styles.btn, styles.btnDanger)} onClick={() => remove(selected.id)}>
                    Видалити контур
                  </button>
                </>
              ) : (
                <p className={styles.muted}>Оберіть об'єкт на мапі, щоб змінити параметри.</p>
              )}
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
        <span>Крок: 0,5 м</span>
        {msg && <span className={styles.msg}>{msg}</span>}
        <span>Стелажів: {racksCount}</span>
        {room?.t === 'room' && <span>Площа: {polygonArea(room.pts).toFixed(0)} м²</span>}
        <span className={conflicts.size ? styles.bad : undefined}>Конфліктів: {conflicts.size}</span>
      </footer>
    </div>
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
          <NumField label="Довжина (X), м" value={o.w} step={0.5} min={0.5} onChange={(w) => onChange({ w: Math.max(0.5, w) })} />
          <NumField label="Ширина (Y), м" value={o.h} step={0.5} min={0.5} onChange={(h) => onChange({ h: Math.max(0.5, h) })} />
        </>
      )}
      <NumField label="X, м" value={o.x} step={0.5} onChange={(x) => onChange({ x })} />
      <NumField label="Y, м" value={o.y} step={0.5} onChange={(y) => onChange({ y })} />
      {o.t !== 'entry' && <NumField label="Кут, °" value={o.a} step={15} onChange={(a) => onChange({ a })} />}
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
            step={0.5}
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
          if (!Number.isNaN(n)) onChange(n);
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
