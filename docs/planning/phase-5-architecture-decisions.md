# Phase 5: Architecture Decisions

Short ADRs, 2026-11-04, written after the
[measurement plan](measurement-plan.md). **All are decided:** ADRs 001,
005, 006 (local only), 012 and 013 were settled with Arthur one by one;
he accepted the rest as recommended the same day. Licences were checked on 2026-11-04
through the GitHub, Hugging Face and PyPI APIs; the key ones were
re-checked by hand. The summary table and the open questions are at the
end.

```
WhatsApp export / JSONL ─► parser ─► chat records (Pydantic, JSONL; source = synthetic | public | real)
                                          │
              ┌───────────────────────────┴──────────── id_chat_anonymiser (no network, no Inspect)
              ▼
   Presidio AnalyzerEngine
     ├─ Indonesian pattern recognisers (phone, NIK, plate, email, order ID, account, honorific+name)
     └─ local NER recogniser (names, street addresses; model pinned by hash)
              ▼
   merge spans ─► numbered typed placeholders per chat (custom Presidio operator)
              ▼
   anonymised chat records ─────────────────────────────── id_chat_rubric
              ▼
   Inspect task: one chat per sample, codebook in the prompt, 3 epochs
     model: local GGUF via llama-server (OpenAI-compatible), refused for hosted providers on real records
              ▼
   scorer: per-turn codes (structured output) ─► construct scores (Score.value), codes in metadata
              ▼
   agreement: Inspect's krippendorff_alpha + bootstrap; κ via scikit-learn ─► results docs + noise file
```

## Reuse map

Arthur's repos were searched first (`grep` for redact, anonymi[sz]e, PII,
NIK, kappa, krippendorff, across the workspace, excluding employer and
client repos). **No repo anonymises text.** What fits:

| Part | Reused | Built (and why) |
|---|---|---|
| PII detection framework, span merging, anonymisation operators | **Presidio** (ADR-003) | Indonesian recognisers: none exist (this is what A demonstrates) |
| Span-level evaluation, cross-check | **presidio-evaluator**'s `SpanEvaluator` (MIT) | The stricter "miss" rule from the measurement plan (partial leaks count), ~50 lines |
| Synthetic PII values | **Faker `id_ID`** (MIT) | A NIK provider (Faker has none), order IDs, WhatsApp-style phone variants |
| Template filling with exact spans | **presidio-evaluator**'s Faker-based sentence generator, if it handles multi-message chats (slice 1 checks) | Otherwise a small template filler |
| Names and addresses | A local NER model (ADR-004) | — |
| Judge loop, epochs, logs, viewer, model providers | **Inspect AI** (MIT), pinned like the harness (ADR-007) | The task, prompt and scorer |
| Krippendorff's α | **Inspect AI's `krippendorff_alpha`** (MIT, since 0.3.258) (ADR-008) | The bootstrap around it |
| Cohen's κ | **scikit-learn** `cohen_kappa_score` (BSD-3) | — |
| Local model serving | **llama.cpp `llama-server`**, as in Project 14 (ADR-007) | — |
| Run records, score-once, provenance, fingerprints | **agent-eval-harness**'s records habits and **mcp-gateway**'s `eval/score.py` discipline | This repo's records, credited |
| Model table and licence reasoning | **Project 14** (`small-model-training`) Phase 5's model comparison | Larger judge sizes (ADR-006) |
| Typed placeholders | **Project 12**'s planned redaction (`<NOMOR_HP>`, `<REKENING>`, `<NAMA>`) | The other way round: Project 12 should depend on this anonymiser (open question 6) |
| Relationship-marketing codebook | Nothing open operationalises Morgan & Hunt or SERVQUAL for chat transcripts (searched GitHub and Hugging Face) | **Built:** this is what C demonstrates |

## ADR-001: One repo, two packages (settled)

**Decision:** `id-chat-research`, a uv workspace with two packages:
- `id_chat_anonymiser`: the chat record format, the parser, the
  anonymiser and its scorer. Depends on Presidio and the NER runtime, not
  on Inspect (N7).
- `id_chat_rubric`: the codebook, rating sheets, the Inspect task and
  scorer, the agreement report. Depends on the anonymiser for the record
  format.

**Why:** one session, one CI, one set of planning docs; the anonymiser can
still be installed and cited alone.

**Rejected:** *two repos* (two CIs, two GitHub repos, a cross-repo
dependency for the record format); *one package* (the anonymiser would
pull in Inspect and the judge's dependencies).

## ADR-002: The chat record format: a small Pydantic model, JSONL

**Decision (accepted 2026-11-04):** `ChatRecord` with `format_version`, `chat_id`,
`source` (`synthetic` | `public` | `real`, required, no default), `domain`,
`turns` (`index`, `role`: `customer` | `agent` | `system`, `text`,
`timestamp` optional), and an optional `outcome` (free key–value, for the
thesis's Stage 1). One record per line. Converters to Inspect messages
live in the rubric package.

**Why:** B, D and the thesis all need one shape. `source` is how the code
refuses to send real data to a hosted model (R4).

**Rejected:**
- *Inspect's `ChatMessage` list:* it would make the anonymiser depend on
  Inspect, and it has no `source` or timestamp.
- *ConvoKit's corpus format* (Cornell, MIT): a full analysis toolkit with
  its own storage, heavier than the problem; a converter can be added if
  the thesis analysis uses it.
- *Raw WhatsApp text:* no roles, ambiguous multi-line messages.

**Changed while building (2026-11-09, slice 0):** the record format is its
own package, `id-chat-records`, depending only on Pydantic, not part of
the anonymiser package. AI Flight School depends on it by git tag
(`v0.1.0`), and would otherwise have installed Presidio and spaCy for one
model. ADR-001's two packages become three.

## ADR-003: Presidio as the anonymiser's engine

**Decision (accepted 2026-11-04):** `presidio-analyzer` and `presidio-anonymizer` (MIT;
2.2.366, 2026-10-27; 224 contributors; the repo moved from
`microsoft/presidio` to `data-privacy-stack/presidio` in 2026).
- Indonesian recognisers as `PatternRecognizer`s with validation (NIK
  structure: region code, birth date with +40 for women).
- Phones through Presidio's `PhoneRecognizer` with
  `supported_regions=("ID",)` (**trap:** Indonesia isn't in its default
  regions), plus patterns for WhatsApp-style variants it misses.
- The NER model as a custom recogniser. **Trap:** Presidio's
  `TransformersNlpEngine` still loads a spaCy pipeline for tokenising, and
  spaCy has no trained Indonesian one. Spike 1 decides between a blank
  Indonesian spaCy pipeline and bypassing the NLP engine.
- Consistent numbering (`<NAMA_1>`) as a custom anonymizer operator that
  keeps its value-to-number map in memory for one chat (P6, P7).

**Why:** Presidio already does the registry, context words, overlapping
spans and anonymisation operators, and presidio-evaluator measures it.
What's missing for Indonesian is exactly the recognisers.

**Rejected:**
| Option | Licence | Why not |
|---|---|---|
| scrubadub | Apache-2.0 on GitHub, MIT on PyPI (inconsistent) | No release since 2023; no Indonesian |
| `NHNA14875/indonesian-pii-anonymization` | MIT | One author, weeks old; read for ideas only |
| `iqbalr3000/palang-ai` | MIT | TypeScript gateway, one maintainer; its NIK/NPWP patterns compared against ours |
| No Indonesian PII package on PyPI | — | Checked several names; none exist |
| Regex and NER glued by hand | — | Rebuilds Presidio's merging and operators |

**Changed while building (2026-11-09, slices 1–2):**
- **The spaCy question (spike 1) is settled for patterns:** a blank
  Indonesian pipeline (`spacy.blank("id")`, a tokeniser, no download).
  Presidio's `SpacyNlpEngine` would otherwise try to download a model it
  can't find. The NER half revisits this.
- **Merging and numbering are ours, not presidio-anonymizer's.** For two
  partly overlapping matches of different types it keeps one and trims
  the other, which can leave part of a number visible; we redact the
  union. It also reports redactions in output positions, and the scorer
  needs input positions. About 40 lines; presidio-anonymizer is dropped.
- **Presidio's `EmailRecognizer` isn't used:** its validation calls
  tldextract, which fetches the public suffix list over the network on
  first use (found with the network blocked in a test). Ours is a plain
  pattern (N1).
- **A Presidio regex timeout fails closed here.** Presidio logs "timed out,
  skipping" and drops that pattern for that text, which would leave data
  unredacted; the anonymiser raises instead.

## ADR-004: NER for names and addresses: benchmark three local models

**Decision (accepted 2026-11-04):** in spike 1 and slice 3, score three candidates on the
**dev** set only, then score the winner once on held-out:

| Model | Licence | Indonesian | Size | Note |
|---|---|---|---|---|
| `cahya/NusaBert-ner-v1.3` | MIT (card) | Yes, trained on NERGrit | 644 MB | Best maintained Indonesian NER (updated 2026-10). NERGrit's original repo is gone, so its data lineage is murky; we use the weights, never redistribute them |
| `Horizon-Labs/pii-redactor-base` | Apache-2.0 | `id` listed | 1.23 GB (641 MB ONNX) | Built for PII; trained on CC-BY-4.0 data, so attribution is owed upstream |
| `urchade/gliner_multi-v2.1` | Apache-2.0 | "Multilingual", Indonesian unverified | 1.16 GB | Zero-shot with our own labels ("street address") |

Runtime: ONNX Runtime where the model ships an ONNX export, else
`transformers` on CPU; whichever keeps R1 under 2 GB RAM (N2). Weights
are fetched by `fetch-models`, pinned by hash (S1), never committed.

**Public evaluation data** (downloaded by script, never committed):
- `ai4privacy/pii-masking-openpii-1.5m`, Indonesian rows (CC-BY-4.0,
  attributed): an **external synthetic set** written by someone else,
  which tests the "same author" limit of our held-out templates.
- SINGGALANG (free use, citation requested): names in formal text.

**Rejected:**
| Option | Why not |
|---|---|
| `cahya/xlm-roberta-*-indonesian-NER` | No licence |
| `w11wo/indonesian-roberta-base-nerp-tagger`; NERP data | NERP is CC-BY-SA-4.0; unclear whether share-alike reaches the weights |
| `0xcynyx/ner-pii-indonesian-mini` | Distilled from an unlicensed teacher; scored against teacher labels |
| `LiquidAI/LFM2.5-Encoder-350M-PII-Detector`, `nvidia/gliner-PII` | Custom licences (and nvidia's is English only) |
| `urchade/gliner_multi_pii-v1`, knowledgator and fastino PII models | No Indonesian |
| `openai/privacy-filter` | 2.8 GB, Indonesian unverified; reserve if all three fail |
| ai4privacy 200k–400k | Custom licence: larger companies pay, redistributed derivatives banned |
| Stanza, Flair | No Indonesian NER model |
| Fine-tuning IndoBERT on our own data | Only if all three miss too much; the generator could supply data |

**Changed while building (2026-11-10, slice 3):**
- **Horizon runs from its int8 ONNX export** (641 MB) instead of the full
  weights (1.23 GB): it keeps the three candidates within the approved
  3 GB, and Horizon's own check reports 99.86% token agreement with the
  full model. The three downloads total 2.49 GB.
- **GLiNER runs through Presidio's own `GLiNERRecognizer`**, which chunks
  long texts and maps labels; GLiNER alone keeps only a text's first 384
  words and drops the rest without an error. gliner also loads its
  backbone's tokenizer (`microsoft/mdeberta-v3-base`, 4 MB) by branch, so
  that repo is pinned too and its commit checked on load.
- **NusaBert and Horizon share our token classifier**
  (`ner/token_classifier.py`, `ner/spans.py`), not Presidio's
  `HuggingFaceNerRecognizer`: that one needs PyTorch weights (Horizon's
  1.23 GB file), and one decoder for both keeps them comparable. It
  redacts whole words, so a name split into sub-words is never half left.
- **Every model drops spans scoring under 0.5**, the default in Horizon's
  own `redact.py` and GLiNER's threshold.
- **On overlap, a pattern's type beats an NER type**: in smoke runs
  NusaBert tagged email addresses and plates as names.
- **Label mapping:** NusaBert `PER` → name, `FAC`/`LOC` → address (`GPE`,
  cities and provinces, stays); Horizon `PERSON` → name, `STREET_ADDRESS`
  → address (`LOCATION` stays); GLiNER is asked for "person" and "street
  address".
- **Versions held back** to releases at least about two weeks old:
  gliner 0.2.29 (so transformers 5.16.1 and huggingface-hub 1.33.0),
  hf-xet below 1.8, sentencepiece below 0.2.3. CI installs CPU-only torch.

## ADR-005: Rubric unit: yes/no behaviour codes per agent turn (settled)

**Decision:** codes per agent turn, summed into construct scores per chat
(measurement plan). The codebook is a versioned YAML file: construct,
code, definition, an Indonesian yes and no example, the source, and
whether the chat score is "share of turns" or "at least once".

**Borrowed, not depended on:** prometheus-eval's way of writing a rubric
(criterion, what each answer means, reference examples; Apache-2.0).
EPITOME's three empathy dimensions are cited as design input; its code
and data have no licence or are non-commercial, so neither is used.

**Rejected:** *1–5 per construct per chat* (lower agreement, harder to
relate to outcomes); *both* (more rater time for the same evidence);
*prometheus-eval as the judge* (its judge models are English only).

## ADR-006: The judges: local open models, $0, compared (settled: local only)

**Decision for the models (accepted 2026-11-04; changed the same day to
compare judges, for the thesis's RQ2):** the agreement, sensitivity and
bias sets are coded by **two or three** judges, each pinned by file hash:
Qwen3.5-9B and Sailor2-8B-Chat, plus Gemma-4-12B-it if spike 2 shows it
fits N2 on long chats, otherwise Apertus-SEA-LION once its base licence
is checked. Spike 2 only checks that each one runs, fits and returns
valid output, and picks the prompt language; it no longer picks the
judge. The judge used downstream is chosen afterwards by the
pre-registered rule in the measurement plan.

**Why compare:** one judge's agreement with people says little about
whether "a local judge" can stand in for people; two or three, with
different Indonesian training, show how much depends on the model. Each
extra judge costs only local compute (run time measured in spike 2) and
disk.

| Model | Licence | 4-bit RAM | Indonesian | Verdict |
|---|---|---|---|---|
| **Qwen3.5-9B** | Apache-2.0 | ~6–7 GB | Multilingual; Indonesian not listed on the card | **Judge**, newest |
| **Sailor2-8B-Chat** | Apache-2.0 | ~5–6 GB | Yes, built for South-East Asian languages | **Judge**, Indonesian-tuned; not updated since 2025-02 |
| Gemma-4-12B-it | Apache-2.0 | ~7–8 GB | Multilingual | **Third judge** if it fits on 16 GB with long chats (spike 2) |
| Apertus-SEA-LION-v4-8B-IT | MIT on the card; base model's licence unverified | ~5–6 GB | Yes | Third judge if Gemma doesn't fit, once the base licence is checked |
| Gemma 2/3, Sahabat-AI, Llama-based SEA-LION | Custom terms (Gemma, Llama) | — | Yes | Rejected: custom licences |

**Why local:** the chosen judge can later read real chats (R4), so the
agreement measured on synthetic chats is for the judge that will be used.

**Rejected:** *a hosted model* (settled); *a hosted comparison* (not
needed for the thesis, and costs a budget).

## ADR-007: Inspect AI for the judge, served by llama-server

**Decision (accepted 2026-11-04):**
- The judge is an Inspect task: one chat per sample, the rubric a
  `@scorer`, `--epochs 3` for test–retest. The scorer returns construct
  scores as `Score.value` (a dict) and the per-turn codes, codebook hash
  and model hash in metadata, so the harness (D) can carry them.
- `inspect-ai` pinned to the **same version as agent-eval-harness**
  (0.3.283 today), so D can import the scorer without a conflict.
- The model is served by **llama.cpp's `llama-server`** from a GGUF file,
  as in Project 14, and reached through Inspect's OpenAI-compatible
  provider, with a JSON schema for structured output (spike 3 checks it
  works).

**Why:** Inspect is Arthur's eval stack, and B and D are both built on
it. llama-server keeps one local runtime across his projects, and a GGUF
file can be pinned by hash.

**Rejected:**
- *Ollama* (MIT; Inspect has a provider): easier to install, but another
  daemon with its own model store. A close second; chosen if llama-server
  fails spike 3.
- *mlx-lm's server:* fast on Apple silicon, but a second runtime next to
  Project 14's llama.cpp path; no mlx-community build of Sailor2.
- *A plain Python loop calling the model:* rebuilds epochs, logs and the
  viewer.

## ADR-008: Agreement statistics: Inspect's α, scikit-learn's κ

**Decision (accepted 2026-11-04):**
- **α:** Inspect AI's `krippendorff_alpha` (nominal for codes, interval
  for construct scores), called through its public metric interface with
  each unit's ratings as a list (R1, R2, judge). A bootstrap over chats
  (2,000 draws, fixed seed) gives the interval.
- **κ:** scikit-learn's `cohen_kappa_score`, per pair.
- **Test oracle:** the `krippendorff` package, in **dev dependencies
  only**, to check our numbers in tests.

**Traps found while checking (from reading the source, not yet
reproduced):**
- `krippendorff` on PyPI is **GPL-3.0**. It must never become a runtime
  dependency of this MIT repo.
- Inspect's α returns **1.0 when all ratings are the same** (no expected
  disagreement). A code nobody ever marks would then "pass" G4. The report
  treats zero-variation codes as **undefined**, and slice 6 writes a test
  for it. Whether Inspect should return NaN there is a question for
  upstream, raised only after a repro.
- Inspect's α has no ratio level (not needed here).
- presidio-evaluator's `SpanEvaluator`: its docstring says the IoU
  threshold defaults to 0.5, but the signature says 0.9. We pass it
  explicitly. Reported upstream only after a repro.

**Rejected:** *writing α by hand* (Inspect's is tested and MIT, and Arthur
contributes to Inspect); *statsmodels* (heavier, only needed for Fleiss'
κ with three or more raters, which v1 doesn't have).

## ADR-009: Rating sheets as CSV, rated in a spreadsheet

**Decision (accepted 2026-11-04):** `rating-sheet` writes a CSV per rater (one row per
agent turn, one column per code, the chat text in a column);
`import-ratings` validates it and pseudonymises it.

**Why:** two raters and ~700 turns. A spreadsheet needs no install and no
server.

**Rejected:** *Label Studio* (Apache-2.0) and *Argilla* (Apache-2.0):
servers, and Docker on the Mac, for two people; *Doccano* (MIT): built
for spans, not per-turn checklists; *Google Sheets:* fine for synthetic
chats, but the procedure must also work for a real sample later, which
can't go to a third party.

## ADR-010: Files, not a database

**Decision (accepted 2026-11-04):** JSONL for records and codes, YAML for the codebook and
config, JSON run records, all fingerprinted.

**Why:** a few thousand chats. Files diff in git and need no server.

**Rejected:** *SQLite or Postgres:* nothing here needs queries or
concurrent writers.

## ADR-011: Typer CLI, the workspace's tooling

**Decision (accepted 2026-11-04):** one `id-chat` Typer CLI; pytest; ruff with the
complexity rules (`C901` at 10, `PLR0911–0915`); pyright strict; gitleaks;
a CI step that fails if any committed record has `source: real`; the
employer-terms check (I1) with its list kept outside the repo.

**Rejected:** *argparse:* the workspace uses Typer.

## ADR-012: Synthetic data: generator for A, Claude-written chats for C (settled)

**Decision:** A's sets come from templates and Faker `id_ID`, so the labels
are exact; hard cases and hard negatives are written by Claude. C's sets
are written by Claude to behaviour plans. Every synthetic record says
`source: synthetic`, and the generator or author is recorded. Arthur
reviews for resemblance to his workplace; he doesn't write chats.
Domains: vehicles, electronics, property and insurance.

**Rejected:** *a local model generating chats* (labels no longer exact;
slow); *Arthur writing chats* (his knowledge of the real chats could leak
in).

## ADR-013: MIT licence and the dependency policy (settled: MIT)

**Decision:** MIT. Runtime dependencies must be MIT, BSD, Apache-2.0 or
similar. GPL only as a dev-only test oracle. Model weights and datasets
are downloaded by script, never committed, and their licences and
attributions are listed in `docs/third-party.md`. Non-commercial,
share-alike and custom-licensed data and models are not used.

## ADR-014: Real data never touches anything but Arthur's Mac

**Decision (accepted 2026-11-04):** the threat model's R-rows: an encrypted volume
outside the workspace and outside synced folders; a Claude Code deny rule
on its path; Arthur runs the runbook himself; `source: real` refused by
any hosted provider; aggregates only leave the volume.

**Why:** the permission and the ethics approval cover local processing.
A Claude Code session is a hosted model: if it reads a real chat, the
chat has left the Mac.

**Rejected:** *anonymise first, then let tools and sessions see the
anonymised chats:* anonymised chats can still re-identify people (R6),
and the residual check would come too late.

## Summary

| ADR | Decision | Main alternative rejected | Status |
|---|---|---|---|
| 001 | One repo, two packages | Two repos | **Settled 2026-11-04** |
| 002 | Own small `ChatRecord` model, JSONL, required `source` | Inspect messages; ConvoKit | **Accepted 2026-11-04** |
| 003 | Presidio with Indonesian recognisers | scrubadub; hand-rolled | **Accepted 2026-11-04** |
| 004 | Benchmark NusaBert, Horizon pii-redactor, GLiNER multi; ai4privacy openpii (id) as external set | Unlicensed, SA or custom models | **Accepted 2026-11-04** |
| 005 | Yes/no codes per agent turn | Likert per chat | **Settled 2026-11-04** |
| 006 | Local judges compared: Qwen3.5-9B, Sailor2-8B, plus Gemma-4-12B or Apertus; one chosen by rule | Hosted model; one judge picked in a spike | **Local settled**; comparison **accepted 2026-11-04** |
| 007 | Inspect AI (harness's pin), llama-server | Ollama; plain loop | **Accepted 2026-11-04** |
| 008 | Inspect's α, scikit-learn's κ; GPL `krippendorff` dev-only | Hand-written α | **Accepted 2026-11-04** |
| 009 | CSV rating sheets | Label Studio, Argilla | **Accepted 2026-11-04** |
| 010 | Files, not a database | SQLite | **Accepted 2026-11-04** |
| 011 | Typer, workspace tooling and checks | argparse | **Accepted 2026-11-04** |
| 012 | Generator for A; Claude-written for C | Local-model generation | **Settled 2026-11-04** |
| 013 | MIT; dependency licence policy | Apache-2.0 | **Settled 2026-11-04** |
| 014 | Real data on the Mac only, Arthur runs it | Sessions see anonymised chats | **Accepted 2026-11-04** |

## Open questions

**For Arthur:**
1. ~~**The recommended ADRs**~~: accepted as recommended, 2026-11-04.
2. **The second rater:** who, and when are they free (about 6 hours)?
3. **Model downloads** (P3): NER candidates ~3 GB in total for the
   benchmark, then one kept; two or three judges at ~5–8 GB each
   (~13–21 GB). OK when the slices start?
4. **The employer's written line** that the tools are separate (P6): when
   to ask for it. It's not needed until the gate, but it costs nothing to
   ask early.
5. **Outcomes in the real logs** (hot-lead flag, handoff, purchase): the
   record format has an optional `outcome`; which fields exist decides
   Stage 1, not this repo.
6. **Project 12's redaction script:** should Project 12 depend on this
   anonymiser instead of writing its own? If yes, it goes to Project 12's
   session when that project resumes.

**For the spikes:** Presidio and spaCy without an Indonesian pipeline;
NER RAM and speed; each judge's RAM, speed and valid output, and
whether Gemma-4-12B fits;
structured output through llama-server; Apertus's base licence.

## Sources (read 2026-11-04)

**Licences and tools:**
[Presidio](https://github.com/data-privacy-stack/presidio) ·
[presidio-research](https://github.com/data-privacy-stack/presidio-research) ·
[Faker](https://github.com/joke2k/faker) ·
[cahya/NusaBert-ner-v1.3](https://huggingface.co/cahya/NusaBert-ner-v1.3) ·
[Horizon-Labs/pii-redactor-base](https://huggingface.co/Horizon-Labs/pii-redactor-base) ·
[urchade/gliner_multi-v2.1](https://huggingface.co/urchade/gliner_multi-v2.1) ·
[ai4privacy/pii-masking-openpii-1.5m](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1.5m) ·
[SEACrowd SINGGALANG loader](https://huggingface.co/datasets/SEACrowd/singgalang) ·
[krippendorff on PyPI](https://pypi.org/project/krippendorff/) ·
[Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) ·
[Sailor2-8B-Chat](https://huggingface.co/sail/Sailor2-8B-Chat) ·
[gemma-4-12B-it](https://huggingface.co/google/gemma-4-12B-it) ·
[prometheus-eval](https://github.com/prometheus-eval/prometheus-eval) ·
Inspect AI's `scorer/_metrics/krippendorff.py` and CHANGELOG (0.3.258)

**Theory:**
Morgan, R. M., & Hunt, S. D. (1994). The commitment-trust theory of
relationship marketing. *Journal of Marketing*, 58(3), 20–38. ·
Parasuraman, A., Zeithaml, V. A., & Berry, L. L. (1988). SERVQUAL: A
multiple-item scale for measuring consumer perceptions of service
quality. *Journal of Retailing*, 64(1), 12–40. ·
Surprenant, C. F., & Solomon, M. R. (1987). Predictability and
personalization in the service encounter. *Journal of Marketing*, 51(2),
86–96. ·
Krippendorff, K. (2004). *Content Analysis* (2nd ed.). Sage. ·
Sharma, A., et al. (2020). A computational approach to understanding
empathy expressed in text-based mental health support (EPITOME). *EMNLP*.
