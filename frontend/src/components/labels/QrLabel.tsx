import { QRCodeSVG } from 'qrcode.react';
import { cx } from '../../lib/cx';
import type { LabelData } from './labelData';
import styles from './QrLabel.module.css';

type QrLabelProps = {
  label: LabelData;
  className?: string;
};

/** Етикетка 58×40 мм (стандартна термоетикетка): QR зліва, підписи справа. */
export function QrLabel({ label, className }: QrLabelProps) {
  return (
    <div className={cx(styles.label, className)}>
      <div className={styles.qrColumn}>
        {/* Рівень корекції M витримує подряпини на етикетці і лишає QR достатньо простим для 28 мм. */}
        <QRCodeSVG value={label.qr} level="M" marginSize={0} className={styles.qr} title={label.qr} />
        <span className={styles.code}>{label.qr}</span>
      </div>
      <div className={styles.text}>
        <span className={styles.kind}>{label.kind}</span>
        <span className={styles.title}>{label.title}</span>
        {label.lines.map((line, index) => (
          <span key={index} className={styles.line}>
            {line}
          </span>
        ))}
      </div>
    </div>
  );
}
