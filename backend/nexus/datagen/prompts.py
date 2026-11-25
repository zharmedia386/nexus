from nexus.datagen.planner import DocType, Lang

SYSTEM: dict[Lang, str] = {
    "id": (
        "Anda adalah penulis dokumen korporat untuk dunia fiksi perusahaan Indonesia. "
        "Tulis dalam Bahasa Indonesia register pers bisnis (gaya Kontan / Bisnis Indonesia)."
    ),
    "en": (
        "You write documents for a fictional Indonesian corporate world. "
        "Write in English as a sell-side equity research analyst."
    ),
}

DOC_STYLE: dict[tuple[DocType, Lang], str] = {
    (
        "news",
        "id",
    ): "Berita bisnis singkat bergaya Kontan/Bisnis Indonesia: judul, teras berita, kutipan tidak wajib.",
    ("news", "en"): "Short business news article in the style of a financial wire.",
    (
        "annual_report",
        "id",
    ): "Bagian laporan tahunan (laporan tahunan perusahaan): profil, susunan dewan, struktur pemegang saham, formal dan naratif.",
    (
        "annual_report",
        "en",
    ): "Section of an annual report: company profile, board composition and shareholder structure, formal narrative.",
    (
        "disclosure",
        "id",
    ): "Keterbukaan informasi kepada publik (gaya pengumuman emiten): perihal, uraian fakta perubahan, formal dan ringkas.",
    (
        "disclosure",
        "en",
    ): "Formal public disclosure notice to the exchange: subject line, then the factual change, concise.",
    (
        "press_release",
        "id",
    ): "Siaran pers korporat tentang kemitraan atau investasi, nada resmi dan positif.",
    (
        "press_release",
        "en",
    ): "Corporate press release about a partnership or investment, formal, upbeat tone.",
    (
        "analyst_note",
        "id",
    ): "Catatan analis riset tentang struktur grup usaha, nada riset sekuritas.",
    (
        "analyst_note",
        "en",
    ): "Sell-side research note on group structure: observations first, neutral analytical tone.",
}

RULES: dict[Lang, str] = {
    "id": (
        "Aturan wajib:\n"
        "- Nyatakan SEMUA fakta di bawah ini, tanpa terkecuali.\n"
        '- Gunakan nama persis seperti tertulis pada fakta (jangan disingkat atau diubah); "PT" dan "Tbk" harus dipertahankan persis seperti tertulis.\n'
        "- Jangan menyebut perusahaan atau orang lain selain yang ada di fakta.\n"
        "- Jangan menambah fakta baru dan jangan bertentangan dengan tahun yang tertulis.\n"
        "- Fakta yang sudah berakhir (ada tahun akhir) ditulis dalam bentuk lampau.\n"
        "- Baris pertama: judul dokumen dalam format '# Judul'. Setelah itu isi dokumen."
    ),
    "en": (
        "Mandatory rules:\n"
        "- State ALL facts below, without exception.\n"
        '- Use each name exactly as written in the facts (do not shorten or alter it); keep "PT" and "Tbk" exactly as given.\n'
        "- Do not mention any company or person that is not in the facts.\n"
        "- Do not add new facts and never contradict the years given.\n"
        "- Facts that have ended (an end year is given) must be written in the past tense.\n"
        "- First line: the document title as '# Title'. Then the document body."
    ),
}

ROUNDUP: dict[Lang, str] = {
    "id": (
        "Fakta-fakta ini berasal dari beberapa perusahaan yang tidak saling terkait. Tulis sebagai "
        "rangkuman berita (misalnya perubahan dewan pada musim RUPST). Jangan mengarang "
        "hubungan apa pun antarperusahaan yang tidak dinyatakan oleh fakta."
    ),
    "en": (
        "These facts concern several unrelated companies. Write a news roundup (for example board "
        "changes in the AGM season). Do not invent any link between companies that the facts "
        "do not state."
    ),
}

FACTS_HEADER: dict[Lang, str] = {"id": "Fakta:", "en": "Facts:"}
YEAR_LINE: dict[Lang, str] = {
    "id": "Tahun dokumen: {year}.",
    "en": "Document year: {year}.",
}


def build_messages(
    doc_type: DocType, lang: Lang, year: int, facts: list[str], roundup: bool
) -> list[dict[str, str]]:
    parts = [DOC_STYLE[(doc_type, lang)], YEAR_LINE[lang].format(year=year), RULES[lang]]
    if roundup:
        parts.append(ROUNDUP[lang])
    parts.append(FACTS_HEADER[lang] + "\n" + "\n".join(f"- {fact}" for fact in facts))
    return [
        {"role": "system", "content": SYSTEM[lang]},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
