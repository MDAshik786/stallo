import type { ProductStatus } from "@/lib/api";

const STYLES: Record<ProductStatus, string> = {
  published: "bg-success-soft text-success",
  draft: "bg-warning-soft text-warning",
  archived: "bg-surface text-subtle",
};

export function StatusPill({ status }: { status: ProductStatus }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${STYLES[status]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {status}
    </span>
  );
}
