import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LazySection } from "@/components/lazy-section";

const search = vi.hoisted(() => ({ value: "" }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search.value) }));

afterEach(() => {
  search.value = "";
  window.history.replaceState(null, "", "/");
});

describe("LazySection arrival scroll", () => {
  it("without a hash scrolls only to the first section whose params are present", () => {
    search.value = "q=hi&e=c0";
    const scrolled: string[] = [];
    Element.prototype.scrollIntoView = function scrollIntoView(this: Element) {
      scrolled.push(this.id);
    };
    render(
      <>
        <LazySection id="ask" placeholderClassName="h-4"><div id="ask" /></LazySection>
        <LazySection id="explore" placeholderClassName="h-4"><div id="explore" /></LazySection>
      </>,
    );
    expect(scrolled).toEqual(["ask"]);
  });
});
