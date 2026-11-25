import pytest

from nexus.db.repo import ChunkRow
from nexus.graph.resolve import PersonContext, entity_id, pair_key, resolve
from nexus.graph.schema import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
    VerifiedRelation,
)


def entity(name: str, entity_type: str = "Company", aliases: list[str] | None = None):
    return ExtractedEntity(name=name, type=entity_type, aliases=aliases or [])


def serves(person: str, company: str, quote: str, start: int = 0, **extra) -> VerifiedRelation:
    fields = {"role": "Direktur", "since": 2019, "until": None, "kind": None} | extra
    relation = ExtractedRelation(
        type="SERVES_AS", src=person, dst=company, pct=None, relation=None, quote=quote, **fields
    )
    return VerifiedRelation(relation=relation, quote_start=start, quote_end=start + len(quote))


def family(person: str, relative: str, quote: str) -> VerifiedRelation:
    relation = ExtractedRelation(
        type="FAMILY_OF",
        src=person,
        dst=relative,
        role=None,
        pct=None,
        relation="spouse",
        kind=None,
        since=None,
        until=None,
        quote=quote,
    )
    return VerifiedRelation(relation=relation, quote_start=0, quote_end=len(quote))


def budi(company: str, spouse: str | None = None) -> ExtractionResult:
    entities = [entity("Budi Santoso", "Person"), entity(company)]
    relations = [serves("Budi Santoso", company, f"Budi di {company.removeprefix('PT ')}")]
    if spouse:
        entities.append(entity(spouse, "Person"))
        relations.append(family("Budi Santoso", spouse, f"Budi suami {spouse}"))
    return result(entities, relations)


def budis(graph) -> list:
    return [person for person in by_type(graph, "Person") if person.name == "Budi Santoso"]


def result(entities, relations=()) -> ExtractionResult:
    return ExtractionResult(
        entities=list(entities),
        relations=list(relations),
        dropped_unverified=0,
        dropped_unknown_entity=0,
    )


def chunk(chunk_id: str, start: int = 0) -> ChunkRow:
    doc_id, ordinal = chunk_id.split(":")
    return ChunkRow(chunk_id, doc_id, int(ordinal), start, start + 1000, "")


def run(extractions: dict[str, ExtractionResult], adjudicate=None, **options):
    chunks = [chunk(chunk_id) for chunk_id in extractions]

    def refuse(a: PersonContext, b: PersonContext) -> bool:
        raise AssertionError("adjudicator must not be called")

    return resolve(extractions, chunks, adjudicate=adjudicate or refuse, **options)


def by_type(graph, entity_type: str):
    return [entity for entity in graph.entities if entity.type == entity_type]


def test_legal_affix_variants_merge():
    graph = run(
        {
            "doc_001:0": result([entity("PT Mega Persada Tbk")]),
            "doc_002:0": result([entity("Mega Persada")]),
        }
    )
    [company] = graph.entities
    assert company.name == "PT Mega Persada Tbk"
    assert company.aliases == ["Mega Persada"]
    assert len(company.mentions) == 2


def test_ticker_alias_merges_via_reference_row():
    graph = run(
        {
            "ref_001:0": result([entity("PT Mega Persada Tbk", aliases=["MGPR"])]),
            "doc_003:0": result([entity("MGPR")]),
        }
    )
    [company] = graph.entities
    assert {mention.name for mention in company.mentions} == {"PT Mega Persada Tbk", "MGPR"}
    assert "MGPR" in company.aliases


def test_group_name_forms_merge():
    graph = run(
        {
            "doc_001:0": result([entity("Grup Bumi Sentosa", "Group")]),
            "doc_002:0": result([entity("Bumi Sentosa Group", "Group")]),
            "doc_003:0": result([entity("Bumi Sentosa", "Company")]),
        }
    )
    assert len(by_type(graph, "Group")) == 1
    assert len(by_type(graph, "Company")) == 1


def test_same_name_shared_company_merges_without_llm():
    graph = run(
        {
            "doc_001:0": result(
                [entity("Budi Santoso", "Person"), entity("PT Mega Persada Tbk")],
                [serves("Budi Santoso", "PT Mega Persada Tbk", "Budi di Mega")],
            ),
            "doc_002:0": result(
                [entity("Budi Santoso", "Person"), entity("Mega Persada")],
                [serves("Budi Santoso", "Mega Persada", "Budi lagi", until=2022)],
            ),
        }
    )
    [person] = by_type(graph, "Person")
    assert {mention.doc_id for mention in person.mentions} == {"doc_001", "doc_002"}
    assert {relation.src_id for relation in graph.relations} == {person.id}


def test_same_name_different_companies_merges_without_llm():
    graph = run({"doc_001:0": budi("PT Alpha"), "doc_002:0": budi("PT Beta")})
    [person] = budis(graph)
    assert {mention.doc_id for mention in person.mentions} == {"doc_001", "doc_002"}
    assert (graph.adjudication_bound, graph.adjudications) == (0, 0)


def test_same_spouse_merges_without_llm():
    graph = run({"doc_001:0": budi("PT Alpha", "Siti"), "doc_002:0": budi("PT Beta", "Siti")})
    assert len(budis(graph)) == 1
    assert (graph.adjudication_bound, graph.adjudications) == (0, 0)


@pytest.mark.parametrize(("same", "people"), [(False, 2), (True, 1)])
def test_different_spouses_adjudicated(same: bool, people: int):
    seen: list[tuple[PersonContext, PersonContext]] = []

    def judge(a: PersonContext, b: PersonContext) -> bool:
        seen.append((a, b))
        return same

    graph = run(
        {
            "doc_001:0": budi("PT Alpha", "Siti"),
            "doc_002:0": budi("PT Beta", "Dewi"),
            "doc_003:0": budi("PT Gamma"),
        },
        adjudicate=judge,
    )
    assert len(budis(graph)) == people
    assert (graph.adjudication_bound, graph.adjudications) == (1, 1)
    assert seen == [
        (
            PersonContext("Budi Santoso", ["Budi di Alpha", "Budi suami Siti"]),
            PersonContext("Budi Santoso", ["Budi di Beta", "Budi suami Dewi"]),
        )
    ]
    # The spouseless doc joins the earliest cluster.
    [first, *_] = sorted(budis(graph), key=lambda person: person.mentions[0].doc_id)
    assert {"doc_001", "doc_003"} <= {mention.doc_id for mention in first.mentions}


def test_adjudication_runs_over_cluster_roots_once():
    seen: list[tuple[list[str], list[str]]] = []

    def merge_alpha_beta(a: PersonContext, b: PersonContext) -> bool:
        seen.append((a.facts, b.facts))
        return {*a.facts, *b.facts} == {
            "Budi di Alpha",
            "Budi di Beta",
            "Budi suami Siti",
            "Budi suami Dewi",
        }

    graph = run(
        {
            "doc_001:0": budi("PT Alpha", "Siti"),
            "doc_002:0": budi("PT Beta", "Dewi"),
            "doc_003:0": budi("PT Gamma", "Ani"),
        },
        adjudicate=merge_alpha_beta,
    )
    assert len(budis(graph)) == 2
    assert (graph.adjudication_bound, graph.adjudications) == (3, 2)
    # After Alpha~Beta merge, Gamma is asked once against the merged cluster.
    assert seen == [
        (["Budi di Alpha", "Budi suami Siti"], ["Budi di Beta", "Budi suami Dewi"]),
        (
            ["Budi di Alpha", "Budi suami Siti", "Budi di Beta", "Budi suami Dewi"],
            ["Budi di Gamma", "Budi suami Ani"],
        ),
    ]


def test_cap_raises_before_any_adjudication():
    calls: list[str] = []
    extractions = {f"doc_{index:03}:0": budi("PT Co", f"Istri {index}") for index in range(5)}
    # 5 different spouses yield 10 conflict pairs, above a cap of 9.
    with pytest.raises(RuntimeError):
        run(extractions, adjudicate=lambda a, b: calls.append(a.name) or False, max_adjudications=9)
    assert calls == []
    graph = run(extractions, adjudicate=lambda a, b: False, max_adjudications=10)
    assert (graph.adjudication_bound, graph.adjudications) == (10, 10)
    assert len(budis(graph)) == 5


def test_ticker_link_merges_person_without_llm():
    graph = run(
        {
            "doc_001:0": result(
                [entity("Budi Santoso", "Person"), entity("PLKZ")],
                [serves("Budi Santoso", "PLKZ", "Budi di PLKZ")],
            ),
            "doc_002:0": result(
                [entity("Budi Santoso", "Person"), entity("PT Pelita X Tbk")],
                [serves("Budi Santoso", "PT Pelita X Tbk", "Budi di Pelita", until=2020)],
            ),
            "ref_001:0": result([entity("PT Pelita X Tbk", aliases=["PLKZ"])]),
        }
    )
    assert len(by_type(graph, "Company")) == 1
    assert len(by_type(graph, "Person")) == 1


def test_non_ticker_alias_between_mentioned_entities_skipped():
    graph = run(
        {
            "doc_001:0": result([entity("PT Alpha", aliases=["Beta Jaya", "ALPH"])]),
            "doc_002:0": result([entity("PT Beta Jaya")]),
            "doc_003:0": result([entity("ALPH")]),
        }
    )
    assert sorted(company.name for company in graph.entities) == ["PT Alpha", "PT Beta Jaya"]
    assert graph.skipped_alias_unions == 1


def test_pair_key_order_independent():
    a, b = PersonContext("Budi", ["x"]), PersonContext("Budi", ["y"])
    assert pair_key(a, b) == pair_key(b, a) != pair_key(a, a)


def test_pair_key_changes_with_prompt_version(monkeypatch):
    a, b = PersonContext("Budi", ["x"]), PersonContext("Budi", ["y"])
    before = pair_key(a, b)
    monkeypatch.setattr("nexus.graph.resolve.ADJUDICATE_PROMPT_VERSION", "v2")
    assert pair_key(a, b) != before


def test_relation_provenance_merged_and_doc_offsets():
    quote_a, quote_b = "Budi menjabat Direktur", "Budi, Direktur Alpha"
    extractions = {
        "doc_001:0": result(
            [entity("Budi Santoso", "Person"), entity("PT Alpha")],
            [serves("Budi Santoso", "PT Alpha", quote_a, start=5)],
        ),
        "doc_001:1": result(
            [entity("Budi Santoso", "Person"), entity("Alpha")],
            [serves("Budi Santoso", "Alpha", quote_b, start=10, kind="board")],
        ),
    }
    chunks = [chunk("doc_001:0", start=0), chunk("doc_001:1", start=900)]
    graph = resolve(extractions, chunks, adjudicate=lambda a, b: False)
    [relation] = graph.relations
    assert relation.chunk_ids == ["doc_001:0", "doc_001:1"]
    assert relation.doc_ids == ["doc_001", "doc_001"]
    assert relation.quotes == [quote_a, quote_b]
    assert relation.quote_spans == [(5, 5 + len(quote_a)), (910, 910 + len(quote_b))]
    assert relation.kind == "board"


def test_entity_ids_deterministic():
    extractions = {
        "doc_002:0": result(
            [entity("Budi Santoso", "Person"), entity("PT Alpha")],
            [serves("Budi Santoso", "PT Alpha", "Budi di Alpha")],
        ),
        "doc_001:0": result([entity("PT Alpha Tbk"), entity("Grup Alpha", "Group")]),
    }
    first = run(extractions)
    second = run(dict(reversed(list(extractions.items()))))
    assert first == second
    ids = {entity.name: entity.id for entity in first.entities}
    assert ids["Budi Santoso"] == entity_id("Person", "budi santoso")
    assert ids["Grup Alpha"] == entity_id("Group", "alpha")
    assert ids["Grup Alpha"].startswith("group_")
    assert [entity.id for entity in first.entities] == sorted(ids.values())
