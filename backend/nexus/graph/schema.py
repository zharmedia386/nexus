from typing import Literal

from pydantic import BaseModel

from nexus.datagen.models import EntityType, RelType

BoardRole = Literal[
    "Komisaris Utama",
    "Komisaris",
    "Komisaris Independen",
    "Direktur Utama",
    "Direktur Keuangan",
    "Direktur Operasional",
    "Direktur",
]
FamilyRelation = Literal["spouse", "sibling", "parent", "child", "in-law"]


class ExtractedEntity(BaseModel):
    name: str
    type: EntityType
    aliases: list[str]


class ExtractedRelation(BaseModel):
    type: RelType
    src: str
    dst: str
    role: BoardRole | None
    pct: float | None
    relation: FamilyRelation | None
    kind: str | None
    since: int | None
    until: int | None
    quote: str


class ChunkExtraction(BaseModel):
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]


class VerifiedRelation(BaseModel):
    relation: ExtractedRelation
    quote_start: int
    quote_end: int


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity]
    relations: list[VerifiedRelation]
    dropped_unverified: int
    dropped_unknown_entity: int
