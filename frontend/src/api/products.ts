import { downloadFile, getAccessToken, refreshAccessToken, request } from './client';
import type {
  Category,
  ImportReport,
  Product,
  ProductList,
  ProductPayload,
  ProductQuery,
} from './types';

const PRODUCTS = '/products';

/** GET /api/v1/products — сторінка каталогу з пошуком, фільтрами та сортуванням. */
export const getProducts = (query: ProductQuery) =>
  request<ProductList>(PRODUCTS, {
    query: {
      search: query.search,
      category_id: query.category_id,
      unit_of_measure: query.unit_of_measure,
      sort_by: query.sort_by,
      sort_order: query.sort_order,
      page: query.page,
      page_size: query.page_size,
    },
  });

/** POST /api/v1/products */
export const createProduct = (payload: ProductPayload) =>
  request<Product>(PRODUCTS, { method: 'POST', body: payload });

/** PATCH /api/v1/products/{id} */
export const updateProduct = (productId: number, payload: Partial<ProductPayload>) =>
  request<Product>(`${PRODUCTS}/${productId}`, { method: 'PATCH', body: payload });

/** DELETE /api/v1/products/{id} */
export const deleteProduct = (productId: number) =>
  request<void>(`${PRODUCTS}/${productId}`, { method: 'DELETE' });

function uploadFile(file: File): Promise<Response> {
  const formData = new FormData();
  formData.append('file', file);
  const token = getAccessToken();
  return fetch(`/api/v1${PRODUCTS}/import`, {
    method: 'POST',
    body: formData,
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

async function parseImportResponse(response: Response): Promise<ImportReport> {
  if (!response.ok) {
    let message = `Не вдалося імпортувати файл (${response.status})`;
    try {
      const data = (await response.json()) as { detail?: unknown };
      if (typeof data.detail === 'string') message = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) message = data.detail[0].msg;
    } catch {
      // тіло не JSON
    }
    throw new Error(message);
  }
  return (await response.json()) as ImportReport;
}

/** POST /api/v1/products/import — імпорт CSV/XLSX зі звітом про помилки. */
export async function importProducts(file: File): Promise<ImportReport> {
  let response = await uploadFile(file);
  if (response.status === 401) {
    const session = await refreshAccessToken();
    if (!session) throw new Error('Сесія завершилася. Увійдіть знову.');
    response = await uploadFile(file);
  }
  return parseImportResponse(response);
}

/** GET /api/v1/products/export — завантаження CSV або Excel. */
export const exportProducts = (format: 'csv' | 'xlsx', query: ProductQuery) =>
  downloadFile(`${PRODUCTS}/export`, {
    query: {
      format,
      search: query.search,
      category_id: query.category_id,
      unit_of_measure: query.unit_of_measure,
      sort_by: query.sort_by,
      sort_order: query.sort_order,
    },
    fallbackFilename: `products.${format}`,
  });

/** GET /api/v1/products/import/template — шаблон для заповнення. */
export const downloadImportTemplate = (format: 'csv' | 'xlsx') =>
  downloadFile(`${PRODUCTS}/import/template`, {
    query: { format },
    fallbackFilename: `products_template.${format}`,
  });

// ── Категорії ──────────────────────────────────────────────────────────────

export const getCategories = () => request<Category[]>('/categories');

export const createCategory = (payload: { name: string; description?: string | null }) =>
  request<Category>('/categories', { method: 'POST', body: payload });
