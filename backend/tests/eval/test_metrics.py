from nexus.datagen.models import Entity, World
from nexus.eval.harness import score
from nexus.eval.metrics import (
    abstain_correct,
    answer_match,
    entity_lexicon,
    extra_entities,
    normalize,
    recall_at_k,
)
from nexus.eval.questions import Question
from nexus.retrieval.answer import Answer


def _answer(text: str, abstained: bool) -> Answer:
    return Answer(
        text=text,
        citations=[],
        invalid_citations=[],
        hits=[],
        abstained=abstained,
        mode="rag",
        latency_ms=1,
    )


def _question(gold: list[list[str]]) -> Question:
    return Question(
        id="q",
        lang="id",
        category="unanswerable" if not gold else "single_hop",
        text="?",
        gold_answers=gold,
        gold_doc_ids=["doc_001"] if gold else [],
    )


def test_normalize_strips_pt_tbk() -> None:
    assert normalize("PT Sinar Jaya Tbk") == "sinar jaya"
    assert normalize("  PT. Sinar-Jaya,  Tbk.  ") == "sinar jaya"


def test_answer_match_partial() -> None:
    gold = [["PT Sinar Jaya Tbk", "SJAY"], ["Budi Santoso"]]
    assert answer_match("Pemiliknya adalah Budi Santoso [c1].", gold) == 0.5
    assert answer_match("PT SINAR JAYA dan budi santoso", gold) == 1.0


def test_answer_match_accepts_alias() -> None:
    assert answer_match("Saham SJAY dikendalikan grup.", [["PT Sinar Jaya Tbk", "SJAY"]]) == 1.0


def test_answer_match_is_whole_token() -> None:
    assert answer_match("PT Jayakarta Abadi", [["Jaya"]]) == 0.0
    assert answer_match("Budi Santosowati", [["Budi Santoso"]]) == 0.0


def test_recall_at_k() -> None:
    assert recall_at_k(["d1", "d1", "d2", "d3"], ["d2", "d4"]) == 0.5
    assert recall_at_k(["d1", "d1", "d2"], ["d2"], k=1) == 0.0
    assert recall_at_k(["d1", "d1", "d2"], ["d2"], k=2) == 1.0
    assert recall_at_k(["d1"], []) is None


def test_abstain_correct_for_unanswerable() -> None:
    unanswerable = _question([])
    assert abstain_correct(_answer("Informasi tidak ditemukan.", True), unanswerable)
    assert not abstain_correct(_answer("PT X [c1]", False), unanswerable)
    answerable = _question([["PT X"]])
    assert abstain_correct(_answer("PT X [c1]", False), answerable)
    assert not abstain_correct(_answer("Informasi tidak ditemukan.", True), answerable)


def _world() -> World:
    people = ["Budi Santoso", "Rina Wijaya", "Agus Halim", "Dewi Lestari", "Agus Halim"]
    entities = [Entity(id=f"pe_{i}", type="Person", name=name) for i, name in enumerate(people)]
    company = Entity(id="co_1", type="Company", name="PT Sinar Jaya Tbk", aliases=["SJAY"])
    return World(seed=0, entities=[*entities, company], edges=[], hidden_paths=[], collisions=[])


def test_entity_lexicon_drops_colliding_forms() -> None:
    lexicon = entity_lexicon(_world())
    assert lexicon["sinar jaya"] == "co_1" and lexicon["sjay"] == "co_1"
    assert "agus halim" not in lexicon


def test_listing_the_board_is_penalized() -> None:
    lexicon = entity_lexicon(_world())
    lexicon["kurnia putra"] = "pe_9"
    gold = [["Budi Santoso"]]
    text = "Dewan: Budi Santoso, Rina Wijaya, Dewi Lestari, Kurnia Putra (SJAY)."
    question = "Siapa Direktur Utama SJAY saat ini?"
    assert answer_match(text, gold) == 1.0
    assert extra_entities(text, gold, lexicon, question) == 3
    metrics = score(_question(gold), _answer(text, False), lexicon)
    assert metrics["extra_entities"] == 4 and metrics["answer_precision"] == 0.2
    asked = _question(gold).model_copy(update={"text": question})
    assert score(asked, _answer(text, False), lexicon)["answer_precision"] == 0.25


def test_precision_none_when_nothing_named() -> None:
    metrics = score(_question([["Budi Santoso"]]), _answer("Tidak jelas.", False), {})
    assert metrics["answer_match"] == 0.0 and metrics["answer_precision"] is None
