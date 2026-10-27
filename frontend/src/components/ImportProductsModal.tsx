import { AlertCircle, CheckCircle2, Download, FileSpreadsheet, Loader, UploadCloud, X } from 'lucide-react';
import { useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from 'react';
import { downloadImportTemplate, importProducts } from '../api/products';
import { downloadBlob } from '../api/client';
import type { ImportReport } from '../api/types';
import { Button } from './Button';
import { Modal } from './Modal';
import styles from './ImportProductsModal.module.css';

const MAX_SIZE_MB = 5;
const ALLOWED = ['.csv', '.xlsx'];
/** Скільки рядків помилок малювати в таблиці; повний список завжди є у CSV-звіті. */
const MAX_VISIBLE_ERRORS = 200;

interface ImportProductsModalProps {
  onClose: () => void;
  onImported: (report: ImportReport) => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
}

function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot === -1 ? '' : name.slice(dot).toLowerCase();
}

/** Звіт про помилки у вигляді CSV для передачі відповідальній особі. */
function downloadErrorReport(report: ImportReport) {
  const escape = (value: string | number | null) => {
    const text = value === null ? '' : String(value);
    return /[";\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const rows = [
    ['row', 'sku_code', 'field', 'message'],
    ...report.errors.map((error) => [error.row, error.sku_code ?? '', error.field ?? '', error.message]),
  ];
  const csv = rows.map((row) => row.map(escape).join(';')).join('\r\n');
  downloadBlob(`\ufeff${csv}`, `import_errors_${Date.now()}.csv`);
}

export function ImportProductsModal({ onClose, onImported }: ImportProductsModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  // dragenter/dragleave спрацьовують і на дочірніх елементах зони, тому рахуємо «глибину»
  const dragDepth = useRef(0);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [report, setReport] = useState<ImportReport | null>(null);

  const pickFile = (candidate: File | null) => {
    setError(null);
    if (!candidate) return;

    if (!ALLOWED.includes(extensionOf(candidate.name))) {
      setError('Підтримуються лише файли .csv та .xlsx');
      return;
    }
    if (candidate.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Файл завеликий — максимум ${MAX_SIZE_MB} МБ`);
      return;
    }
    if (candidate.size === 0) {
      setError('Файл порожній');
      return;
    }
    setFile(candidate);
  };

  const openPicker = () => {
    if (!uploading) inputRef.current?.click();
  };

  const handleDragEnter = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (uploading) return;
    dragDepth.current += 1;
    setDragging(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragging(false);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault(); // без цього drop не спрацює
    event.dataTransfer.dropEffect = uploading ? 'none' : 'copy';
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (uploading) return; // не підміняємо файл, поки йде імпорт
    pickFile(event.dataTransfer.files?.[0] ?? null);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    // події з вкладених елементів (кнопка «Прибрати файл») не повинні відкривати діалог
    if (event.target !== event.currentTarget) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault(); // пробіл не має прокручувати сторінку
      openPicker();
    }
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    pickFile(event.target.files?.[0] ?? null);
    // скидаємо значення, щоб той самий файл можна було вибрати повторно
    event.target.value = '';
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);

    let result: ImportReport;
    try {
      result = await importProducts(file);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не вдалося імпортувати файл');
      return;
    } finally {
      setUploading(false);
    }

    setReport(result);
    // збій оновлення таблиці не повинен виглядати як невдалий імпорт
    try {
      onImported(result);
    } catch (err) {
      console.error('onImported failed', err);
    }
  };

  const reset = () => {
    setFile(null);
    setReport(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const close = () => {
    if (uploading) return;
    onClose();
  };

  const hiddenErrors = report ? Math.max(0, report.errors.length - MAX_VISIBLE_ERRORS) : 0;

  return (
    <Modal
      title={report ? 'Результат імпорту' : 'Імпорт товарів'}
      subtitle={
        report
          ? `Файл ${report.filename}`
          : 'Завантажте CSV або Excel з товарами — коректні рядки буде збережено'
      }
      onClose={close}
      size="lg"
      dismissible={!uploading}
      footer={
        report ? (
          <>
            <Button variant="secondary" onClick={reset}>
              Імпортувати ще
            </Button>
            <Button variant="save" onClick={onClose}>
              Готово
            </Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={close} disabled={uploading}>
              Скасувати
            </Button>
            <Button variant="save" onClick={handleUpload} disabled={!file || uploading}>
              {uploading ? (
                <>
                  <Loader size={17} className="spin" aria-hidden /> Обробка…
                </>
              ) : (
                <>
                  <UploadCloud size={17} aria-hidden /> Імпортувати
                </>
              )}
            </Button>
          </>
        )
      }
    >
      {!report && (
        <div className={styles.content}>
          <div
            className={`${styles.dropzone} ${dragging ? styles.dragging : ''} ${file ? styles.hasFile : ''}`}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={openPicker}
            onKeyDown={handleKeyDown}
            role="button"
            tabIndex={uploading ? -1 : 0}
            aria-disabled={uploading}
            aria-label="Оберіть файл для імпорту"
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.xlsx"
              className={styles.hiddenInput}
              onChange={handleInputChange}
              disabled={uploading}
              tabIndex={-1}
            />

            {file ? (
              <div className={styles.fileCard}>
                <FileSpreadsheet size={34} aria-hidden />
                <div className={styles.fileInfo}>
                  <span className={styles.fileName}>{file.name}</span>
                  <span className={styles.fileMeta}>{formatSize(file.size)}</span>
                </div>
                {!uploading && (
                  <button
                    type="button"
                    className={styles.removeFile}
                    onClick={(event) => {
                      event.stopPropagation();
                      reset();
                    }}
                    aria-label="Прибрати файл"
                  >
                    <X size={16} aria-hidden />
                  </button>
                )}
              </div>
            ) : (
              <>
                <UploadCloud size={40} aria-hidden />
                <p className={styles.dropTitle}>Перетягніть файл сюди або натисніть, щоб обрати</p>
                <p className={styles.dropHint}>CSV або Excel (.xlsx), до {MAX_SIZE_MB} МБ</p>
              </>
            )}
          </div>

          {uploading && (
            <div className={styles.progress} role="status">
              <div className={styles.progressBar}>
                <span />
              </div>
              <p>Перевіряємо рядки та зберігаємо товари…</p>
            </div>
          )}

          {error && (
            <p className={styles.error} role="alert">
              <AlertCircle size={16} aria-hidden /> {error}
            </p>
          )}

          <div className={styles.templates}>
            <span>Потрібен зразок?</span>
            <button type="button" className={styles.link} onClick={() => void downloadImportTemplate('csv')}>
              <Download size={14} aria-hidden /> Шаблон CSV
            </button>
            <button type="button" className={styles.link} onClick={() => void downloadImportTemplate('xlsx')}>
              <Download size={14} aria-hidden /> Шаблон Excel
            </button>
          </div>

          <div className={styles.rules}>
            <p className={styles.rulesTitle}>Як працює імпорт</p>
            <ul>
              <li>Обовʼязкові колонки: sku_code, name, unit_of_measure, width, length, height, weight.</li>
              <li>Категорію вкажіть назвою — нова створиться автоматично.</li>
              <li>Товари з наявним артикулом оновлюються, нові — створюються.</li>
              <li>Рядки з помилками не зберігаються й потрапляють у звіт.</li>
            </ul>
          </div>
        </div>
      )}

      {report && (
        <div className={styles.content}>
          <div className={styles.summary}>
            <div className={`${styles.stat} ${styles.statTotal}`}>
              <span className={styles.statValue}>{report.total}</span>
              <span className={styles.statLabel}>Рядків у файлі</span>
            </div>
            <div className={`${styles.stat} ${styles.statCreated}`}>
              <span className={styles.statValue}>{report.created}</span>
              <span className={styles.statLabel}>Створено</span>
            </div>
            <div className={`${styles.stat} ${styles.statUpdated}`}>
              <span className={styles.statValue}>{report.updated}</span>
              <span className={styles.statLabel}>Оновлено</span>
            </div>
            <div className={`${styles.stat} ${report.failed ? styles.statFailed : styles.statClean}`}>
              <span className={styles.statValue}>{report.failed}</span>
              <span className={styles.statLabel}>З помилками</span>
            </div>
          </div>

          {report.categories_created > 0 && (
            <p className={styles.note}>
              Створено нових категорій: {report.categories_created}
            </p>
          )}

          {report.failed === 0 ? (
            <div className={styles.success} role="status">
              <CheckCircle2 size={22} aria-hidden />
              <div>
                <p className={styles.successTitle}>Імпорт завершено без помилок</p>
                <p className={styles.successText}>
                  Усі {report.total} рядків оброблено. Каталог товарів оновлено.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className={styles.errorHeader}>
                <div>
                  <h3 className={styles.errorTitle}>Рядки з помилками</h3>
                  <p className={styles.errorSubtitle}>
                    Виправте їх у файлі й повторіть імпорт — решта товарів уже збережена.
                  </p>
                </div>
                <Button variant="secondary" onClick={() => downloadErrorReport(report)}>
                  <Download size={16} aria-hidden /> Звіт CSV
                </Button>
              </div>

              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th scope="col">Рядок</th>
                      <th scope="col">Артикул</th>
                      <th scope="col">Поле</th>
                      <th scope="col">Помилка</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.errors.slice(0, MAX_VISIBLE_ERRORS).map((item, index) => (
                      <tr key={`${item.row}-${item.field}-${index}`}>
                        <td className={styles.rowNumber}>{item.row}</td>
                        <td>{item.sku_code || '—'}</td>
                        <td>{item.field || '—'}</td>
                        <td>{item.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {hiddenErrors > 0 && (
                <p className={styles.note}>
                  Показано перші {MAX_VISIBLE_ERRORS} помилок, ще {hiddenErrors} — лише у звіті CSV.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </Modal>
  );
}