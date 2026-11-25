import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from nexus.datagen.models import Edge, World
from nexus.datagen.planner import BLOOD_RELATIONS, DocPlan, Lang
from nexus.datagen.reference import REFERENCE_DOC_ID, TICKER
from nexus.datagen.world import LAST_CHANGE_YEAR

Category = Literal[
    "single_hop", "multi_hop_2", "multi_hop_3", "temporal", "unanswerable", "thematic"
]

ALIAS_RATE = 0.2
EN_RATE = 0.4
SINGLE_PER_TEMPLATE = 10
TEMPORAL_COUNT = 24
UNANSWERABLE_PER_TEMPLATE = 6
THEMATIC_EN_RATE = 0.5
THEMATIC_GOLD_CAP = 15
SECTOR_MAX_COMPANIES = 15
SECTOR_DOC_CAP = 20
UNIQUE_ROLES = ("Direktur Utama", "Komisaris Utama", "Direktur Keuangan")
ABSENT_ROLE = "Direktur Pemasaran"
OPEN_END = 10_000
# multi_hop_3 means "3+ hops": the world plants 2-, 3- and 4-hop paths.
HOP_CATEGORY: dict[int, Category] = {2: "multi_hop_2", 3: "multi_hop_3", 4: "multi_hop_3"}
ID_PREFIX: dict[Category, str] = {
    "single_hop": "sh",
    "multi_hop_2": "m2",
    "multi_hop_3": "m3",
    "temporal": "tp",
    "unanswerable": "un",
    "thematic": "th",
}
INVERSE = {
    "parent": "child",
    "child": "parent",
    "spouse": "spouse",
    "sibling": "sibling",
    # Docs state in-law links without direction, so questions treat them as symmetric.
    "in-law": "in-law",
}

SINGLE: dict[str, dict[Lang, str]] = {
    "role": {
        "id": "Siapa {role} {subject} saat ini?",
        "en": "Who is the current {role} of {subject}?",
    },
    "parent": {
        "id": "Apa induk usaha {subject}?",
        "en": "What is the parent company of {subject}?",
    },
    "founder": {"id": "Siapa pendiri {subject}?", "en": "Who founded {subject}?"},
    "group": {
        "id": "Grup usaha apa yang menaungi {subject}?",
        "en": "Which business group does {subject} belong to?",
    },
}
TEMPORAL: dict[Lang, str] = {
    "id": "Siapa {role} {subject} pada tahun {year}?",
    "en": "Who was the {role} of {subject} in {year}?",
}
UNANSWERABLE: dict[str, dict[Lang, str]] = {
    "partner": {
        "id": "Apa bentuk kerja sama antara {a} dan {b}?",
        "en": "What kind of partnership do {a} and {b} have?",
    },
    "invest": {
        "id": "Berapa nilai investasi {a} di {b}?",
        "en": "How much did {a} invest in {b}?",
    },
    "founder": {"id": "Siapa pendiri {a}?", "en": "Who founded {a}?"},
    "role": {
        "id": f"Siapa {ABSENT_ROLE} {{a}} saat ini?",
        "en": "Who is the current Marketing Director of {a}?",
    },
}
# Hop phrases: (edge type, side reached) -> template; "src"/"dst" is the edge end we land on.
HOP_PHRASE: dict[tuple[str, str], dict[Lang, str]] = {
    ("SERVES_AS", "src"): {"id": "{role} {np}{since}", "en": "the {role} of {np}{since}"},
    ("SERVES_AS", "dst"): {
        "id": "perusahaan tempat {np} menjabat sebagai {role}{since}",
        "en": "the company where {np} serves as {role}{since}",
    },
    ("OWNS_STAKE", "src"): {
        "id": "pemegang{pct} saham {np}",
        "en": "the holder of a{pct} stake in {np}",
    },
    ("OWNS_STAKE", "dst"): {
        "id": "perusahaan tempat {np} memegang{pct} saham",
        "en": "the company in which {np} holds a{pct} stake",
    },
    ("SUBSIDIARY_OF", "src"): {"id": "anak usaha {np}", "en": "the subsidiary of {np}"},
    ("SUBSIDIARY_OF", "dst"): {"id": "induk usaha {np}", "en": "the parent company of {np}"},
}
FAMILY_PHRASE: dict[Lang, dict[str, str]] = {
    "id": {
        "parent": "orang tua {np}",
        "child": "anak {np}",
        "spouse": "pasangan {np}",
        "sibling": "saudara kandung {np}",
        "in-law": "kerabat semenda {np}",
    },
    "en": {
        "parent": "the parent of {np}",
        "child": "the child of {np}",
        "spouse": "the spouse of {np}",
        "sibling": "the sibling of {np}",
        "in-law": "the in-law relative of {np}",
    },
}
FINAL_PHRASE: dict[tuple[str, str], dict[Lang, str]] = {
    ("SERVES_AS", "dst"): {
        "id": "Di perusahaan mana {np} saat ini menjabat sebagai {role}{since}?",
        "en": "At which company does {np} currently serve as {role}{since}?",
    },
    ("OWNS_STAKE", "dst"): {
        "id": "Di perusahaan mana {np} saat ini memegang{pct} saham?",
        "en": "In which company does {np} currently hold a{pct} stake?",
    },
    ("OWNS_STAKE", "src"): {
        "id": "Perusahaan mana yang saat ini memegang{pct} saham {np}?",
        "en": "Which company currently holds a{pct} stake in {np}?",
    },
    ("SUBSIDIARY_OF", "dst"): {
        "id": "Apa induk usaha {np}?",
        "en": "What is the parent company of {np}?",
    },
    ("SUBSIDIARY_OF", "src"): {
        "id": "Perusahaan mana yang merupakan anak usaha {np}?",
        "en": "Which company is a subsidiary of {np}?",
    },
}
THEMATIC: dict[str, dict[Lang, str]] = {
    "group": {
        "id": "Perusahaan apa saja yang tergabung dalam {group} dan bagaimana keterkaitannya?",
        "en": "Which companies belong to {group} and how are they connected?",
    },
    "surname": {
        "id": "Perusahaan apa saja yang dipimpin atau dimiliki oleh anggota keluarga {surname}?",
        "en": "Which companies are led or owned by members of the {surname} family?",
    },
    "founder": {
        "id": "Perusahaan apa saja yang dipimpin atau dimiliki oleh anggota keluarga {founder}?",
        "en": "Which companies are led or owned by members of the family of {founder}?",
    },
    "sector": {
        "id": "Siapa saja pemain utama di sektor {sector} dan bagaimana hubungan di antara mereka?",
        "en": "Who are the main players in the {sector} sector and how are they related?",
    },
}
SINCE: dict[Lang, str] = {"id": " sejak {year}", "en": " since {year}"}


class Question(BaseModel):
    id: str
    lang: Lang
    category: Category
    text: str
    gold_answers: list[list[str]]
    gold_doc_ids: list[str]
    # Multi-hop only: path entities a correct answer may name while explaining the chain.
    support_entities: list[str] = []


@dataclass(frozen=True)
class _Hop:
    type: str
    side: str
    role: str | None
    pct: int | None
    since: int | None


@dataclass(frozen=True)
class _Draft:
    category: Category
    templates: dict[Lang, str]
    mentions: dict[str, str]
    params: dict[str, str | int]
    answers: list[str]
    edge_ids: list[str]
    support: tuple[str, ...] = ()
    doc_ids: tuple[str, ...] = ()


class _Generator:
    def __init__(self, world: World, plans: list[DocPlan], seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.entities = {entity.id: entity for entity in world.entities}
        self.edges = world.edges
        self.paths = world.hidden_paths
        self.edge_by_id = {edge.id: edge for edge in world.edges}
        self.docs_of: dict[str, list[str]] = defaultdict(list)
        for plan in plans:
            for edge_id in plan.edge_ids:
                self.docs_of[edge_id].append(plan.doc_id)
        people = Counter(e.name for e in world.entities if e.type == "Person")
        self.colliding = {name for name, count in people.items() if count > 1}
        self.adjacency: dict[str, list[Edge]] = defaultdict(list)
        for edge in world.edges:
            if edge.until is None:
                self.adjacency[edge.src].append(edge)
                self.adjacency[edge.dst].append(edge)

    def build(self) -> list[Question]:
        drafts = [
            *self._single_hop(),
            *self._multi_hop(),
            *self._temporal(),
            *self._unanswerable(),
        ]
        counters: Counter[str] = Counter()
        questions = []
        for draft in drafts:
            counters[draft.category] += 1
            questions.append(self._question(draft, counters[draft.category]))
        self.rng.shuffle(questions)
        # A fresh stream keeps the earlier questions byte-identical to the published set.
        self.rng = random.Random(self.seed + 1)
        thematic = [
            self._question(draft, number, THEMATIC_EN_RATE)
            for number, draft in enumerate(self._thematic(), 1)
        ]
        return [*questions, *thematic]

    def _question(self, draft: _Draft, number: int, en_rate: float = EN_RATE) -> Question:
        lang: Lang = "en" if self.rng.random() < en_rate else "id"
        names = {key: self._surface(entity_id) for key, entity_id in draft.mentions.items()}
        edge_docs = {doc for edge_id in draft.edge_ids for doc in self.docs_of[edge_id]}
        doc_ids = sorted(edge_docs | set(draft.doc_ids))
        return Question(
            id=f"{ID_PREFIX[draft.category]}_{number:03d}",
            lang=lang,
            category=draft.category,
            text=draft.templates[lang].format(**names, **draft.params),
            gold_answers=[self._forms(answer) for answer in draft.answers],
            gold_doc_ids=doc_ids,
            support_entities=list(draft.support),
        )

    def _surface(self, entity_id: str) -> str:
        entity = self.entities[entity_id]
        if entity.aliases and self.rng.random() < ALIAS_RATE:
            return self.rng.choice(entity.aliases)
        return entity.name

    def _forms(self, entity_id: str) -> list[str]:
        entity = self.entities[entity_id]
        return [entity.name, *entity.aliases]

    def _usable(self, *edges: Edge, person: str | None = None) -> bool:
        named = person is None or self.entities[person].name not in self.colliding
        return named and all(self.docs_of[edge.id] for edge in edges)

    def _sample(self, drafts: list[_Draft], count: int) -> list[_Draft]:
        return self.rng.sample(drafts, min(count, len(drafts)))

    def _single_hop(self) -> list[_Draft]:
        current = [edge for edge in self.edges if edge.until is None]
        seats: dict[tuple[str, str], list[Edge]] = defaultdict(list)
        for edge in current:
            if edge.type == "SERVES_AS" and edge.props["role"] in UNIQUE_ROLES:
                seats[(edge.dst, str(edge.props["role"]))].append(edge)
        by_template: dict[str, list[_Draft]] = {
            "role": [
                self._single("role", edge.dst, edge.src, edge, role=role)
                for (_, role), (edge, *rest) in seats.items()
                if not rest and self._usable(edge, person=edge.src)
            ]
        }
        # Each pair: template, edge type, which end is asked about, which end answers.
        for template, rel_type, subject_end, answer_end in (
            ("parent", "SUBSIDIARY_OF", "src", "dst"),
            ("founder", "FOUNDED", "dst", "src"),
            ("group", "MEMBER_OF_GROUP", "src", "dst"),
        ):
            grouped: dict[str, list[Edge]] = defaultdict(list)
            for edge in current:
                if edge.type == rel_type:
                    grouped[getattr(edge, subject_end)].append(edge)
            by_template[template] = [
                self._single(template, subject, getattr(edge, answer_end), edge)
                for subject, (edge, *rest) in grouped.items()
                if not rest and self._usable(edge, person=self._person(getattr(edge, answer_end)))
            ]
        return [
            draft
            for template in SINGLE
            for draft in self._sample(by_template[template], SINGLE_PER_TEMPLATE)
        ]

    def _person(self, entity_id: str) -> str | None:
        return entity_id if self.entities[entity_id].type == "Person" else None

    def _single(
        self, template: str, subject: str, answer: str, edge: Edge, **params: str
    ) -> _Draft:
        return _Draft(
            "single_hop", SINGLE[template], {"subject": subject}, params, [answer], [edge.id]
        )

    def _multi_hop(self) -> list[_Draft]:
        drafts = []
        for path in self.paths:
            category = HOP_CATEGORY.get(path.hops)
            if category is None:
                continue
            edges = [self.edge_by_id[edge_id] for edge_id in path.edge_ids]
            for anchor, target, ordered in (
                (path.start, path.end, edges),
                (path.end, path.start, edges[::-1]),
            ):
                for qualified in (False, True):
                    hops = self._hops(anchor, ordered, qualified)
                    if self._reach(anchor, hops, qualified) == {target}:
                        drafts.append(
                            _Draft(
                                category,
                                {lang: self._render(hops, lang) for lang in ("id", "en")},
                                {"anchor": anchor},
                                {},
                                [target],
                                path.edge_ids,
                                tuple(
                                    sorted({n for e in edges for n in (e.src, e.dst)} - {target})
                                ),
                            )
                        )
                        break
        return drafts

    def _step(self, edge: Edge, node: str, qualified: bool) -> tuple[_Hop, str]:
        to_src = edge.dst == node
        if edge.type == "FAMILY_OF":
            relation = str(edge.props["relation"])
            side = relation if to_src else INVERSE[relation]
        else:
            side = "src" if to_src else "dst"
        role = edge.props.get("role")
        pct = edge.props.get("pct")
        hop = _Hop(
            edge.type,
            side,
            str(role) if role is not None else None,
            int(pct) if qualified and pct is not None else None,
            edge.since if qualified and edge.type == "SERVES_AS" else None,
        )
        return hop, edge.src if to_src else edge.dst

    def _hops(self, anchor: str, edges: list[Edge], qualified: bool) -> list[_Hop]:
        hops, node = [], anchor
        for edge in edges:
            hop, node = self._step(edge, node, qualified)
            hops.append(hop)
        return hops

    def _reach(self, anchor: str, hops: list[_Hop], qualified: bool) -> set[str]:
        # Answer set of the phrased question; middle hops also use only current edges ("saat ini").
        nodes = {anchor}
        for hop in hops:
            nodes = {
                other
                for node in nodes
                for edge in self.adjacency[node]
                for step, other in [self._step(edge, node, qualified)]
                if step == hop
            }
        return {node for node in nodes if self.entities[node].type == "Company"}

    def _render(self, hops: list[_Hop], lang: Lang) -> str:
        phrase = "{anchor}"
        for index, hop in enumerate(hops):
            if hop.type == "FAMILY_OF":
                template = FAMILY_PHRASE[lang][hop.side]
            else:
                table = FINAL_PHRASE if index == len(hops) - 1 else HOP_PHRASE
                template = table[(hop.type, hop.side)][lang]
            phrase = template.format(
                np=phrase,
                role=hop.role,
                pct=f" {hop.pct}%" if hop.pct is not None else "",
                since=SINCE[lang].format(year=hop.since) if hop.since is not None else "",
            )
        return phrase

    def _temporal(self) -> list[_Draft]:
        seats: dict[tuple[str, str], list[Edge]] = defaultdict(list)
        for edge in self.edges:
            if edge.type == "SERVES_AS" and edge.props["role"] in UNIQUE_ROLES:
                seats[(edge.dst, str(edge.props["role"]))].append(edge)
        drafts = []
        for (company, role), group in seats.items():
            if all(edge.until is None for edge in group):
                continue
            for edge in group:
                if not self._usable(edge, person=edge.src):
                    continue
                assert edge.since is not None
                end = min(edge.until or OPEN_END, LAST_CHANGE_YEAR + 1)
                # Skip the change years themselves: a mid-year handover makes them ambiguous.
                years = [
                    year
                    for year in range(edge.since + 1, end - (edge.until is not None))
                    if _holders(group, year) == {edge.src}
                ]
                if years:
                    params: dict[str, str | int] = {"role": role, "year": self.rng.choice(years)}
                    drafts.append(
                        _Draft(
                            "temporal",
                            TEMPORAL,
                            {"subject": company},
                            params,
                            [edge.src],
                            [edge.id],
                        )
                    )
        return self._sample(drafts, TEMPORAL_COUNT)

    def _unanswerable(self) -> list[_Draft]:
        linked: dict[str, set[frozenset[str]]] = defaultdict(set)
        founded, staffed = set(), set()
        for edge in self.edges:
            linked[edge.type].add(frozenset((edge.src, edge.dst)))
            if edge.type == "FOUNDED":
                founded.add(edge.dst)
            if edge.type == "SERVES_AS" and edge.props["role"] == ABSENT_ROLE:
                staffed.add(edge.dst)
        partners = sorted({node for pair in linked["PARTNERS_WITH"] for node in pair})
        investors = sorted({e.src for e in self.edges if e.type == "INVESTED_IN"})
        startups = sorted({e.dst for e in self.edges if e.type == "INVESTED_IN"})
        companies = [e for e in self.entities if self.entities[e].type == "Company"]
        candidates: dict[str, list[tuple[str, ...]]] = {
            "partner": [
                pair
                for pair in combinations(partners, 2)
                if frozenset(pair) not in linked["PARTNERS_WITH"]
            ],
            "invest": [
                (investor, startup)
                for investor in investors
                for startup in startups
                if frozenset((investor, startup)) not in linked["INVESTED_IN"]
            ],
            "founder": [(company,) for company in companies if company not in founded],
            "role": [(company,) for company in companies if company not in staffed],
        }
        drafts = []
        for template, options in candidates.items():
            for chosen in self.rng.sample(options, min(UNANSWERABLE_PER_TEMPLATE, len(options))):
                mentions = dict(zip(("a", "b"), chosen, strict=False))
                drafts.append(_Draft("unanswerable", UNANSWERABLE[template], mentions, {}, [], []))
        return drafts

    def _thematic(self) -> list[_Draft]:
        current = [edge for edge in self.edges if edge.until is None and self.docs_of[edge.id]]
        blood = [
            e for e in current if e.type == "FAMILY_OF" and e.props["relation"] in BLOOD_RELATIONS
        ]
        groups = sorted(e.id for e in self.entities.values() if e.type == "Group")
        drafts = []
        for group in groups:
            members = [e for e in current if e.type == "MEMBER_OF_GROUP" and e.dst == group]
            founder = str(self.entities[group].attrs["founder"])
            family = _component(founder, blood)
            drafts.append(self._thematic_draft("group", {"group": group}, members, family))
        for group in groups:
            founder = str(self.entities[group].attrs["founder"])
            if self.entities[founder].name in self.colliding:
                continue
            family = _component(founder, blood)
            led = [e for e in current if e.type in ("SERVES_AS", "OWNS_STAKE") and e.src in family]
            relatives = {
                other
                for e in current
                if e.type == "FAMILY_OF" and {e.src, e.dst} & family
                for other in (e.src, e.dst)
            }
            in_laws = {
                e.dst
                for e in current
                if e.type in ("SERVES_AS", "OWNS_STAKE") and e.src in relatives
            }
            surnames = {self.entities[person].name.split()[-1] for person in family}
            if len(surnames) == 1:
                template, mentions, params = "surname", {}, {"surname": surnames.pop()}
            else:
                template, mentions, params = "founder", {"founder": founder}, {}
            support = family | relatives | in_laws | {group}
            drafts.append(self._thematic_draft(template, mentions, led, support, params))
        names = {entity_id: entity.name for entity_id, entity in self.entities.items()}
        for sector in sorted(e.id for e in self.entities.values() if e.type == "Sector"):
            players = [e.src for e in self.edges if e.type == "IN_SECTOR" and e.dst == sector]
            # Sector facts appear only in the ticker reference table, so only listed companies count.
            listed = [
                c for c in players if any(TICKER.fullmatch(a) for a in self.entities[c].aliases)
            ]
            if len(players) > SECTOR_MAX_COMPANIES or len(listed) < 2:
                continue
            gold = self._top(listed)
            linking = [
                e
                for e in current
                if e.type in ("MEMBER_OF_GROUP", "SUBSIDIARY_OF", "SERVES_AS")
                and {e.src, e.dst} & set(gold)
            ]
            covered: dict[str, set[str]] = defaultdict(set)
            for edge in linking:
                for doc in self.docs_of[edge.id]:
                    covered[doc] |= {edge.src, edge.dst} & set(gold)
            ranked = sorted(covered, key=lambda doc: (-len(covered[doc]), doc))
            docs = (REFERENCE_DOC_ID, *ranked[: SECTOR_DOC_CAP - 1])
            # Groups and parents explain "how they are related", so naming them is allowed.
            related = {n for e in linking if e.type != "SERVES_AS" for n in (e.src, e.dst)}
            drafts.append(
                _Draft(
                    "thematic",
                    THEMATIC["sector"],
                    {},
                    {"sector": names[sector]},
                    gold,
                    [],
                    tuple(sorted((set(listed) | related) - set(gold))),
                    docs,
                )
            )
        return drafts

    def _thematic_draft(
        self,
        template: str,
        mentions: dict[str, str],
        edges: list[Edge],
        support: set[str],
        params: dict[str, str | int] | None = None,
    ) -> _Draft:
        companies = sorted(
            {edge.src if edge.type == "MEMBER_OF_GROUP" else edge.dst for edge in edges}
        )
        gold = self._top(companies)
        kept = [edge for edge in edges if {edge.src, edge.dst} & set(gold)]
        # Companies cut by the cap stay allowed, so naming them costs no precision.
        extra = (support | set(companies)) - set(gold) - set(mentions.values())
        return _Draft(
            "thematic",
            THEMATIC[template],
            mentions,
            params or {},
            gold,
            [edge.id for edge in kept],
            tuple(sorted(extra)),
        )

    def _top(self, companies: list[str]) -> list[str]:
        ranked = sorted(companies, key=lambda c: (-len(self.adjacency[c]), c))
        return sorted(ranked[:THEMATIC_GOLD_CAP])


def _component(person: str, edges: list[Edge]) -> set[str]:
    found, frontier = {person}, [person]
    while frontier:
        node = frontier.pop()
        for edge in edges:
            if node in (edge.src, edge.dst):
                for other in {edge.src, edge.dst} - found:
                    found.add(other)
                    frontier.append(other)
    return found


def _holders(seats: list[Edge], year: int) -> set[str]:
    return {
        edge.src
        for edge in seats
        if (edge.since or 0) <= year < (edge.until if edge.until is not None else OPEN_END)
    }


def build_questions(world: World, plans: list[DocPlan], seed: int = 42) -> list[Question]:
    return _Generator(world, plans, seed).build()


def write_questions(questions: list[Question], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [question.model_dump_json() for question in questions]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_questions(path: Path) -> list[Question]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Question.model_validate_json(line) for line in lines if line.strip()]
