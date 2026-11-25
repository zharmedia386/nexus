import json

import pytest

from nexus.graph.extract import EXTRACT_TIMEOUT, extract_chunk
from nexus.graph.schema import ChunkExtraction, ExtractedEntity, ExtractedRelation

TEXT = "Rahmi Nasyiah menjabat sebagai Direktur Utama di BRMN sejak 2019."
ENTITIES = [
    ExtractedEntity(name="Rahmi Nasyiah", type="Person", aliases=[]),
    ExtractedEntity(name="BRMN", type="Company", aliases=[]),
]


def relation(quote: str, dst: str = "BRMN") -> ExtractedRelation:
    return ExtractedRelation(
        type="SERVES_AS",
        src="Rahmi Nasyiah",
        dst=dst,
        role="Direktur Utama",
        pct=None,
        relation=None,
        kind=None,
        since=2019,
        until=None,
        quote=quote,
    )


def fake_llm(*relations: ExtractedRelation, seen: dict | None = None):
    def llm(
        messages: list[dict[str, str]],
        schema: type[ChunkExtraction],
        *,
        temperature: float,
        timeout: float,
    ) -> ChunkExtraction:
        if seen is not None:
            seen.update(temperature=temperature, timeout=timeout)
        return ChunkExtraction(entities=ENTITIES, relations=list(relations))

    return llm


def test_keeps_verified_relation_with_offsets() -> None:
    quote = "Rahmi Nasyiah menjabat sebagai Direktur Utama di BRMN"
    result = extract_chunk(TEXT, llm=fake_llm(relation(quote)))
    [kept] = result.relations
    assert TEXT[kept.quote_start : kept.quote_end] == quote
    assert result.dropped_unverified == result.dropped_unknown_entity == 0


def test_paraphrased_quote_is_dropped() -> None:
    result = extract_chunk(TEXT, llm=fake_llm(relation("Rahmi Nasyiah is CEO of BRMN")))
    assert result.relations == []
    assert result.dropped_unverified == 1


def test_unknown_entity_relation_dropped() -> None:
    result = extract_chunk(TEXT, llm=fake_llm(relation("Direktur Utama", dst="PT Buana Raya")))
    assert result.relations == []
    assert result.dropped_unknown_entity == 1


def test_whitespace_tolerant_quote_match() -> None:
    text = "Rahmi Nasyiah menjabat sebagai\nDirektur  Utama di BRMN sejak 2019."
    result = extract_chunk(text, llm=fake_llm(relation("sebagai Direktur Utama di BRMN")))
    [kept] = result.relations
    assert text[kept.quote_start : kept.quote_end] == "sebagai\nDirektur  Utama di BRMN"


@pytest.mark.parametrize("quote", ["", "   ", "\n"])
def test_blank_quote_is_unverified(quote: str) -> None:
    result = extract_chunk(TEXT, llm=fake_llm(relation(quote)))
    assert result.relations == []
    assert result.dropped_unverified == 1


def test_overlong_quote_is_unverified() -> None:
    text = TEXT + " " + "x" * 300
    result = extract_chunk(text, llm=fake_llm(relation(text)))
    assert result.dropped_unverified == 1


def test_extract_passes_long_timeout() -> None:
    seen: dict = {}
    extract_chunk(TEXT, llm=fake_llm(seen=seen))
    assert seen == {"temperature": 0.0, "timeout": EXTRACT_TIMEOUT}


def test_schema_is_strict_compatible() -> None:
    assert "additionalProperties" not in json.dumps(ChunkExtraction.model_json_schema())


@pytest.mark.live
def test_live_extracts_board_role() -> None:
    text = (
        "Berdasarkan RUPS Tahunan 2024, PT Sinar Wibawa Tbk mengangkat Darsono Hutapea "
        "sebagai Direktur Utama sejak 2024. Darsono Hutapea sebelumnya menjabat sebagai "
        "Direktur Keuangan di PT Lintas Bahari."
    )
    result = extract_chunk(text)
    print(result.model_dump_json(indent=2))
    assert any(
        verified.relation.type == "SERVES_AS"
        and verified.relation.role == "Direktur Utama"
        and verified.relation.src == "Darsono Hutapea"
        for verified in result.relations
    )
