"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { StatTile } from "@/components/charts";
import { api, formatPaise, type Order } from "@/lib/api";

const FILTERS = [
  { value: undefined, label: "All" },
  { value: "delivered", label: "Delivered" },
  { value: "shipped", label: "Shipped" },
  { value: "paid", label: "Paid" },
  { value: "cancelled", label: "Cancelled" },
];

const TONE: Record<Order["status"], string> = {
  delivered: "bg-success-soft text-success",
  shipped: "bg-accent-soft text-accent",
  paid: "bg-accent-soft text-accent",
  pending: "bg-warning-soft text-warning",
  cancelled: "bg-surface text-subtle",
};

export default function OrdersPage() {
  const [status, setStatus] = useState<string | undefined>(undefined);

  const orders = useQuery({
    queryKey: ["orders", status ?? "all"],
    queryFn: () => api.listOrders(status, 25),
  });
  const revenue = useQuery({ queryKey: ["revenue", 30, "month"], queryFn: () => api.revenue(30, "month") });

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10">
      <h1 className="text-xl font-semibold tracking-tight">Orders</h1>
      <p className="mt-1 text-[13px] text-muted">
        {orders.data ? `${orders.data.total} in total` : "Loading…"}
      </p>

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <StatTile label="Revenue, 30 days" value={revenue.data ? formatPaise(revenue.data.total_paise) : "—"} />
        <StatTile label="Orders, 30 days" value={revenue.data ? String(revenue.data.order_count) : "—"} />
        <StatTile
          label="Average order"
          value={
            revenue.data && revenue.data.order_count
              ? formatPaise(Math.round(revenue.data.total_paise / revenue.data.order_count))
              : "—"
          }
        />
      </div>

      <div className="mt-6 flex items-center gap-1 overflow-x-auto border-b border-border">
        {FILTERS.map((filter) => {
          const active = status === filter.value;
          return (
            <button
              key={filter.label}
              type="button"
              onClick={() => setStatus(filter.value)}
              className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-[13px] transition-colors ${
                active
                  ? "border-accent font-medium text-foreground"
                  : "border-transparent text-muted hover:text-foreground"
              }`}
            >
              {filter.label}
            </button>
          );
        })}
      </div>

      {orders.isPending ? (
        <ul className="mt-6 divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {Array.from({ length: 6 }).map((_, i) => (
            <li key={i} className="flex items-center gap-4 px-5 py-3.5">
              <div className="h-3.5 w-28 animate-pulse rounded bg-border" />
              <div className="h-3.5 w-24 animate-pulse rounded bg-border" />
              <div className="ml-auto h-3.5 w-16 animate-pulse rounded bg-border" />
            </li>
          ))}
        </ul>
      ) : orders.data?.orders.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-border p-12 text-center">
          <p className="text-[13px] font-medium">No orders here</p>
        </div>
      ) : (
        <ul className="mt-6 divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {orders.data?.orders.map((order) => (
            <li key={order.id} className="flex items-center gap-4 px-5 py-3.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">{order.customer_name}</p>
                <p className="mt-0.5 truncate font-mono text-[11px] text-subtle">
                  {order.order_number}
                </p>
              </div>

              <p className="hidden shrink-0 text-[12px] text-muted sm:block">
                {order.items.length} item{order.items.length === 1 ? "" : "s"}
              </p>

              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${TONE[order.status]}`}
              >
                {order.status}
              </span>

              <p className="w-20 shrink-0 text-right text-[13px] font-medium tabular-nums">
                {formatPaise(order.total_paise)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
