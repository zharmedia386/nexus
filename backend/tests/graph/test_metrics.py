import json

from nexus.datagen.models import Edge, Entity, World
from nexus.datagen.planner import DocPlan
from nexus.graph.metrics import (
    entity_scores,
    er_scores,
    evaluate_graph,
    gold_id,
    gold_ids,
    relation_scores,
    write_graph_report,
)
from nexus.graph.resolve import Mention, ResolvedEntity, ResolvedGraph, ResolvedRelation

WORLD = World(
    seed=0,
    entities=[
        Entity(id="co_1", type="Company", name="PT Mega Persada Tbk", aliases=["MGPR"]),
        Entity(id="co_2", type="Company", name="PT Bumi Raya"),
        Entity(id="pe_1", type="Person", name="Reksa Lazuardi"),
        Entity(id="pe_2", type="Person", name="Reksa Lazuardi"),
        Entity(id="pe_3", type="Person", name="Budi Santoso"),
    ],
    edges=[
        Edge(id="ed_1", type="SERVES_AS", src="pe_1", dst="co_1", props={"role": "Direktur"}),
        Edge(
            id="ed_2",
            type="SERVES_AS",
            src="pe_2",
            dst="co_2",
            props={"role": "Komisaris"},
            since=2020,
            until=2023,
        ),
        Edge(id="ed_3", type="FAMILY_OF", src="pe_3", dst="pe_1", props={"relation": "parent"}),
    ],
    hidden_paths=[],
    collisions=[("pe_1", "pe_2")],
)
PLANS = {
    "doc_001": DocPlan(
        doc_id="doc_001",
        doc_type="news",
        lang="id",
        year=2024,
        edge_ids=["ed_1", "ed_3"],
        surface_forms={"pe_1": "Reksa Lazuardi", "co_1": "Mega Persada", "pe_3": "Budi Santoso"},
    ),
    "doc_002": DocPlan(
        doc_id="doc_002",
        doc_type="news",
        lang="id",
        year=2024,
        edge_ids=["ed_2"],
        surface_forms={"pe_2": "Reksa Lazuardi", "co_2": "PT Bumi Raya"},
    ),
}


def mention(doc_id: str, name: str, entity_type: str = "Company") -> Mention:
    return Mention(f"{doc_id}:0", doc_id, name, entity_type)


REKSA_1 = mention("doc_001", "Reksa Lazuardi", "Person")
BUDI = mention("doc_001", "Budi Santoso", "Person")
MEGA = mention("doc_001", "PT Mega Persada Tbk")
REKSA_2 = mention("doc_002", "Reksa Lazuardi", "Person")
BUMI = mention("doc_002", "Bumi Raya")


def entity(entity_id: str, *mentions: Mention) -> ResolvedEntity:
    return ResolvedEntity(entity_id, mentions[0].type, mentions[0].name, [], list(mentions))


def relation(rel_type, src, dst, doc_id, **extra) -> ResolvedRelation:
    fields = {"role": None, "relation": None, "since": None, "until": None} | extra
    return ResolvedRelation(
        type=rel_type, src_id=src, dst_id=dst, pct=None, kind=None, doc_ids=[doc_id], **fields
    )


def graph(*relations: ResolvedRelation, entities=None) -> ResolvedGraph:
    default = [
        entity("p1", REKSA_1),
        entity("p2", REKSA_2),
        entity("p3", BUDI),
        entity("c1", MEGA),
        entity("c2", BUMI),
    ]
    return ResolvedGraph(entities=entities or default, relations=list(relations))


def scores(resolved: ResolvedGraph):
    mentions = [m for e in resolved.entities for m in e.mentions]
    return relation_scores(resolved, gold_ids(mentions, WORLD, PLANS), WORLD, PLANS)


def test_gold_mapping_tolerates_legal_affixes():
    assert gold_id(mention("doc_001", "PT Mega Persada Tbk"), WORLD, PLANS) == "co_1"
    assert gold_id(mention("doc_001", "Mega Persada, Tbk."), WORLD, PLANS) == "co_1"
    assert gold_id(mention("doc_002", "Bumi Raya"), WORLD, PLANS) == "co_2"
    assert gold_id(mention("ref_001", "MGPR"), WORLD, PLANS) == "co_1"
    # Namesakes resolve by the doc they appear in.
    assert gold_id(REKSA_1, WORLD, PLANS) == "pe_1"
    assert gold_id(REKSA_2, WORLD, PLANS) == "pe_2"
    # A company outside the doc's plan is not attributed.
    assert gold_id(mention("doc_002", "Mega Persada"), WORLD, PLANS) is None


def test_unmapped_mention_is_false_positive():
    extra = mention("doc_001", "PT Sinar Jaya")
    mentions = [REKSA_1, MEGA, extra, mention("doc_001", "Sinar Jaya")]
    score = entity_scores(mentions, gold_ids(mentions, WORLD, PLANS), PLANS["doc_001"])
    assert score.precision == round(2 / 3, 4)
    assert score.recall == round(2 / 3, 4)
    assert score.support == 3


def test_relation_match_requires_role_for_serves_as():
    wrong = scores(graph(relation("SERVES_AS", "p1", "c1", "doc_001", role="Komisaris")))
    assert (wrong.micro.precision, wrong.micro.recall) == (0.0, 0.0)
    right = scores(graph(relation("SERVES_AS", "p1", "c1", "doc_001", role="Direktur")))
    assert right.micro.precision == 1.0
    assert right.micro.recall == round(1 / 3, 4)
    assert right.by_type["SERVES_AS"].recall == 0.5


def test_relation_from_doc_without_that_edge_is_false_positive():
    report = scores(graph(relation("SERVES_AS", "p1", "c1", "doc_002", role="Direktur")))
    assert report.micro.precision == 0.0


def test_family_inverse_and_unscored_reference_relations():
    report = scores(
        graph(
            relation("FAMILY_OF", "p1", "p3", "doc_001", relation="child"),
            relation("IN_SECTOR", "c1", "c2", "ref_001"),
        )
    )
    assert report.by_type["FAMILY_OF"].recall == 1.0
    assert report.micro.precision == 1.0
    assert report.unscored_by_type == {"IN_SECTOR": 1}
    flipped = scores(graph(relation("FAMILY_OF", "p1", "p3", "doc_001", relation="parent")))
    assert flipped.micro.precision == 0.0


def test_context_types_are_unscored_even_from_plan_docs():
    report = scores(graph(relation("HEADQUARTERED_IN", "c1", "c2", "doc_001")))
    assert report.unscored_by_type == {"HEADQUARTERED_IN": 1}
    assert report.micro.precision == 0.0 and "HEADQUARTERED_IN" not in report.by_type


def test_reversed_partners_with_is_true_positive():
    world = WORLD.model_copy(
        update={"edges": [Edge(id="ed_9", type="PARTNERS_WITH", src="co_1", dst="co_2")]}
    )
    forms = {"co_1": "Mega Persada", "co_2": "PT Bumi Raya"}
    plans = {
        "doc_001": PLANS["doc_001"].model_copy(
            update={"edge_ids": ["ed_9"], "surface_forms": forms}
        )
    }
    bumi = mention("doc_001", "Bumi Raya")
    resolved = graph(
        relation("PARTNERS_WITH", "c2", "c1", "doc_001"),
        entities=[entity("c1", MEGA), entity("c2", bumi)],
    )
    gold = gold_ids([MEGA, bumi], world, plans)
    assert relation_scores(resolved, gold, world, plans).micro.precision == 1.0


def test_reversed_family_with_non_symmetric_label_is_false_positive():
    report = scores(graph(relation("FAMILY_OF", "p1", "p3", "doc_001", relation="parent")))
    assert (report.micro.precision, report.by_type["FAMILY_OF"].recall) == (0.0, 0.0)


def test_temporal_accuracy():
    report = scores(
        graph(
            relation("SERVES_AS", "p1", "c1", "doc_001", role="Direktur"),
            relation("SERVES_AS", "p2", "c2", "doc_002", role="Komisaris", since=2020, until=None),
        )
    )
    assert report.temporal_accuracy == 0.5
    # A second temporal variant of the same claim neither adds a TP nor hides the wrong years.
    report = scores(
        graph(
            relation("SERVES_AS", "p2", "c2", "doc_002", role="Komisaris", since=2020, until=2023),
            relation("SERVES_AS", "p2", "c2", "doc_002", role="Komisaris", since=2019, until=2023),
        )
    )
    assert report.micro.precision == 1.0
    assert report.temporal_accuracy == 0.0
    assert report.temporal_support == 1


def test_er_pairwise_perfect_and_split():
    reksa_again = Mention("doc_001:1", "doc_001", "Reksa Lazuardi", "Person")
    mentions = [REKSA_1, reksa_again, MEGA]
    gold = gold_ids(mentions, WORLD, PLANS)
    perfect = graph(entities=[entity("p1", REKSA_1, reksa_again), entity("c1", MEGA)])
    report = er_scores(perfect, gold, WORLD)
    assert (report.precision, report.recall, report.f1) == (1.0, 1.0, 1.0)
    split = graph(entities=[entity("p1", REKSA_1), entity("p9", reksa_again), entity("c1", MEGA)])
    report = er_scores(split, gold, WORLD)
    assert (report.recall, report.f1) == (0.0, 0.0)


def test_er_reports_collision_merges():
    mentions = [REKSA_1, REKSA_2]
    merged = graph(entities=[entity("p1", REKSA_1, REKSA_2)])
    report = er_scores(merged, gold_ids(mentions, WORLD, PLANS), WORLD)
    assert report.collision_merges == 1
    assert report.precision == 0.0
    apart = graph(entities=[entity("p1", REKSA_1), entity("p2", REKSA_2)])
    assert er_scores(apart, gold_ids(mentions, WORLD, PLANS), WORLD).collision_merges == 0


def test_ticker_link_counted():
    ticker = mention("ref_001", "MGPR")
    name = mention("ref_001", "PT Mega Persada Tbk")
    mentions = [ticker, name, MEGA]
    gold = gold_ids(mentions, WORLD, PLANS)
    linked = graph(entities=[entity("c1", name, MEGA, ticker)])
    report = er_scores(linked, gold, WORLD)
    assert (report.ticker_links, report.ticker_total) == (1, 1)
    unlinked = graph(entities=[entity("c1", name, MEGA), entity("c9", ticker)])
    report = er_scores(unlinked, gold, WORLD)
    assert (report.ticker_links, report.ticker_total) == (0, 1)


def test_write_graph_report(tmp_path):
    resolved = graph(relation("SERVES_AS", "p1", "c1", "doc_001", role="Direktur"))
    result = evaluate_graph(resolved, {}, WORLD, PLANS)
    assert result.entity_micro.recall == 1.0
    path = write_graph_report(result, tmp_path)
    assert path.name.startswith("graph-") and path.suffix == ".md"
    assert "relation (micro)" in path.read_text()
    payload = json.loads(path.with_suffix(".json").read_text())
    assert payload["relations"]["micro"]["support"] == 3
