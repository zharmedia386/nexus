import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Reveal } from "@/components/ui/reveal";

function stubMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduce && query.includes("reduce"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Reveal", () => {
  it("renders statically without animation under reduced motion", () => {
    stubMotion(true);
    const observe = vi.fn();
    vi.stubGlobal("IntersectionObserver", vi.fn(function () {
      return { observe, disconnect: vi.fn() };
    }));

    render(<Reveal>content</Reveal>);
    const wrapper = screen.getByText("content");

    expect(wrapper).toHaveAttribute("data-reveal", "static");
    expect(wrapper.className).not.toContain("animate-");
    expect(observe).not.toHaveBeenCalled();
  });

  it("adds the animation class once the element intersects", () => {
    stubMotion(false);
    let trigger: (entries: Partial<IntersectionObserverEntry>[]) => void = () => {};
    vi.stubGlobal("IntersectionObserver", vi.fn(function (callback: typeof trigger) {
      trigger = callback;
      return { observe: vi.fn(), disconnect: vi.fn() };
    }));

    render(<Reveal>content</Reveal>);
    const wrapper = screen.getByText("content");
    expect(wrapper).toHaveAttribute("data-reveal", "pending");

    act(() => trigger([{ isIntersecting: true }]));
    expect(wrapper).toHaveClass("animate-fade-up");
    expect(wrapper).toHaveAttribute("data-reveal", "shown");
  });
});
