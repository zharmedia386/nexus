from pathlib import Path
from typing import Literal

from pydantic import BaseModel

EntityType = Literal["Company", "Person", "Group", "Sector", "Location"]
RelType = Literal[
    "FOUNDED",
    "SERVES_AS",
    "OWNS_STAKE",
    "SUBSIDIARY_OF",
    "INVESTED_IN",
    "PARTNERS_WITH",
    "FAMILY_OF",
    "MEMBER_OF_GROUP",
    "IN_SECTOR",
    "HEADQUARTERED_IN",
]


class Entity(BaseModel):
    id: str
    type: EntityType
    name: str
    aliases: list[str] = []
    attrs: dict[str, str | int | float | bool] = {}


class Edge(BaseModel):
    id: str
    type: RelType
    src: str
    dst: str
    # FAMILY_OF reads "src is <relation> of dst", e.g. parent: src is dst's parent.
    props: dict[str, str | int | float | None] = {}
    since: int | None = None
    until: int | None = None


class HiddenPath(BaseModel):
    id: str
    edge_ids: list[str]
    start: str
    end: str
    hops: int


class World(BaseModel):
    seed: int
    entities: list[Entity]
    edges: list[Edge]
    hidden_paths: list[HiddenPath]
    collisions: list[tuple[str, str]]

    def to_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path) -> "World":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
