import { useEffect, type RefObject } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

type MotionContext = { gsap: typeof gsap; ScrollTrigger: typeof ScrollTrigger; reduced: boolean };

let registered = false;

export function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Build must only gsap.set end states when `reduced` is true; it runs once per deps change (list every value it reads) and reduced is read at mount.
export function useGsap(
  scope: RefObject<HTMLElement | null>,
  build: (ctx: MotionContext) => void,
  deps: unknown[] = [],
): void {
  useEffect(() => {
    if (!registered) {
      gsap.registerPlugin(ScrollTrigger);
      registered = true;
    }
    const reduced = prefersReducedMotion();
    const ctx = gsap.context(() => build({ gsap, ScrollTrigger, reduced }), scope);
    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- caller owns deps; build is typically an inline closure
  }, deps);
}
