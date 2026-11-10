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
- **Names and addresses** are the NER half's job (slice 3). Their target is
  set before R1 is built, as the measurement plan requires; R0 gives the
  floor (100% missed).
- The held-out run used `regex` 2026.11.9, the version current that day.
  The lockfile was then held to `regex` 2026.9.29 (a release more than two
  weeks old); a dev re-run with it gives identical numbers.
