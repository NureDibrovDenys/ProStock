import { Check, Loader, Plus, X } from 'lucide-react';
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import { createCategory, createProduct, updateProduct } from '../api/products';
import type { Category, Product, ProductPayload, UnitOfMeasure } from '../api/types';
import { UNIT_LABELS } from '../api/types';
import { Button } from './Button';
import { Input } from './Input';
import { Modal } from './Modal';
import { Select } from './Select';
import { mapServerErrors, type FieldErrors } from '../lib/validation';
import styles from './ProductFormModal.module.css';

type FormState = {
  sku_code: string;
  name: string;
  category_id: string;
  unit_of_measure: UnitOfMeasure;
  width: string;
  length: string;
  height: string;
  weight: string;
  min_stock_level: string;
};

const EMPTY_FORM: FormState = {
  sku_code: '',
  name: '',
  category_id: '',
  unit_of_measure: 'pcs',
  width: '',
  length: '',
  height: '',
  weight: '',
  min_stock_level: '',
};

const FORM_FIELDS = Object.keys(EMPTY_FORM);

function toForm(product: Product): FormState {
  return {
    sku_code: product.sku_code,
    name: product.name,
    category_id: String(product.category_id),
    unit_of_measure: product.unit_of_measure,
    width: product.width,
    length: product.length,
    height: product.height,
    weight: product.weight,
    min_stock_level: product.min_stock_level ?? '',
  };
}

function parseNumber(value: string): number | null {
  const normalized = value.trim().replace(',', '.');
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function validate(form: FormState, categories: Category[]): FieldErrors {
  const errors: FieldErrors = {};

  if (!form.sku_code.trim()) errors.sku_code = 'Вкажіть артикул';
  else if (form.sku_code.trim().length > 100) errors.sku_code = 'Максимум 100 символів';
  else if (/["'\\;]/.test(form.sku_code)) errors.sku_code = 'Без лапок, «;» та «\\»';

  if (!form.name.trim()) errors.name = 'Вкажіть назву товару';
  else if (form.name.trim().length > 255) errors.name = 'Максимум 255 символів';

  const categoryId = Number(form.category_id);
  if (!form.category_id || !Number.isInteger(categoryId) || categoryId <= 0) {
    errors.category_id = 'Оберіть категорію';
  } else if (!categories.some((category) => category.category_id === categoryId)) {
    errors.category_id = 'Категорію не знайдено';
  }

  const dimensions: Array<[keyof FormState, string]> = [
    ['width', 'ширину'],
    ['length', 'довжину'],
    ['height', 'висоту'],
    ['weight', 'вагу'],
  ];
  for (const [field, label] of dimensions) {
    const value = parseNumber(form[field]);
    if (value === null) errors[field] = `Вкажіть ${label}`;
    else if (value <= 0) errors[field] = 'Значення має бути більше 0';
    else if (value > 999999) errors[field] = 'Занадто велике значення';
  }

  if (form.min_stock_level.trim()) {
    const minStock = parseNumber(form.min_stock_level);
    if (minStock === null) errors.min_stock_level = 'Некоректне число';
    else if (minStock < 0) errors.min_stock_level = 'Не може бути відʼємним';
  }

  return errors;
}

interface ProductFormModalProps {
  product: Product | null;
  categories: Category[];
  onClose: () => void;
  onSaved: (product: Product) => void;
  onCategoryCreated: (category: Category) => void;
}

export function ProductFormModal({
  product,
  categories,
  onClose,
  onSaved,
  onCategoryCreated,
}: ProductFormModalProps) {
  const [form, setForm] = useState<FormState>(() => (product ? toForm(product) : EMPTY_FORM));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [newCategory, setNewCategory] = useState('');
  const [showCategoryInput, setShowCategoryInput] = useState(false);
  const [categoryError, setCategoryError] = useState<string | null>(null);

  const isEdit = Boolean(product);

  const saveMutation = useMutation({
    mutationFn: (payload: ProductPayload) =>
      product ? updateProduct(product.product_id, payload) : createProduct(payload),
    onSuccess: (saved) => onSaved(saved),
  });

  const categoryMutation = useMutation({
    mutationFn: (name: string) => createCategory({ name }),
    onSuccess: (category) => {
      onCategoryCreated(category);
      setForm((prev) => ({ ...prev, category_id: String(category.category_id) }));
      setErrors((prev) => ({ ...prev, category_id: undefined }));
      setNewCategory('');
      setShowCategoryInput(false);
      setCategoryError(null);
    },
    onError: (error) => {
      setCategoryError(error instanceof ApiError ? error.message : 'Не вдалося створити категорію');
    },
  });

  // Серверні 422 → підсвітка конкретних полів
  useEffect(() => {
    const requestError = saveMutation.error;
    if (requestError instanceof ApiError && requestError.details.length > 0) {
      setErrors((prev) => ({ ...prev, ...mapServerErrors(requestError.details, FORM_FIELDS) }));
    }
  }, [saveMutation.error]);

  const serverError = useMemo(() => {
    const error = saveMutation.error;
    if (!error) return null;
    if (error instanceof ApiError && error.status === 422) return 'Перевірте виділені поля';
    return error instanceof Error ? error.message : 'Не вдалося зберегти товар';
  }, [saveMutation.error]);

  const update = <K extends keyof FormState>(field: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const nextErrors = validate(form, categories);
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;

    const payload: ProductPayload = {
      sku_code: form.sku_code.trim(),
      name: form.name.trim(),
      category_id: Number(form.category_id),
      unit_of_measure: form.unit_of_measure,
      width: parseNumber(form.width)!,
      length: parseNumber(form.length)!,
      height: parseNumber(form.height)!,
      weight: parseNumber(form.weight)!,
      min_stock_level: parseNumber(form.min_stock_level),
    };
    saveMutation.mutate(payload);
  };

  const handleCategoryCreate = () => {
    const name = newCategory.trim();
    if (!name) {
      setCategoryError('Вкажіть назву категорії');
      return;
    }
    if (name.length > 150) {
      setCategoryError('Максимум 150 символів');
      return;
    }
    categoryMutation.mutate(name);
  };

  return (
    <Modal
      title={isEdit ? 'Редагування товару' : 'Новий товар'}
      subtitle={isEdit ? `Артикул ${product?.sku_code}` : 'Заповніть картку товару'}
      onClose={onClose}
      size="md"
      dismissible={!saveMutation.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saveMutation.isPending}>
            Скасувати
          </Button>
          <Button
            variant="save"
            onClick={() => {
              const formElement = document.getElementById('product-form') as HTMLFormElement | null;
              formElement?.requestSubmit();
            }}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending ? (
              <>
                <Loader size={17} className="spin" aria-hidden /> Збереження…
              </>
            ) : (
              <>
                <Check size={17} aria-hidden /> Зберегти
              </>
            )}
          </Button>
        </>
      }
    >
      <form id="product-form" className={styles.form} onSubmit={handleSubmit} noValidate>
        <div className={styles.row}>
          <Input
            label="Артикул (SKU) *"
            name="sku_code"
            placeholder="CHEM-001"
            value={form.sku_code}
            onChange={(e) => update('sku_code', e.target.value)}
            error={errors.sku_code}
            autoFocus
            maxLength={100}
          />
          <Input
            label="Назва товару *"
            name="name"
            placeholder="Мило рідке, 1 л"
            value={form.name}
            onChange={(e) => update('name', e.target.value)}
            error={errors.name}
            maxLength={255}
          />
        </div>

        <div className={styles.row}>
          <div className={styles.categoryField}>
            <Select
              label="Категорія *"
              name="category_id"
              value={form.category_id}
              onChange={(e) => update('category_id', e.target.value)}
              error={errors.category_id}
            >
              <option value="">Оберіть категорію</option>
              {categories.map((category) => (
                <option key={category.category_id} value={category.category_id}>
                  {category.name}
                </option>
              ))}
            </Select>
            {!showCategoryInput ? (
              <button type="button" className={styles.addCategory} onClick={() => setShowCategoryInput(true)}>
                <Plus size={14} aria-hidden /> Нова категорія
              </button>
            ) : (
              <div className={styles.newCategory}>
                <input
                  className={styles.newCategoryInput}
                  placeholder="Назва категорії"
                  value={newCategory}
                  onChange={(e) => {
                    setNewCategory(e.target.value);
                    setCategoryError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleCategoryCreate();
                    }
                  }}
                  maxLength={150}
                  aria-label="Назва нової категорії"
                />
                <button
                  type="button"
                  className={styles.categoryAction}
                  onClick={handleCategoryCreate}
                  disabled={categoryMutation.isPending}
                  aria-label="Створити категорію"
                  title="Створити категорію"
                >
                  {categoryMutation.isPending ? <Loader size={15} className="spin" /> : <Check size={15} />}
                </button>
                <button
                  type="button"
                  className={styles.categoryAction}
                  onClick={() => {
                    setShowCategoryInput(false);
                    setNewCategory('');
                    setCategoryError(null);
                  }}
                  aria-label="Скасувати створення категорії"
                  title="Скасувати"
                >
                  <X size={15} />
                </button>
              </div>
            )}
            {categoryError && (
              <p className={styles.categoryError} role="alert">
                {categoryError}
              </p>
            )}
          </div>

          <Select
            label="Одиниця виміру *"
            name="unit_of_measure"
            value={form.unit_of_measure}
            onChange={(e) => update('unit_of_measure', e.target.value as UnitOfMeasure)}
          >
            {(Object.keys(UNIT_LABELS) as UnitOfMeasure[]).map((unit) => (
              <option key={unit} value={unit}>
                {UNIT_LABELS[unit]} ({unit})
              </option>
            ))}
          </Select>
        </div>

        <fieldset className={styles.fieldset}>
          <legend className={styles.legend}>Габарити та вага</legend>
          <div className={styles.grid4}>
            <Input
              label="Ширина, м *"
              name="width"
              inputMode="decimal"
              placeholder="0.4"
              value={form.width}
              onChange={(e) => update('width', e.target.value)}
              error={errors.width}
            />
            <Input
              label="Довжина, м *"
              name="length"
              inputMode="decimal"
              placeholder="0.6"
              value={form.length}
              onChange={(e) => update('length', e.target.value)}
              error={errors.length}
            />
            <Input
              label="Висота, м *"
              name="height"
              inputMode="decimal"
              placeholder="0.25"
              value={form.height}
              onChange={(e) => update('height', e.target.value)}
              error={errors.height}
            />
            <Input
              label="Вага, кг *"
              name="weight"
              inputMode="decimal"
              placeholder="1.2"
              value={form.weight}
              onChange={(e) => update('weight', e.target.value)}
              error={errors.weight}
            />
          </div>
        </fieldset>

        <div className={styles.row}>
          <Input
            label="Мінімальний залишок"
            name="min_stock_level"
            inputMode="decimal"
            placeholder="10"
            value={form.min_stock_level}
            onChange={(e) => update('min_stock_level', e.target.value)}
            error={errors.min_stock_level}
            hint="Порожнє поле — контроль залишку вимкнено"
          />
        </div>

        {serverError && (
          <p className={styles.serverError} role="alert">
            {serverError}
          </p>
        )}
      </form>
    </Modal>
  );
}
