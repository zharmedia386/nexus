"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type CSSProperties, type ReactNode } from "react";

type RevealState = "pending" | "shown" | "static";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(onChange: () => void) {
  const query = window.matchMedia(REDUCED_MOTION);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function useReducedMotion() {
  return useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia(REDUCED_MOTION).matches,
    () => false,
  );
}

// One shared observer hook: marks the element once it enters the viewport.
export function useReveal<T extends Element>() {
  const ref = useRef<T>(null);
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element || reduced) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        setShown(true);
        observer.disconnect();
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [reduced]);

  const state: RevealState = reduced ? "static" : shown ? "shown" : "pending";
  return { ref, state };
}

type RevealProps = {
  children: ReactNode;
  animation?: string;
  delayMs?: number;
  className?: string;
};

export function Reveal({ children, animation = "animate-fade-up", delayMs = 0, className = "" }: RevealProps) {
  const { ref, state } = useReveal<HTMLDivElement>();
  const style: CSSProperties | undefined = delayMs ? { animationDelay: `${delayMs}ms` } : undefined;

  return (
    <div
      ref={ref}
      data-reveal={state}
      style={style}
      className={`${state === "shown" ? animation : ""} ${className}`}
    >
      {children}
    </div>
  );
}
