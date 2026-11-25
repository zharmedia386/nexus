import re
from collections import Counter
from pathlib import Path

import pytest

from nexus.datagen.models import Edge, World
from nexus.datagen.planner import BLOOD_RELATIONS, DocPlan, plan_documents
from nexus.datagen.world import build_world
from nexus.eval.harness import score
from nexus.eval.metrics import entity_lexicon, extra_entities, normalize
from nexus.eval.questions import Question, build_questions, load_questions, write_questions
from nexus.retrieval.answer import Answer, detect_lang

ROLES = (
    "Komisaris Independen",
    "Direktur Operasional",
    "Direktur Keuangan",
    "Komisaris Utama",
    "Direktur Utama",
    "Komisaris",
    "Direktur",
)
# The original 114 published questions must never change.
BASELINE_COUNT = 114
REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def world() -> World:
    return build_world(42)


@pytest.fixture(scope="module")
def plans(world: World) -> list[DocPlan]:
    return plan_documents(world)


@pytest.fixture(scope="module")
def questions(world: World, plans: list[DocPlan]) -> list[Question]:
    return build_questions(world, plans)


def _mentions(world: World, text: str, entity_type: str) -> set[str]:
    padded = f" {normalize(text)} "
    return {
        entity.id
        for entity in world.entities
        if entity.type == entity_type
        and any(f" {normalize(form)} " in padded for form in [entity.name, *entity.aliases])
    }


def _holders(world: World, company: str, role: str, year: int | None) -> set[str]:
    def active(edge: Edge) -> bool:
        if year is None:
            return edge.until is None
        return (edge.since or 0) <= year < (edge.until or 10_000)

    return {
        edge.src
        for edge in world.edges
        if edge.type == "SERVES_AS"
        and edge.dst == company
        and edge.props["role"] == role
        and active(edge)
    }


def _names(world: World, ids: set[str]) -> set[str]:
    return {entity.name for entity in world.entities if entity.id in ids}


def test_categories_present(questions: list[Question]) -> None:
    counts = Counter(question.category for question in questions)
    assert set(counts) == {
        "single_hop",
        "multi_hop_2",
        "multi_hop_3",
        "temporal",
        "unanswerable",
        "thematic",
    }
    assert all(count >= 10 for count in counts.values()), counts
    assert 120 <= len(questions) <= 140
    assert len({question.id for question in questions}) == len(questions)


def test_cross_lingual_share(questions: list[Question], plans: list[DocPlan]) -> None:
    lang_of = {plan.doc_id: plan.lang for plan in plans}
    answerable = [question for question in questions if question.gold_answers]
    crossing = [
        question
        for question in answerable
        if all(lang_of[doc_id] != question.lang for doc_id in question.gold_doc_ids)
    ]
    assert len(crossing) >= 0.2 * len(answerable)


def test_multi_hop_gold_docs_span_multiple_docs(
    world: World, plans: list[DocPlan], questions: list[Question]
) -> None:
    edges_of = {plan.doc_id: set(plan.edge_ids) for plan in plans}
    path_edges = [set(path.edge_ids) for path in world.hidden_paths]
    counts = Counter(question.category for question in questions)
    assert counts["multi_hop_3"] > sum(path.hops == 3 for path in world.hidden_paths) * 2
    for question in questions:
        if question.category.startswith("multi_hop"):
            assert len(set(question.gold_doc_ids)) >= 2
            covered = set().union(*(edges_of[doc_id] for doc_id in question.gold_doc_ids))
            hops = {len(edges) for edges in path_edges if edges <= covered}
            expected = {2} if question.category == "multi_hop_2" else {3, 4}
            assert hops & expected, question.id
            assert len(question.gold_answers) == 1
            assert len(_mentions(world, question.gold_answers[0][0], "Company")) >= 1


def test_answerable_gold_is_well_formed(questions: list[Question]) -> None:
    for question in questions:
        if question.category == "unanswerable":
            assert question.gold_answers == [] and question.gold_doc_ids == []
        else:
            assert question.gold_answers and question.gold_doc_ids
            assert all(forms for forms in question.gold_answers)


def test_no_colliding_person_names(world: World, questions: list[Question]) -> None:
    counts = Counter(entity.name for entity in world.entities if entity.type == "Person")
    colliding = {normalize(name) for name, count in counts.items() if count > 1}
    for question in questions:
        padded = f" {normalize(question.text)} "
        assert not any(f" {name} " in padded for name in colliding), question.text
        for forms in question.gold_answers:
            assert not colliding & {normalize(form) for form in forms}, question.id


def test_role_questions_match_world(world: World, questions: list[Question]) -> None:
    checked = 0
    for question in questions:
        roles = [role for role in ROLES if f" {role} " in question.text]
        if question.category not in ("single_hop", "temporal") or not roles:
            continue
        year_match = re.search(r"\b(19|20)\d{2}\b", question.text)
        year = int(year_match.group()) if question.category == "temporal" and year_match else None
        (company,) = _mentions(world, question.text, "Company")
        holders = _holders(world, company, roles[0], year)
        assert {forms[0] for forms in question.gold_answers} == _names(world, holders)
        assert len(holders) == 1
        checked += 1
    assert checked >= 20


def test_unanswerable_relations_absent(world: World, questions: list[Question]) -> None:
    keywords = {
        "PARTNERS_WITH": ("kerja sama", "partnership"),
        "INVESTED_IN": ("investasi", "invest"),
        "FOUNDED": ("pendiri", "founded"),
    }
    for question in questions:
        if question.category != "unanswerable":
            continue
        companies = _mentions(world, question.text, "Company")
        assert companies, question.text
        lowered = question.text.lower()
        rel_types = [rel for rel, words in keywords.items() if any(w in lowered for w in words)]
        absent_role = "Pemasaran" in question.text or "Marketing" in question.text
        assert rel_types or absent_role, question.text
        for edge in world.edges:
            if edge.type in rel_types and edge.dst in companies:
                assert edge.type != "FOUNDED" and edge.src not in companies, question.text
            if absent_role and edge.type == "SERVES_AS":
                assert "Pemasaran" not in str(edge.props["role"])


def test_question_lang_is_detectable(questions: list[Question]) -> None:
    assert all(detect_lang(question.text) == question.lang for question in questions)


def test_some_questions_use_aliases(world: World, questions: list[Question]) -> None:
    tickers = {str(entity.attrs["ticker"]) for entity in world.entities if "ticker" in entity.attrs}
    assert any(set(question.text.replace("?", " ").split()) & tickers for question in questions)


def test_deterministic_and_roundtrip(
    world: World, plans: list[DocPlan], questions: list[Question], tmp_path
) -> None:
    assert build_questions(world, plans) == questions
    path = tmp_path / "questions.jsonl"
    write_questions(questions, path)
    assert load_questions(path) == questions


def test_support_entities_only_on_multi_hop(world: World, questions: list[Question]) -> None:
    lexicon = entity_lexicon(world)
    for question in questions:
        if question.category == "thematic":
            continue
        if not question.category.startswith("multi_hop"):
            assert question.support_entities == []
            continue
        gold_ids = {lexicon.get(normalize(form)) for form in question.gold_answers[0]}
        assert question.support_entities and not gold_ids & set(question.support_entities)


def test_explaining_the_chain_keeps_full_precision(world: World, questions: list[Question]) -> None:
    names = {entity.id: entity.name for entity in world.entities}
    lexicon = entity_lexicon(world)
    question = next(
        q for q in questions if q.category == "multi_hop_3" and len(q.support_entities) == 4
    )
    chain = ", ".join(names[entity_id] for entity_id in question.support_entities)
    text = f"Melalui {chain}, jawabannya {question.gold_answers[0][0]}."
    ans = Answer(
        text=text,
        citations=[],
        invalid_citations=[],
        hits=[],
        abstained=False,
        mode="rag",
        latency_ms=1,
    )
    assert score(question, ans, lexicon)["answer_precision"] == 1.0
    on_path = set(question.support_entities) | {lexicon.get(normalize(question.gold_answers[0][0]))}
    outsider = next(
        name
        for form, name in ((normalize(n), n) for n in names.values())
        if form in lexicon and lexicon[form] not in on_path and lexicon[form].startswith("pe_")
    )
    padded = ans.model_copy(update={"text": f"{text} Lihat juga {outsider}."})
    assert (
        extra_entities(
            padded.text, question.gold_answers, lexicon, question.text, question.support_entities
        )
        == 1
    )


def test_existing_questions_unchanged(questions: list[Question]) -> None:
    published = (REPO_ROOT / "eval/questions.jsonl").read_text(encoding="utf-8").splitlines()
    baseline = published[:BASELINE_COUNT]
    assert len(baseline) == BASELINE_COUNT
    assert [question.model_dump_json() for question in questions[:BASELINE_COUNT]] == baseline


def test_thematic_count_and_langs(questions: list[Question]) -> None:
    thematic = [question for question in questions if question.category == "thematic"]
    assert questions[114:] == thematic
    assert 18 <= len(thematic) <= 24
    assert {question.lang for question in thematic} == {"id", "en"}
    assert [question.id for question in thematic] == [
        f"th_{number:03d}" for number in range(1, len(thematic) + 1)
    ]


def test_thematic_gold_capped(world: World, questions: list[Question]) -> None:
    lexicon = entity_lexicon(world)
    for question in questions:
        if question.category != "thematic":
            continue
        assert 2 <= len(question.gold_answers) <= 15, question.id
        assert question.gold_doc_ids
        gold_ids = {lexicon.get(normalize(forms[0])) for forms in question.gold_answers}
        assert all(entity_id and entity_id.startswith("co_") for entity_id in gold_ids)
        assert not gold_ids & set(question.support_entities), question.id


def test_family_footprint_gold_matches_world(world: World, questions: list[Question]) -> None:
    current = [edge for edge in world.edges if edge.until is None]
    blood = [
        edge
        for edge in current
        if edge.type == "FAMILY_OF" and edge.props["relation"] in BLOOD_RELATIONS
    ]
    checked = 0
    for question in questions:
        family_words = ("led or owned", "dipimpin atau dimiliki")
        if question.category != "thematic" or not any(w in question.text for w in family_words):
            continue
        (founder,) = _mentions(world, question.text, "Person")
        family = {founder}
        while (
            grown := {
                other
                for edge in blood
                if {edge.src, edge.dst} & family
                for other in (edge.src, edge.dst)
            }
            - family
        ):
            family |= grown
        assert len(family) == 4
        companies = {
            edge.dst
            for edge in current
            if edge.type in ("SERVES_AS", "OWNS_STAKE") and edge.src in family
        }
        assert len(companies) <= 15
        assert {forms[0] for forms in question.gold_answers} == _names(world, companies)
        checked += 1
    assert checked == 8
