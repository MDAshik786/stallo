"use client";

import { useState } from "react";

import { formatPaise } from "@/lib/api";

/**
 * Inline SVG charts. Single series throughout, so no legend — each title names
 * what is plotted. Marks are thin with 4px rounded data-ends anchored to the
 * baseline, a 2px surface gap between neighbours, and recessive gridlines.
 */

const compact = (paise: number) => {
  const rupees = paise / 100;
  if (rupees >= 1e7) return `₹${(rupees / 1e7).toFixed(1)}Cr`;
  if (rupees >= 1e5) return `₹${(rupees / 1e5).toFixed(1)}L`;
  if (rupees >= 1e3) return `₹${Math.round(rupees / 1e3)}k`;
  return `₹${Math.round(rupees)}`;
};

type Point = { label: string; value: number; sub?: string };

export function ColumnChart({ title, data }: { title: string; data: Point[] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (data.length === 0) return <Empty title={title} />;

  const W = 520;
  const H = 180;
  const PAD = { top: 16, right: 8, bottom: 26, left: 44 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const max = Math.max(...data.map((d) => d.value)) || 1;
  const step = plotW / data.length;
  const barW = Math.max(6, Math.min(44, step - 10));

  const ticks = [0, 0.5, 1].map((t) => ({ t, y: PAD.top + plotH - t * plotH }));

  return (
    <figure className="min-w-0 rounded-xl border border-border bg-surface p-4">
      <figcaption className="text-[13px] font-medium">{title}</figcaption>
      {/* The viewBox scales with the container, so on a narrow screen 9px
          axis labels render at ~5px. Keep the chart at a legible minimum and
          let it scroll instead of shrinking the type. */}
      <div className="relative mt-3 overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full min-w-[420px]"
          role="img"
          aria-label={title}
        >
          {ticks.map(({ t, y }) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y}
                    stroke="var(--color-grid)" strokeWidth="1" />
              <text x={PAD.left - 8} y={y + 3} textAnchor="end"
                    className="fill-subtle text-[9px] tabular-nums">
                {compact(max * t)}
              </text>
            </g>
          ))}

          {data.map((d, i) => {
            const h = Math.max(2, (d.value / max) * plotH);
            const x = PAD.left + i * step + (step - barW) / 2;
            const y = PAD.top + plotH - h;
            return (
              <g key={d.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                <rect x={PAD.left + i * step} y={PAD.top} width={step} height={plotH} fill="transparent" />
                <rect x={x} y={y} width={barW} height={h} rx="4"
                      fill="var(--color-series-1)"
                      opacity={hover === null || hover === i ? 1 : 0.45} />
                <text x={x + barW / 2} y={H - 8} textAnchor="middle"
                      className="fill-subtle text-[9px]">
                  {d.label}
                </text>
              </g>
            );
          })}
        </svg>

        {hover !== null && (
          <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 rounded-lg border border-border bg-background px-2.5 py-1.5 text-[11px] shadow-sm">
            <span className="font-medium">{data[hover].label}</span>
            <span className="ml-2 tabular-nums">{formatPaise(data[hover].value)}</span>
            {data[hover].sub && <span className="ml-2 text-subtle">{data[hover].sub}</span>}
          </div>
        )}
      </div>
    </figure>
  );
}

export function BarList({ title, data }: { title: string; data: Point[] }) {
  if (data.length === 0) return <Empty title={title} />;
  const max = Math.max(...data.map((d) => d.value)) || 1;

  return (
    <figure className="min-w-0 rounded-xl border border-border bg-surface p-4">
      <figcaption className="text-[13px] font-medium">{title}</figcaption>
      <ul className="mt-3 space-y-2.5">
        {data.map((d) => (
          <li key={d.label}>
            <div className="flex items-baseline justify-between gap-3 text-[12px]">
              <span className="truncate">{d.label}</span>
              <span className="shrink-0 tabular-nums text-muted">
                {formatPaise(d.value)}
                {d.sub && <span className="ml-1.5 text-subtle">{d.sub}</span>}
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-grid">
              <div
                className="h-full rounded-full bg-series-1"
                style={{ width: `${Math.max(2, (d.value / max) * 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </figure>
  );
}

export function StatTile({
  label, value, note, tone = "neutral",
}: {
  label: string;
  value: string;
  note?: string;
  tone?: "neutral" | "up" | "down";
}) {
  const toneClass =
    tone === "up" ? "text-success" : tone === "down" ? "text-warning" : "text-muted";
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-[12px] text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums tracking-tight">{value}</p>
      {note && <p className={`mt-0.5 text-[11px] ${toneClass}`}>{note}</p>}
    </div>
  );
}

function Empty({ title }: { title: string }) {
  return (
    <figure className="min-w-0 rounded-xl border border-dashed border-border p-6">
      <figcaption className="text-[13px] font-medium">{title}</figcaption>
      <p className="mt-1 text-[12px] text-muted">No data in this period.</p>
    </figure>
  );
}
