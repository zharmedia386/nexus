import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DEBOUNCE_MS, EntitySearch } from "@/components/graph/entity-search";
import { ExploreView } from "@/components/graph/explore-view";
import { buildGraph, CANVAS_CAP, computeLayout } from "@/components/graph/layout";
import type { EntityDetail, EntityEdge, EntitySearchResult } from "@/lib/types";

const search = vi.hoisted(() => ({ value: "" }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search.value) }));

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const edge = (otherId: string, overrides: Partial<EntityEdge> = {}): EntityEdge => ({
  type: "SERVES_AS",
  outgoing: false,
  role: "Komisaris",
  relation: null,
  pct: null,
  since: 2010,
  until: null,
  other_id: otherId,
  other_name: `Person ${otherId}`,
  other_type: "Person",
  chunk_ids: [`doc_${otherId}:0000`],
  quotes: [`${otherId} serves on the board`],
  ...overrides,
});

const detail = (id: string, edges: EntityEdge[]): EntityDetail => ({
  id,
  name: `Entity ${id}`,
  type: "Company",
  aliases: [],
  chunk_ids: [],
  edges,
});

function stubApi(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    const key = `${url.pathname}${url.search}`;
    const match = Object.keys(routes).find((route) => key === route || url.pathname === route);
    return match === undefined ? json({ detail: "not found" }, 404) : json(routes[match]);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  search.value = "";
});

describe("computeLayout", () => {
  const ids = ["c", "a", "b", "d", "e"];
  const links = [
    { source: "c", target: "a" },
    { source: "c", target: "b" },
    { source: "c", target: "d" },
    { source: "d", target: "e" },
  ];

  it("is deterministic and independent of input order", () => {
    const first = computeLayout(ids, links, "c", 1000, 600);
    expect(computeLayout(ids, links, "c", 1000, 600)).toEqual(first);
    expect(computeLayout([...ids].reverse(), [...links].reverse(), "c", 1000, 600)).toEqual(first);
    for (const point of Object.values(first)) {
      expect(point.x).toBeGreaterThanOrEqual(0);
      expect(point.x).toBeLessThanOrEqual(1000);
      expect(point.y).toBeGreaterThanOrEqual(0);
      expect(point.y).toBeLessThanOrEqual(600);
    }
  });

  it("matches the seeded snapshot within tolerance", () => {
    const layout = computeLayout(ids, links, "c", 1000, 600);
    const expected = { a: [760.1, 106.2], b: [239.9, 469.8], c: [471.7, 235.1], d: [626.2, 441.2], e: [262, 259.8] };
    for (const [id, [x, y]] of Object.entries(expected)) {
      expect(layout[id].x).toBeCloseTo(x, 0);
      expect(layout[id].y).toBeCloseTo(y, 0);
    }
  });
});

describe("buildGraph", () => {
  it("caps canvas neighbours but keeps path nodes and lists everything", () => {
    const edges = Array.from({ length: CANVAS_CAP + 6 }, (_, index) => edge(`p${String(index).padStart(2, "0")}`));
    const path = {
      node_ids: ["c0", "p29"],
      node_names: ["Entity c0", "Person p29"],
      rel_types: ["SERVES_AS"],
      chunk_ids: [],
      hops: [{ src_id: "c0", src_name: "Entity c0", rel_type: "SERVES_AS", dst_id: "p29", dst_name: "Person p29", chunk_ids: [], quotes: [], doc_ids: [], forward: false }],
    };
    const graph = buildGraph(detail("c0", edges), path);
    expect(graph.hidden).toBe(6);
    expect(graph.all).toHaveLength(CANVAS_CAP + 6);
    expect(graph.nodes.map((node) => node.id)).toContain("p29");
    expect(graph.links.find((link) => link.target === "p29")?.onPath).toBe(true);
  });

  it("leaves out a path that does not pass through the centre", () => {
    const path = {
      node_ids: ["x1", "x2"],
      node_names: ["X1", "X2"],
      rel_types: ["FOUNDED"],
      chunk_ids: [],
      hops: [{ src_id: "x1", src_name: "X1", rel_type: "FOUNDED", dst_id: "x2", dst_name: "X2", chunk_ids: [], quotes: [], doc_ids: [], forward: true }],
    };
    const graph = buildGraph(detail("c0", [edge("p1")]), path);
    expect(graph.nodes.map((node) => node.id)).toEqual(["c0", "p1"]);
    expect(graph.links.every((link) => !link.onPath)).toBe(true);
  });
});

describe("ExploreView", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      disconnect() {}
    });
  });

  it("renders a more-indicator when the neighbourhood is capped", async () => {
    search.value = "e=c0";
    const edges = Array.from({ length: CANVAS_CAP + 6 }, (_, index) => edge(`p${String(index).padStart(2, "0")}`));
    stubApi({ "/graph/entity/c0": detail("c0", edges) });
    render(<ExploreView />);
    const more = await screen.findByRole("button", { name: /\+6 more/ });
    fireEvent.click(more);
    expect(await screen.findByRole("heading", { name: /30 connected entities/ })).toBeInTheDocument();
  });

  it("shows the no-path state when the API finds none", async () => {
    search.value = "from=a&to=b";
    stubApi({ "/graph/path": null, "/graph/entity/a": detail("a", []), "/graph/entity/b": detail("b", []) });
    render(<ExploreView />);
    expect(await screen.findByText("No path within 4 hops between Entity a and Entity b.")).toBeInTheDocument();
  });

  it("keeps a found path when an entity lookup fails, naming nodes from the hops", async () => {
    search.value = "from=a&to=b";
    const hop = { src_id: "a", src_name: "Alpha", rel_type: "OWNS", dst_id: "b", dst_name: "Beta", chunk_ids: [], quotes: [], doc_ids: [], forward: true };
    stubApi({
      "/graph/path": { node_ids: ["a", "b"], node_names: ["Alpha", "Beta"], rel_types: ["OWNS"], chunk_ids: [], hops: [hop] },
      "/graph/entity/a": detail("a", []),
    });
    render(<ExploreView />);
    expect(await screen.findByText(/Graph path · 1 hop/)).toBeInTheDocument();
    expect(screen.getAllByText("Beta").length).toBeGreaterThan(0);
  });

  it("shows the centre's name in the Neighbourhood search after re-centring", async () => {
    search.value = "e=c0";
    stubApi({ "/graph/entity/c0": detail("c0", []) });
    render(<ExploreView />);
    await waitFor(() => expect(screen.getByLabelText("Entity")).toHaveValue("Entity c0"));
  });

  it("opens a side panel with the quotes when an edge is clicked", async () => {
    search.value = "e=c0";
    stubApi({ "/graph/entity/c0": detail("c0", [edge("p1", { quotes: ["Budi menjabat Komisaris sejak 2010"], chunk_ids: ["doc_001:0002"] })]) });
    render(<ExploreView />);
    const edgeButton = await screen.findByRole("button", { name: /serves as.*Show evidence/ });
    expect(edgeButton).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(edgeButton);
    expect(edgeButton).toHaveAttribute("aria-expanded", "true");
    expect(edgeButton).toHaveAttribute("aria-controls", "edge-panel");
    const panel = screen.getByRole("region", { name: /Person p1/ });
    expect(within(panel).getByText("Budi menjabat Komisaris sejak 2010")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "doc_001:0002" })).toBeInTheDocument();
    expect(within(panel).getByText("Komisaris")).toBeInTheDocument();
  });

  it("opens the best-connected entity when the URL names none, without writing e", async () => {
    window.history.replaceState(null, "", "/?q=Who");
    stubApi({
      "/graph/stats": { nodes: 2, relationships: 1, by_type: {}, top: [{ id: "c0", name: "Entity c0", type: "Company", degree: 1 }] },
      "/graph/entity/c0": detail("c0", [edge("p1")]),
    });
    render(<ExploreView />);
    expect(await screen.findByRole("button", { name: /serves as.*Show evidence/ })).toBeInTheDocument();
    expect(window.location.search).toBe("?q=Who");
    window.history.replaceState(null, "", "/");
  });

  it("keeps the search hint when stats fail", async () => {
    const fetchMock = stubApi({});
    render(<ExploreView />);
    await act(async () => {});
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/graph/stats", expect.anything());
    expect(screen.getByText(/Search for a company, person or group/)).toBeInTheDocument();
  });

  it("writes only its own keys, keeping Ask's q and modes", async () => {
    window.history.replaceState(null, "", "/?q=Who&modes=rag&from=stale#ask");
    search.value = "e=c0";
    stubApi({ "/graph/entity/c0": detail("c0", []) });
    render(<ExploreView />);
    await screen.findAllByText("Entity c0");
    const url = new URL(window.location.href);
    expect(url.searchParams.get("e")).toBe("c0");
    expect(url.searchParams.get("q")).toBe("Who");
    expect(url.searchParams.get("modes")).toBe("rag");
    expect(url.searchParams.has("from")).toBe(false);
    expect(url.hash).toBe("#ask");
    window.history.replaceState(null, "", "/");
  });
});

describe("EntitySearch", () => {
  it("debounces, then selects with the keyboard through aria-activedescendant", async () => {
    vi.useFakeTimers();
    const rows: EntitySearchResult[] = [
      { id: "c1", name: "Nusantara Mulia", type: "Company", aliases: [], match: "prefix" },
      { id: "c2", name: "PT Bintang Kreasi Tbk", type: "Company", aliases: ["BKMC"], match: "exact" },
    ];
    const fetchMock = stubApi({ "/graph/search": rows });
    const onPick = vi.fn();
    render(<EntitySearch id="s" label="Entity" placeholder="Search" onPick={onPick} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "bk" } });
    fireEvent.change(input, { target: { value: "bkm" } });
    expect(fetchMock).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("listbox")).toBeVisible();
    expect(screen.getByText("alias · BKMC")).toBeInTheDocument();
    expect(input).toHaveAttribute("aria-activedescendant", "s-option-0");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input).toHaveAttribute("aria-activedescendant", "s-option-1");
    expect(screen.getByRole("option", { name: /Bintang/ })).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onPick).toHaveBeenCalledWith(rows[1]);
    expect(input).toHaveValue("PT Bintang Kreasi Tbk");
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("announces no matches in a status region and never picks a stale row", async () => {
    vi.useFakeTimers();
    const rows: EntitySearchResult[] = [{ id: "c1", name: "Nusantara Mulia", type: "Company", aliases: [], match: "prefix" }];
    let found: EntitySearchResult[] = rows;
    vi.stubGlobal("fetch", vi.fn(async () => json(found)));
    const onPick = vi.fn();
    render(<EntitySearch id="s" label="Entity" placeholder="Search" onPick={onPick} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "nus" } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
    });
    expect(screen.getByRole("option", { name: /Nusantara/ })).toBeInTheDocument();
    found = [];
    fireEvent.change(input, { target: { value: "nusx" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onPick).not.toHaveBeenCalled();
    expect(input).not.toHaveAttribute("aria-activedescendant");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
    });
    expect(screen.getByRole("status")).toHaveTextContent("No entity matches “nusx”.");
    expect(within(screen.getByRole("listbox", { hidden: true })).queryByText(/No entity/)).toBeNull();
  });
});
