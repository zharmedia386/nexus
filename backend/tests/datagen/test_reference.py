import re

import pytest

from nexus.datagen.models import World
from nexus.datagen.reference import REFERENCE_DOC_ID, render_reference
from nexus.datagen.world import build_world
from nexus.datagen.writer import parse_front_matter


@pytest.fixture(scope="module")
def world() -> World:
    return build_world(42)


def test_reference_lists_every_ticker(world: World) -> None:
    _, body = parse_front_matter(render_reference(world))
    rows = [line for line in body.splitlines() if line.startswith("| ")][2:]
    expected = [
        (alias, entity.name)
        for entity in world.entities
        if entity.type == "Company"
        for alias in entity.aliases
        if re.fullmatch(r"[A-Z]{4}", alias)
    ]
    assert expected and len(rows) == len(expected)
    for (ticker, name), row in zip(sorted(expected), rows, strict=True):
        assert row.startswith(f"| {ticker} | {name} |")


def test_reference_front_matter_parses(world: World) -> None:
    meta, _ = parse_front_matter(render_reference(world))
    assert meta == {
        "doc_id": REFERENCE_DOC_ID,
        "doc_type": "reference",
        "lang": "id",
        "year": 2025,
        "title": "Daftar Kode Emiten",
    }


def test_reference_deterministic(world: World) -> None:
    assert render_reference(world) == render_reference(build_world(42))
