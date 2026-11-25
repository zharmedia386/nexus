from contextlib import nullcontext

import pytest

from nexus.graph.neo4j_store import GraphPath
from nexus.llm import GatewayError
from nexus.retrieval import orchestrator
from nexus.retrieval.answer import ANSWER_MAX_TOKENS, answer, detect_lang
from nexus.retrieval.modes import retrieve
from nexus.retrieval.orchestrator import Deps, RouteChoice, classify
from nexus.retrieval.prompts import build_messages
from nexus.retrieval.verify import Verdict, Verdicts
from nexus.vector.milvus_store import Hit

HITS = [
    Hit("doc_a:0001", "doc_a", "PT Maju Jaya didirikan oleh Budi.", 0.9),
    Hit("doc_b:0002", "doc_b", "Budi menjabat Direktur Utama PT Sinar.", 0.8),
]
REPLY = "Budi mendirikan PT Maju Jaya [doc_a:0001]. Ia memimpin PT Sinar [doc_b:0002]."
PATH = GraphPath(["e1", "e2"], ["Budi", "PT Maju Jaya"], ["FOUNDED"], ["doc_a:0001"])


class FakeStore:
    def dense_search(self, tenant, vector, k):
        return HITS

    def hybrid_search(self, tenant, query_text, vector, k):
        return HITS


class FakeChatText:
    def __init__(self, reply: str = REPLY) -> None:
        self.reply = reply
        self.calls: list[tuple[list[dict], dict]] = []

    def __call__(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.reply


class FakeChatJson:
    def __init__(self, route: str = "graph_local") -> None:
        self.route = route
        self.calls: list[tuple[list[dict], type]] = []

    def __call__(self, messages, schema, **kwargs):
        self.calls.append((messages, schema))
        if schema is RouteChoice:
            return RouteChoice(route=self.route)
        if schema is Verdicts:
            return Verdicts(items=[Verdict(index=0, supported=True)])
        raise AssertionError(f"unexpected schema {schema}")

    def schemas(self) -> list[type]:
        return [schema for _, schema in self.calls]


def embedder(texts):
    return [[0.0] for _ in texts]


def reranker(query, docs, top_n):
    return [(index, 0.9) for index in range(len(docs))][:top_n]


def make_deps(chat_json=None, chat_text=None) -> Deps:
    return Deps(
        store=FakeStore(),
        community_store=FakeStore(),
        graph=object(),
        connect=lambda: nullcontext(None),
        embedder=embedder,
        reranker=reranker,
        chat_text=chat_text or FakeChatText(),
        chat_json=chat_json or FakeChatJson(),
    )


@pytest.fixture
def graph_modes(monkeypatch):
    def fake_local(question, tenant, *, store, graph, conn, embedder, reranker, llm):
        return HITS, [PATH], 2

    def fake_global(question, tenant, *, community_store, conn, embedder, reranker, llm):
        return HITS[:1], 3, ["c1"]

    monkeypatch.setattr(orchestrator, "retrieve_graph_local", fake_local)
    monkeypatch.setattr(orchestrator, "retrieve_graph_global", fake_global)


def test_forced_mode_skips_classify():
    chat_json = FakeChatJson()
    result = answer("Siapa pendiri PT Maju Jaya?", "hybrid", "demo", deps=make_deps(chat_json))
    assert RouteChoice not in chat_json.schemas()
    assert result.routed_mode is None
    assert result.mode == "hybrid"


def test_auto_routes_relationship_question_to_graph_local(graph_modes):
    chat_json = FakeChatJson("graph_local")
    question = "How is Budi linked to PT Sinar?"
    result = answer(question, "auto", "demo", deps=make_deps(chat_json))
    assert result.mode == "auto"
    assert result.routed_mode == "graph_local"
    assert result.graph_paths == [PATH]
    messages, schema = chat_json.calls[0]
    assert schema is RouteChoice
    assert messages[-1]["content"] == question
    assert "graph_local" in messages[0]["content"]


def test_classify_falls_back_to_hybrid_on_gateway_error():
    def boom(*args, **kwargs):
        raise GatewayError("down")

    assert classify("q", boom) == "hybrid"


@pytest.mark.parametrize("mode", ["rag", "hybrid"])
def test_rag_and_hybrid_answers_unchanged(mode):
    question = "Siapa pendiri PT Maju Jaya?"
    hits = retrieve(question, mode, "demo", store=FakeStore(), embedder=embedder, reranker=reranker)
    expected = build_messages(question, [(h.chunk_id, h.text) for h in hits], detect_lang(question))
    chat_text = FakeChatText()
    result = answer(question, mode, "demo", deps=make_deps(chat_text=chat_text), verify=False)
    assert chat_text.calls == [(expected, {"temperature": 0.0, "max_tokens": ANSWER_MAX_TOKENS})]
    assert result.text == REPLY
    assert result.citations == ["doc_a:0001", "doc_b:0002"]
    assert result.hits == hits
    assert result.llm_calls == 1
    assert (result.verify_calls, result.verify_ms) == (0, 0)


def test_llm_calls_counted(graph_modes):
    chat_json = FakeChatJson("graph_global")
    result = answer("What patterns dominate?", "auto", "demo", deps=make_deps(chat_json))
    assert result.routed_mode == "graph_global"
    assert result.communities == ["c1"]
    # classify 1 + map 3 + generate 1; verification is reported separately
    assert result.llm_calls == 5
    assert result.verify_calls == 1
    assert result.verify_ms >= 0 and result.latency_ms >= 0
    assert chat_json.schemas() == [RouteChoice, Verdicts]
    # Only doc_a:0001 is in the graph_global hits, so the second claim is unsupported unchecked.
    assert [claim.supported for claim in result.claims] == [True, False]


def test_no_hits_abstains_without_llm(monkeypatch):
    monkeypatch.setattr(orchestrator, "retrieve", lambda *args, **kwargs: [])
    chat_json, chat_text = FakeChatJson(), FakeChatText()
    result = answer("Siapa pendiri?", "rag", "demo", deps=make_deps(chat_json, chat_text))
    assert result.abstained
    assert result.llm_calls == 0
    assert chat_text.calls == [] and chat_json.calls == []


def test_verify_false_skips_verifier():
    chat_json = FakeChatJson()
    result = answer("Siapa pendiri?", "hybrid", "demo", deps=make_deps(chat_json), verify=False)
    assert chat_json.calls == []
    assert result.claims == []
    assert result.llm_calls == 1
    assert (result.verify_calls, result.verify_ms) == (0, 0)


def test_graph_compiled_once_per_deps(monkeypatch):
    builds: list[int] = []
    real_state_graph = orchestrator.StateGraph

    class CountingStateGraph(real_state_graph):
        def compile(self, *args, **kwargs):
            builds.append(1)
            return super().compile(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "StateGraph", CountingStateGraph)
    deps = make_deps()
    for _ in range(2):
        answer("Siapa pendiri?", "hybrid", "demo", deps=deps, verify=False)
    assert len(builds) == 1


def test_auto_graph_global_populates_communities(graph_modes):
    result = answer(
        "What patterns dominate?",
        "auto",
        "demo",
        deps=make_deps(FakeChatJson("graph_global")),
        verify=False,
    )
    assert result.communities == ["c1"] and result.graph_paths == []
