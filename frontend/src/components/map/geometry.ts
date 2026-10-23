// Геометрія мапи: SAT для повернутих прямокутників, точка в полігоні, площа полігона.

export type Point = [number, number];

export interface OrientedRect {
  x: number; // центр
  y: number;
  w: number; // розмір уздовж власної осі X
  h: number; // розмір уздовж власної осі Y
  a: number; // кут повороту, градуси
}

export const SNAP_STEP = 0.5;
export const snap = (v: number) => Math.round(v / SNAP_STEP) * SNAP_STEP;

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
