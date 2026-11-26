import { Printer } from 'lucide-react';
import { useState } from 'react';
import type { Shelf } from '../api/types';
import { Button } from './Button';
import { LabelPrinter } from './labels/LabelPrinter';
import { shelfLabel } from './labels/labelData';
import { QrLabel } from './labels/QrLabel';
import { Modal } from './Modal';
import styles from './ShelfQrModal.module.css';

type ShelfQrModalProps = {
  shelf: Shelf;
  rackCode: string;
  onClose: () => void;
};

/** QR полиці: збільшений попередній перегляд етикетки і друк. */
export function ShelfQrModal({ shelf, rackCode, onClose }: ShelfQrModalProps) {
  const [printing, setPrinting] = useState(false);
  const label = shelfLabel(shelf, rackCode);

  return (
    <Modal
      title={`QR полиці ${shelf.shelf_code}`}
      subtitle={`Стелаж ${rackCode}`}
      size="sm"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Закрити
          </Button>
          <Button onClick={() => setPrinting(true)} disabled={printing}>
            <Printer size={18} aria-hidden /> Друкувати етикетку
          </Button>
        </>
      }
    >
      <div className={styles.preview}>
        <QrLabel label={label} className={styles.label} />
      </div>
      <p className={styles.hint}>Етикетка 58×40 мм. Комірник сканує QR, щоб підтвердити полицю під час розміщення.</p>

      {printing && <LabelPrinter labels={[label]} onDone={() => setPrinting(false)} />}
    </Modal>
  );
}
