import { createElement, useRef } from "react";
import { render } from "@testing-library/react";
import { gsap } from "gsap";
import { afterEach, describe, expect, it, vi } from "vitest";
import { prefersReducedMotion, useGsap } from "@/lib/motion";

function mockReducedMotion(matches: boolean) {
  window.matchMedia = vi.fn().mockReturnValue({ matches, addEventListener: vi.fn(), removeEventListener: vi.fn() }) as unknown as typeof window.matchMedia;
}

function Probe() {
  const scope = useRef<HTMLDivElement>(null);
  useGsap(scope, ({ gsap: g, reduced }) => {
    if (reduced) g.set(".box", { opacity: 1 });
    else g.to(".box", { opacity: 0.5 });
  });
  // eslint-disable-next-line react-hooks/refs -- createElement form of a plain ref prop
  return createElement("div", { ref: scope }, createElement("i", { className: "box", style: { opacity: 0 } }));
}

const originalMatchMedia = window.matchMedia;

afterEach(() => {
  vi.restoreAllMocks();
  window.matchMedia = originalMatchMedia;
});

describe("motion", () => {
  it("reads the reduced-motion media query", () => {
    mockReducedMotion(true);
    expect(prefersReducedMotion()).toBe(true);
    mockReducedMotion(false);
    expect(prefersReducedMotion()).toBe(false);
  });

  it("sets end states without tweens when reduced, and reverts on unmount", () => {
    mockReducedMotion(true);
    const revert = vi.fn();
    const realContext = gsap.context.bind(gsap);
    vi.spyOn(gsap, "context").mockImplementation((...args: Parameters<typeof gsap.context>) => {
      const ctx = realContext(...args);
      const realRevert = ctx.revert.bind(ctx);
      ctx.revert = (...revertArgs) => (revert(), realRevert(...revertArgs));
      return ctx;
    });
    const { container, unmount } = render(createElement(Probe));
    expect((container.querySelector(".box") as HTMLElement).style.opacity).toBe("1");
    // ScrollTrigger registers its own zero-duration delayedCall; only real tweens count.
    expect(gsap.globalTimeline.getChildren().filter((child) => child.duration() > 0)).toHaveLength(0);
    unmount();
    expect(revert).toHaveBeenCalled();
  });

  it("creates one real tween when motion is allowed, and reverts it on unmount", () => {
    mockReducedMotion(false);
    const { unmount } = render(createElement(Probe));
    const realTweens = () => gsap.globalTimeline.getChildren().filter((child) => child.duration() > 0);
    expect(realTweens()).toHaveLength(1);
    unmount();
    expect(realTweens()).toHaveLength(0);
  });
});
