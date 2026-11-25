import re
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel

from nexus.graph.neo4j_store import GraphPath
from nexus.retrieval.modes import MODES, Mode
from nexus.retrieval.prompts import CITATION_PATTERN, Lang, is_abstain
from nexus.retrieval.verify import Claim
from nexus.vector.milvus_store import Hit

if TYPE_CHECKING:
    from nexus.retrieval.orchestrator import Deps

WORD_PATTERN = re.compile(r"[a-z]+")
INDONESIAN_MARKERS = frozenset(
    [
        "yang", "dan", "di", "ke", "dari", "adalah", "pada", "untuk", "dengan", "dalam",
        "ini", "itu", "oleh", "tahun", "mana", "dimiliki", "persen", "saham",
    ]
)  # fmt: skip
ENGLISH_MARKERS = frozenset(
    ["who", "what", "which", "how", "when", "where", "the", "of", "is", "are", "did", "does",
     "was", "in", "and"]
)  # fmt: skip
# A leading interrogative decides the language outright.
INDONESIAN_INTERROGATIVES = frozenset(
    ["siapa", "siapakah", "apa", "apakah", "berapa", "kapan", "bagaimana", "dimana", "mengapa",
     "kenapa", "di"]
)  # fmt: skip
ANSWER_MAX_TOKENS = 1024


class Answer(BaseModel):
    text: str
    citations: list[str]
    invalid_citations: list[str]
    hits: list[Hit]
    abstained: bool
    mode: Mode
    latency_ms: int
    claims: list[Claim] = []
    graph_paths: list[GraphPath] = []
    communities: list[str] = []
    routed_mode: Mode | None = None
    llm_calls: int = 0
    verify_ms: int = 0
    verify_calls: int = 0


def detect_lang(text: str) -> Lang:
    words = WORD_PATTERN.findall(text.lower())
    if not words:
        return "en"
    first = words[0]
    if first in ENGLISH_MARKERS:
        return "en"
    if first in INDONESIAN_INTERROGATIVES and (first != "di" or words[1:2] == ["mana"]):
        return "id"
    score = sum(word in INDONESIAN_MARKERS for word in words) - sum(
        word in ENGLISH_MARKERS for word in words
    )
    return "id" if score > 0 else "en"


def _split_citations(text: str, hits: list[Hit]) -> tuple[list[str], list[str]]:
    known = {hit.chunk_id for hit in hits}
    found = list(dict.fromkeys(CITATION_PATTERN.findall(text)))
    return [cid for cid in found if cid in known], [cid for cid in found if cid not in known]


def answer(question: str, mode: Mode, tenant: str, *, deps: "Deps", verify: bool = True) -> Answer:
    # Imported here: the orchestrator imports this module for detect_lang.
    from nexus.retrieval.orchestrator import build_graph

    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode!r}")
    started = time.perf_counter()
    state = build_graph(deps).invoke(
        {
            "question": question,
            "tenant": tenant,
            "mode": mode,
            "routed_mode": None,
            "hits": [],
            "graph_paths": [],
            "communities": [],
            "text": "",
            "claims": [],
            "llm_calls": 0,
            "verify_calls": 0,
            "verify_ms": 0,
            "run_verify": verify,
        }
    )
    text, hits = state["text"], state["hits"]
    abstained = is_abstain(text)
    citations, invalid = ([], []) if abstained else _split_citations(text, hits)
    return Answer(
        text=text,
        citations=citations,
        invalid_citations=invalid,
        hits=hits,
        abstained=abstained,
        mode=mode,
        latency_ms=round((time.perf_counter() - started) * 1000) - state["verify_ms"],
        claims=state["claims"],
        graph_paths=state["graph_paths"],
        communities=state["communities"],
        routed_mode=state["routed_mode"],
        llm_calls=state["llm_calls"],
        verify_ms=state["verify_ms"],
        verify_calls=state["verify_calls"],
    )
