"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { SECTIONS, type SectionId } from "@/lib/sections";

type LazySectionProps = { id: SectionId; placeholderClassName: string; eager?: boolean; children: ReactNode };

// Mounts its section once it is near the viewport, or at once when the URL targets it (or a section below).
export function LazySection({ id, placeholderClassName, eager = false, children }: LazySectionProps) {
  const params = useSearchParams();
  const ref = useRef<HTMLDivElement>(null);
  const [arrival] = useState(() => {
    const own = SECTIONS.findIndex((section) => section.id === id);
    const keys: readonly string[] = SECTIONS[own]?.keys ?? [];
    const hash = window.location.hash.slice(1);
    const linked = keys.some((key) => params.has(key));
    const firstLinked = SECTIONS.findIndex((section) => section.keys.some((key) => params.has(key)));
    // Sections above a hash target mount too, so their real height is in place before the jump.
    const aboveTarget = own <= SECTIONS.findIndex((section) => section.id === hash);
    return { mount: eager || linked || aboveTarget, scroll: hash === id || (!hash && firstLinked === own) };
  });
  const [near, setNear] = useState(arrival.mount);

  useEffect(() => {
    const element = ref.current;
    if (near || !element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        setNear(true);
        observer.disconnect();
      },
      { rootMargin: "400px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [near]);

  // Sections above hydrate after the browser's own hash jump, so land on the target again.
  useEffect(() => {
    if (arrival.scroll) document.getElementById(id)?.scrollIntoView({ block: "start" });
  }, [arrival, id]);

  return near ? <>{children}</> : <div ref={ref} aria-hidden="true" className={placeholderClassName} />;
}
