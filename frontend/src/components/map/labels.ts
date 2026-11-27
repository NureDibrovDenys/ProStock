import type { ShapeObject } from './model';

export type MapLabel = { id: string; x: number; y: number; text: string };

type Box = { x0: number; y0: number; x1: number; y1: number };
type Point = [number, number];

// Середня ширина гліфа відносно розміру шрифту - для оцінки ширини підпису без вимірювання DOM
const CHAR_WIDTH = 0.6;
const ENTRY_RADIUS = 0.7;

const isZone = (o: ShapeObject) => o.t === 'zin' || o.t === 'zout' || o.t === 'zstore';

function textWidth(text: string, fs: number) {
  return text.length * fs * CHAR_WIDTH;
}

function textBox([x, y]: Point, text: string, fs: number): Box {
  const w = textWidth(text, fs) / 2;
  const h = (fs * 1.2) / 2;
  return { x0: x - w, y0: y - h, x1: x + w, y1: y + h };
}

function overlapArea(a: Box, b: Box) {
  const w = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0);
  const h = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
  return w > 0 && h > 0 ? w * h : 0;
}

// Точка в локальних координатах фігури (з урахуванням повороту) -> світові координати
function toWorld(o: ShapeObject, [lx, ly]: Point): Point {
  const rad = (o.a * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  return [o.x + lx * cos - ly * sin, o.y + lx * sin + ly * cos];
}

function bodyBox(o: ShapeObject): Box {
  if (o.t === 'entry') {
    return { x0: o.x - ENTRY_RADIUS, y0: o.y - ENTRY_RADIUS, x1: o.x + ENTRY_RADIUS, y1: o.y + ENTRY_RADIUS };
  }
  const corners = [
    [-o.w / 2, -o.h / 2],
    [o.w / 2, -o.h / 2],
    [o.w / 2, o.h / 2],
    [-o.w / 2, o.h / 2],
  ].map((p) => toWorld(o, p as Point));
  const xs = corners.map((p) => p[0]);
  const ys = corners.map((p) => p[1]);
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
}

function candidates(o: ShapeObject, text: string, fs: number): Point[] {
  if (o.t === 'rack') {
    // Над стелажем (як було), інакше під ним
    return [toWorld(o, [0, -(o.h / 2 + fs)]), toWorld(o, [0, o.h / 2 + fs])];
  }
  if (o.t === 'entry') {
    const dy = ENTRY_RADIUS + fs * 0.9;
    const dx = ENTRY_RADIUS + fs * 0.4 + textWidth(text, fs) / 2;
    return [
      [o.x, o.y + dy],
      [o.x, o.y - dy],
      [o.x + dx, o.y],
      [o.x - dx, o.y],
    ];
  }
  // Зона: кути всередині, центр, потім над/під зоною
  const pad = fs * 0.5;
  const tw = textWidth(text, fs);
  const top = -o.h / 2 + pad + fs * 0.6;
  const bottom = o.h / 2 - pad - fs * 0.6;
  const left = -o.w / 2 + pad + tw / 2;
  const right = o.w / 2 - pad - tw / 2;
  const inside: Point[] =
    tw + pad * 2 <= o.w && fs * 1.2 + pad * 2 <= o.h
      ? [
          [left, top],
          [right, top],
          [left, bottom],
          [right, bottom],
          [0, 0],
        ]
      : [];
  const outside: Point[] = [
    [0, -o.h / 2 - fs * 0.8],
    [0, o.h / 2 + fs * 0.8],
  ];
  return [...inside, ...outside].map((p) => toWorld(o, p));
}

/**
 * Розставляє підписи так, щоб вони не налазили один на одного й на стелажі/перешкоди/входи.
 * Пріоритет: стелажі, входи, зони. Кожен підпис бере першу вільну позицію зі свого списку,
 * а якщо вільних немає - ту, що перекривається найменше.
 */
export function layoutLabels(
  shapes: ShapeObject[],
  fs: number,
  textOf: (o: ShapeObject) => string,
): MapLabel[] {
  const priority = (o: ShapeObject) => (o.t === 'rack' ? 0 : o.t === 'entry' ? 1 : 2);
  const labelled = shapes.filter((o) => o.t !== 'obst').sort((a, b) => priority(a) - priority(b));
  const solids = shapes.filter((o) => !isZone(o)).map((o) => ({ id: o.id, box: bodyBox(o) }));
  const placed: Box[] = [];
  const result: MapLabel[] = [];

  for (const o of labelled) {
    const text = textOf(o);
    let best: { point: Point; box: Box; cost: number } | null = null;
    for (const point of candidates(o, text, fs)) {
      const box = textBox(point, text, fs);
      const cost =
        placed.reduce((sum, b) => sum + overlapArea(box, b), 0) +
        solids.reduce((sum, s) => sum + (s.id === o.id ? 0 : overlapArea(box, s.box)), 0);
      if (!best || cost < best.cost) best = { point, box, cost };
      if (cost === 0) break;
    }
    if (!best) continue;
    placed.push(best.box);
    result.push({ id: o.id, x: best.point[0], y: best.point[1], text });
  }
  return result;
}
