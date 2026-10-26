import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import type { Bounds } from '../components/map/geometry';

/** x, y — зсув у пікселях; scale — пікселів на метр. */
export interface Viewport {
  x: number;
  y: number;
  scale: number;
}

const MIN_SCALE = 4;
const MAX_SCALE = 200;
const DRAG_THRESHOLD = 3;

const clampScale = (s: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

/**
 * Панорамування й масштабування SVG-мапи. Координати об'єктів — світові (метри),
 * viewport переводить їх в екранні пікселі.
 */
export function useViewport(initial: Viewport = { x: 70, y: 50, scale: 22 }) {
  const [viewport, setViewport] = useState<Viewport>(initial);
  const [size, setSize] = useState({ width: 800, height: 500 });
  const svgRef = useRef<SVGSVGElement | null>(null);
  // Callback-ref: SVG може з'явитися пізніше (після завантаження даних) — слухачі чіпляються тоді ж
  const [svgEl, setSvgEl] = useState<SVGSVGElement | null>(null);
  const bindSvg = useCallback((el: SVGSVGElement | null) => {
    svgRef.current = el;
    setSvgEl(el);
  }, []);
  const viewportRef = useRef(viewport);
  viewportRef.current = viewport;
  const homeRef = useRef(initial);

  const panState = useRef<{ pointerId: number; startX: number; startY: number; origin: Viewport; moved: boolean } | null>(
    null,
  );
  const lastPanMoved = useRef(false);

  // Розмір полотна потрібен для сітки та підгонки мапи
  useEffect(() => {
    const svg = svgEl;
    if (!svg) return;
    const ro = new ResizeObserver(([entry]) =>
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height }),
    );
    ro.observe(svg);
    return () => ro.disconnect();
  }, [svgEl]);

  /** Екранні (client) координати → світові координати мапи. */
  const toWorld = useCallback((clientX: number, clientY: number): [number, number] => {
    const rect = svgRef.current?.getBoundingClientRect();
    const vp = viewportRef.current;
    return [(clientX - (rect?.left ?? 0) - vp.x) / vp.scale, (clientY - (rect?.top ?? 0) - vp.y) / vp.scale];
  }, []);

  /** Масштабування відносно точки (у координатах SVG); за замовчуванням — центр. */
  const zoomBy = useCallback((factor: number, anchor?: { x: number; y: number }) => {
    setViewport((vp) => {
      const scale = clampScale(vp.scale * factor);
      const rect = svgRef.current?.getBoundingClientRect();
      const ax = anchor?.x ?? (rect ? rect.width / 2 : 0);
      const ay = anchor?.y ?? (rect ? rect.height / 2 : 0);
      const k = scale / vp.scale;
      return { scale, x: ax - (ax - vp.x) * k, y: ay - (ay - vp.y) * k };
    });
  }, []);

  /** Вписати прямокутник (у метрах) у полотно; запам'ятовується як «домашній» вигляд. */
  const fitTo = useCallback((b: Bounds | null, padding = 40) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!b || !rect || rect.width === 0) return;
    const w = Math.max(b.maxX - b.minX, 1);
    const h = Math.max(b.maxY - b.minY, 1);
    const scale = clampScale(Math.min((rect.width - padding * 2) / w, (rect.height - padding * 2) / h));
    const next = {
      scale,
      x: (rect.width - w * scale) / 2 - b.minX * scale,
      y: (rect.height - h * scale) / 2 - b.minY * scale,
    };
    homeRef.current = next;
    setViewport(next);
  }, []);

  const reset = useCallback(() => setViewport(homeRef.current), []);

  // wheel-слухач має бути non-passive, щоб заблокувати прокрутку сторінки
  useEffect(() => {
    const svg = svgEl;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      zoomBy(Math.exp(-e.deltaY * 0.0015), { x: e.clientX - rect.left, y: e.clientY - rect.top });
    };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
  }, [svgEl, zoomBy]);

  const startPan = useCallback((e: ReactPointerEvent) => {
    if (e.button !== 0 && e.button !== 1) return;
    svgRef.current?.setPointerCapture(e.pointerId);
    panState.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      origin: viewportRef.current,
      moved: false,
    };
  }, []);

  const movePan = useCallback((e: ReactPointerEvent) => {
    const pan = panState.current;
    if (!pan || pan.pointerId !== e.pointerId) return false;
    const dx = e.clientX - pan.startX;
    const dy = e.clientY - pan.startY;
    if (!pan.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return true;
    pan.moved = true;
    setViewport({ ...pan.origin, x: pan.origin.x + dx, y: pan.origin.y + dy });
    return true;
  }, []);

  const endPan = useCallback((e: ReactPointerEvent) => {
    const pan = panState.current;
    if (!pan || pan.pointerId !== e.pointerId) return false;
    lastPanMoved.current = pan.moved;
    panState.current = null;
    return true;
  }, []);

  /** true, якщо останній жест був перетягуванням, а не кліком. */
  const wasDrag = useCallback(() => lastPanMoved.current, []);
  const isPanning = () => panState.current?.moved ?? false;

  return { viewport, size, svgRef, bindSvg, toWorld, zoomBy, fitTo, reset, startPan, movePan, endPan, wasDrag, isPanning };
}
