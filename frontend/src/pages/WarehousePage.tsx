import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { getRacks, getWarehouseMap } from '../api/warehouse';
import { Button } from '../components/Button';
import { MapLayers } from '../components/map/MapLayers';
import { ZoomControls } from '../components/map/ZoomControls';
import mapStyles from '../components/map/map.module.css';
import { fromApi, isShape, mapBounds, type ShapeObject } from '../components/map/model';
import { ErrorState, LoadingState, PageHeader } from '../components/ui';
import { WAREHOUSE_ID } from '../config';
import { useViewport } from '../hooks/useViewport';
import { useWarehouseName } from '../hooks/useWarehouse';
import { cx } from '../lib/cx';
import styles from './WarehousePage.module.css';

const LEGEND = [
  { label: 'Стіни та перегородки', className: styles.swatchRoom },
  { label: 'Стелаж', className: styles.swatchRack },
  { label: 'Перешкода', className: styles.swatchObstacle },
  { label: 'Зона приймання', className: styles.swatchInbound },
  { label: 'Зона зберігання', className: styles.swatchStorage },
  { label: 'Зона відвантаження', className: styles.swatchOutbound },
  { label: 'Точка входу', className: styles.swatchEntry },
];

export function WarehousePage() {
  const navigate = useNavigate();
  const warehouseName = useWarehouseName();
  const mapQuery = useQuery({
    queryKey: ['map', WAREHOUSE_ID],
    queryFn: () => getWarehouseMap(WAREHOUSE_ID),
  });
  const racksQuery = useQuery({
    queryKey: ['racks', WAREHOUSE_ID],
    queryFn: () => getRacks(WAREHOUSE_ID),
  });

  const objs = useMemo(() => (mapQuery.data ? fromApi(mapQuery.data) : []), [mapQuery.data]);
  const fills = useMemo(
    () => Object.fromEntries((racksQuery.data ?? []).map((r) => [r.rack_code, r.fill_percent])),
    [racksQuery.data],
  );

  const vp = useViewport();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const pressedId = useRef<string | null>(null);

  // Вписати мапу у вікно, коли дані прийшли
  useEffect(() => {
    if (objs.length) vp.fitTo(mapBounds(objs));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objs]);

  const racks = objs.filter((o): o is ShapeObject => o.t === 'rack');
  const hovered = objs.find((o) => o.id === hoveredId);
  const legendRack = hovered?.t === 'rack' ? hovered : racks[0];

  const idFromEvent = (e: ReactPointerEvent) =>
    ((e.target as Element).closest('[data-id]') as SVGElement | null)?.dataset.id ?? null;

  const handlePointerDown = (e: ReactPointerEvent) => {
    pressedId.current = idFromEvent(e);
    vp.startPan(e);
  };

  const handlePointerMove = (e: ReactPointerEvent) => {
    if (vp.movePan(e)) return;
    const id = idFromEvent(e);
    const obj = objs.find((o) => o.id === id);
    setHoveredId(obj && isShape(obj) ? obj.id : null);
  };

  const handlePointerUp = (e: ReactPointerEvent) => {
    vp.endPan(e);
    const pressed = objs.find((o) => o.id === pressedId.current);
    pressedId.current = null;
    if (pressed?.t === 'rack' && !vp.wasDrag()) navigate(`/warehouse/racks/${encodeURIComponent(pressed.name)}`);
  };

  const isEmpty = mapQuery.isSuccess && objs.length === 0;

  return (
    <>
      <PageHeader
        title={`Склад ${warehouseName}`}
        subtitle="Наведіть на стелаж — побачите його заповненість. Клік по стелажу відкриває його полиці."
        actions={
          <Button variant="secondary" to="/warehouse/edit">
            Редагувати склад
          </Button>
        }
      />

      <div className={styles.layout}>
        <div className={styles.mapCard}>
          {mapQuery.isPending && <LoadingState label="Завантаження мапи…" />}
          {mapQuery.isError && <ErrorState error={mapQuery.error} onRetry={() => mapQuery.refetch()} />}

          {mapQuery.isSuccess && (
            <>
              <svg
                ref={vp.bindSvg}
                className={cx(mapStyles.svg, vp.isPanning() && mapStyles.panning)}
                style={{ cursor: hovered?.t === 'rack' ? 'pointer' : undefined }}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={vp.endPan}
                onPointerLeave={() => setHoveredId(null)}
                role="img"
                aria-label={`Мапа складу ${warehouseName}`}
              >
                <MapLayers
                  objs={objs}
                  viewport={vp.viewport}
                  size={vp.size}
                  hoveredId={hoveredId}
                  showGrid={false}
                  rackCaption={(r) => (fills[r.name] !== undefined ? `${fills[r.name]}%` : null)}
                />
              </svg>

              {isEmpty && (
                <div className={styles.empty}>
                  <p>Мапа складу порожня.</p>
                  <p>Натисніть «Редагувати склад», щоб додати контур, стелажі та зони.</p>
                </div>
              )}

              <ZoomControls
                scale={vp.viewport.scale / 22}
                onZoomIn={() => vp.zoomBy(1.25)}
                onZoomOut={() => vp.zoomBy(0.8)}
                onReset={vp.reset}
              />
            </>
          )}
        </div>

        <aside className={styles.legend}>
          <h2 className={styles.legendTitle}>Легенда</h2>
          {LEGEND.map((entry) => (
            <div key={entry.label} className={styles.legendRow}>
              <span className={cx(styles.swatch, entry.className)} />
              {entry.label}
            </div>
          ))}
          {legendRack && (
            <p className={styles.legendNote}>
              Стелаж {legendRack.name}{' '}
              {fills[legendRack.name] !== undefined
                ? `заповнений на ${fills[legendRack.name]}%`
                : racksQuery.isError
                  ? '— дані про заповнення недоступні'
                  : '— немає даних про заповнення'}
            </p>
          )}
        </aside>
      </div>
    </>
  );
}
