"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api, rupeesToPaise, type ProductCreate } from "@/lib/api";

const CATEGORIES = [
  "flowers",
  "valentines",
  "gifts",
  "chocolates",
  "plants",
  "home-decor",
  "festive",
];

type Props = {
  open: boolean;
  onClose: () => void;
};

export function NewProductDialog({ open, onClose }: Props) {
  const queryClient = useQueryClient();
  const firstFieldRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState("");
  const [rupees, setRupees] = useState("");
  const [category, setCategory] = useState("");
  const [stock, setStock] = useState("0");
  const [description, setDescription] = useState("");

  const mutation = useMutation({
    mutationFn: (body: ProductCreate) => api.createProduct(body),
    onSuccess: () => {
      // Every cached products list is now stale — refetch whichever are mounted.
      queryClient.invalidateQueries({ queryKey: ["products"] });
      reset();
      onClose();
    },
  });

  function reset() {
    setName("");
    setRupees("");
    setCategory("");
    setStock("0");
    setDescription("");
    mutation.reset();
  }

  useEffect(() => {
    if (!open) return;
    firstFieldRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const paise = rupees ? rupeesToPaise(rupees) : 0;
  const valid = name.trim().length > 0 && paise > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-4 backdrop-blur-sm sm:items-center">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-product-title"
        className="relative w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-xl"
      >
        <h2 id="new-product-title" className="text-[15px] font-semibold">
          New product
        </h2>
        <p className="mt-1 text-[13px] text-muted">
          Saved as a draft. Shoppers won&apos;t see it until you publish.
        </p>

        <form
          className="mt-5 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!valid) return;
            mutation.mutate({
              name: name.trim(),
              price_paise: paise,
              category_slug: category || null,
              description: description.trim() || null,
              stock_quantity: Number(stock) || 0,
            });
          }}
        >
          <Field label="Name">
            <input
              ref={firstFieldRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Rose Bouquet"
              maxLength={120}
              className={inputClass}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Price" hint={paise > 0 ? `${paise} paise` : undefined}>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[13px] text-subtle">
                  ₹
                </span>
                <input
                  value={rupees}
                  onChange={(e) => setRupees(e.target.value)}
                  inputMode="decimal"
                  placeholder="899"
                  className={`${inputClass} pl-7`}
                />
              </div>
            </Field>

            <Field label="Stock">
              <input
                value={stock}
                onChange={(e) => setStock(e.target.value)}
                inputMode="numeric"
                className={inputClass}
              />
            </Field>
          </div>

          <Field label="Category">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={inputClass}
            >
              <option value="">Uncategorised</option>
              {CATEGORIES.map((slug) => (
                <option key={slug} value={slug}>
                  {slug}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Description" optional>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              maxLength={2000}
              placeholder="12 fresh red roses, hand-tied."
              className={`${inputClass} resize-none`}
            />
          </Field>

          {mutation.isError && (
            <p className="rounded-lg bg-warning-soft px-3 py-2 text-[12px] text-warning">
              Could not save — {mutation.error.message}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-3.5 py-2 text-[13px] text-muted transition-colors hover:text-foreground"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!valid || mutation.isPending}
              className="rounded-lg bg-accent px-3.5 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40 dark:text-black"
            >
              {mutation.isPending ? "Saving…" : "Create draft"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const inputClass =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-[13px] outline-none transition-colors placeholder:text-subtle focus:border-accent";

function Field({
  label,
  hint,
  optional,
  children,
}: {
  label: string;
  hint?: string;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline justify-between text-[12px] font-medium text-muted">
        {label}
        {optional && <span className="text-subtle">optional</span>}
        {hint && <span className="font-normal text-subtle tabular-nums">{hint}</span>}
      </span>
      {children}
    </label>
  );
}
