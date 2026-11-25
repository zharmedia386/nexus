from dataclasses import dataclass, field
from itertools import combinations
from threading import Lock
from typing import Self, get_args

from neo4j import Driver, GraphDatabase

from nexus.config import get_settings
from nexus.datagen.models import EntityType, RelType
from nexus.eval.metrics import NAMED_TYPES, build_lexicon, normalize
from nexus.graph.communities import Community
from nexus.graph.resolve import ResolvedGraph
from nexus.vector.milvus_store import TENANT_PATTERN

BATCH = 1000
CONTEXT_RELS = ("IN_SECTOR", "HEADQUARTERED_IN", "IN_COMMUNITY", "CHILD_OF")
ENTITY_TYPES = frozenset(get_args(EntityType))
REL_TYPES = frozenset(get_args(RelType))
TRAVERSAL_RELS = sorted(REL_TYPES - set(CONTEXT_RELS))
MAX_PATH_PAIRS = 6
MEMBER_CAP = 50
SCHEMA = (
    (
        "CREATE CONSTRAINT entity_tenant_id IF NOT EXISTS "
        "FOR (e:Entity) REQUIRE (e.tenant_id, e.id) IS UNIQUE"
    ),
    "CREATE INDEX entity_tenant_name IF NOT EXISTS FOR (e:Entity) ON (e.tenant_id, e.name)",
)


@dataclass(frozen=True)
class PathHop:
    src_id: str
    src_name: str
    rel_type: str
    dst_id: str
    dst_name: str
    chunk_ids: list[str]
    quotes: list[str]
    doc_ids: list[str]
    # False when the stored edge points dst -> src (against the walk).
    forward: bool = True


@dataclass(frozen=True)
class GraphPath:
    node_ids: list[str]
    node_names: list[str]
    rel_types: list[str]
    chunk_ids: list[str]
    hops: list[PathHop] = field(default_factory=list)


def make_path(
    ids: list[str],
    names: list[str],
    rels: list[str],
    chunks: list[list[str]],
    quotes: list[list[str]] | None = None,
    doc_ids: list[list[str]] | None = None,
    starts: list[str] | None = None,
) -> GraphPath:
    # Hop i joins node i to node i+1; missing provenance arrays become empty per hop.
    empty: list[list[str]] = [[] for _ in rels]
    hops = [
        PathHop(
            ids[i],
            names[i],
            rel,
            ids[i + 1],
            names[i + 1],
            hop_chunks or [],
            hop_quotes or [],
            hop_docs or [],
            starts is None or starts[i] == ids[i],
        )
        for i, (rel, hop_chunks, hop_quotes, hop_docs) in enumerate(
            zip(rels, chunks, quotes or empty, doc_ids or empty, strict=True)
        )
    ]
    # Each hop's first provenance chunk leads, so a later top-N cut keeps every hop covered.
    leading = [hop_chunks[0] for hop_chunks in chunks if hop_chunks]
    rest = [chunk for hop_chunks in chunks for chunk in hop_chunks[1:]]
    return GraphPath(ids, names, rels, list(dict.fromkeys(leading + rest)), hops)


@dataclass(frozen=True)
class FrontierEdge:
    key: str
    type: str
    src_id: str
    src_name: str
    dst_id: str
    dst_name: str
    role: str | None
    relation: str | None
    pct: float | None
    since: int | None
    until: int | None
    chunk_ids: list[str]
    quotes: list[str] = field(default_factory=list)
    doc_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    src: str
    rel: str
    dst: str
    quote: str


def cap_evidence(found: set[Evidence] | list[Evidence], limit: int) -> list[Evidence]:
    groups: dict[str, list[Evidence]] = {}
    for item in sorted(found, key=lambda e: (e.rel, e.src, e.dst, e.chunk_id, e.quote)):
        groups.setdefault(item.rel, []).append(item)
    # Round-robin over rel types (fixed alphabetical order) so a cap never drops a whole type.
    queues = [groups[rel] for rel in sorted(groups)]
    capped: list[Evidence] = []
    for depth in range(max((len(queue) for queue in queues), default=0)):
        for queue in queues:
            if depth < len(queue) and len(capped) < limit:
                capped.append(queue[depth])
    return capped


def _batches[T](rows: list[T]) -> list[list[T]]:
    return [rows[start : start + BATCH] for start in range(0, len(rows), BATCH)]


class GraphStore:
    def __init__(self, driver: Driver | None = None) -> None:
        self._driver = driver
        self._lexicons: dict[str, dict[str, str]] = {}
        self._driver_lock = Lock()

    @property
    def driver(self) -> Driver:
        with self._driver_lock:
            if self._driver is None:
                settings = get_settings()
                self._driver = GraphDatabase.driver(
                    settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
            return self._driver

    def close(self) -> None:
        with self._driver_lock:
            if self._driver is not None:
                self._driver.close()
                self._driver = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @staticmethod
    def _validate(tenant: str) -> None:
        if not TENANT_PATTERN.fullmatch(tenant):
            raise ValueError(f"invalid tenant: {tenant!r}")

    def _run(self, query: str, **params: object) -> list[dict[str, object]]:
        records, _, _ = self.driver.execute_query(
            query, params, database_=get_settings().NEO4J_DATABASE
        )
        return [record.data() for record in records]

    def ensure_schema(self) -> None:
        for statement in SCHEMA:
            self._run(statement)

    def clear_tenant(self, tenant: str) -> None:
        self._validate(tenant)
        while True:
            deleted = self._run(
                "MATCH (e:Entity {tenant_id: $tenant}) WITH e LIMIT $batch "
                "DETACH DELETE e RETURN count(*) AS deleted",
                tenant=tenant,
                batch=BATCH,
            )[0]["deleted"]
            if not deleted:
                return

    def write_graph(self, tenant: str, graph: ResolvedGraph) -> dict[str, int]:
        self._validate(tenant)
        unknown = {entity.type for entity in graph.entities} - ENTITY_TYPES
        unknown |= {relation.type for relation in graph.relations} - REL_TYPES
        if unknown:
            raise ValueError(f"unknown graph types: {sorted(unknown)}")
        # Clear and writes are separate transactions by design: rebuilt from Postgres, CLI refuses partial extractions.
        self.clear_tenant(tenant)
        self.invalidate_lexicon(tenant)
        for entity_type in ENTITY_TYPES:
            rows = [
                {
                    "id": entity.id,
                    "name": entity.name,
                    "aliases": entity.aliases,
                    "chunk_ids": sorted({mention.chunk_id for mention in entity.mentions}),
                    "doc_ids": sorted({mention.doc_id for mention in entity.mentions}),
                }
                for entity in graph.entities
                if entity.type == entity_type
            ]
            for batch in _batches(rows):
                # Label comes from the allow-list above, never from input.
                self._run(
                    "UNWIND $rows AS row MERGE (e:Entity {tenant_id: $tenant, id: row.id}) "
                    "SET e.name = row.name, e.aliases = row.aliases, e.chunk_ids = row.chunk_ids, "
                    f"e.doc_ids = row.doc_ids, e:{entity_type}",
                    tenant=tenant,
                    rows=batch,
                )
        for rel_type in REL_TYPES:
            rows = [
                {
                    "src": relation.src_id,
                    "dst": relation.dst_id,
                    "role": relation.role,
                    "pct": relation.pct,
                    "relation": relation.relation,
                    "kind": relation.kind,
                    "since": relation.since,
                    "until": relation.until,
                    "chunk_ids": relation.chunk_ids,
                    "doc_ids": relation.doc_ids,
                    "quotes": relation.quotes,
                    # Offsets index the document body (documents.content), not the chunk.
                    "quote_starts": [start for start, _ in relation.quote_spans],
                    "quote_ends": [end for _, end in relation.quote_spans],
                }
                for relation in graph.relations
                if relation.type == rel_type
            ]
            for batch in _batches(rows):
                self._run(
                    "UNWIND $rows AS row "
                    "MATCH (a:Entity {tenant_id: $tenant, id: row.src}) "
                    "MATCH (b:Entity {tenant_id: $tenant, id: row.dst}) "
                    f"CREATE (a)-[r:{rel_type}]->(b) SET r = row, r.tenant_id = $tenant "
                    "REMOVE r.src, r.dst",
                    tenant=tenant,
                    rows=batch,
                )
        self.invalidate_lexicon(tenant)
        return self.counts(tenant)

    def counts(self, tenant: str) -> dict[str, int]:
        self._validate(tenant)
        nodes = self._run(
            "MATCH (e:Entity {tenant_id: $tenant}) RETURN count(e) AS n", tenant=tenant
        )[0]["n"]
        relationships = self._run(
            "MATCH (:Entity {tenant_id: $tenant})-[r {tenant_id: $tenant}]->(:Entity {tenant_id: $tenant}) RETURN count(r) AS n",
            tenant=tenant,
        )[0]["n"]
        return {"nodes": nodes, "relationships": relationships}

    def stats(self, tenant: str) -> dict[str, object]:
        self._validate(tenant)
        by_type = {
            str(row["type"]): row["n"]
            for row in self._run(
                "MATCH (e:Entity {tenant_id: $tenant}) "
                "WITH [label IN labels(e) WHERE label IN $types][0] AS type, count(e) AS n "
                "WHERE type IS NOT NULL RETURN type, n ORDER BY type",
                tenant=tenant,
                types=sorted(ENTITY_TYPES),
            )
        }
        # Most connected entities by non-context relations: the default centre for the explorer.
        top = self._run(
            "MATCH (e:Entity {tenant_id: $tenant})-[r {tenant_id: $tenant}]-(:Entity {tenant_id: $tenant}) "
            "WHERE NOT type(r) IN $context "
            "WITH e, count(r) AS degree "
            "RETURN e.id AS id, e.name AS name, [label IN labels(e) WHERE label IN $types][0] AS type, degree "
            "ORDER BY degree DESC, id LIMIT 5",
            tenant=tenant,
            context=list(CONTEXT_RELS),
            types=sorted(ENTITY_TYPES),
        )
        return {**self.counts(tenant), "by_type": by_type, "top": [dict(row) for row in top]}

    def read_entity_graph(self, tenant: str) -> tuple[list[str], list[tuple[str, str]]]:
        self._validate(tenant)
        nodes = self._run(
            "MATCH (e:Entity {tenant_id: $tenant}) RETURN e.id AS id ORDER BY id", tenant=tenant
        )
        edges = self._run(
            "MATCH (a:Entity {tenant_id: $tenant})-[r {tenant_id: $tenant}]->(b:Entity {tenant_id: $tenant}) "
            "WHERE NOT type(r) IN $context RETURN a.id AS src, b.id AS dst",
            tenant=tenant,
            context=list(CONTEXT_RELS),
        )
        return [row["id"] for row in nodes], [(row["src"], row["dst"]) for row in edges]  # type: ignore[misc]

    def write_communities(self, tenant: str, communities: list[Community]) -> int:
        self._validate(tenant)
        self._run("MATCH (c:Community {tenant_id: $tenant}) DETACH DELETE c", tenant=tenant)
        for batch in _batches(
            [
                {"id": c.id, "level": c.level, "size": len(c.member_ids), "parent": c.parent_id}
                for c in communities
            ]
        ):
            self._run(
                "UNWIND $rows AS row "
                "CREATE (c:Community {tenant_id: $tenant, id: row.id, level: row.level, size: row.size})",
                tenant=tenant,
                rows=batch,
            )
            self._run(
                "UNWIND $rows AS row WITH row WHERE row.parent IS NOT NULL "
                "MATCH (c:Community {tenant_id: $tenant, id: row.id}) "
                "MATCH (p:Community {tenant_id: $tenant, id: row.parent}) "
                "CREATE (c)-[:CHILD_OF {tenant_id: $tenant}]->(p)",
                tenant=tenant,
                rows=batch,
            )
        memberships = [
            {"community": c.id, "entity": entity_id}
            for c in communities
            for entity_id in c.member_ids
        ]
        for batch in _batches(memberships):
            self._run(
                "UNWIND $rows AS row "
                "MATCH (e:Entity {tenant_id: $tenant, id: row.entity}) "
                "MATCH (c:Community {tenant_id: $tenant, id: row.community}) "
                "CREATE (e)-[:IN_COMMUNITY {tenant_id: $tenant}]->(c)",
                tenant=tenant,
                rows=batch,
            )
        return len(communities)

    def read_communities(self, tenant: str) -> list[Community]:
        self._validate(tenant)
        rows = self._run(
            "MATCH (c:Community {tenant_id: $tenant}) "
            "OPTIONAL MATCH (c)-[:CHILD_OF]->(p:Community {tenant_id: $tenant}) "
            "CALL (c) { MATCH (e:Entity {tenant_id: $tenant})-[:IN_COMMUNITY]->(c) "
            "RETURN collect(e.id) AS members } "
            "RETURN c.id AS id, c.level AS level, p.id AS parent, members "
            "ORDER BY level, id",
            tenant=tenant,
        )
        return [
            Community(row["id"], row["level"], row["parent"], sorted(row["members"]))  # type: ignore[arg-type, type-var]
            for row in rows
        ]

    def community_evidence(self, tenant: str, community_id: str, limit: int = 60) -> list[Evidence]:
        self._validate(tenant)
        rows = self._run(
            "MATCH (c:Community {tenant_id: $tenant, id: $community}) "
            "MATCH (a:Entity {tenant_id: $tenant})-[:IN_COMMUNITY]->(c) "
            "MATCH (a)-[r {tenant_id: $tenant}]->(b:Entity {tenant_id: $tenant})-[:IN_COMMUNITY]->(c) "
            "WHERE NOT type(r) IN $context "
            "RETURN a.name AS src, type(r) AS rel, b.name AS dst, "
            "r.chunk_ids AS chunk_ids, r.quotes AS quotes",
            tenant=tenant,
            community=community_id,
            context=list(CONTEXT_RELS),
        )
        # chunk_ids and quotes are parallel arrays: one provenance entry per pair.
        found = {
            Evidence(chunk_id, row["src"], row["rel"], row["dst"], quote)  # type: ignore[arg-type]
            for row in rows
            for chunk_id, quote in zip(row["chunk_ids"], row["quotes"], strict=True)  # type: ignore[call-overload]
        }
        return cap_evidence(found, limit)

    def write_community_summary(
        self, tenant: str, community_id: str, title: str, summary: str, chunk_ids: list[str]
    ) -> None:
        self._validate(tenant)
        self._run(
            "MATCH (c:Community {tenant_id: $tenant, id: $community}) "
            "SET c.title = $title, c.summary = $summary, c.summary_chunk_ids = $chunk_ids",
            tenant=tenant,
            community=community_id,
            title=title,
            summary=summary,
            chunk_ids=chunk_ids,
        )

    def invalidate_lexicon(self, tenant: str) -> None:
        self._lexicons.pop(tenant, None)

    def entity_lexicon(self, tenant: str) -> dict[str, str]:
        self._validate(tenant)
        if tenant in self._lexicons:
            return self._lexicons[tenant]
        rows = self._run(
            "MATCH (e:Entity {tenant_id: $tenant}) "
            "WHERE any(label IN labels(e) WHERE label IN $types) "
            "RETURN e.id AS id, e.name AS name, e.aliases AS aliases",
            tenant=tenant,
            types=sorted(NAMED_TYPES),
        )
        self._lexicons[tenant] = build_lexicon(
            (row["id"], [row["name"], *(row["aliases"] or [])])  # type: ignore[misc]
            for row in rows
        )
        return self._lexicons[tenant]

    def entities_in_chunks(self, tenant: str, chunk_ids: list[str], limit: int = 3) -> list[str]:
        self._validate(tenant)
        rows = self._run(
            "MATCH (e:Entity {tenant_id: $tenant}) "
            "WHERE any(label IN labels(e) WHERE label IN $types) "
            "WITH e, size([chunk IN e.chunk_ids WHERE chunk IN $chunks]) AS hits WHERE hits > 0 "
            "RETURN e.id AS id ORDER BY hits DESC, id LIMIT $limit",
            tenant=tenant,
            types=sorted(NAMED_TYPES),
            chunks=chunk_ids,
            limit=limit,
        )
        return [row["id"] for row in rows]  # type: ignore[misc]

    def paths_between(self, tenant: str, ids: list[str], max_hops: int = 4) -> list[GraphPath]:
        self._validate(tenant)
        if not 1 <= max_hops <= 4:
            raise ValueError(f"max_hops must be 1..4: {max_hops!r}")
        paths = []
        for src, dst in list(combinations(dict.fromkeys(ids), 2))[:MAX_PATH_PAIRS]:
            # max_hops is a validated int; Cypher cannot parameterize path length.
            rows = self._run(
                "MATCH (a:Entity {tenant_id: $tenant, id: $src}), "
                "(b:Entity {tenant_id: $tenant, id: $dst}) "
                f"MATCH p = shortestPath((a)-[*..{max_hops}]-(b)) "
                "WHERE all(r IN relationships(p) WHERE type(r) IN $types) "
                "AND all(n IN nodes(p) WHERE n.tenant_id = $tenant) "
                "RETURN [n IN nodes(p) | n.id] AS ids, [n IN nodes(p) | n.name] AS names, "
                "[r IN relationships(p) | type(r)] AS rels, "
                "[r IN relationships(p) | r.chunk_ids] AS chunks, "
                "[r IN relationships(p) | r.quotes] AS quotes, "
                "[r IN relationships(p) | r.doc_ids] AS doc_ids, "
                "[r IN relationships(p) | startNode(r).id] AS starts",
                tenant=tenant,
                src=src,
                dst=dst,
                types=TRAVERSAL_RELS,
            )
            paths.extend(make_path(**row) for row in rows)  # type: ignore[arg-type]
        return paths

    def neighbourhood(self, tenant: str, ids: list[str], limit: int = 40) -> list[GraphPath]:
        self._validate(tenant)
        rows = self._run(
            "MATCH (a:Entity {tenant_id: $tenant})-[r]-(b:Entity {tenant_id: $tenant}) "
            "WHERE a.id IN $ids AND type(r) IN $types "
            "RETURN [a.id, b.id] AS ids, [a.name, b.name] AS names, [type(r)] AS rels, "
            "[r.chunk_ids] AS chunks, [r.quotes] AS quotes, [r.doc_ids] AS doc_ids, "
            "[startNode(r).id] AS starts ORDER BY a.id, rels, b.id, chunks LIMIT $limit",
            tenant=tenant,
            ids=ids,
            types=TRAVERSAL_RELS,
            limit=limit,
        )
        return [make_path(**row) for row in rows]  # type: ignore[arg-type]

    def frontier_edges(
        self, tenant: str, entity_ids: list[str], limit: int = 40, exclude: list[str] | None = None
    ) -> list[FrontierEdge]:
        self._validate(tenant)
        if not entity_ids:
            return []
        rows = self._run(
            "MATCH (a:Entity {tenant_id: $tenant}) WHERE a.id IN $ids "
            "CALL (a) { "
            "MATCH (a)-[r]-(b:Entity {tenant_id: $tenant}) "
            "WHERE type(r) IN $types AND NOT elementId(r) IN $exclude "
            "WITH r, b ORDER BY type(r), b.id, r.since, elementId(r) "
            "RETURN collect(r)[..$limit] AS rels } "
            # Round-robin by per-entity rank so a hub cannot crowd out quieter frontier entities.
            "UNWIND range(0, size(rels) - 1) AS rank "
            "WITH rels[rank] AS r, rank "
            "WITH r, min(rank) AS rank "
            "WITH r, rank, startNode(r) AS s, endNode(r) AS e "
            "RETURN elementId(r) AS key, type(r) AS type, s.id AS src_id, s.name AS src_name, "
            "e.id AS dst_id, e.name AS dst_name, r.role AS role, r.relation AS relation, "
            "r.pct AS pct, r.since AS since, r.until AS until, r.chunk_ids AS chunk_ids, "
            "coalesce(r.quotes, []) AS quotes, coalesce(r.doc_ids, []) AS doc_ids "
            "ORDER BY rank, src_id, type, dst_id, since, key LIMIT $limit",
            tenant=tenant,
            ids=entity_ids,
            types=TRAVERSAL_RELS,
            exclude=exclude or [],
            limit=limit,
        )
        return [FrontierEdge(**row) for row in rows]  # type: ignore[arg-type]

    def entity_node(self, tenant: str, entity_id: str) -> dict[str, object] | None:
        self._validate(tenant)
        rows = self._run(
            "MATCH (e:Entity {tenant_id: $tenant, id: $id}) "
            "RETURN e.id AS id, e.name AS name, "
            "[label IN labels(e) WHERE label IN $types][0] AS type, "
            "coalesce(e.aliases, []) AS aliases, coalesce(e.chunk_ids, []) AS chunk_ids",
            tenant=tenant,
            id=entity_id,
            types=sorted(ENTITY_TYPES),
        )
        return rows[0] if rows else None

    def entity_edges(self, tenant: str, entity_id: str, limit: int = 40) -> list[dict[str, object]]:
        self._validate(tenant)
        return self._run(
            "MATCH (a:Entity {tenant_id: $tenant, id: $id})-[r]-(b:Entity {tenant_id: $tenant}) "
            "WHERE type(r) IN $types "
            "RETURN type(r) AS type, startNode(r).id = a.id AS outgoing, "
            "r.role AS role, r.relation AS relation, r.pct AS pct, r.since AS since, "
            "r.until AS until, b.id AS other_id, b.name AS other_name, "
            "[label IN labels(b) WHERE label IN $entity_types][0] AS other_type, "
            "coalesce(r.chunk_ids, []) AS chunk_ids, coalesce(r.quotes, []) AS quotes "
            "ORDER BY type, other_id, since, elementId(r) LIMIT $limit",
            tenant=tenant,
            id=entity_id,
            types=TRAVERSAL_RELS,
            entity_types=sorted(ENTITY_TYPES),
            limit=limit,
        )

    def list_communities(self, tenant: str, level: int) -> list[dict[str, object]]:
        self._validate(tenant)
        return self._run(
            "MATCH (c:Community {tenant_id: $tenant, level: $level}) "
            "OPTIONAL MATCH (c)-[:CHILD_OF]->(p:Community {tenant_id: $tenant}) "
            "CALL (c) { MATCH (e:Entity {tenant_id: $tenant})-[:IN_COMMUNITY]->(c) "
            "WITH e ORDER BY e.name, e.id "
            "RETURN collect(e.id) AS member_ids, collect(e.name) AS member_names } "
            "RETURN c.id AS id, c.level AS level, c.size AS size, c.title AS title, "
            "c.summary AS summary, p.id AS parent_id, "
            "member_ids[..$cap] AS member_ids, member_names[..$cap] AS member_names, "
            "coalesce(c.summary_chunk_ids, []) AS summary_chunk_ids "
            "ORDER BY size DESC, id",
            tenant=tenant,
            level=level,
            cap=MEMBER_CAP,
        )

    def search_entities(self, tenant: str, text: str, limit: int = 10) -> list[dict[str, object]]:
        self._validate(tenant)
        needle = normalize(text)
        if not needle:
            return []
        # shortcut: full tenant scan per search, upgrade to a fulltext index when the corpus grows.
        rows = self._run(
            "MATCH (e:Entity {tenant_id: $tenant}) "
            "RETURN e.id AS id, e.name AS name, "
            "[label IN labels(e) WHERE label IN $types][0] AS type, "
            "coalesce(e.aliases, []) AS aliases",
            tenant=tenant,
            types=sorted(ENTITY_TYPES),
        )
        ranked = []
        for row in rows:
            forms = [normalize(row["name"]), *map(normalize, row["aliases"])]  # type: ignore[arg-type, union-attr]
            if needle in forms:
                rank, match = 0, "exact"
            elif any(form.startswith(needle) for form in forms):
                rank, match = 1, "prefix"
            elif any(needle in form for form in forms):
                rank, match = 2, "substring"
            else:
                continue
            ranked.append((rank, str(row["name"]), {**row, "match": match}))
        ranked.sort(key=lambda item: item[:2])
        return [item[2] for item in ranked[:limit]]
