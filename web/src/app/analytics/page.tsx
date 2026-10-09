"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { BarList, ColumnChart, StatTile } from "@/components/charts";
import { api, formatPaise } from "@/lib/api";

const RANGES = [
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: 180, label: "6 months" },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function shortLabel(label: string) {
  const [y, m, d] = label.split("-");
  if (d) return `${d} ${MONTHS[Number(m) - 1]}`;
  return `${MONTHS[Number(m) - 1]} ${y.slice(2)}`;
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(90);
  const groupBy = days <= 30 ? "day" : "month";

  const revenue = useQuery({
    queryKey: ["revenue", days, groupBy],
    queryFn: () => api.revenue(days, groupBy),
  });
  const byCategory = useQuery({
    queryKey: ["revenue", days, "category"],
    queryFn: () => api.revenue(days, "category"),
  });
  const products = useQuery({
    queryKey: ["product-sales", days],
    queryFn: () => api.productSales(days, 6),
  });

  const r = revenue.data;
  const change = r?.change_pct;

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Analytics</h1>
          <p className="mt-1 text-[13px] text-muted">
            Cancelled orders are excluded. Ask the assistant the same questions in words.
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-border bg-surface p-0.5">
          {RANGES.map((range) => (
            <button
              key={range.days}
              type="button"
              onClick={() => setDays(range.days)}
              className={`rounded-md px-3 py-1.5 text-[12px] transition-colors ${
                days === range.days
                  ? "bg-accent-soft font-medium text-accent"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <StatTile
          label="Revenue"
          value={r ? formatPaise(r.total_paise) : "—"}
          note={
            change === null || change === undefined
              ? undefined
              : `${change > 0 ? "+" : ""}${change}% vs previous ${days} days`
          }
          tone={change == null ? "neutral" : change >= 0 ? "up" : "down"}
        />
        <StatTile label="Orders" value={r ? String(r.order_count) : "—"} />
        <StatTile
          label="Average order"
          value={r && r.order_count ? formatPaise(Math.round(r.total_paise / r.order_count)) : "—"}
        />
      </div>

      <div className="mt-6 grid min-w-0 gap-4 lg:grid-cols-2">
        <div className="min-w-0 lg:col-span-2">
          <ColumnChart
            title={groupBy === "day" ? "Revenue by day" : "Revenue by month"}
            data={(r?.buckets ?? []).map((b) => ({
              label: shortLabel(b.label),
              value: b.revenue_paise,
              sub: `${b.orders} orders`,
            }))}
          />
        </div>

        <BarList
          title="Revenue by category"
          data={(byCategory.data?.buckets ?? []).map((b) => ({
            label: b.label,
            value: b.revenue_paise,
          }))}
        />

        <BarList
          title="Top products by revenue"
          data={(products.data ?? []).map((p) => ({
            label: p.name,
            value: p.revenue_paise,
            sub: `${p.quantity} sold`,
          }))}
        />
      </div>
    </main>
  );
}
