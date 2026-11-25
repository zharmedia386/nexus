# Claim audit: run 23b9a166-a905-4500-bc84-5d2f6f0c30d5 / graph_local / multi_hop_3

Sampled 30 unsupported claims (seed 42).

## 1. m3_006

**Question:** Which company currently holds a 5% stake in the company where the spouse of the Komisaris Utama of PT Gemilang Mandala since 2014 serves as Komisaris Utama since 2018?

**Claim:** Identify the stakeholder: The question asks which company holds a 5% stake in PT Buana Raya Tbk.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) meta: restates the question; no citation, not a factual assertion

## 2. m3_014

**Question:** Di perusahaan mana pasangan kerabat semenda pemegang 20% saham PT Sinar Semesta Capital saat ini menjabat sebagai Komisaris Utama sejak 2020?

**Claim:** Berikut adalah rincian data yang ditemukan dalam dokumen:

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) scaffolding line ("here are the details"); no citation

## 3. m3_012

**Question:** Di perusahaan mana kerabat semenda Direktur Utama Tirta Lancar saat ini menjabat sebagai Komisaris Utama?

**Claim:** Dengan demikian, Najam Wacana adalah kerabat semenda dari Galak Gunawan.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (a) uncited factual inference (true per doc_023:0000, but the answer cited nothing)

## 4. m3_010

**Question:** Di perusahaan mana pasangan pemegang 20% saham induk usaha Gemilang Sakti saat ini menjabat sebagai Direktur Utama sejak 2017?

**Claim:** menyebutkan Najam Wacana memegang 20%.

**Verifier:** not supported

**[doc_023:0000]**

> # Profil Alambana Wacana: Pendiri Empat Entitas Bisnis dan Struktur Keluarga
> 
> **Jakarta, Kontan** – Alambana Wacana tercatat sebagai pendiri empat entitas bisnis, yakni PT Graha Perkasa, PT Bumi Sentosa Capital, PT Lintas Mandala, dan Mulia Pratama.
> 
> Berdasarkan data yang dihimpun, Alambana Wacana mendirikan PT Graha Perkasa pada 1987. Tiga tahun kemudian, tepatnya pada 1990, Alambana Wacana mendirikan PT Bumi Sentosa Capital. Selanjutnya, pada 1993, Alambana Wacana mendirikan PT Lintas Mandala. Terakhir, pada 2001, Alambana Wacana mendirikan Mulia Pratama.
> 
> Dalam struktur keluarga, Alambana Wacana adalah pasangan suami/istri dari Kamaria Puspasari. Keduanya merupakan orang tua dari Najam Wacana dan Michelle Wacana. Najam Wacana adalah saudara kandung Michelle Wacana.
> 
> Najam Wacana diketahui adalah pasangan suami/istri dari Tiara Gunawan. Sementara itu, Galak Gunawan tercatat sebagai kerabat semenda (ipar/mertua/menantu) dari Najam Wacana.


human: [x] supported [ ] not supported

**Audit class:** (c) true per doc_043:0000; split_claims moved the next sentence's leading [doc_023:0000] onto this fragment and gave its own leading [doc_043:0000] to the previous sentence

## 5. m3_004

**Question:** At which company does the spouse of the holder of a 20% stake in the holder of a 60% stake in PT Sinar Cemerlang currently serve as Direktur Utama since 2007?

**Claim:** The company is Tunas Teguh.

**Verifier:** not supported

**[doc_062:0000]**

> # Laporan Tahunan Nusantara Sakti Capital 2024
> 
> **Profil Perusahaan dan Struktur Kepemilikan**
> 
> Nusantara Sakti Capital merupakan entitas induk yang memiliki portofolio investasi strategis di berbagai sektor. Hingga tahun 2024, struktur kepemilikan saham Nusantara Sakti Capital di anak-anak usahanya mencerminkan komitmen jangka panjang dan konsolidasi bisnis yang telah dibangun selama lebih dari satu dekade.
> 
> Nusantara Sakti Capital memegang 77% saham Tunas Teguh sejak 2009. Status Tunas Teguh sebagai anak usaha Nusantara Sakti Capital telah berlaku sejak 2012.
> 
> Selain itu, Nusantara Sakti Capital memegang 74% saham Gemilang Sukses sejak 2013. Gemilang Sukses diakui sebagai anak usaha Nusantara Sakti Capital sejak 2014. Pada struktur pemegang saham Gemilang Sukses, terdapat pula kepemilikan oleh Gemilang Nirwana Capital yang memegang 3% saham sejak 2021.
> 
> Di segmen lain, Nusantara Sakti Capital memegang 55% saham Citra Kencana sejak 2009. Citra Kencana telah menjadi anak usaha Nusantara Sakti Capital sejak 2005.
> 
> Terakhir, Nusantara Sakti Capital memegang 51% saham Citra Lancar sejak 2005. Citra Lancar tercatat sebagai anak usaha Nusantara Sakti Capital sejak 2021.
> 
> **Susunan Dewan Komisaris dan Direksi**
> 
> Tata kelola perusahaan yang baik diterapkan melalui penunjukan dewan komisaris dan direksi yang berpengalaman di masing-masing entitas anak.
> 
> Di Tunas Teguh, Nova Kusmawati menjabat sebagai Komisaris Utama sejak 2013. Sementara itu, Zaenab Thamrin menjabat sebagai Direktur Utama sejak 2007.
> 
> Untuk Gemilang Sukses, susunan pimpinannya terdiri dari Kartika Purnawati yang menjabat sebagai Komisaris Utama sejak 2018, serta Radika Sitompul yang menjabat sebagai Komisaris Independen sejak 2017. Di jajaran direksi, Kadir Thamrin menjabat sebagai Direktur Utama sejak 2015, Cakrawala Maulana menjabat sebagai Direktur Operasional sejak 2015, dan Ida Hastuti menjabat sebagai Direktur Keuangan sejak 2014.
> 
> Pada Citra Kencana, Karya Thamrin menjabat sebagai Komisaris Utama sejak 2011, sedangkan Nova Kusmawati menjabat sebagai Direktur Utama sejak 2006.


human: [ ] supported [x] not supported

**Audit class:** (d) context-dependent final answer ("The company is ..."); correct, but the cited chunk only supports the last hop and the claim is meaningless alone

## 6. m3_004

**Question:** At which company does the spouse of the holder of a 20% stake in the holder of a 60% stake in PT Sinar Cemerlang currently serve as Direktur Utama since 2007?

**Claim:** Conclusion:

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) header "Conclusion:"

## 7. m3_004

**Question:** At which company does the spouse of the holder of a 20% stake in the holder of a 60% stake in PT Sinar Cemerlang currently serve as Direktur Utama since 2007?

**Claim:** It does not explicitly state Oni Prasasta's spouse in this excerpt, but it identifies his parents.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) meta statement about what an excerpt does not say; no citation

## 8. m3_014

**Question:** Di perusahaan mana pasangan kerabat semenda pemegang 20% saham PT Sinar Semesta Capital saat ini menjabat sebagai Komisaris Utama sejak 2020?

**Claim:** Najam Wacana (pasangan Tiara) tidak disebutkan memiliki jabatan Komisaris Utama dalam dokumen.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) negative/meta statement about the documents; no citation

## 9. m3_003

**Question:** Di perusahaan mana perusahaan tempat pasangan Direktur Utama PT Tunas Teguh sejak 2007 memegang 20% saham saat ini memegang 60% saham?

**Claim:** Jika pertanyaan mengacu pada entitas tempat *Raden Prasasta* secara langsung memegang 60% saham, dokumen tidak menyebutkan Raden Prasasta memegang 60% saham di perusahaan mana pun.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) negative/meta statement about the documents; no citation

## 10. m3_014

**Question:** Di perusahaan mana pasangan kerabat semenda pemegang 20% saham PT Sinar Semesta Capital saat ini menjabat sebagai Komisaris Utama sejak 2020?

**Claim:** Berdasarkan dokumen yang disediakan, tidak ada informasi mengenai siapa pasangan kerabat semenda pemegang 20% saham PT Sinar Semesta Capital (yaitu Tiara Gunawan atau Maman Gunawan) yang menjabat sebagai Komisaris Utama sejak 2020.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) abstention sentence; no citation

## 11. m3_010

**Question:** Di perusahaan mana pasangan pemegang 20% saham induk usaha Gemilang Sakti saat ini menjabat sebagai Direktur Utama sejak 2017?

**Claim:** Identifikasi Induk Usaha Gemilang Sakti:

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) step header

## 12. m3_016

**Question:** In which company does the company in which the in-law relative of the Komisaris Utama of Dharma Cemerlang since 2017 holds a 60% stake currently hold a 57% stake?

**Claim:** Identify the in-law relative of Kadir Thamrin:

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) step header

## 13. m3_020

**Question:** At which company does the spouse of the holder of a 20% stake in the parent company of PT Buana Raya Tbk currently serve as Komisaris since 2007?

**Claim:** [doc_030:0001

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) malformed citation "[doc_030:0001" (no closing bracket) left as claim text

## 14. m3_007

**Question:** Di perusahaan mana pasangan Komisaris Utama perusahaan tempat Mitra Lestari Sejahtera memegang 5% saham sejak 2018 saat ini menjabat sebagai Komisaris Utama sejak 2014?

**Claim:** Karena premis pertanyaan (Mitra Lestari Sejahtera memegang 5% saham sejak 2018) tidak sesuai dengan data dalam dokumen, maka informasi mengenai pasangan Komisaris Utama di perusahaan tersebut tidak dapat ditemukan.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) premise-rejection/meta statement; no citation

## 15. m3_015

**Question:** Di perusahaan mana pasangan Komisaris Utama Delta Teguh sejak 2009 saat ini menjabat sebagai Direktur Utama sejak 2015?

**Claim:** Jika pertanyaan mengacu pada pasangan dari Komisaris Utama tersebut (yaitu Kadir Thamrin), maka jawabannya adalah Gemilang Sukses.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (a) uncited conditional answer ("maka jawabannya adalah Gemilang Sukses")

## 16. m3_020

**Question:** At which company does the spouse of the holder of a 20% stake in the parent company of PT Buana Raya Tbk currently serve as Komisaris since 2007?

**Claim:** The question asks for the spouse of the holder of a 20% stake.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) meta: restates the question

## 17. m3_012

**Question:** Di perusahaan mana kerabat semenda Direktur Utama Tirta Lancar saat ini menjabat sebagai Komisaris Utama?

**Claim:** Cari Jabatan Komisaris Utama yang dipegang oleh Najam Wacana:

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) step header

## 18. m3_003

**Question:** Di perusahaan mana perusahaan tempat pasangan Direktur Utama PT Tunas Teguh sejak 2007 memegang 20% saham saat ini memegang 60% saham?

**Claim:** Namun, melihat struktur pertanyaan "perusahaan tempat memegang 20% saham...

**Verifier:** not supported

**[subjek]**

> _(chunk not found)_


human: [ ] supported [x] not supported

**Audit class:** (d) reasoning fragment; "[subjek]" parsed as a citation id, so auto-unsupported

## 19. m3_010

**Question:** Di perusahaan mana pasangan pemegang 20% saham induk usaha Gemilang Sakti saat ini menjabat sebagai Direktur Utama sejak 2017?

**Claim:** Jawaban: PT Tunas Mandala

**Verifier:** not supported

**[doc_048:0001]**

> *   Lanang Halim menjabat sebagai Direktur Operasional sejak 2016.
>     *   Dalimin Uwais menjabat sebagai Direktur Keuangan sejak 2019.
> *   **Dewan Komisaris:**
>     *   Tiara Gunawan menjabat sebagai Komisaris Utama sejak 2014.
>     *   Halim Thamrin menjabat sebagai Komisaris sejak 2015.
>     *   Wahyu Iswahyudi menjabat sebagai Komisaris Independen sejak 2019.
> 
> **Gemilang Makmur**
> *   **Direksi:**
>     *   Tiara Gunawan menjabat sebagai Direktur Utama sejak 2020.
> *   **Dewan Komisaris:**
>     *   Lega Sihotang menjabat sebagai Komisaris Utama sejak 2007.
> 
> **PT Tunas Mandala**
> *   **Direksi:**
>     *   Tiara Gunawan menjabat sebagai Direktur Utama sejak 2017.
> *   **Dewan Komisaris:**
>     *   Maman Gunawan menjabat sebagai Komisaris Utama sejak 2014.


human: [ ] supported [x] not supported

**Audit class:** (d) context-dependent final answer ("Jawaban: PT Tunas Mandala"); correct, cited chunk supports only the last hop

## 20. m3_004

**Question:** At which company does the spouse of the holder of a 20% stake in the holder of a 60% stake in PT Sinar Cemerlang currently serve as Direktur Utama since 2007?

**Claim:** Identify the spouse of the 20% stakeholder(s):

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) step header

## 21. m3_004

**Question:** At which company does the spouse of the holder of a 20% stake in the holder of a 60% stake in PT Sinar Cemerlang currently serve as Direktur Utama since 2007?

**Claim:** Determine which spouse serves as Direktur Utama since 2007:

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) step header

## 22. m3_020

**Question:** At which company does the spouse of the holder of a 20% stake in the parent company of PT Buana Raya Tbk currently serve as Komisaris since 2007?

**Claim:** Kartika Pertiwi: 50%

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (a) uncited factual list item ("Kartika Pertiwi: 50%")

## 23. m3_015

**Question:** Di perusahaan mana pasangan Komisaris Utama Delta Teguh sejak 2009 saat ini menjabat sebagai Direktur Utama sejak 2015?

**Claim:** Informasi tidak ditemukan dalam dokumen.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) abstention sentence

## 24. m3_010

**Question:** Di perusahaan mana pasangan pemegang 20% saham induk usaha Gemilang Sakti saat ini menjabat sebagai Direktur Utama sejak 2017?

**Claim:** Mari kita periksa siapa yang menjabat sebagai Direktur Utama sejak 2017 di perusahaan mana pun yang terkait.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) scaffolding ("let us check ...")

## 25. m3_013

**Question:** Di perusahaan mana kerabat semenda pasangan Komisaris Utama PT Jaya Agung sejak 2020 saat ini memegang 20% saham?

**Claim:** Jadi, perusahaan tersebut adalah Sinar Semesta Capital.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (a) uncited answer sentence ("Jadi, perusahaan tersebut adalah ...")

## 26. m3_004

**Question:** At which company does the spouse of the holder of a 20% stake in the holder of a 60% stake in PT Sinar Cemerlang currently serve as Direktur Utama since 2007?

**Claim:** There are two such holders.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (a) uncited factual sentence ("There are two such holders")

## 27. m3_006

**Question:** Which company currently holds a 5% stake in the company where the spouse of the Komisaris Utama of PT Gemilang Mandala since 2014 serves as Komisaris Utama since 2018?

**Claim:** None of the provided excerpts contain information about the shareholders of PT Buana Raya Tbk or specifically who holds a 5% stake in it.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) negative/meta statement about excerpts

## 28. m3_021

**Question:** Di perusahaan mana kerabat semenda Komisaris Utama PT Harapan Makmur sejak 2019 saat ini menjabat sebagai Komisaris Utama sejak 2013?

**Claim:** Namun, dalam dokumen yang disediakan, tidak ditemukan informasi mengenai siapa kerabat semenda Karya Thamrin, maupun perusahaan di mana kerabat tersebut menjabat sebagai Komisaris Utama sejak 2013.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) abstention sentence

## 29. m3_020

**Question:** At which company does the spouse of the holder of a 20% stake in the parent company of PT Buana Raya Tbk currently serve as Komisaris since 2007?

**Claim:** Let's re-read carefully.

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) scaffolding ("Let's re-read carefully.")

## 30. m3_016

**Question:** In which company does the company in which the in-law relative of the Komisaris Utama of Dharma Cemerlang since 2017 holds a 60% stake currently hold a 57% stake?

**Claim:** Identify the company in which Arta Utama Capital currently holds a 57% stake:

**Verifier:** not supported

_No citations._

human: [ ] supported [x] not supported

**Audit class:** (d) step header

## Breakdown

| class | meaning | count |
|---|---|---|
| a | verifier correct (claim not supported by its citations) | 5 |
| b | verifier too strict (citations jointly support / cross-language / translated roles) | 0 |
| c | claim true in the world, wrong chunk attached | 1 |
| d | other (non-claim: header, scaffolding, meta, abstention, malformed citation, context-dependent) | 24 |

27 of 30 sampled claims never reached the LLM verifier: 26 had no citation and 1 cited a non-chunk id ("[subjek]"); verify_claims marks those unsupported by rule. Only #4, #5 and #19 were judged by the LLM, and none of them is a case where its cited chunks support the claim.
