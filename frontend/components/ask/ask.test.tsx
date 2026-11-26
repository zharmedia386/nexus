import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnswerText, VERDICT_STYLES } from "@/components/ask/answer-text";
import { AskView } from "@/components/ask/ask-view";
import { EvidenceDrawer } from "@/components/ask/evidence-drawer";
import { PathStrip } from "@/components/ask/path-strip";
import type { Answer, GraphPath } from "@/lib/types";

const search = vi.hoisted(() => ({ value: "" }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search.value) }));

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const hit = (chunkId: string) => ({ chunk_id: chunkId, doc_id: chunkId.split(":")[0], text: "", score: 1 });

function makeAnswer(overrides: Partial<Answer> = {}): Answer {
  return {
    text: "",
    citations: [],
    invalid_citations: [],
    hits: [],
    abstained: false,
    mode: "hybrid",
    latency_ms: 1200,
    claims: [],
    graph_paths: [],
    communities: [],
    routed_mode: null,
    llm_calls: 2,
    verify_ms: 300,
    verify_calls: 1,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  search.value = "";
});

describe("AskView compare", () => {
  it("shows a per-mode error without blanking the other mode", async () => {
    search.value = "q=Who+owns+X%3F&modes=hybrid,graph_local";
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
      expect(url).toBe("http://localhost:8000/query");
      const { mode } = JSON.parse(String(init.body)) as { mode: string };
      if (mode === "graph_local") return jsonResponse({ detail: "neo4j down" }, 503);
      return jsonResponse(makeAnswer({ text: "Hybrid says PT Alpha." }));
    }));

    render(<AskView />);

    const hybrid = await screen.findByRole("article", { name: "Hybrid" });
    const graph = screen.getByRole("article", { name: "Graph local" });
    await within(hybrid).findByText("Hybrid says PT Alpha.");
    expect(await within(graph).findByRole("alert")).toHaveTextContent("503 · neo4j down");
    expect(within(hybrid).queryByRole("alert")).toBeNull();
  });
});

describe("AnswerText verdicts", () => {
  it("renders an unknown citation (not in hits) as an unverified chip", () => {
    const answer = makeAnswer({
      text: "PT Alpha owns Beta [doc_999:0001].",
      claims: [{ text: "PT Alpha owns Beta.", chunk_ids: ["doc_999:0001"], supported: true }],
    });
    render(<AnswerText answer={answer} onCite={() => {}} />);

    const chip = screen.getByRole("button", { name: /doc_999:0001/ });
    expect(chip).toHaveAttribute("data-verdict", "unverified");
  });

  it("maps supported / unsupported / null claim verdicts to chip colours", () => {
    const onCite = vi.fn();
    const answer = makeAnswer({
      text: "Ani founded Alpha [doc_001:0000]. Budi runs Beta [doc_002:0000]. Citra chairs Gamma [doc_003:0000].",
      hits: [hit("doc_001:0000"), hit("doc_002:0000"), hit("doc_003:0000")],
      claims: [
        { text: "Ani founded Alpha.", chunk_ids: ["doc_001:0000"], supported: true },
        { text: "Budi runs Beta.", chunk_ids: ["doc_002:0000"], supported: false },
        { text: "Citra chairs Gamma.", chunk_ids: ["doc_003:0000"], supported: null },
      ],
    });
    render(<AnswerText answer={answer} onCite={onCite} />);

    const cases = [
      ["doc_001:0000", "supported"],
      ["doc_002:0000", "unsupported"],
      ["doc_003:0000", "unverified"],
    ] as const;
    for (const [chunkId, verdict] of cases) {
      const chip = screen.getByRole("button", { name: new RegExp(chunkId) });
      expect(chip).toHaveAttribute("data-verdict", verdict);
      for (const className of VERDICT_STYLES[verdict].split(" ")) expect(chip).toHaveClass(className);
    }
    fireEvent.click(screen.getByRole("button", { name: /doc_002:0000/ }));
    expect(onCite).toHaveBeenCalledWith("doc_002:0000", expect.any(HTMLButtonElement));
  });

  it("does not let a short sentence borrow a longer claim's verdict", () => {
    const answer = makeAnswer({
      text: "Yes [doc_001:0000].",
      hits: [hit("doc_001:0000")],
      claims: [{ text: "Yes, Ani founded Alpha and still holds a 46% stake in it.", chunk_ids: ["doc_001:0000"], supported: true }],
    });
    render(<AnswerText answer={answer} onCite={() => {}} />);

    expect(screen.getByRole("button", { name: /doc_001:0000/ })).toHaveAttribute("data-verdict", "unverified");
  });

  it("attributes a trailing citation-only sentence to the sentence before it", () => {
    const answer = makeAnswer({
      text: "Ani founded **Alpha**. [doc_001:0000]",
      hits: [hit("doc_001:0000")],
      claims: [{ text: "Ani founded Alpha.", chunk_ids: ["doc_001:0000"], supported: false }],
    });
    render(<AnswerText answer={answer} onCite={() => {}} />);

    expect(screen.getByRole("button", { name: /doc_001:0000/ })).toHaveAttribute("data-verdict", "unsupported");
    expect(screen.getByText("Alpha").tagName).toBe("STRONG");
  });
});

describe("AnswerText lists", () => {
  it("keeps the source numbering when paragraphs split an ordered list", () => {
    const answer = makeAnswer({
      text: "Based on the documents provided:\n\n1.  **Step one:**\n    First fact.\n\n2.  **Step two:**\n    Second fact.\n\n3.  **Step three:**\n    Third fact.",
    });
    const { container } = render(<AnswerText answer={answer} onCite={() => {}} />);
    const lists = [...container.querySelectorAll("ol")];
    expect(lists).toHaveLength(3);
    expect(lists.map((list) => list.start)).toEqual([1, 2, 3]);
  });
});

describe("EvidenceDrawer", () => {
  it("highlights exactly [start_char, end_char) of the document and closes on Escape", async () => {
    const content = "Intro line. Prasetya Utama menjabat sebagai Direktur Keuangan. Outro.";
    const start = content.indexOf("Prasetya");
    const end = content.indexOf(" Outro");
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("/chunks/")) {
        return jsonResponse({ id: "doc_063:0001", doc_id: "doc_063", ordinal: 1, start_char: start, end_char: end, text: "" });
      }
      return jsonResponse({ id: "doc_063", title: "Laporan Tahunan 2024", doc_type: "annual_report", lang: "id", year: 2024, content, sha256: "", status: "ingested", error: null });
    }));
    const onClose = vi.fn();

    render(<EvidenceDrawer chunkId="doc_063:0001" opener={null} onClose={onClose} />);

    const title = await screen.findByRole("heading", { name: "Laporan Tahunan 2024" });
    const mark = document.querySelector("mark");
    expect(mark?.textContent).toBe(content.slice(start, end));
    expect(mark?.parentElement?.textContent).toBe(content);
    expect(screen.getByRole("button", { name: "Close evidence" })).toHaveFocus();

    fireEvent.keyDown(title, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});

describe("EvidenceDrawer offsets and focus", () => {
  it("treats backend offsets as code points and returns focus to the opener", async () => {
    // Python offsets count the emoji as 1 char; UTF-16 counts it as 2.
    const content = "🏢 Kantor pusat. PT Alpha dipimpin Ani. Akhir.";
    const points = Array.from(content);
    const start = points.indexOf("P");
    const end = start + "PT Alpha dipimpin Ani.".length;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("/chunks/")) {
        return jsonResponse({ id: "doc_001:0000", doc_id: "doc_001", ordinal: 0, start_char: start, end_char: end, text: "" });
      }
      return jsonResponse({ id: "doc_001", title: "Profil", doc_type: "news", lang: "id", year: 2024, content, sha256: "", status: "ingested", error: null });
    }));
    const opener = document.createElement("button");
    document.body.append(opener);

    const { unmount } = render(<EvidenceDrawer chunkId="doc_001:0000" opener={opener} onClose={() => {}} />);

    await screen.findByRole("heading", { name: "Profil" });
    expect(document.querySelector("mark")?.textContent).toBe("PT Alpha dipimpin Ani.");
    unmount();
    expect(opener).toHaveFocus();
    opener.remove();
  });
});

describe("AskView races and timeouts", () => {
  it("ignores a late response from a superseded question", async () => {
    search.value = "q=First+question&modes=hybrid";
    let releaseFirst: (response: Response) => void = () => {};
    vi.stubGlobal("fetch", vi.fn((_url: string, init: RequestInit) => {
      const { question } = JSON.parse(String(init.body)) as { question: string };
      if (question === "First question") {
        // Deliberately ignores the abort signal, like a slow proxy would.
        return new Promise<Response>((resolve) => { releaseFirst = resolve; });
      }
      return Promise.resolve(jsonResponse(makeAnswer({ text: "Second answer." })));
    }));

    render(<AskView />);
    fireEvent.click(screen.getByRole("button", { name: /Single hop/ }));
    await screen.findByText("Second answer.");

    await act(async () => releaseFirst(jsonResponse(makeAnswer({ text: "Stale first answer." }))));
    expect(screen.queryByText("Stale first answer.")).toBeNull();
    expect(screen.getByText("Second answer.")).toBeInTheDocument();
  });

  it("times out a mode after 120 s and offers a retry", async () => {
    vi.useFakeTimers();
    search.value = "q=Slow&modes=graph_local";
    vi.stubGlobal("fetch", vi.fn((_url: string, init: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      }),
    ));

    render(<AskView />);
    await act(async () => vi.advanceTimersByTime(120_000));
    vi.useRealTimers();

    expect(screen.getByRole("alert")).toHaveTextContent("Timed out after 120 s");
    expect(screen.getByRole("button", { name: "Run again" })).toBeInTheDocument();
  });
});

describe("PathStrip", () => {
  it("points each hop arrow along its stored edge direction", () => {
    const path: GraphPath = {
      node_ids: ["a", "b", "c"],
      node_names: ["Nusantara Mulia", "Prasetya Utama", "PT Bintang Kreasi Tbk"],
      rel_types: ["FOUNDED", "SERVES_AS"],
      chunk_ids: [],
      hops: [
        { src_id: "a", src_name: "Nusantara Mulia", rel_type: "FOUNDED", dst_id: "b", dst_name: "Prasetya Utama", chunk_ids: ["doc_078:0000"], quotes: ["Prasetya Utama yang mendirikan entitas ini"], doc_ids: ["doc_078"], forward: false },
        { src_id: "b", src_name: "Prasetya Utama", rel_type: "SERVES_AS", dst_id: "c", dst_name: "PT Bintang Kreasi Tbk", chunk_ids: [], quotes: [], doc_ids: [], forward: true },
      ],
    };
    const onCite = vi.fn();
    const { container } = render(<PathStrip path={path} onCite={onCite} />);

    const directions = [...container.querySelectorAll("[data-direction]")].map((node) => node.getAttribute("data-direction"));
    expect(directions).toEqual(["backward", "forward"]);

    const founded = screen.getByRole("button", { name: /Prasetya Utama founded Nusantara Mulia/ });
    fireEvent.click(founded);
    expect(founded).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: "doc_078:0000" }));
    expect(onCite).toHaveBeenCalledWith("doc_078:0000", expect.any(HTMLButtonElement));
  });
});

describe("PathStrip leftover chunks", () => {
  it("renders chunk ids beyond the quotes as chips", () => {
    const hop = { src_id: "a", src_name: "A", rel_type: "OWNS", dst_id: "b", dst_name: "B", chunk_ids: ["d1:0", "d2:0", "d3:0"], quotes: ["one quote"], doc_ids: [], forward: true };
    const onCite = vi.fn();
    render(<PathStrip path={{ node_ids: ["a", "b"], node_names: ["A", "B"], rel_types: ["OWNS"], chunk_ids: [], hops: [hop] }} onCite={onCite} />);
    fireEvent.click(screen.getByRole("button", { name: /A owns B/ }));
    expect(screen.getByRole("button", { name: "d1:0" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "d3:0" }));
    expect(onCite).toHaveBeenCalledWith("d3:0", expect.any(HTMLButtonElement));
    expect(screen.queryByText(/No quotes stored/)).toBeNull();
  });
});

describe("AskView URL state", () => {
  it("writes q and modes without dropping Explore's params", async () => {
    window.history.replaceState(null, "", "/ask?e=c0&from=a");
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(makeAnswer({ text: "ok" }))));
    render(<AskView />);

    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Who owns X?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    const url = new URL(window.location.href);
    expect(url.searchParams.get("q")).toBe("Who owns X?");
    expect(url.searchParams.get("modes")).toBe("hybrid,graph_local");
    expect(url.searchParams.get("e")).toBe("c0");
    expect(url.searchParams.get("from")).toBe("a");
    expect(url.pathname).toBe("/ask");
    window.history.replaceState(null, "", "/");
  });

  it("does not run a query without ?q=", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<AskView />);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
