import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemesSection } from "@/components/themes/themes-section";
import type { Community } from "@/lib/types";

const search = vi.hoisted(() => ({ value: "" }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search.value) }));

const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

const community = (id: string, level: number, overrides: Partial<Community> = {}): Community => ({
  id,
  level,
  size: 3,
  title: `Theme ${id}`,
  summary: null,
  parent_id: null,
  member_ids: [`${id}-m1`],
  member_names: [`Member of ${id}`],
  summary_chunk_ids: [],
  ...overrides,
});

const LEVEL0 = [
  community("small", 0, { size: 2 }),
  community("big", 0, { size: 9, summary: "Banks cluster together [doc_a:0001] and lend [doc_b:0002]." }),
];
const LEVEL1 = [community("big-1", 1, { parent_id: "big", title: "Sub theme" })];

const scrollIntoView = vi.fn();

beforeEach(() => {
  Element.prototype.scrollIntoView = scrollIntoView;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => json(new URL(String(input)).searchParams.get("level") === "1" ? LEVEL1 : LEVEL0)),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  scrollIntoView.mockReset();
  search.value = "";
  window.history.replaceState(null, "", "/");
});

describe("ThemesSection", () => {
  it("sorts by size and renders summary citations as chips", async () => {
    render(<ThemesSection />);
    const headings = await screen.findAllByRole("heading", { level: 3 });
    expect(headings.map((heading) => heading.textContent)).toEqual(["Theme big", "Theme small"]);
    expect(screen.getByRole("button", { name: /Evidence 1, doc_a:0001/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Evidence 2, doc_b:0002/ })).toBeTruthy();
  });

  it("shows level-1 children on expand", async () => {
    render(<ThemesSection />);
    await screen.findByText("Theme big");
    expect(screen.queryByText("Sub theme")).toBeNull();
    fireEvent.click(screen.getAllByRole("button", { name: /sub-themes and members/ })[0]);
    expect(screen.getByText("Sub theme")).toBeTruthy();
  });

  it("member chip writes ?e and targets #explore", async () => {
    const explore = document.createElement("section");
    explore.id = "explore";
    document.body.append(explore);
    render(<ThemesSection />);
    fireEvent.click((await screen.findAllByRole("button", { name: /sub-themes and members|Members/ }))[0]);
    fireEvent.click(screen.getAllByRole("button", { name: "Member of big" })[0]);
    expect(new URL(window.location.href).searchParams.get("e")).toBe("big-m1");
    expect(window.location.hash).toBe("#explore");
    expect(scrollIntoView).toHaveBeenCalled();
    explore.remove();
  });

  it("?c expands the matching card", async () => {
    search.value = "c=small";
    render(<ThemesSection />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Hide detail" })).toBeTruthy());
    expect(screen.getAllByRole("button", { name: "Hide detail" })).toHaveLength(1);
    expect(document.getElementById("community-panel-small")?.hasAttribute("hidden")).toBe(false);
    expect(document.getElementById("community-panel-big")?.hasAttribute("hidden")).toBe(true);
  });

  it("re-opens the target card after the reader collapsed it and ?c changes", async () => {
    search.value = "c=small";
    const { rerender } = render(<ThemesSection />);
    fireEvent.click(await screen.findByRole("button", { name: "Hide detail" }));
    expect(screen.queryByRole("button", { name: "Hide detail" })).toBeNull();
    search.value = "c=big";
    rerender(<ThemesSection />);
    search.value = "c=small";
    rerender(<ThemesSection />);
    await waitFor(() => expect(document.getElementById("community-panel-small")?.hasAttribute("hidden")).toBe(false));
  });

  it("shows the empty and error states", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([])));
    const { unmount } = render(<ThemesSection />);
    await screen.findByText(/No communities yet/);
    unmount();
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("down"); }));
    render(<ThemesSection />);
    await screen.findByRole("alert");
  });
});
