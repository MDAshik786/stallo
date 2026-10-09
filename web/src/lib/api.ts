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

export type RunStatus =
  | "running"
  | "awaiting_input"
  | "awaiting_approval"
  | "completed"
  | "rejected"
  | "failed";

export type Suspension = {
  kind: "request_choice" | "request_confirmation";
  field?: string;
  prompt?: string;
  options?: { value: string; label: string }[];
  action?: string;
  target_id?: string;
  summary?: string;
};

export type ToolResult = { tool: string; result: Record<string, unknown> };

export type AgentRun = {
  id: string;
  status: RunStatus;
  utterance: string;
  suspension: Suspension | null;
  reply: string | null;
  error: string | null;
  results: ToolResult[] | null;
};

export type AgentAction = {
  id: string;
  tool: string;
  status: "success" | "failed" | "refused";
  args: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  undoable: boolean;
  undone: boolean;
  duration_ms: number | null;
  created_at: string;
};

export type Order = {
  id: string;
  order_number: string;
  customer_name: string;
  status: "pending" | "paid" | "shipped" | "delivered" | "cancelled";
  total_paise: number;
  placed_at: string;
  items: { name: string; quantity: number; unit_price_paise: number; line_total_paise: number }[];
};

export type OrderPage = { orders: Order[]; total: number };

export type RevenueBucket = { label: string; revenue_paise: number; orders: number };

export type Revenue = {
  start_date: string;
  end_date: string;
  group_by: string;
  category_slug: string | null;
  total_paise: number;
  order_count: number;
  previous_total_paise: number | null;
  change_pct: number | null;
  buckets: RevenueBucket[];
};

export type ProductSales = {
  name: string;
  category_slug: string | null;
  quantity: number;
  revenue_paise: number;
};

export const api = {
  listProducts: (status?: ProductStatus) =>
    request<Product[]>(`/products${status ? `?status=${status}` : ""}`),
  getProduct: (id: string) => request<Product>(`/products/${id}`),
  createProduct: (body: ProductCreate) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(body) }),

  listRuns: (limit = 20) => request<AgentRun[]>(`/agent/runs?limit=${limit}`),
  startRun: (utterance: string) =>
    request<AgentRun>("/agent/runs", {
      method: "POST",
      body: JSON.stringify({ utterance }),
    }),
  resumeRun: (id: string, body: { answer?: string; approved?: boolean }) =>
    request<AgentRun>(`/agent/runs/${id}/resume`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listActions: (limit = 25) => request<AgentAction[]>(`/agent/actions?limit=${limit}`),

  listOrders: (status?: string, limit = 25) =>
    request<OrderPage>(`/orders?limit=${limit}${status ? `&status=${status}` : ""}`),
  revenue: (days: number, groupBy: "day" | "week" | "month" | "category") =>
    request<Revenue>(`/analytics/revenue?days=${days}&group_by=${groupBy}`),
  productSales: (days: number, limit = 6) =>
    request<ProductSales[]>(`/analytics/products?days=${days}&limit=${limit}`),
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
