import pytest

from nexus.retrieval.answer import answer, detect_lang
from nexus.retrieval.orchestrator import Deps
from nexus.retrieval.prompts import ABSTAIN_EN, ABSTAIN_ID
from nexus.vector.milvus_store import Hit

HIT = Hit("doc_a:0001", "doc_a", "PT Maju Jaya didirikan oleh Budi.", 0.9)


class FakeStore:
    def __init__(self, hits: list[Hit]) -> None:
        self.hits = hits

    def dense_search(self, tenant, vector, k):
        return self.hits

    def hybrid_search(self, tenant, query_text, vector, k):
        return self.hits


class FakeLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[list[dict], dict]] = []

    def __call__(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.reply


def run(question, reply, hits=(HIT,), mode="rag"):
    llm = FakeLLM(reply)
    result = answer(
        question,
        mode,
        "demo",
        deps=Deps(
            store=FakeStore(list(hits)),
            embedder=lambda texts: [[0.0] for _ in texts],
            reranker=lambda query, docs, top_n: [(i, 0.9) for i in range(len(docs))][:top_n],
            chat_text=llm,
        ),
        verify=False,
    )
    return result, llm


def test_detect_lang():
    assert detect_lang("Siapa yang mendirikan PT Maju Jaya dan di mana kantornya?") == "id"
    assert detect_lang("Who founded Maju Jaya and where is its office?") == "en"
    assert detect_lang("") == "en"
    assert detect_lang("Siapa Direktur Utama PT Sinar Jaya Tbk?") == "id"
    assert detect_lang("Who is the Komisaris Utama of PT Bumi Sentosa Tbk?") == "en"
    assert detect_lang("Berapa persen saham PT X Tbk yang dimiliki PT Y?") == "id"
    assert detect_lang("Which companies does Budi Santoso serve as Komisaris?") == "en"
    assert detect_lang("Apakah PT A bermitra dengan PT B?") == "id"
    assert detect_lang("Di mana kantor pusat PT Maju?") == "id"


def test_abstains_without_llm_when_no_hits():
    result, llm = run("Siapa pendiri PT Maju Jaya?", "x", hits=())
    assert result.abstained
    assert result.text == ABSTAIN_ID
    assert result.citations == []
    assert llm.calls == []
    result, _ = run("Who founded Maju Jaya?", "x", hits=())
    assert result.text == ABSTAIN_EN


def test_parses_citations_and_flags_invalid():
    reply = "Budi pendirinya [doc_a:0001]. Ia lahir 1970 [doc_z:0009] [doc_a:0001]."
    result, llm = run("Siapa pendiri PT Maju Jaya?", reply)
    assert result.citations == ["doc_a:0001"]
    assert result.invalid_citations == ["doc_z:0009"]
    assert not result.abstained
    messages, kwargs = llm.calls[0]
    assert kwargs["temperature"] == 0.0
    assert "[doc_a:0001] PT Maju Jaya" in messages[1]["content"]
    assert ABSTAIN_ID in messages[0]["content"]


def test_detects_model_abstain_string():
    result, _ = run("Who founded Maju Jaya?", f"  {ABSTAIN_EN} [doc_a:0001]")
    assert result.abstained
    assert result.citations == []


def test_prompt_identical_across_modes():
    _, rag_llm = run("Siapa pendiri?", "ok", mode="rag")
    _, hybrid_llm = run("Siapa pendiri?", "ok", mode="hybrid")
    assert rag_llm.calls[0][0] == hybrid_llm.calls[0][0]


def test_unknown_mode_and_serialization():
    with pytest.raises(ValueError):
        run("q", "x", mode="graph")
    result, _ = run("Siapa pendiri?", "Budi [doc_a:0001]")
    assert result.model_dump()["hits"][0]["chunk_id"] == "doc_a:0001"
