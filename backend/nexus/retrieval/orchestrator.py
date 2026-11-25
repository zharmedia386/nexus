import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Literal, TypedDict

import psycopg
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from nexus.config import get_settings
from nexus.db import repo
from nexus.graph.neo4j_store import GraphPath, GraphStore
from nexus.llm import GatewayError, chat_json, chat_text, embed, rerank
from nexus.retrieval.answer import ANSWER_MAX_TOKENS, detect_lang
from nexus.retrieval.graph_global import retrieve_graph_global
from nexus.retrieval.graph_local import retrieve_graph_local
from nexus.retrieval.modes import Mode, Reranker, retrieve
from nexus.retrieval.prompts import ABSTAIN, build_messages
from nexus.retrieval.verify import Claim, split_claims, verify_claims
from nexus.vector.milvus_store import ChunkStore, Hit

Route = Literal["hybrid", "graph_local", "graph_global"]
CLASSIFY_TIMEOUT = 60
CLASSIFY_SYSTEM = (
    "You route a question about Indonesian companies, people and groups to a retrieval "
    "strategy. Answer with route:\n"
    "- hybrid: lookup of a single fact (who holds a role, a date, an amount, where a "
    "company is).\n"
    "- graph_local: relationships between named entities: connections, ownership or "
    "control chains, 'how is X linked to Y', multi-step who-owns-whom questions.\n"
    "- graph_global: themes or an overview across many entities: 'what patterns', "
    "'which groups dominate', broad summaries."
)


class RouteChoice(BaseModel):
    route: Route


@dataclass
class Deps:
    store: ChunkStore
    community_store: ChunkStore | None = None
    graph: GraphStore | None = None
    connect: Callable[[], AbstractContextManager[psycopg.Connection]] = repo.connect
    embedder: Callable[[list[str]], list[list[float]]] = embed
    reranker: Reranker = rerank
    chat_text: Callable[..., str] = chat_text
    chat_json: Callable[..., BaseModel] = chat_json
    compiled: CompiledStateGraph | None = field(default=None, init=False, repr=False)


def default_deps() -> Deps:
    settings = get_settings()
    stores = [ChunkStore(settings.collection(name)) for name in ("chunks", "communities")]
    for store in stores:
        store.ensure()
    # GraphStore opens its Neo4j driver lazily, on the first graph query.
    return Deps(store=stores[0], community_store=stores[1], graph=GraphStore())


class QueryState(TypedDict):
    question: str
    tenant: str
    mode: Mode
    routed_mode: Route | None
    hits: list[Hit]
    graph_paths: list[GraphPath]
    communities: list[str]
    text: str
    claims: list[Claim]
    llm_calls: int
    verify_calls: int
    verify_ms: int
    run_verify: bool


def classify(question: str, llm: Callable[..., BaseModel] = chat_json) -> Route:
    messages = [
        {"role": "system", "content": CLASSIFY_SYSTEM},
        {"role": "user", "content": question},
    ]
    try:
        choice = llm(messages, RouteChoice, temperature=0.0, timeout=CLASSIFY_TIMEOUT)
    except GatewayError:
        return "hybrid"
    return choice.route


def build_graph(deps: Deps) -> CompiledStateGraph:
    if deps.compiled is None:
        deps.compiled = _compile(deps)
    return deps.compiled


def _compile(deps: Deps) -> CompiledStateGraph:
    def classify_node(state: QueryState) -> dict:
        if state["mode"] != "auto":
            return {}
        return {
            "routed_mode": classify(state["question"], deps.chat_json),
            "llm_calls": state["llm_calls"] + 1,
        }

    def retrieve_node(state: QueryState) -> dict:
        mode = state["routed_mode"] or state["mode"]
        question, tenant = state["question"], state["tenant"]
        if mode == "graph_local":
            if deps.graph is None:
                raise ValueError("graph_local needs a graph store")
            with deps.connect() as conn:
                hits, paths, calls = retrieve_graph_local(
                    question,
                    tenant,
                    store=deps.store,
                    graph=deps.graph,
                    conn=conn,
                    embedder=deps.embedder,
                    reranker=deps.reranker,
                    llm=deps.chat_json,
                )
            return {"hits": hits, "graph_paths": paths, "llm_calls": state["llm_calls"] + calls}
        if mode == "graph_global":
            if deps.community_store is None:
                raise ValueError("graph_global needs a community store")
            with deps.connect() as conn:
                hits, calls, communities = retrieve_graph_global(
                    question,
                    tenant,
                    community_store=deps.community_store,
                    conn=conn,
                    embedder=deps.embedder,
                    reranker=deps.reranker,
                    llm=deps.chat_json,
                )
            return {
                "hits": hits,
                "communities": communities,
                "llm_calls": state["llm_calls"] + calls,
            }
        hits = retrieve(
            question, mode, tenant, store=deps.store, embedder=deps.embedder, reranker=deps.reranker
        )
        return {"hits": hits}

    def generate_node(state: QueryState) -> dict:
        lang = detect_lang(state["question"])
        hits = state["hits"]
        if not hits:
            return {"text": ABSTAIN[lang]}
        messages = build_messages(
            state["question"], [(hit.chunk_id, hit.text) for hit in hits], lang
        )
        text = deps.chat_text(messages, temperature=0.0, max_tokens=ANSWER_MAX_TOKENS).strip()
        return {"text": text, "llm_calls": state["llm_calls"] + 1}

    def verify_node(state: QueryState) -> dict:
        if not state["run_verify"]:
            return {}
        started = time.perf_counter()
        claims = split_claims(state["text"])
        chunk_text = {hit.chunk_id: hit.text for hit in state["hits"]}
        verified, calls = verify_claims(claims, chunk_text, llm=deps.chat_json)
        return {
            "claims": verified,
            "verify_calls": calls,
            "verify_ms": round((time.perf_counter() - started) * 1000),
        }

    builder = StateGraph(QueryState)
    builder.add_node("classify", classify_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)
    builder.add_node("verify", verify_node)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", "verify")
    builder.add_edge("verify", END)
    return builder.compile()
