"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { CONTENT_PAGES, REPO_URL } from "@/lib/routes";

const linkClass = (current: boolean) =>
  `block rounded-pill px-3.5 py-1.5 text-ui transition-colors duration-150 ease-std ${current ? "bg-paper/15 font-medium text-paper" : "text-paper/75 hover:text-paper"}`;

export function SiteNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const [menuPath, setMenuPath] = useState(pathname);

  // Any navigation closes the sheet, including back/forward that never clicks a menu link.
  if (menuPath !== pathname) {
    setMenuPath(pathname);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      menuButton.current?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const close = () => setOpen(false);

  return (
    <header data-surface="dark" className="fixed inset-x-0 top-6 z-30 flex justify-center px-3 animate-nav-reveal sm:px-6">
      <nav aria-label="Primary" className="relative">
        <div className="glass-nav flex items-center gap-2 py-1.5 pr-1.5 pl-4 text-paper sm:gap-4">
          <Link href="/" className="flex items-center gap-2 rounded-pill text-ui font-medium tracking-[0.14em]">
            <svg viewBox="0 0 20 20" className="size-[18px]" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
              <circle cx="4" cy="15" r="2" />
              <circle cx="16" cy="5" r="2" />
              <circle cx="15" cy="15" r="1.5" />
              <path d="M5.6 13.6 14.4 6.4M6 15h7.5" strokeDasharray="2 2" />
            </svg>
            <span>NEXUS</span>
          </Link>
          <ul className="hidden items-center md:flex">
            {CONTENT_PAGES.map((page) => (
              <li key={page.href}>
                <Link href={page.href} aria-current={pathname === page.href ? "page" : undefined} className={linkClass(pathname === page.href)}>
                  {page.label}
                </Link>
              </li>
            ))}
            <li>
              <a href={REPO_URL} target="_blank" rel="noreferrer" className={linkClass(false)}>
                GitHub<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </li>
          </ul>
          <Link href="/ask" className="hidden rounded-pill bg-paper px-3.5 py-1.5 text-ui font-medium text-carbon md:block">
            Open app
          </Link>
          <ThemeToggle />
          <button
            ref={menuButton}
            type="button"
            aria-expanded={open}
            aria-controls={open ? "site-menu" : undefined}
            onClick={() => setOpen((value) => !value)}
            className="grid size-8 place-items-center rounded-pill text-paper/80 hover:text-paper md:hidden"
          >
            <span className="sr-only">Menu</span>
            <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
              <path d={open ? "M6 6l12 12M18 6 6 18" : "M4 7h16M4 12h16M4 17h16"} />
            </svg>
          </button>
        </div>
        {open && (
          <ul id="site-menu" className="glass-nav absolute inset-x-0 top-full mt-2 flex flex-col gap-1 p-2 text-paper md:hidden">
            {CONTENT_PAGES.map((page) => (
              <li key={page.href}>
                <Link href={page.href} onClick={close} aria-current={pathname === page.href ? "page" : undefined} className={linkClass(pathname === page.href)}>
                  {page.label}
                </Link>
              </li>
            ))}
            <li>
              <a href={REPO_URL} target="_blank" rel="noreferrer" className={linkClass(false)}>
                GitHub<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </li>
            <li>
              <Link href="/ask" onClick={close} className="block rounded-pill bg-paper px-3.5 py-1.5 text-center text-ui font-medium text-carbon">Open app</Link>
            </li>
          </ul>
        )}
      </nav>
    </header>
  );
}
