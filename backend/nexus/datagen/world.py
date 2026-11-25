import random
from collections import defaultdict, deque

from faker import Faker

from nexus.datagen.models import Edge, Entity, EntityType, HiddenPath, RelType, World
from nexus.datagen.names import HOLDING_SUFFIXES, company_stem, person_name, ticker

SECTORS = {
    "perbankan": "Perbankan",
    "tambang": "Tambang/Nikel",
    "sawit": "Sawit",
    "properti": "Properti",
    "telekomunikasi": "Telekomunikasi",
    "logistik": "Logistik",
    "consumer_goods": "Consumer Goods",
    "fintech": "Fintech",
    "energi": "Energi",
}
STATE_SECTORS = ["perbankan", "energi", "tambang", "telekomunikasi", "logistik"]
LOCATIONS = {
    "jakarta": ("Jakarta", "DKI Jakarta"),
    "surabaya": ("Surabaya", "Jawa Timur"),
    "bandung": ("Bandung", "Jawa Barat"),
    "semarang": ("Semarang", "Jawa Tengah"),
    "medan": ("Medan", "Sumatera Utara"),
    "pekanbaru": ("Pekanbaru", "Riau"),
    "palembang": ("Palembang", "Sumatera Selatan"),
    "batam": ("Batam", "Kepulauan Riau"),
    "balikpapan": ("Balikpapan", "Kalimantan Timur"),
    "makassar": ("Makassar", "Sulawesi Selatan"),
    "kendari": ("Kendari", "Sulawesi Tenggara"),
    "denpasar": ("Denpasar", "Bali"),
}
GROUPS = 8
MEMBERS_PER_GROUP = 12
STATE_MEMBERS = 11
INDEPENDENTS = 26
PEOPLE = 250
PARTNERSHIPS = 40
INVESTMENTS = 12
MALE_COLLISIONS = 12
FEMALE_COLLISIONS = 8
ROLE_CHANGES = 16
STAKE_SALES = 6
HIDDEN_PATHS = 20
LAST_CHANGE_YEAR = 2025
MIN_SEAT_AGE = 28
MIN_FOUNDER_AGE = 22
MIN_BUYER_AGE = 25
MAX_DIRUT_SEATS = 2
FAMILY_ROLES = ("Komisaris Utama", "Komisaris", "Direktur Utama")
PATH_TYPES = ("FAMILY_OF", "SERVES_AS", "OWNS_STAKE", "SUBSIDIARY_OF")
NON_RELATION_TYPES = ("IN_SECTOR", "HEADQUARTERED_IN")


class _WorldBuilder:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.faker = Faker("id_ID")
        self.faker.seed_instance(self.rng.randrange(2**32))
        self.entities: dict[str, Entity] = {}
        self.edges: list[Edge] = []
        self.stems: set[str] = set()
        self.tickers: set[str] = set()
        self.person_names: set[str] = set()
        self.group_of: dict[str, str] = {}
        self.board: dict[str, set[str]] = defaultdict(set)
        self.dirut_seats: dict[str, int] = defaultdict(int)
        self.stake_room: dict[str, int] = defaultdict(lambda: 100)
        self.families: list[list[str]] = []
        self.professionals: list[str] = []
        self.collisions: list[tuple[str, str]] = []

    def entity(
        self, entity_id: str, entity_type: EntityType, name: str, **attrs: str | int | bool
    ) -> str:
        self.entities[entity_id] = Entity(id=entity_id, type=entity_type, name=name, attrs=attrs)
        return entity_id

    def edge(
        self, rel_type: RelType, src: str, dst: str, since: int | None = None, **props: str | int
    ) -> Edge:
        edge_id = f"ed_{len(self.edges) + 1:05d}"
        edge = Edge(id=edge_id, type=rel_type, src=src, dst=dst, props=props, since=since)
        self.edges.append(edge)
        return edge

    def found(self, person_id: str, company_id: str) -> None:
        founded = int(self.entities[company_id].attrs["founded"])
        self.edge("FOUNDED", person_id, company_id, since=founded)

    def since(self, company_id: str) -> int:
        founded = int(self.entities[company_id].attrs["founded"])
        return self.rng.randint(max(2005, founded + 1), 2021)

    def born(self, person_id: str) -> int:
        return int(self.entities[person_id].attrs["birth_year"])

    def company(
        self,
        sector: str | None,
        listed: bool,
        kind: str,
        suffix: str = "",
        bumn: bool = False,
        earliest_founding: int = 0,
    ) -> str:
        stem = company_stem(self.rng, self.stems)
        base = f"{stem} {suffix}".strip()
        name = f"PT {base} Tbk" if listed else f"PT {base}"
        low, high = (2008, 2016) if sector == "fintech" else (1975, 2004)
        founded = self.rng.randint(max(low, earliest_founding), high)
        company_id = f"co_{sum(e.type == 'Company' for e in self.entities.values()) + 1:04d}"
        attrs: dict[str, str | int | bool] = {
            "kind": kind,
            "listed": listed,
            "bumn": bumn,
            "founded": founded,
        }
        aliases = [base]
        if listed:
            code = ticker(stem, self.rng, self.tickers)
            attrs["ticker"] = code
            aliases.append(code)
        self.entity(company_id, "Company", name, **attrs)
        self.entities[company_id].aliases = aliases
        if sector:
            self.edge("IN_SECTOR", company_id, f"se_{sector}")
        location = "jakarta" if kind != "operating" else self.rng.choice(sorted(LOCATIONS))
        self.edge("HEADQUARTERED_IN", company_id, f"lo_{location}")
        return company_id

    def person(self, female: bool, birth_year: int, surname: str | None = None) -> str:
        name = person_name(self.faker, female, surname)
        while name in self.person_names:
            name = person_name(self.faker, female, surname)
        self.person_names.add(name)
        person_id = f"pe_{sum(e.type == 'Person' for e in self.entities.values()) + 1:04d}"
        return self.entity(
            person_id,
            "Person",
            name,
            gender="F" if female else "M",
            birth_year=birth_year,
        )

    def stake(self, owner: str, target: str, pct: int) -> None:
        pct = min(pct, self.stake_room[target])
        if pct > 0:
            self.stake_room[target] -= pct
            self.edge("OWNS_STAKE", owner, target, since=self.since(target), pct=pct)

    def pick(self, pool: list[str], company_id: str, role: str, year: int) -> str:
        def eligible(person: str) -> bool:
            return (
                person not in self.board[company_id]
                and self.born(person) + MIN_SEAT_AGE <= year
                and (role != "Direktur Utama" or self.dirut_seats[person] < MAX_DIRUT_SEATS)
            )

        candidates = [p for p in pool if eligible(p)] or [
            p for p in self.professionals if eligible(p)
        ]
        if not candidates:
            raise RuntimeError(f"no eligible person for {role} at {company_id} in {year}")
        chosen = self.rng.choice(candidates)
        self.board[company_id].add(chosen)
        if role == "Direktur Utama":
            self.dirut_seats[chosen] += 1
        return chosen

    def staff_board(self, company_id: str, family: list[str]) -> None:
        roles = ["Komisaris Utama", "Direktur Utama"]
        if self.entities[company_id].attrs["listed"]:
            roles += ["Komisaris Independen"] * self.rng.randint(1, 2) + ["Direktur Keuangan"]
            roles += ["Komisaris"] if self.rng.random() < 0.5 else []
            roles += ["Direktur Operasional"] if self.rng.random() < 0.5 else []
        elif self.rng.random() < 0.5:
            roles.append("Direktur")
        for role in roles:
            use_family = family and role in FAMILY_ROLES and self.rng.random() < 0.5
            year = self.since(company_id)
            pool = family if use_family else self.professionals
            person = self.pick(pool, company_id, role, year)
            self.edge("SERVES_AS", person, company_id, since=year, role=role)

    def build_reference(self) -> None:
        for key, name in SECTORS.items():
            self.entity(f"se_{key}", "Sector", name)
        for key, (city, province) in LOCATIONS.items():
            self.entity(f"lo_{key}", "Location", city, province=province)

    def build_people(self) -> None:
        for _ in range(GROUPS):
            # Children share one birth window so cross-family marriages stay age-plausible.
            son_year = self.rng.randint(1966, 1970)
            founder_year = son_year - self.rng.randint(25, 32)
            founder = self.person(False, founder_year)
            surname = self.entities[founder].name.split()[-1]
            # Spouse stays <=34 years older than the son so a daughter still fits the 20..35 gap.
            age_gap = son_year - founder_year
            spouse_gap = self.rng.randint(max(-3, age_gap - 34), min(8, age_gap - 20))
            spouse_year = founder_year + spouse_gap
            spouse = self.person(True, spouse_year)
            son = self.person(False, son_year, surname)
            oldest_parent = min(founder_year, spouse_year)
            daughter_offset = self.rng.randint(1, min(4, oldest_parent + 35 - son_year))
            daughter = self.person(True, son_year + daughter_offset, surname)
            self.edge("FAMILY_OF", founder, spouse, relation="spouse")
            self.edge("FAMILY_OF", founder, son, relation="parent")
            self.edge("FAMILY_OF", founder, daughter, relation="parent")
            self.edge("FAMILY_OF", spouse, son, relation="parent")
            self.edge("FAMILY_OF", daughter, spouse, relation="child")
            self.edge("FAMILY_OF", son, daughter, relation="sibling")
            self.families.append([founder, spouse, son, daughter])
        family_count = sum(len(family) for family in self.families)
        self.professionals = [
            self.person(self.rng.random() < 0.35, self.rng.randint(1950, 1990))
            for _ in range(PEOPLE - family_count)
        ]
        # Cross-family marriages (son of i weds daughter of i+1) bridge groups for hidden paths.
        for index, family in enumerate(self.families):
            next_family = self.families[(index + 1) % GROUPS]
            self.edge("FAMILY_OF", family[2], next_family[3], relation="spouse")
            self.edge("FAMILY_OF", next_family[0], family[2], relation="in-law")
        for gender, count in (("M", MALE_COLLISIONS), ("F", FEMALE_COLLISIONS)):
            same = [p for p in self.professionals if self.entities[p].attrs["gender"] == gender]
            chosen = self.rng.sample(same, count * 2)
            for first, second in zip(chosen[:count], chosen[count:], strict=True):
                self.entities[second].name = self.entities[first].name
                self.collisions.append((min(first, second), max(first, second)))
        self.collisions.sort()

    def build_groups(self) -> None:
        sector_keys = sorted(SECTORS)
        for index, family in enumerate(self.families):
            founder, spouse, first_child, second_child = family
            group_id = f"gr_{index + 1:02d}"
            holding = self.company(None, False, "holding", self.rng.choice(HOLDING_SUFFIXES[:2]))
            nominee = self.company(None, False, "nominee", self.rng.choice(HOLDING_SUFFIXES[1:]))
            stem = self.entities[holding].aliases[0].rsplit(" ", 1)[0]
            self.entity(group_id, "Group", f"{stem} Group", founder=founder)
            self.entities[group_id].aliases = [f"Grup {stem}"]
            self.found(founder, holding)
            for owner, pct in ((founder, 60), (first_child, 20), (second_child, 20)):
                self.stake(owner, holding, pct)
            for owner, pct in ((spouse, 50), (first_child, 25), (second_child, 25)):
                self.stake(owner, nominee, pct)
            core_sectors = self.rng.sample(sector_keys, 3)
            members = [
                self.company(self.rng.choice(core_sectors), self.rng.random() < 0.4, "operating")
                for _ in range(MEMBERS_PER_GROUP)
            ]
            for company_id in [holding, nominee, *members]:
                self.group_of[company_id] = group_id
                self.edge("MEMBER_OF_GROUP", company_id, group_id)
                self.staff_board(company_id, family)
            for position, member in enumerate(members):
                listed = bool(self.entities[member].attrs["listed"])
                self.stake(holding, member, self.rng.randint(51, 80 if listed else 100))
                self.edge("SUBSIDIARY_OF", member, holding, since=self.since(member))
                if listed:
                    self.stake(nominee, member, self.rng.randint(3, 9))
                if position < 3:
                    self.found(founder, member)

    def build_state_and_independents(self) -> None:
        state = self.company(None, False, "state_holding", "(Persero)", bumn=True)
        self.group_of[state] = state
        self.staff_board(state, [])
        for _ in range(STATE_MEMBERS):
            sector = self.rng.choice(STATE_SECTORS)
            member = self.company(sector, self.rng.random() < 0.5, "operating", bumn=True)
            self.group_of[member] = state
            self.staff_board(member, [])
            self.stake(state, member, self.rng.randint(51, 70))
            self.edge("SUBSIDIARY_OF", member, state, since=self.since(member))
        sector_keys = sorted(SECTORS)
        for index in range(INDEPENDENTS):
            sector = "fintech" if index < 5 else self.rng.choice(sector_keys)
            # Founder is chosen first so the founding year can respect their age.
            founder = self.rng.choice([p for p in self.professionals if self.born(p) <= 1980])
            company_id = self.company(
                sector,
                self.rng.random() < 0.25,
                "operating",
                earliest_founding=self.born(founder) + MIN_FOUNDER_AGE,
            )
            self.found(founder, company_id)
            self.stake(founder, company_id, self.rng.randint(20, 60))
            self.staff_board(company_id, [])
        # Nominee vehicles quietly cross-hold listed companies of other groups.
        listed = [cid for cid in self._companies() if self.entities[cid].attrs["listed"]]
        for cid in self._companies("nominee"):
            others = [other for other in listed if self.group_of.get(other) != self.group_of[cid]]
            self.stake(cid, self.rng.choice(others), self.rng.randint(2, 5))

    def build_links(self) -> None:
        operating = self._companies("operating")
        pairs: set[frozenset[str]] = set()
        while len(pairs) < PARTNERSHIPS:
            first, second = self.rng.sample(operating, 2)
            if frozenset((first, second)) in pairs:
                continue
            pairs.add(frozenset((first, second)))
            kind = self.rng.choice(["JV", "supply", "distribution"])
            self.edge("PARTNERS_WITH", first, second, since=self.rng.randint(2012, 2025), kind=kind)
        investors = self._companies("holding") + self._companies("nominee")
        fintech = [e.src for e in self.edges if e.type == "IN_SECTOR" and e.dst == "se_fintech"]
        deals: set[tuple[str, str]] = set()
        while len(deals) < INVESTMENTS:
            deal = (self.rng.choice(investors), self.rng.choice(fintech))
            if deal in deals:
                continue
            deals.add(deal)
            self.edge(
                "INVESTED_IN",
                *deal,
                since=self.rng.randint(2016, 2025),
                round=self.rng.choice(["Seed", "Seri A", "Seri B", "Seri C"]),
                amount_idr_bn=self.rng.randint(5, 500),
            )

    def build_temporal_changes(self) -> None:
        seats = [e for e in self.edges if e.type == "SERVES_AS"]
        for seat in self.rng.sample(seats, ROLE_CHANGES):
            assert seat.since is not None
            seat.until = self.rng.randint(seat.since + 1, LAST_CHANGE_YEAR)
            role = str(seat.props["role"])
            successor = self.pick(self.professionals, seat.dst, role, seat.until)
            self.board[seat.dst].discard(seat.src)
            if role == "Direktur Utama":
                self.dirut_seats[seat.src] -= 1
            self.edge("SERVES_AS", successor, seat.dst, since=seat.until, role=role)
        # Only minority/person stakes change hands; holding majorities stay tied to SUBSIDIARY_OF.
        sellable = [
            e
            for e in self.edges
            if e.type == "OWNS_STAKE"
            and (self.entities[e.src].type == "Person" or self._kind(e.src) == "nominee")
        ]
        for sale in self.rng.sample(sellable, STAKE_SALES):
            assert sale.since is not None
            sale.until = self.rng.randint(sale.since + 1, LAST_CHANGE_YEAR)
            owners = {e.src for e in self.edges if e.type == "OWNS_STAKE" and e.dst == sale.dst}
            buyer = self.rng.choice(
                [
                    p
                    for p in self.professionals
                    if p not in owners and self.born(p) + MIN_BUYER_AGE <= sale.until
                ]
            )
            self.edge("OWNS_STAKE", buyer, sale.dst, since=sale.until, pct=int(sale.props["pct"]))

    def plant_hidden_paths(self) -> list[HiddenPath]:
        adjacency: dict[str, list[tuple[Edge, str]]] = defaultdict(list)
        for edge in self.edges:
            if edge.type in PATH_TYPES and edge.until is None:
                adjacency[edge.src].append((edge, edge.dst))
                adjacency[edge.dst].append((edge, edge.src))
        direct = {frozenset((edge.src, edge.dst)) for edge in self.edges}
        # Minimality is judged over every relationship edge, ended ones included.
        relations: dict[str, list[tuple[Edge, str]]] = defaultdict(list)
        for edge in self.edges:
            if edge.type not in NON_RELATION_TYPES:
                relations[edge.src].append((edge, edge.dst))
                relations[edge.dst].append((edge, edge.src))
        companies = self._companies()
        company_set = set(companies)
        relatives = {person for family in self.families for person in family}
        # Longer paths start at a family-linked company and must cross a FAMILY_OF hop.
        family_linked = [c for c in companies if any(n in relatives for _, n in adjacency[c])]
        paths: list[HiddenPath] = []
        pairs: set[frozenset[str]] = set()
        for _ in range(200_000):
            if len(paths) == HIDDEN_PATHS:
                return paths
            hops = 2 + len(paths) % 3
            needs_family = hops > 2
            start = node = self.rng.choice(family_linked if needs_family else companies)
            visited, used = [start], []
            for _ in range(hops):
                options = [(edge, nxt) for edge, nxt in adjacency[node] if nxt not in visited]
                if not options:
                    break
                edge, node = self.rng.choice(options)
                used.append(edge)
                visited.append(node)
            pair = frozenset((start, node))
            if (
                len(used) == hops
                and node in company_set
                and self._group_key(start) != self._group_key(node)
                and pair not in direct
                and pair not in pairs
                and len({edge.type for edge in used}) >= 2
                and (not needs_family or any(edge.type == "FAMILY_OF" for edge in used))
                and _distance(relations, start, node) == hops
            ):
                pairs.add(pair)
                paths.append(
                    HiddenPath(
                        id=f"hp_{len(paths) + 1:02d}",
                        edge_ids=[edge.id for edge in used],
                        start=start,
                        end=node,
                        hops=hops,
                    )
                )
        raise RuntimeError("could not plant enough hidden paths")

    def _kind(self, entity_id: str) -> str | None:
        kind = self.entities[entity_id].attrs.get("kind")
        return str(kind) if kind is not None else None

    def _companies(self, kind: str | None = None) -> list[str]:
        return [
            entity.id
            for entity in self.entities.values()
            if entity.type == "Company" and (kind is None or entity.attrs["kind"] == kind)
        ]

    def _group_key(self, company_id: str) -> str:
        return self.group_of.get(company_id, company_id)


def _distance(adjacency: dict[str, list[tuple[Edge, str]]], start: str, end: str) -> int:
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        node, depth = queue.popleft()
        if node == end:
            return depth
        for _, nxt in adjacency[node]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, depth + 1))
    return -1


def build_world(seed: int = 42) -> World:
    builder = _WorldBuilder(seed)
    builder.build_reference()
    builder.build_people()
    builder.build_groups()
    builder.build_state_and_independents()
    builder.build_links()
    builder.build_temporal_changes()
    hidden_paths = builder.plant_hidden_paths()
    return World(
        seed=seed,
        entities=list(builder.entities.values()),
        edges=builder.edges,
        hidden_paths=hidden_paths,
        collisions=builder.collisions,
    )
