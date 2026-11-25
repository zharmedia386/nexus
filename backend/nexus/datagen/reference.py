import json
import re

from nexus.datagen.models import World

REFERENCE_DOC_ID = "ref_001"
TITLE = "Daftar Kode Emiten"
TICKER = re.compile(r"[A-Z]{4}")


def _cell(value: str) -> str:
    return value.replace("|", "\\|")


def render_reference(world: World) -> str:
    names = {entity.id: entity.name for entity in world.entities}
    sectors = {edge.src: names[edge.dst] for edge in world.edges if edge.type == "IN_SECTOR"}
    rows = sorted(
        (alias, entity.name, sectors.get(entity.id, ""))
        for entity in world.entities
        if entity.type == "Company"
        for alias in entity.aliases
        if TICKER.fullmatch(alias)
    )
    lines = [
        "---",
        f"doc_id: {REFERENCE_DOC_ID}",
        "doc_type: reference",
        "lang: id",
        "year: 2025",
        f"title: {json.dumps(TITLE, ensure_ascii=False)}",
        "---",
        "",
        "| Kode | Nama Perusahaan | Sektor |",
        "| --- | --- | --- |",
        *(f"| {' | '.join(_cell(cell) for cell in row)} |" for row in rows),
    ]
    return "\n".join(lines) + "\n"
