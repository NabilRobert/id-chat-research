# Anonymiser results

Every number here comes from a committed run record in
[`results/anonymiser/`](../results/anonymiser/). The rules (what a miss is,
how intervals are computed) are the [measurement plan's](planning/measurement-plan.md#a-the-anonymiser),
and the scorer is `packages/id-chat-anonymiser/src/id_chat_anonymiser/scoring.py`.

## R0: patterns only (v0.1.0, config `d5430d0507d3`, 2026-11-09)

**Held-out, scored once:** 1,704 synthetic chats from the 12 held-out
templates (fingerprint `4f42e33c…`, frozen in commit `a5daf2c` before any
recogniser existed). Record: `heldout-v0.1.0-d5430d0507d3.json`.

| Type | Gold values | Missed | Miss rate | 95% upper bound | Wrong type | Gate |
|---|---:|---:|---:|---:|---:|---|
| Phone (`TELEPON`) | 1,827 | 0 | 0% | 0.21% | 0 | G1 met |
| NIK | 1,552 | 0 | 0% | 0.25% | 0 | G1 met |
| Email | 1,704 | 0 | 0% | 0.22% | 0 | G1 met |
| Plate (`PLAT`) | 1,000 | 0 | 0% | 0.38% | 0 | G1 met |
| Account (`REKENING`) | 1,552 | 0 | 0% | 0.25% | 3 | G1 met |
| Order ID (`ID_PESANAN`) | 559 | 0 | 0% | 0.68% | 0 | no gate |
| Name (`NAMA`) | 2,554 | 2,554 | 100% | — | — | not tried in R0 |
| Address (`ALAMAT`) | 593 | 593 | 100% | — | — | not tried in R0 |

- **Over-redaction:** 0 characters outside personal data were redacted.
- **Look-alikes:** none of the 4,844 in the set were redacted: 1,571
  product names, 1,429 prices, 822 dates, 447 promo codes, 436 years and
  139 kilometre readings (G3 for these types).
- **Wrong type:** 3 sixteen-digit account numbers were hidden as NIKs:
  their digits happened to pass the NIK structure check, which scores
  higher than the bank-word match. They are hidden, so they are not
  misses.
- **Speed:** 635 chats per second on the M2 (1,704 chats in 2.7 s);
  dev ran at 779.

**Dev** (2,000 chats, 16 templates; record `dev-v0.1.0-d5430d0507d3.json`)
gives the same picture: 0 misses on every direct identifier, 6 accounts
under another type, no over-redaction.

## What this does and doesn't show

- **It shows** that the patterns cover every format the generator writes
  (eight phone forms, landlines, NIKs plain or in groups of four, three
  plate forms in either case, four order-ID forms, accounts with dashes),
  in sentences the recognisers were never tuned on, without touching
  prices or product names.
- **It doesn't show** that real chats are covered. Dev and held-out share
  the generator's value formats and were written by the same author, so
  this is a lower bound on difficulty. Still to come, from the
  measurement plan:
  - the **hand-written hard cases** (numbers in words, numbers split
    across messages, typos), about 200 chats;
  - the **external synthetic set** (ai4privacy, Indonesian rows), written
    by someone else, which tests exactly the shared-author limit.
- **Known misses, found while trying to break it** (not in either set):
  numbers written in words ("nol delapan satu dua…") and obfuscated emails
  ("budi [at] gmail [dot] com").
- **Known over-redaction:** a region letter, a number and a short word
  read as a plate ("ukuran L 2 pcs", "blok B 12 no 5"). Privacy wins over
  tidiness here; lowercase plates are common in chats.
- **Names and addresses** are the NER half's job; see R1 below. R0 gives
  the floor (100% missed).
- The held-out run used `regex` 2026.11.9, the version current that day.
  The lockfile was then held to `regex` 2026.9.29 (a release more than two
  weeks old); a dev re-run with it gives identical numbers.

## R1: the three NER candidates on dev (2026-11-11)

R1 is R0 plus one local NER model for names and addresses (ADR-004). The
three candidates were run on the same 2,000 dev chats, one after another,
on the M2's CPU with 4 threads. Held-out is not touched: only the winner
is scored there, once Arthur has set the names and addresses targets.
Records: `dev-v0.1.0-r0-63dad4467600.json` and
`dev-v0.1.0-r1-{nusabert,horizon,gliner}-*.json`. The table is printed by
`uv run id-chat compare` from those records.

| Config | Names missed (95% upper) | Name precision | Addresses missed (95% upper) | Address precision | Direct identifiers missed | Look-alikes redacted | Over-redaction | Chats/s | Peak memory |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 patterns | 2,219 of 2,219: 100% | — | 646 of 646: 100% | — | 0 | 0 | 0.00% | 847 | 0.55 GB |
| **R1 + NusaBert** | 549: **24.7%** (26.6%) | **97.8%** | 33: **5.1%** (7.1%) | 95.8% | 0 | 19 | 0.18% | 3.0 | 1.2 GB |
| R1 + Horizon (int8) | 444: 20.0% (21.7%) | 78.7% | 624: 96.6% (97.7%) | 75.3% | 0 | 493 | 1.48% | 5.8 | 1.6 GB |
| R1 + GLiNER | 302: 13.6% (15.1%) | 48.8% | 320: 49.5% (53.4%) | 57.3% | 0 | 123 | 3.02% | 2.1 | 2.9 GB |

Peak memory is the process's maximum resident size from `/usr/bin/time`;
it is not in the run records.

**NusaBert is the candidate to take forward.** It is the only one that
finds most addresses, its redactions are nearly all real names and
addresses, and it stays inside the 2 GB memory limit (N2). None of the
three meets a 5% names target yet.

- **NusaBert:**
  - Every one of its 33 missed addresses is an alley ("Gg. Laswi No. 3",
    "Gang Kutai No. 481"); it finds "Jl." streets. A pattern for alley
    addresses would close most of the gap.
  - Missed names are mostly single first names, often lower case
    ("nasrullah", "citra", "Oman"), unusual ones Faker draws ("balamantri",
    "luwes", "kacung"), and names in brackets after a NIK ("(Irma
    Hassanah)"). 16% of name characters stay visible.
  - The 19 look-alikes are all one case: the "1" of the insurance plan
    "rawat inap kelas 1", tagged as a place. That breaks G3, which allows
    none. (An earlier version of this page listed "cluster Anggrek",
    "tipe" and "TLO" too; the run record shows only "1".)
- **Horizon** misses almost every address: it leaves "No." unlabelled
  inside Indonesian addresses, so "No" stays visible and the address
  counts as missed. Its decoding was checked on an English sentence, where
  it finds the street exactly. It also redacts prices ("133jt") as street
  addresses: 186 prices and 254 product names.
- **GLiNER** finds the most names but half its name redactions are wrong:
  it flags chat words such as "kak", "saya", "nama" and "alamat". 190 real
  names are hidden under another placeholder. It is the slowest and
  needs 2.9 GB, over N2.

**Bugs found while building it** (all fixed, with tests):
- Presidio's `GLiNERRecognizer` adds every entity type it is asked for as
  an extra prompt, and Presidio asks every recogniser for every type in
  the registry. GLiNER was therefore also searching for "TELEPON", "NIK"
  and so on, and redacted 321 prices in the first dev run. It is now asked
  only for its two labels; that run's record was discarded.
- NER and pattern matches overlapped on emails and plates, and the more
  confident NER type won, so emails became `<NAMA_n>`. A pattern's type
  now wins.
- Faker names can start with a title ("Dt.", "Hj."). The gold name
  included it, so a model that redacted the name but not the title was
  scored as a miss; titles are now outside the name, as the measurement
  plan says.

**Limits of these numbers:**
- Dev only, generated by the same templates and author as the R0 sets.
  Faker's first names include rare words, which may make names harder
  than in real chats; nicknames like "kak dew" are not generated yet. The
  hand-written hard cases and the external set are still to come.
- The address miss rule counts a visible "No" or house number as a miss
  (any whole word left visible). That is the plan's rule and it stays,
  but it is why Horizon's address rate is so high.
- A decomposed accent ("Dewi" plus a combining mark) makes NusaBert drop
  the surname; text is not normalised before NER.
- With the `ner` group installed, Presidio imports torch on start-up, so
  every `id-chat` command takes about 5 seconds longer, R0 included.

**Next:** the alley and short-name round below.

## R1 round 2: name-cue and street patterns on dev (2026-11-11)

NusaBert's slips on dev had clear shapes, so this round adds patterns
under it (`name_address_patterns.py`) and a filter on its spans
(`ner/recogniser.py: names_no_one`). Same 2,000 dev chats, same CPU
settings; held-out still untouched. New records:
`dev-v0.1.0-r0-209ab471a95b.json` and
`dev-v0.1.0-r1-nusabert-62f27a2568f6.json`.

| Config | Names missed (95% upper) | Name precision | Addresses missed (95% upper) | Address precision | Direct identifiers missed | Look-alikes redacted | Over-redaction | Chats/s | Peak memory |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R1 + NusaBert, before | 549: 24.7% (26.6%) | 97.8% | 33: 5.1% (7.1%) | 95.8% | 0 | 19 | 0.18% | 3.0 | 1.2 GB |
| R0 patterns, now | 259: 11.7% (13.1%) | 100.0% | 0: 0.0% (0.6%) | 100.0% | 0 | 0 | 0.00% | 683 | 0.55 GB |
| **R1 + NusaBert, now** | 54: **2.4%** (3.2%) | **100.0%** | 0: **0.0%** (0.6%) | 98.9% | 0 | **0** | 0.11% | 2.6 | 1.1 GB |

**What changed:**
- **Streets:** "Gang", "Gg.", "Jalan" or "Jl." followed by up to five
  words and a house number ("Gg. Laswi No. 3 RT 01/RW 01"). The house
  number is required, so "lagi di jalan ke kantor" stays readable.
- **Names after a cue:** "a.n", "atas nama", "nama" (also "nama saya",
  "nama anak"); "saya" opening a message and ending at a comma or the end
  of the line; brackets after a 10–16 digit number; a name opening a line
  right before a phone, NIK or account number; a capitalised word after
  "kak", "Pak", "Bu" and so on. A list of chat words (`NOT_NAMES`) stops
  "saya mau booking", "nama anak dan NIK" and "Halo kak Selamat pagi"
  being read as names.
- **NER spans that name no one** are dropped: spans with no letters (the
  "1" of "kelas 1"), bank names before an account number ("Mandiri
  5118..."), and the cue "a.n" itself. G3 holds again on dev.

**Read these numbers with care.** The dev templates have only 17 name
slots and every generated address has "No.", so these rules were written
knowing every shape dev contains. That the patterns alone now miss only
11.7% of names and no addresses on dev says as much about the templates
as about the rules. Held-out uses separate templates and is the real
test; real chats will hold cues and spellings neither set has.

**Still missed (54 names):**
- a name sent alone as the whole reply to "siapa namanya?"; recognising
  it needs the previous turn, and the recognisers see one turn at a time;
- a lower-case name after "kak" ("Salam kenal kak citra"); lower case is
  left out because "kak barang yg datang salah" names no one;
- "Sales kami Galang akan hubungi": a name after a noun phrase, with no
  cue word.

**Bug found while building it** (fixed, with a test): Presidio's phone
recogniser read prices from Rp 1 to 2 million written with dots
("Rp 1.500.000") as phone numbers. Dev had no such price yet, so R0 had
shown no look-alike hits.

**Next:** Arthur sets the names and addresses targets; then NusaBert R1
with these patterns is scored once on held-out.
