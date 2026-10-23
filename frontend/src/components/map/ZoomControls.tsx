import styles from './map.module.css';

type ZoomControlsProps = {
  scale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
};

export function ZoomControls({ scale, onZoomIn, onZoomOut, onReset }: ZoomControlsProps) {
  return (
    <div className={styles.zoom}>
      <button type="button" onClick={onZoomOut} aria-label="Зменшити">
        −
      </button>
      <button type="button" onClick={onReset} aria-label="Скинути масштаб" className={styles.zoomValue}>
        {Math.round(scale * 100)}%
      </button>
      <button type="button" onClick={onZoomIn} aria-label="Збільшити">
        +
      </button>
    </div>
  );
}
