from itertools import pairwise

import pytest

from nexus.ingest.chunker import chunk_id, chunk_text

PARAGRAPH = (
    "PT Maju Jaya Tbk. membukukan pendapatan Rp1.250 miliar, naik 12,5% dari tahun lalu. "
    "Menurut Dr. Budi dkk., hasil ini melampaui target. Is this the end? Yes! "
    "The company, Maju Inc. reported strong growth across all segments of its business."
)


def make_doc(paragraphs: int) -> str:
    return "\n\n".join(f"## Bagian {i}\n\n{PARAGRAPH}" for i in range(paragraphs))


def words(text: str) -> int:
    return len(text.split())


def test_empty_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("  \n\t ") == []


def test_tiny_doc_single_chunk():
    text = "  Halo dunia. Ini dokumen kecil.  "
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].ordinal == 0
    assert chunks[0].text == "Halo dunia. Ini dokumen kecil."
    assert text[chunks[0].start : chunks[0].end] == chunks[0].text


def test_offsets_slice_back():
    text = make_doc(60)
    assert words(text) >= 2000
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(text[c.start : c.end] == c.text for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_overlap_and_limit():
    text = make_doc(60)
    chunks = chunk_text(text)
    assert all(words(c.text) <= 300 for c in chunks)
    for previous, current in pairwise(chunks):
        assert current.start < previous.end
        assert current.start > previous.start
        assert current.end > previous.end


def test_abbreviations_do_not_end_chunks():
    chunks = chunk_text(make_doc(60), max_words=40, overlap_words=10)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert chunk.text.split()[-1] not in {"Tbk.", "Dr.", "dkk.", "Inc.", "(Dr."}


def test_decimals_and_leading_paren_abbreviation():
    text = "Harga Rp1.250 naik 12,5% (Dr. Budi) lalu turun. " * 30
    chunks = chunk_text(text, max_words=20, overlap_words=5)
    assert len(chunks) > 1
    assert all(c.text.endswith(("turun.", "Budi)", "lalu")) or c is chunks[-1] for c in chunks)
    assert all(text[c.start : c.end] == c.text for c in chunks)


def test_long_sentence_split_at_word_boundaries():
    text = " ".join(f"w{i}" for i in range(1000)) + "."
    chunks = chunk_text(text)
    assert len(chunks) > 3
    assert all(words(c.text) <= 300 for c in chunks)
    assert all(text[c.start : c.end] == c.text for c in chunks)
    assert chunks[-1].text.endswith("w999.")


def test_no_punctuation_terminates():
    text = "kata " * 5000
    chunks = chunk_text(text, max_words=300, overlap_words=50)
    assert all(words(c.text) <= 300 for c in chunks)
    assert chunks[-1].end == len(text.rstrip())


@pytest.mark.parametrize(
    ("max_words", "overlap_words"), [(0, 0), (-1, 0), (10, -1), (10, 5), (10, 10), (300, 150)]
)
def test_invalid_limits_raise(max_words, overlap_words):
    with pytest.raises(ValueError):
        chunk_text("a b c", max_words=max_words, overlap_words=overlap_words)


def test_chunk_id_stable():
    assert chunk_id("doc_007", 3) == "doc_007:0003"
