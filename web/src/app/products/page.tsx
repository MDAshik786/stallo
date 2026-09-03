"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { NewProductDialog } from "@/components/new-product-dialog";
import { StatusPill } from "@/components/status-pill";
import { api, formatPaise, type ProductStatus } from "@/lib/api";

const FILTERS = [
  { value: undefined, label: "All" },
  { value: "published" as const, label: "Published" },
  { value: "draft" as const, label: "Drafts" },
];

export default function ProductsPage() {
  const [status, setStatus] = useState<ProductStatus | undefined>(undefined);
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data, isPending, isError, error, isFetching } = useQuery({
    queryKey: ["products", status ?? "all"],
    queryFn: () => api.listProducts(status),
  });

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10">
      <NewProductDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Products</h1>
          <p className="mt-1 text-[13px] text-muted">
            {isPending ? "Loading…" : `${data?.length ?? 0} in your catalogue`}
          </p>
        </div>

        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="rounded-lg bg-accent px-3.5 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90 dark:text-black"
        >
          New product
        </button>
      </div>

      <div className="mt-6 flex items-center gap-1 border-b border-border">
        {FILTERS.map((filter) => {
          const active = status === filter.value;
          return (
            <button
              key={filter.label}
              type="button"
              onClick={() => setStatus(filter.value)}
              className={`-mb-px border-b-2 px-3 py-2 text-[13px] transition-colors ${
                active
                  ? "border-accent font-medium text-foreground"
                  : "border-transparent text-muted hover:text-foreground"
              }`}
            >
              {filter.label}
            </button>
          );
        })}
        {isFetching && !isPending && (
          <span className="ml-auto pb-2 text-[11px] text-subtle">Refreshing…</span>
        )}
      </div>

      {isError ? (
        <div className="mt-6 rounded-xl border border-border bg-surface p-6">
          <p className="text-[13px] font-medium">Could not load products</p>
          <p className="mt-1 text-[13px] text-muted">{error.message}</p>
        </div>
      ) : isPending ? (
        <ProductSkeleton />
      ) : data.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-border p-12 text-center">
          <p className="text-[13px] font-medium">Nothing here yet</p>
          <p className="mt-1 text-[13px] text-muted">
            Products you add will show up in this list.
          </p>
        </div>
      ) : (
        <ul className="mt-6 divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {data.map((product) => (
            <li
              key={product.id}
              className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-background"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-background text-[13px] font-medium text-subtle">
                {product.name.charAt(0)}
              </div>

              <div className="min-w-0 flex-1">
                <p className="truncate text-[14px] font-medium">{product.name}</p>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                  <p className="truncate text-[12px] text-muted">
                    {product.category_slug ?? "uncategorised"} · {product.stock_quantity} in stock
                  </p>
                  <span className="sm:hidden">
                    <StatusPill status={product.status} />
                  </span>
                </div>
              </div>

              <span className="hidden sm:block">
                <StatusPill status={product.status} />
              </span>

              <p className="w-16 shrink-0 text-right text-[14px] font-medium tabular-nums sm:w-20">
                {formatPaise(product.price_paise)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

function ProductSkeleton() {
  return (
    <ul className="mt-6 divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
      {Array.from({ length: 5 }).map((_, i) => (
        <li key={i} className="flex items-center gap-4 px-5 py-4">
          <div className="h-10 w-10 shrink-0 animate-pulse rounded-lg bg-border" />
          <div className="min-w-0 flex-1 space-y-2">
            <div className="h-3.5 w-40 animate-pulse rounded bg-border" />
            <div className="h-3 w-24 animate-pulse rounded bg-border" />
          </div>
          <div className="h-5 w-16 shrink-0 animate-pulse rounded-full bg-border" />
          <div className="h-3.5 w-14 shrink-0 animate-pulse rounded bg-border" />
        </li>
      ))}
    </ul>
  );
}
