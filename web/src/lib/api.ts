const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SELLER_ID = process.env.NEXT_PUBLIC_DEV_SELLER_ID ?? "";

export type ProductStatus = "draft" | "published" | "archived";

export type Product = {
  id: string;
  name: string;
  description: string | null;
  price_paise: number;
  category_slug: string | null;
  status: ProductStatus;
  stock_quantity: number;
  created_at: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Seller-Id": SELLER_ID,
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

export type ProductCreate = {
  name: string;
  price_paise: number;
  description?: string | null;
  category_slug?: string | null;
  stock_quantity?: number;
};

export const api = {
  listProducts: (status?: ProductStatus) =>
    request<Product[]>(`/products${status ? `?status=${status}` : ""}`),
  getProduct: (id: string) => request<Product>(`/products/${id}`),
  createProduct: (body: ProductCreate) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(body) }),
};

export function formatPaise(paise: number): string {
  // Show paise only when there are any — never round a real price away.
  const fraction = paise % 100 === 0 ? 0 : 2;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: fraction,
    maximumFractionDigits: fraction,
  }).format(paise / 100);
}
/** Rupees as typed by a human -> integer paise. Money crosses this boundary once. */
export function rupeesToPaise(rupees: string): number {
  const cleaned = rupees.replace(/[₹,\s]/g, "");
  return Math.round(Number(cleaned) * 100);
}
