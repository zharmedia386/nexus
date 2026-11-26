"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { APP_PAGES } from "@/lib/routes";

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="App pages" className="mx-auto flex max-w-content gap-1 overflow-x-auto px-6 pt-28">
      {APP_PAGES.map((page) => {
        const current = pathname === page.href;
        return (
          <Link
            key={page.href}
            href={page.href}
            aria-current={current ? "page" : undefined}
            className={`rounded-pill px-3.5 py-1.5 text-ui transition-colors duration-150 ease-std ${current ? "bg-inverse-bg font-medium text-inverse-fg" : "text-muted-fg hover:text-fg"}`}
          >
            {page.label}
          </Link>
        );
      })}
    </nav>
  );
}
