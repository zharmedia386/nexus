import random
import string
from functools import lru_cache
from pathlib import Path

from faker import Faker

STEM_FIRST = [
    "Sinar",
    "Prima",
    "Nusantara",
    "Bumi",
    "Cahaya",
    "Mitra",
    "Karya",
    "Surya",
    "Mega",
    "Graha",
    "Tirta",
    "Buana",
    "Citra",
    "Dharma",
    "Fajar",
    "Harapan",
    "Indah",
    "Jaya",
    "Lintas",
    "Mulia",
    "Pelita",
    "Rimba",
    "Samudra",
    "Tunas",
    "Wahana",
    "Arta",
    "Bintang",
    "Delta",
    "Gemilang",
]
STEM_SECOND = [
    "Sentosa",
    "Makmur",
    "Abadi",
    "Perkasa",
    "Lestari",
    "Utama",
    "Persada",
    "Gemilang",
    "Mulia",
    "Raya",
    "Bahari",
    "Cemerlang",
    "Kencana",
    "Mandala",
    "Pratama",
    "Agung",
    "Nirwana",
    "Wibawa",
    "Sakti",
    "Semesta",
    "Teguh",
    "Unggul",
    "Kreasi",
    "Sukses",
    "Berkah",
    "Harmoni",
    "Lancar",
]
HOLDING_SUFFIXES = ["Investama", "Capital", "Sejahtera"]
REAL_TICKERS = frozenset(
    {
        "TLKM",
        "BBCA",
        "BBRI",
        "BMRI",
        "BBNI",
        "ASII",
        "UNVR",
        "SMGR",
        "SSIA",
        "PWON",
        "AKRA",
        "BSDE",
        "CTRA",
        "HRUM",
        "TKIM",
        "TBIG",
        "INDF",
        "ICBP",
        "GGRM",
        "HMSP",
        "ADRO",
        "PTBA",
        "ANTM",
        "INCO",
        "MDKA",
        "EXCL",
        "ISAT",
        "KLBF",
        "CPIN",
        "JSMR",
    }
)


@lru_cache
def blocklist() -> tuple[str, ...]:
    path = Path(__file__).with_name("blocklist.txt")
    return tuple(line.strip().lower() for line in path.read_text().splitlines() if line.strip())


def is_blocked(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in blocklist())


def company_stem(rng: random.Random, used: set[str]) -> str:
    while True:
        first, second = rng.choice(STEM_FIRST), rng.choice(STEM_SECOND)
        stem = f"{first} {second}"
        if first != second and stem not in used and not is_blocked(stem):
            used.add(stem)
            return stem


def ticker(stem: str, rng: random.Random, used: set[str]) -> str:
    initials = "".join(word[0] for word in stem.split())
    while True:
        code = initials + "".join(rng.choice(string.ascii_uppercase) for _ in range(2))
        if code not in used and code not in REAL_TICKERS and not is_blocked(code):
            used.add(code)
            return code


def person_name(faker: Faker, female: bool, surname: str | None = None) -> str:
    while True:
        first = faker.first_name_female() if female else faker.first_name_male()
        last = surname or (faker.last_name_female() if female else faker.last_name_male())
        name = f"{first} {last}"
        if not is_blocked(name):
            return name
