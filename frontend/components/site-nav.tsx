"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { SECTIONS, onSectionLink, type SectionId } from "@/lib/sections";

// Scroll-spy: the section crossing a thin band just above mid-viewport is the active one.
function useActiveSection(pathname: string) {
  const [active, setActive] = useState<SectionId | null>(null);

  useEffect(() => {
    const visible = new Set<string>();
    // The last section can be too short to reach the band, so the page bottom selects it.
    const update = () => {
      const atBottom = window.scrollY > 0 && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
      setActive(atBottom ? SECTIONS[SECTIONS.length - 1].id : (SECTIONS.find((section) => visible.has(section.id))?.id ?? null));
    };
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => (entry.isIntersecting ? visible.add(entry.target.id) : visible.delete(entry.target.id)));
        update();
      },
      { rootMargin: "-45% 0px -54% 0px" },
    );
    window.addEventListener("scroll", update, { passive: true });
    SECTIONS.forEach((section) => {
      const element = document.getElementById(section.id);
      if (element) observer.observe(element);
    });
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", update);
    };
  }, [pathname]);

  return active;
}

export function SiteNav() {
  const pathname = usePathname();
  const active = useActiveSection(pathname);

  return (
    <header data-surface="dark" className="fixed inset-x-0 top-6 z-30 flex justify-center px-3 animate-nav-reveal sm:px-6">
      <nav aria-label="Primary" className="glass-nav flex items-center gap-2 py-1.5 pr-1.5 pl-4 text-paper sm:gap-4">
        <Link href="/" className="flex items-center gap-2 rounded-pill text-ui font-medium tracking-[0.14em]">
          <svg viewBox="0 0 20 20" className="size-[18px]" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
            <circle cx="4" cy="15" r="2" />
            <circle cx="16" cy="5" r="2" />
            <circle cx="15" cy="15" r="1.5" />
            <path d="M5.6 13.6 14.4 6.4M6 15h7.5" strokeDasharray="2 2" />
          </svg>
          <span className="sr-only sm:not-sr-only">NEXUS</span>
        </Link>
        <ul className="flex items-center">
          {SECTIONS.map((section) => {
            const current = active === section.id;
            return (
              <li key={section.id}>
                <Link
                  href={`/#${section.id}`}
                  onClick={(event) => onSectionLink(event, section.id)}
                  aria-current={current ? "location" : undefined}
                  className={`block rounded-pill px-2.5 py-1.5 text-ui transition-colors duration-150 ease-std sm:px-3.5 ${current ? "bg-paper/15 font-medium text-paper" : "text-paper/75 hover:text-paper"}`}
                >
                  {section.label}
                </Link>
              </li>
            );
          })}
        </ul>
        <ThemeToggle />
      </nav>
    </header>
  );
}
