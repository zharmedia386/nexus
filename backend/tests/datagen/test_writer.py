import json
from pathlib import Path

import pytest

from nexus import cli
from nexus.datagen.models import Edge, World
from nexus.datagen.planner import DocPlan, components, plan_documents
from nexus.datagen.world import build_world
from nexus.datagen.writer import (
    DocGenError,
    generate_docs,
    parse_front_matter,
    render_facts,
    render_markdown,
    write_document,
)
from nexus.llm import GatewayError


@pytest.fixture(scope="module")
def world() -> World:
    return build_world(42)


@pytest.fixture(scope="module")
def plans(world: World) -> list[DocPlan]:
    return plan_documents(world)


def _plan(plans: list[DocPlan], lang: str) -> DocPlan:
    return next(p for p in plans if p.lang == lang and p.doc_type != "annual_report")


def _complete(plan: DocPlan) -> str:
    return "# Judul\n\n" + " ".join(plan.surface_forms.values())


def test_render_facts_uses_surface_forms_and_dates(world: World, plans: list[DocPlan]) -> None:
    for lang in ("id", "en"):
        plan = _plan(plans, lang)
        facts = render_facts(plan, world)
        assert len(facts) == len(plan.edge_ids)
        joined = " ".join(facts)
        assert all(form in joined for form in plan.surface_forms.values())
        edges = {e.id: e for e in world.edges}
        for edge_id, fact in zip(plan.edge_ids, facts, strict=True):
            for year in (edges[edge_id].since, edges[edge_id].until):
                if year is not None:
                    assert str(year) in fact


def test_prompt_states_all_facts_and_forbids_invention(world: World, plans: list[DocPlan]) -> None:
    plan = next(p for p in plans if p.doc_type == "news" and p.lang == "id")
    seen: list[list[dict[str, str]]] = []

    def llm(messages: list[dict[str, str]]) -> str:
        seen.append(messages)
        return _complete(plan)

    write_document(plan, world, llm)
    prompt = "\n".join(m["content"] for m in seen[0])
    assert all(fact in prompt for fact in render_facts(plan, world))
    assert "Bahasa Indonesia" in prompt


def test_regenerates_when_surface_form_missing(world: World, plans: list[DocPlan]) -> None:
    plan = _plan(plans, "id")
    good = _complete(plan)
    forms = list(plan.surface_forms.values())
    replies = iter([good.replace(forms[0], "X"), good])
    calls: list[int] = []

    def llm(messages: list[dict[str, str]]) -> str:
        calls.append(1)
        return next(replies)

    assert write_document(plan, world, llm) == good
    assert len(calls) == 2


def test_raises_after_three_misses(world: World, plans: list[DocPlan]) -> None:
    plan = _plan(plans, "en")
    calls: list[int] = []

    def llm(messages: list[dict[str, str]]) -> str:
        calls.append(1)
        return "nothing here"

    with pytest.raises(DocGenError) as error:
        write_document(plan, world, llm)
    assert len(calls) == 3
    assert all(form in str(error.value) for form in plan.surface_forms.values())


def test_cli_skips_existing(world: World, plans: list[DocPlan], tmp_path: Path) -> None:
    subset = plans[:3]
    calls: list[str] = []

    def llm(messages: list[dict[str, str]]) -> str:
        plan = subset[len(calls)]
        calls.append(plan.doc_id)
        return _complete(plan)

    docs_dir = tmp_path / "docs"
    facts_path = tmp_path / "doc_facts.json"
    assert generate_docs(world, subset[:2], docs_dir, facts_path, llm) == (2, {})
    assert generate_docs(world, subset, docs_dir, facts_path, llm) == (1, {})
    assert calls == [p.doc_id for p in subset]
    text = (docs_dir / f"{subset[0].doc_id}.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert f"doc_id: {subset[0].doc_id}" in text and 'title: "Judul"' in text
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    assert facts == {p.doc_id: p.edge_ids for p in subset}
    assert not list(tmp_path.rglob("*.tmp"))
    calls.clear()
    assert generate_docs(world, subset[:1], docs_dir, facts_path, llm, force=True) == (1, {})


def test_front_matter_round_trips_awkward_title(plans: list[DocPlan]) -> None:
    title = 'PT Maju: "Tbk" naik'
    plan = plans[0]
    meta, body = parse_front_matter(render_markdown(plan, f"# {title}\n\nIsi."))
    assert meta == {
        "doc_id": plan.doc_id,
        "doc_type": plan.doc_type,
        "lang": plan.lang,
        "year": plan.year,
        "title": title,
    }
    assert body.startswith("# ") and body.endswith("Isi.\n")


def test_failed_doc_does_not_stop_others(
    world: World, plans: list[DocPlan], tmp_path: Path
) -> None:
    subset = plans[:3]

    def picky(messages: list[dict[str, str]]) -> str:
        prompt = messages[-1]["content"]
        plan = next(p for p in subset if all(f in prompt for f in render_facts(p, world)))
        return "nothing" if plan is subset[1] else _complete(plan)

    written, failures = generate_docs(world, subset, tmp_path / "d", tmp_path / "f.json", picky)
    assert written == 2 and list(failures) == [subset[1].doc_id]
    assert json.loads((tmp_path / "f.json").read_text()) == {
        p.doc_id: p.edge_ids for p in (subset[0], subset[2])
    }


def test_gateway_error_is_a_failure_not_a_crash(
    world: World, plans: list[DocPlan], tmp_path: Path
) -> None:
    def down(messages: list[dict[str, str]]) -> str:
        raise GatewayError("timeout")

    written, failures = generate_docs(world, plans[:2], tmp_path / "d", tmp_path / "f.json", down)
    assert written == 0 and len(failures) == 2


def _edge(world: World, **match: object) -> Edge:
    return next(e for e in world.edges if all(getattr(e, k) == v for k, v in match.items()))


def test_sentence_tense_and_one_off_wording(world: World) -> None:
    ended = next(e for e in world.edges if e.type == "SERVES_AS" and e.until)
    plan = DocPlan(
        doc_id="d",
        doc_type="news",
        lang="id",
        year=2025,
        edge_ids=[ended.id],
        surface_forms={ended.src: "Budi", ended.dst: "Maju"},
    )
    fact = render_facts(plan, world)[0]
    assert "pernah menjabat" in fact and f"hingga {ended.until}" in fact
    founded = _edge(world, type="FOUNDED")
    plan = plan.model_copy(
        update={
            "lang": "en",
            "edge_ids": [founded.id],
            "surface_forms": {founded.src: "Budi", founded.dst: "Maju"},
        }
    )
    assert f"in {founded.since}" in render_facts(plan, world)[0]
    member = _edge(world, type="MEMBER_OF_GROUP")
    plan = plan.model_copy(
        update={
            "edge_ids": [member.id],
            "surface_forms": {member.src: "Maju", member.dst: "Sinar Group"},
        }
    )
    assert "Group group" not in render_facts(plan, world)[0]


def test_roundup_prompt_branch(world: World, plans: list[DocPlan]) -> None:
    seen: list[str] = []

    def llm(messages: list[dict[str, str]]) -> str:
        seen.append(messages[-1]["content"])
        return _complete(plan)

    edges = {e.id: e for e in world.edges}
    multi = next(p for p in plans if components([edges[i] for i in p.edge_ids]) > 1)
    single = next(p for p in plans if components([edges[i] for i in p.edge_ids]) == 1)
    for plan in (multi, single):
        write_document(plan, world, llm)
    assert "hubungan apa pun" in seen[0] or "link between" in seen[0]
    assert not ("hubungan apa pun" in seen[1] or "link between" in seen[1])


def test_main_datagen_docs(world: World, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "WORLD_DIR", tmp_path)
    monkeypatch.setattr(cli, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(cli, "WORLD_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(cli, "plan_documents", lambda w: plan_documents(w)[:2])
    pending = iter(plan_documents(world)[:2])

    def llm(messages: list[dict[str, str]]) -> str:
        return _complete(next(pending))

    cli.main(["datagen", "docs"], llm)
    assert len(list((tmp_path / "docs").glob("*.md"))) == 2
