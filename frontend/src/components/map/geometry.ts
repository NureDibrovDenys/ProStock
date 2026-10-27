// Геометрія мапи: SAT для повернутих прямокутників, точка в полігоні, площа полігона,
// перевірка простоти полігона, відрізки (перегородки) та прив'язка точок.

export type Point = [number, number];

const EPS = 1e-9;

export const dist = (a: Point, b: Point) => Math.hypot(a[0] - b[0], a[1] - b[1]);

/** Знак повороту a → b відносно o: > 0, < 0 або 0 (на одній прямій). */
const cross = (o: Point, a: Point, b: Point) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);

const sign = (v: number) => (v > EPS ? 1 : v < -EPS ? -1 : 0);

/** Точка p лежить на відрізку ab (за умови, що всі три на одній прямій). */
const withinBox = (a: Point, b: Point, p: Point) =>
  Math.min(a[0], b[0]) - EPS <= p[0] &&
  p[0] <= Math.max(a[0], b[0]) + EPS &&
  Math.min(a[1], b[1]) - EPS <= p[1] &&
  p[1] <= Math.max(a[1], b[1]) + EPS;

export interface OrientedRect {
  x: number; // центр
  y: number;
  w: number; // розмір уздовж власної осі X
  h: number; // розмір уздовж власної осі Y
  a: number; // кут повороту, градуси
}

export const SNAP_STEP = 0.5;
export const snap = (v: number) => Math.round(v / SNAP_STEP) * SNAP_STEP;
/** Дрібний крок (1 см) — для перегородок, що ставляться без сітки. */
export const FINE_STEP = 0.01;
export const snapFine = (v: number) => Math.round(v * 100) / 100;

/** Кут у діапазоні [0, 360). */
export const normalizeAngle = (a: number) => {
  const r = ((a % 360) + 360) % 360;
  return Math.abs(r - 360) < 1e-9 ? 0 : r;
};

export function corners(o: OrientedRect): Point[] {
  const r = (o.a * Math.PI) / 180;
  const c = Math.cos(r);
  const s = Math.sin(r);
  return ([
    [-1, -1],
    [1, -1],
    [1, 1],
    [-1, 1],
  ] as const).map(([i, j]) => {
    const x = (i * o.w) / 2;
    const y = (j * o.h) / 2;
    return [o.x + x * c - y * s, o.y + x * s + y * c];
  });
}

const axes = (p: Point[]): Point[] =>
  p.map((a, i) => {
    const b = p[(i + 1) % p.length];
    return [-(b[1] - a[1]), b[0] - a[0]];
  });

function project(p: Point[], ax: Point): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const q of p) {
    const d = q[0] * ax[0] + q[1] * ax[1];
    min = Math.min(min, d);
    max = Math.max(max, d);
  }
  return [min, max];
}

/** Перетин двох опуклих многокутників (теорема про роздільну вісь). */
export function intersects(A: Point[], B: Point[]): boolean {
  return [...axes(A), ...axes(B)].every((ax) => {
    const a = project(A, ax);
    const b = project(B, ax);
    return a[1] > b[0] + 1e-6 && b[1] > a[0] + 1e-6;
  });
}

export function pointInPolygon(pt: Point, poly: Point[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [a, b] = poly[i];
    const [d, e] = poly[j];
    if (b > pt[1] !== e > pt[1] && pt[0] < ((d - a) * (pt[1] - b)) / (e - b) + a) inside = !inside;
  }
  return inside;
}

export function polygonArea(p: Point[]): number {
  return (
    Math.abs(
      p.reduce((sum, a, i) => {
        const b = p[(i + 1) % p.length];
        return sum + a[0] * b[1] - b[0] * a[1];
      }, 0),
    ) / 2
  );
}

export function polygonSignedArea(p: Point[]): number {
  return (
    p.reduce((sum, a, i) => {
      const b = p[(i + 1) % p.length];
      return sum + a[0] * b[1] - b[0] * a[1];
    }, 0) / 2
  );
}

/** Зсуває ребро разом із двома його вершинами вздовж зовнішньої нормалі. */
export function movePolygonEdge(points: Point[], edgeIndex: number, distance: number): Point[] {
  if (points.length < 3 || edgeIndex < 0 || edgeIndex >= points.length) return points;

  const start = points[edgeIndex];
  const end = points[(edgeIndex + 1) % points.length];
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  const length = Math.hypot(dx, dy);
  if (length === 0) return points;

  const orientation = polygonSignedArea(points) >= 0 ? 1 : -1;
  const normal: Point = [(orientation * dy) / length, (-orientation * dx) / length];
  const offset: Point = [normal[0] * distance, normal[1] * distance];

  return points.map((point, index) =>
    index === edgeIndex || index === (edgeIndex + 1) % points.length
      ? [point[0] + offset[0], point[1] + offset[1]]
      : point,
  );
}

/** Відрізки перетинаються «навхрест» — дотик кінцем або накладання не рахуються. */
export function segmentsCross(p1: Point, p2: Point, q1: Point, q2: Point): boolean {
  const d1 = sign(cross(q1, q2, p1));
  const d2 = sign(cross(q1, q2, p2));
  const d3 = sign(cross(p1, p2, q1));
  const d4 = sign(cross(p1, p2, q2));
  return d1 * d2 < 0 && d3 * d4 < 0;
}

/** Відрізки мають хоча б одну спільну точку (перетин, дотик або накладання). */
export function segmentsTouch(p1: Point, p2: Point, q1: Point, q2: Point): boolean {
  const d1 = sign(cross(q1, q2, p1));
  const d2 = sign(cross(q1, q2, p2));
  const d3 = sign(cross(p1, p2, q1));
  const d4 = sign(cross(p1, p2, q2));
  if (d1 * d2 < 0 && d3 * d4 < 0) return true;
  return (
    (d1 === 0 && withinBox(q1, q2, p1)) ||
    (d2 === 0 && withinBox(q1, q2, p2)) ||
    (d3 === 0 && withinBox(p1, p2, q1)) ||
    (d4 === 0 && withinBox(p1, p2, q2))
  );
}

/**
 * Простий полігон: ≥ 3 вершини, немає нульових ребер і «шпильок» (ребро повертає назад
 * по собі), несусідні ребра не торкаються одне одного.
 */
export function isSimplePolygon(pts: Point[]): boolean {
  const n = pts.length;
  if (n < 3) return false;
  for (let i = 0; i < n; i++) {
    const prev = pts[(i - 1 + n) % n];
    const cur = pts[i];
    const next = pts[(i + 1) % n];
    if (dist(cur, next) < EPS) return false;
    const backwards =
      sign(cross(prev, cur, next)) === 0 &&
      (prev[0] - cur[0]) * (next[0] - cur[0]) + (prev[1] - cur[1]) * (next[1] - cur[1]) > 0;
    if (backwards) return false;
  }
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const adjacent = j === i + 1 || (i === 0 && j === n - 1);
      if (adjacent) continue;
      if (segmentsTouch(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n])) return false;
    }
  }
  return Math.abs(polygonSignedArea(pts)) > EPS;
}

/**
 * Канонічний вигляд контуру для збереження: без повторених і колінеарних вершин,
 * з додатною знаковою площею (однаковий напрям обходу для всіх складів).
 */
export function normalizePolygon(pts: Point[]): Point[] {
  const out = pts.filter((p, i) => dist(p, pts[(i - 1 + pts.length) % pts.length]) > EPS);
  for (let i = 0; out.length > 3 && i < out.length; ) {
    const n = out.length;
    if (sign(cross(out[(i - 1 + n) % n], out[i], out[(i + 1) % n])) === 0) out.splice(i, 1);
    else i++;
  }
  return polygonSignedArea(out) < 0 ? out.reverse() : out;
}

/** Точка лежить на межі полігона (з допуском tol). */
export function pointOnPolygonEdge(pt: Point, poly: Point[], tol = 1e-6): boolean {
  return poly.some((a, i) => distToSegment(pt, a, poly[(i + 1) % poly.length]) <= tol);
}

/**
 * Опуклий многокутник (повернутий прямокутник) повністю всередині полігона приміщення.
 * Вершини на самій стіні допустимі (стелаж впритул до стіни). Окрім вершин перевіряємо
 * ребра — інакше в непрямокутному приміщенні стелаж «прорізає» внутрішній кут стіни.
 */
export function rectInsidePolygon(rect: Point[], poly: Point[]): boolean {
  const inside = rect.every((p) => pointInPolygon(p, poly) || pointOnPolygonEdge(p, poly));
  if (!inside) return false;
  return rect.every((a, i) => {
    const b = rect[(i + 1) % rect.length];
    return poly.every((c, j) => !segmentsCross(a, b, c, poly[(j + 1) % poly.length]));
  });
}

/**
 * Відрізок усередині полігона: кінці всередині або на стіні, і жодна стіна його не перетинає.
 * Кінець, прив'язаний до стіни, після округлення до сантиметра може опинитися на волосину
 * зовні — тому для перевірки перетину кінці трохи стягуються всередину відрізка.
 */
export function segmentInsidePolygon(a: Point, b: Point, poly: Point[], tol = 0.01): boolean {
  const ok = (p: Point) => pointInPolygon(p, poly) || pointOnPolygonEdge(p, poly, tol);
  if (!ok(a) || !ok(b)) return false;
  const len = dist(a, b);
  const t = len > EPS ? Math.min(0.5, (2 * tol) / len) : 0;
  const a2: Point = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  const b2: Point = [b[0] + (a[0] - b[0]) * t, b[1] + (a[1] - b[1]) * t];
  if (!pointInPolygon([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], poly)) return false;
  return poly.every((c, j) => !segmentsCross(a2, b2, c, poly[(j + 1) % poly.length]));
}

/** Відрізок із товщиною → повернутий прямокутник; кінці подовжено на півтовщини (кути стиків закриті). */
export function segmentRect(a: Point, b: Point, thickness: number): OrientedRect {
  return {
    x: (a[0] + b[0]) / 2,
    y: (a[1] + b[1]) / 2,
    w: dist(a, b) + thickness,
    h: thickness,
    a: (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI,
  };
}

export function closestPointOnSegment(p: Point, a: Point, b: Point): Point {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  if (len2 < EPS) return a;
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
  return [a[0] + t * dx, a[1] + t * dy];
}

export function distToSegment(p: Point, a: Point, b: Point): number {
  return dist(p, closestPointOnSegment(p, a, b));
}

/** Напрямок from → to прив'язується до кута, кратного stepDeg, довжина — до кроку сітки (або lenStep). */
export function snapAngle(from: Point, to: Point, stepDeg: number, lenStep = SNAP_STEP): Point {
  const step = (stepDeg * Math.PI) / 180;
  const angle = Math.round(Math.atan2(to[1] - from[1], to[0] - from[0]) / step) * step;
  const len = Math.round(dist(from, to) / lenStep) * lenStep;
  const round = (v: number) => Math.round(v * 100) / 100;
  return [round(from[0] + Math.cos(angle) * len), round(from[1] + Math.sin(angle) * len)];
}

/** Точку b посунути вздовж напрямку a → b так, щоб довжина відрізка стала len. */
export function withLength(a: Point, b: Point, len: number): Point {
  const d = dist(a, b);
  if (d < EPS) return [a[0] + len, a[1]];
  return [a[0] + ((b[0] - a[0]) / d) * len, a[1] + ((b[1] - a[1]) / d) * len];
}

export interface EdgeAngle {
  /** Стіна, на якій лежить точка from. */
  edge: [Point, Point];
  /** Кут від напрямку стіни a → b до відрізка from → to, 0–180°. */
  angle: number;
  /** З якого боку стіни лежить відрізок: 1 або -1. */
  side: 1 | -1;
}

/** Кут між відрізком from → to і стіною, на якій лежить from; null — якщо from не на жодній стіні. */
export function angleToEdge(from: Point, to: Point, edges: Array<[Point, Point]>, tol = 0.02): EdgeAngle | null {
  const v: Point = [to[0] - from[0], to[1] - from[1]];
  if (Math.hypot(v[0], v[1]) < EPS) return null;
  for (const [a, b] of edges) {
    if (dist(a, b) < EPS || distToSegment(from, a, b) > tol) continue;
    const u: Point = [b[0] - a[0], b[1] - a[1]];
    const c = u[0] * v[1] - u[1] * v[0];
    const d = u[0] * v[0] + u[1] * v[1];
    return { edge: [a, b], angle: Math.abs((Math.atan2(c, d) * 180) / Math.PI), side: c < 0 ? -1 : 1 };
  }
  return null;
}

/** Точка на відстані len від pivot під кутом deg до напрямку стіни a → b (з боку side). */
export function pointAtEdgeAngle(pivot: Point, edge: [Point, Point], deg: number, side: 1 | -1, len: number): Point {
  const base = Math.atan2(edge[1][1] - edge[0][1], edge[1][0] - edge[0][0]);
  const r = base + (side * deg * Math.PI) / 180;
  return [pivot[0] + Math.cos(r) * len, pivot[1] + Math.sin(r) * len];
}

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export function boundsOf(points: Point[]): Bounds | null {
  if (points.length === 0) return null;
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return { minX: Math.min(...xs), minY: Math.min(...ys), maxX: Math.max(...xs), maxY: Math.max(...ys) };
}
