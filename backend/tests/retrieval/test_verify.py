import pytest

from nexus.llm import GatewayError
from nexus.retrieval.verify import Claim, Verdict, Verdicts, split_claims, verify_claims

ANSWER = (
    "# Ringkasan\n"
    "PT Alpha Tbk dimiliki oleh Budi [d1:0000]. Ia menjabat sejak 2020 [d1:0000][d2:0001]\n"
    "- **Beta** is a sector leader. [d2:0001]\n"
    "2. Tidak ada sumber.\n"
    "[d3:0002] Baris ini punya sitasi di depan."
)


def test_split_claims_parses_citations() -> None:
    claims = split_claims(ANSWER)
    assert [claim.text for claim in claims] == [
        "PT Alpha Tbk dimiliki oleh Budi.",
        "Ia menjabat sejak 2020",
        "Beta is a sector leader.",
        "Tidak ada sumber.",
        "Baris ini punya sitasi di depan.",
    ]
    assert [claim.chunk_ids for claim in claims] == [
        ["d1:0000"],
        ["d1:0000", "d2:0001"],
        ["d2:0001"],
        [],
        ["d3:0002"],
    ]


def test_uncited_sentence_unsupported() -> None:
    claims = split_claims("Tidak ada sumber.")
    assert claims[0].supported is False
    result, calls = verify_claims(claims, {}, llm=_unreachable)
    assert (result[0].supported, calls) == (False, 0)


def _unreachable(*args: object, **kwargs: object) -> Verdicts:
    raise AssertionError("LLM must not be called")


def test_verifier_marks_supported() -> None:
    claims = [
        Claim(text="A", chunk_ids=["c1"]),
        Claim(text="B", chunk_ids=["c1"]),
        Claim(text="C", chunk_ids=["missing"]),
        Claim(text="D", chunk_ids=["c1"]),
    ]
    seen: dict = {}

    def fake(messages: list[dict], schema: type, **kwargs: object) -> Verdicts:
        seen.update(messages=messages, kwargs=kwargs)
        # Index 7 is out of range and must be ignored; claim 3 gets no verdict.
        return Verdicts(
            items=[
                Verdict(index=0, supported=True),
                Verdict(index=1, supported=False),
                Verdict(index=7, supported=True),
            ]
        )

    result, calls = verify_claims(claims, {"c1": "x" * 5000}, llm=fake)
    assert calls == 1
    assert [claim.supported for claim in result] == [True, False, False, None]
    assert seen["kwargs"] == {"temperature": 0.0, "timeout": 120}
    assert "Claim 2" not in seen["messages"][1]["content"]
    assert "x" * 2501 not in seen["messages"][1]["content"]


def test_verifier_failure_marks_unverified() -> None:
    def failing(*args: object, **kwargs: object) -> Verdicts:
        raise GatewayError("down")

    claims = [Claim(text="A", chunk_ids=["c1"]), Claim(text="B", chunk_ids=[])]
    result, calls = verify_claims(claims, {"c1": "t"}, llm=failing)
    assert [claim.supported for claim in result] == [None, False]
    assert calls == 1


def test_abstain_has_no_claims() -> None:
    assert split_claims("Informasi tidak ditemukan dalam dokumen.") == []
    assert split_claims("The documents do not contain this information.") == []


@pytest.mark.live
def test_live_bilingual_verdicts() -> None:
    chunk_text = {
        "d1:0000": "PT Sinar Wibawa Tbk is owned 60% by Budi Santoso, who has been President Director since 2019.",
    }
    claims = [
        Claim(text="Budi Santoso memiliki 60% saham PT Sinar Wibawa Tbk.", chunk_ids=["d1:0000"]),
        Claim(text="Budi Santoso memiliki 90% saham PT Sinar Wibawa Tbk.", chunk_ids=["d1:0000"]),
    ]
    result, _ = verify_claims(claims, chunk_text)
    print(result)
    assert [claim.supported for claim in result] == [True, False]


@pytest.mark.parametrize(
    "line",
    [
        "## Jawaban",
        "Berikut adalah rincian data yang ditemukan dalam dokumen:",
        "1.  **Identify the holder of a 60% stake in PT Sinar Cemerlang:**",
        "Langkah 1:",
        "Identify the stakeholder: The question asks which company holds a 5% stake.",
        "Let's re-read carefully.",
        "Mari kita periksa siapa yang menjabat sebagai Direktur Utama sejak 2017.",
        "Informasi tidak ditemukan dalam dokumen.",
        "Najam Wacana tidak disebutkan memiliki jabatan Komisaris Utama dalam dokumen.",
        "None of the provided excerpts contain information about the shareholders.",
    ],
)
def test_split_claims_skips_non_claims(line: str) -> None:
    assert split_claims(f"Budi memegang 20% saham [d1:0000].\n{line}") == [
        Claim(text="Budi memegang 20% saham.", chunk_ids=["d1:0000"], supported=False)
    ]


def test_split_claims_keeps_uncited_fact_and_cited_no_info() -> None:
    claims = split_claims(
        "Dengan demikian, Najam Wacana adalah kerabat semenda dari Galak Gunawan.\n"
        "Dokumen [d1:0000] tidak menyebutkan pasangan Oni."
    )
    assert [(c.text, c.chunk_ids) for c in claims] == [
        ("Dengan demikian, Najam Wacana adalah kerabat semenda dari Galak Gunawan.", []),
        ("Dokumen tidak menyebutkan pasangan Oni.", ["d1:0000"]),
    ]


def test_leading_citation_attaches_to_following_sentence() -> None:
    claims = split_claims(
        "- Mari kita lihat pemegang lain. [d4:0000] menyebutkan Najam memegang 20%. "
        "[d2:0000] menyatakan Najam pasangan Tiara. [d2:0000]"
    )
    assert [(c.text, c.chunk_ids) for c in claims] == [
        ("menyebutkan Najam memegang 20%.", ["d4:0000"]),
        ("menyatakan Najam pasangan Tiara.", ["d2:0000"]),
    ]


AUTO_M3_003 = (
    "Perusahaan tempat Raden Prasasta (sebagai pemegang saham 20% di Mulia Lancar Capital) "
    "memegang 60% saham saat ini adalah **Sinar Cemerlang**, di mana Oni Prasasta (saudara "
    "kandung Raden Prasasta) menjabat sebagai Direktur Utama, namun dokumen tidak menyebutkan "
    "Raden Prasasta memegang 60% saham di Sinar Cemerlang."
)


@pytest.mark.parametrize(
    ("line", "kept"),
    [
        ("Kesimpulan: PT X dimiliki 60% oleh Raden.", "PT X dimiliki 60% oleh Raden."),
        ("Step 2: Budi is the spouse of Ani.", "Budi is the spouse of Ani."),
        ("Budi holds 60% of PT X, but his spouse is not mentioned.", None),
        (AUTO_M3_003, None),
    ],
)
def test_split_claims_keeps_labelled_and_mixed_sentences(line: str, kept: str | None) -> None:
    claims = split_claims(line)
    assert [c.text for c in claims] == [kept or line.replace("**", "")]


def test_colon_rule_is_per_sentence() -> None:
    claims = split_claims("Budi holds 60% [d1:0000]. Others include:")
    assert [(c.text, c.chunk_ids) for c in claims] == [("Budi holds 60%.", ["d1:0000"])]
