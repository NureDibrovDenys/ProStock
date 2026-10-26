import { AlertTriangle, Loader } from 'lucide-react';
import { Button } from './Button';
import { Modal } from './Modal';
import styles from './ConfirmDialog.module.css';

interface ConfirmDialogProps {
  title: string;
  message: string;
  details?: string;
  confirmLabel?: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({
  title,
  message,
  details,
  confirmLabel = 'Видалити',
  busy = false,
  error,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Modal
      title={title}
      onClose={onClose}
      size="sm"
      dismissible={!busy}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Скасувати
          </Button>
          <Button variant="cancel" onClick={onConfirm} disabled={busy}>
            {busy ? (
              <>
                <Loader size={16} className="spin" aria-hidden /> Видалення…
              </>
            ) : (
              confirmLabel
            )}
          </Button>
        </>
      }
    >
      <div className={styles.content}>
        <span className={styles.icon} aria-hidden>
          <AlertTriangle size={22} />
        </span>
        <div>
          <p className={styles.message}>{message}</p>
          {details && <p className={styles.details}>{details}</p>}
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
}
