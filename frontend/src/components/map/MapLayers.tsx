import type { ReactNode } from 'react';
import type { Viewport } from '../../hooks/useViewport';
import { isPartition, isShape, type MapObject, type PartitionObject, type ShapeObject } from './model';

type MapLayersProps = {
  objs: MapObject[];
  viewport: Viewport;
  size: { width: number; height: number };
  selectedId?: string | null;
  hoveredId?: string | null;
  conflicts?: Set<string>;
  /** Підпис стелажа замість «N пол.», напр. заповненість на сторінці складу. */
  rackCaption?: (rack: ShapeObject) => string | null;
  showGrid?: boolean;
  /** Додаткові шари поверх мапи (у світових координатах), напр. чернетки редактора. */
  children?: ReactNode;
};

/** Малює мапу складу в SVG. Інтерактивні елементи позначені атрибутом data-id. */
export function MapLayers({
  objs,
  viewport,
  size,
  selectedId,
  hoveredId,
  conflicts,
  rackCaption,
  showGrid = true,
  children,
}: MapLayersProps) {
  const { x: tx, y: ty, scale: k } = viewport;
  const sw = (n: number) => n / k; // товщина лінії, стала на екрані
  const room = objs.find((o) => o.t === 'room');
  const shapes = objs.filter(isShape);
  const partitions = objs.filter(isPartition);
  const view = { x: -tx / k, y: -ty / k, width: size.width / k, height: size.height / k };

  return (
    <>
      <defs>
        <pattern id="map-g1" width="1" height="1" patternUnits="userSpaceOnUse">
          <path d="M1 0H0V1" fill="none" stroke="var(--map-grid-minor)" strokeWidth={sw(1)} />
        </pattern>
        <pattern id="map-g5" width="5" height="5" patternUnits="userSpaceOnUse">
          <path d="M5 0H0V5" fill="none" stroke="var(--map-grid-major)" strokeWidth={sw(1)} />
        </pattern>
        <pattern id="map-hatch" width=".4" height=".4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2=".4" stroke="var(--map-ink)" strokeWidth=".1" />
        </pattern>
      </defs>
      <g transform={`translate(${tx} ${ty}) scale(${k})`}>
        {showGrid && (
          <>
            {k >= 10 && <rect {...view} fill="url(#map-g1)" pointerEvents="none" />}
            <rect {...view} fill="url(#map-g5)" pointerEvents="none" />
            <path
              d={`M${view.x} 0H${view.x + view.width}M0 ${view.y}V${view.y + view.height}`}
              stroke="var(--map-acc)"
              strokeOpacity=".7"
              strokeWidth={sw(1.5)}
              pointerEvents="none"
            />
          </>
        )}

        {room && room.t === 'room' && (
          <>
            <polygon
              data-id={room.id}
              points={room.pts.map((p) => p.join(',')).join(' ')}
              fill="var(--map-room)"
              stroke={selectedId === room.id ? 'var(--map-acc)' : 'var(--map-pri)'}
              strokeWidth=".35"
              strokeLinejoin="miter"
            />
            <polygon points={room.pts.map((p) => p.join(',')).join(' ')} fill="url(#map-g1)" pointerEvents="none" />
          </>
        )}

        {partitions.map((p) => (
          <Partition key={p.id} p={p} k={k} selected={selectedId === p.id} conflict={conflicts?.has(p.id) ?? false} />
        ))}

        {shapes
          .filter((o) => o.t !== 'entry')
          .map((o) => (
            <Shape
              key={o.id}
              o={o}
              k={k}
              selected={selectedId === o.id}
              hovered={hoveredId === o.id}
              conflict={conflicts?.has(o.id) ?? false}
              caption={o.t === 'rack' ? rackCaption?.(o) : undefined}
            />
          ))}
        {shapes
          .filter((o) => o.t === 'entry')
          .map((o) => (
            <Entry key={o.id} o={o} k={k} selected={selectedId === o.id} />
          ))}

        {children}
      </g>
    </>
  );
}

function Shape({
  o,
  k,
  selected,
  hovered,
  conflict,
  caption,
}: {
  o: ShapeObject;
  k: number;
  selected: boolean;
  hovered: boolean;
  conflict: boolean;
  caption?: string | null;
}) {
  const sw = (n: number) => n / k;
  const fs = 12 / k;
  let body: ReactNode;
  let label = o.name;

  if (o.t === 'rack') {
    const shelves = Math.max(1, o.shelves ?? 1);
    label = `${o.name} · ${caption ?? `${shelves} пол.`}`;
    body = (
      <>
        <rect
          x={-o.w / 2}
          y={-o.h / 2}
          width={o.w}
          height={o.h}
          fill={conflict ? 'var(--map-bad)' : hovered ? 'var(--map-pri-hover)' : 'var(--map-pri)'}
          fillOpacity=".9"
        />
        {Array.from({ length: shelves - 1 }, (_, i) => {
          const x = -o.w / 2 + ((i + 1) * o.w) / shelves;
          return <line key={i} x1={x} x2={x} y1={-o.h / 2} y2={o.h / 2} stroke="#fff" strokeOpacity=".5" strokeWidth={sw(1)} />;
        })}
        {(o.w / shelves) * k >= 18 &&
          Array.from({ length: shelves }, (_, i) => (
            <text
              key={`n${i}`}
              x={-o.w / 2 + ((i + 0.5) * o.w) / shelves}
              y="0"
              fontSize={11 / k}
              textAnchor="middle"
              dominantBaseline="central"
              fill="#fff"
              pointerEvents="none"
            >
              {i + 1}
            </text>
          ))}
      </>
    );
  } else if (o.t === 'obst') {
    body = (
      <rect
        x={-o.w / 2}
        y={-o.h / 2}
        width={o.w}
        height={o.h}
        fill={conflict ? 'var(--map-bad)' : 'url(#map-hatch)'}
        fillOpacity={conflict ? 0.6 : 1}
        stroke={conflict ? 'var(--map-bad)' : 'var(--map-ink)'}
        strokeWidth={sw(1.5)}
      />
    );
  } else {
    const color = o.t === 'zin' ? 'var(--map-acc)' : o.t === 'zout' ? 'var(--map-okd)' : 'var(--map-store)';
    body = (
      <rect
        x={-o.w / 2}
        y={-o.h / 2}
        width={o.w}
        height={o.h}
        fill={color}
        fillOpacity={hovered ? 0.32 : 0.2}
        stroke={color}
        strokeWidth={sw(2)}
        strokeDasharray={`${sw(7)} ${sw(4)}`}
      />
    );
  }

  // Підпис стелажа — над ним (з урахуванням повороту), решти — по центру
  const rad = (o.a * Math.PI) / 180;
  const lx = o.t === 'rack' ? o.x + Math.sin(rad) * (o.h / 2 + fs) : o.x;
  const ly = o.t === 'rack' ? o.y - Math.cos(rad) * (o.h / 2 + fs) : o.y;

  return (
    <g>
      <g data-id={o.id} transform={`translate(${o.x} ${o.y}) rotate(${o.a})`}>
        {body}
        {selected && (
          <rect
            x={-o.w / 2 - 0.1}
            y={-o.h / 2 - 0.1}
            width={o.w + 0.2}
            height={o.h + 0.2}
            fill="none"
            stroke="var(--map-acc)"
            strokeWidth={sw(2.5)}
            strokeDasharray={`${sw(6)} ${sw(3)}`}
          />
        )}
      </g>
      <text
        x={lx}
        y={ly}
        fontSize={fs}
        textAnchor="middle"
        dominantBaseline="central"
        fill="var(--map-ink)"
        pointerEvents="none"
      >
        {label}
      </text>
    </g>
  );
}

function Partition({ p, k, selected, conflict }: { p: PartitionObject; k: number; selected: boolean; conflict: boolean }) {
  const line = { x1: p.start[0], y1: p.start[1], x2: p.end[0], y2: p.end[1] };
  return (
    <g data-id={p.id}>
      {/* Невидима широка лінія — щоб тонку перегородку було легко вибрати */}
      <line {...line} stroke="transparent" strokeWidth={Math.max(p.thickness, 12 / k)} />
      <line
        {...line}
        stroke={conflict ? 'var(--map-bad)' : selected ? 'var(--map-acc)' : 'var(--map-pri)'}
        strokeWidth={p.thickness}
        strokeLinecap="square"
        pointerEvents="none"
      />
    </g>
  );
}

function Entry({ o, k, selected }: { o: ShapeObject; k: number; selected: boolean }) {
  const sw = (n: number) => n / k;
  return (
    <g data-id={o.id} transform={`translate(${o.x} ${o.y}) rotate(${o.a})`}>
      <circle r=".7" fill="var(--map-ok)" stroke="var(--map-okd)" strokeWidth={sw(2)} />
      <path d="M-.35 0H.35M.05 -.3L.4 0L.05 .3" fill="none" stroke="var(--map-ink)" strokeWidth={sw(2)} />
      {selected && (
        <circle r=".95" fill="none" stroke="var(--map-acc)" strokeWidth={sw(2)} strokeDasharray={`${sw(5)} ${sw(3)}`} />
      )}
      <text y="1.5" fontSize={12 / k} textAnchor="middle" fill="var(--map-ink)" pointerEvents="none">
        {o.name}
      </text>
    </g>
  );
}
