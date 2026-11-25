from collections import Counter, defaultdict, deque
from pathlib import Path

import pytest
from faker.providers.person.id_ID import Provider as IdNames

from nexus.datagen.models import Edge, World
from nexus.datagen.names import REAL_TICKERS
from nexus.datagen.world import build_world

BLOCKLIST = Path(__file__).resolve().parents[2] / "nexus" / "datagen" / "blocklist.txt"


@pytest.fixture(scope="module")
def world() -> World:
    return build_world(42)


def _companies(world: World) -> list:
    return [entity for entity in world.entities if entity.type == "Company"]


def _born(world: World) -> dict[str, int]:
    return {
        entity.id: int(entity.attrs["birth_year"])
        for entity in world.entities
        if entity.type == "Person"
    }


def _family(world: World, relation: str) -> list[Edge]:
    return [e for e in world.edges if e.type == "FAMILY_OF" and e.props["relation"] == relation]


def _distance(world: World, start: str, end: str) -> int:
    neighbours: dict[str, list[str]] = defaultdict(list)
    for edge in world.edges:
        if edge.type not in ("IN_SECTOR", "HEADQUARTERED_IN"):
            neighbours[edge.src].append(edge.dst)
            neighbours[edge.dst].append(edge.src)
    seen, queue = {start}, deque([(start, 0)])
    while queue:
        node, depth = queue.popleft()
        if node == end:
            return depth
        for nxt in neighbours[node]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, depth + 1))
    return -1


def test_deterministic(world: World) -> None:
    assert build_world(42).model_dump_json() == world.model_dump_json()


def test_json_roundtrip(world: World, tmp_path: Path) -> None:
    path = tmp_path / "world.json"
    world.to_json(path)
    assert World.from_json(path) == world


def test_scale(world: World) -> None:
    counts = Counter(entity.type for entity in world.entities)
    partnerships = sum(edge.type == "PARTNERS_WITH" for edge in world.edges)
    assert 140 <= counts["Company"] <= 160
    assert 230 <= counts["Person"] <= 270
    assert 35 <= partnerships <= 45
    assert 6 <= counts["Group"] <= 10


def test_unique_ids(world: World) -> None:
    entity_ids = [entity.id for entity in world.entities]
    edge_ids = [edge.id for edge in world.edges]
    assert len(set(entity_ids)) == len(entity_ids)
    assert len(set(edge_ids)) == len(edge_ids)
    known = set(entity_ids)
    assert all(edge.src in known and edge.dst in known for edge in world.edges)


def test_every_tbk_has_current_boards(world: World) -> None:
    listed = [company for company in _companies(world) if company.name.endswith("Tbk")]
    assert listed
    for company in listed:
        roles = Counter(
            edge.props["role"]
            for edge in world.edges
            if edge.type == "SERVES_AS" and edge.dst == company.id and edge.until is None
        )
        assert roles["Komisaris Utama"] == 1, company.name
        assert roles["Direktur Utama"] == 1, company.name
        assert roles["Komisaris Independen"] >= 1, company.name


def test_temporal_changes(world: World) -> None:
    changes = 0
    for edge in world.edges:
        if edge.type not in ("SERVES_AS", "OWNS_STAKE") or edge.until is None:
            continue
        assert edge.since is not None and edge.since < edge.until
        successors = [
            other
            for other in world.edges
            if other.id != edge.id
            and other.type == edge.type
            and other.dst == edge.dst
            and other.since == edge.until
            and other.src != edge.src
            and other.until is None
            and (edge.type == "OWNS_STAKE" or other.props["role"] == edge.props["role"])
        ]
        assert successors, edge.id
        changes += 1
    assert changes >= 20


def test_aliases(world: World) -> None:
    with_aliases = [company for company in _companies(world) if len(company.aliases) >= 2]
    assert len(with_aliases) >= 20
    for company in with_aliases:
        stripped = company.name.removeprefix("PT ").removesuffix(" Tbk")
        assert stripped in company.aliases
    owners = Counter(alias for company in _companies(world) for alias in set(company.aliases))
    assert max(owners.values()) == 1


def test_collisions(world: World) -> None:
    people = {entity.id: entity for entity in world.entities if entity.type == "Person"}
    assert len(world.collisions) >= 20
    for first, second in world.collisions:
        assert first != second
        assert people[first].name == people[second].name
        assert people[first].attrs["gender"] == people[second].attrs["gender"]


def test_gender_matches_first_name(world: World) -> None:
    for person in (entity for entity in world.entities if entity.type == "Person"):
        first = person.name.split()[0]
        female = person.attrs["gender"] == "F"
        names = IdNames.first_names_female if female else IdNames.first_names_male
        assert first in names, person.name


def test_parents_older_than_children(world: World) -> None:
    born = _born(world)
    pairs = [(e.src, e.dst) for e in _family(world, "parent")]
    pairs += [(e.dst, e.src) for e in _family(world, "child")]
    assert pairs and _family(world, "child") and _family(world, "in-law")
    for parent, child in pairs:
        assert 20 <= born[child] - born[parent] <= 35, (parent, child)


def test_spouses_plausible(world: World) -> None:
    people = {entity.id: entity for entity in world.entities if entity.type == "Person"}
    spouses = _family(world, "spouse")
    assert spouses
    for edge in spouses:
        first, second = people[edge.src], people[edge.dst]
        assert first.attrs["gender"] != second.attrs["gender"], edge.id
        assert abs(int(first.attrs["birth_year"]) - int(second.attrs["birth_year"])) <= 10


def test_founders_adult(world: World) -> None:
    born = _born(world)
    founded = [edge for edge in world.edges if edge.type == "FOUNDED"]
    assert founded
    for edge in founded:
        assert edge.since is not None and edge.since - born[edge.src] >= 22, edge.id


def test_appointees_adult(world: World) -> None:
    born = _born(world)
    for edge in world.edges:
        if edge.type == "SERVES_AS":
            assert edge.since is not None and edge.since - born[edge.src] >= 28, edge.id


def test_dirut_concurrency(world: World) -> None:
    seats = Counter(
        edge.src
        for edge in world.edges
        if edge.type == "SERVES_AS"
        and edge.until is None
        and edge.props["role"] == "Direktur Utama"
    )
    assert max(seats.values()) <= 2


def test_no_real_tickers(world: World) -> None:
    tickers = [str(c.attrs["ticker"]) for c in _companies(world) if "ticker" in c.attrs]
    assert tickers and not set(tickers) & REAL_TICKERS


def test_hidden_paths(world: World) -> None:
    edges = {edge.id: edge for edge in world.edges}
    direct = {frozenset((edge.src, edge.dst)) for edge in world.edges}
    companies = {company.id: company for company in _companies(world)}
    groups = {e.src: e.dst for e in world.edges if e.type == "MEMBER_OF_GROUP"}
    state = {c for c in companies if companies[c].attrs["bumn"]}

    def group(company_id: str) -> str:
        return "state" if company_id in state else groups.get(company_id, company_id)

    assert len(world.hidden_paths) >= 20
    for path in world.hidden_paths:
        assert 2 <= path.hops <= 4
        assert path.hops == len(path.edge_ids)
        assert path.start in companies and path.end in companies
        assert group(path.start) != group(path.end), path.id
        assert all(edges[edge_id].until is None for edge_id in path.edge_ids)
        assert len({edges[edge_id].type for edge_id in path.edge_ids}) >= 2
        assert _distance(world, path.start, path.end) == path.hops, path.id
        node = path.start
        for edge_id in path.edge_ids:
            edge = edges[edge_id]
            assert node in (edge.src, edge.dst), path.id
            node = edge.dst if edge.src == node else edge.src
        assert node == path.end
        assert frozenset((path.start, path.end)) not in direct


def test_blocklist(world: World) -> None:
    terms = [line.strip().lower() for line in BLOCKLIST.read_text().splitlines() if line.strip()]
    assert "salim" in terms and "danantara" in terms
    for entity in world.entities:
        for text in [entity.name, *entity.aliases]:
            assert not any(term in text.lower() for term in terms), text


def test_stakes_sum(world: World) -> None:
    totals: Counter[str] = Counter()
    for edge in world.edges:
        if edge.type == "OWNS_STAKE" and edge.until is None:
            totals[edge.dst] += edge.props["pct"]
    assert totals and max(totals.values()) <= 100
