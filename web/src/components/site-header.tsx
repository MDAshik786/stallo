"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/agent", label: "Assistant" },
  { href: "/products", label: "Products" },
  { href: "/orders", label: "Orders" },
  { href: "/analytics", label: "Analytics" },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center gap-4 px-4 sm:gap-8 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-accent text-[13px] font-semibold text-white dark:text-black">
            S
          </span>
          <span className="text-[15px] font-semibold tracking-tight">Stallo</span>
        </Link>

        <nav className="flex min-w-0 items-center gap-0.5 overflow-x-auto sm:gap-1">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`shrink-0 rounded-md px-2.5 py-1.5 text-[13px] transition-colors sm:px-3 ${
                  active
                    ? "bg-accent-soft font-medium text-accent"
                    : "text-muted hover:bg-surface hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-2 text-[13px] text-muted">
          <span className="hidden sm:inline">Demo Florist</span>
          <span className="flex h-7 w-7 items-center justify-center rounded-full border border-border bg-surface text-[11px] font-medium">
            DF
          </span>
        </div>
      </div>
    </header>
  );
}
