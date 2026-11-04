# Phase 2: Requirements & Constraints

Phases 3 (threats) and 4 (design) are folded in, as in Projects 9 and 12.
Threats have their own page: [threat model](threat-model.md). The build
goes in slices ([slice plan](slice-plan.md)).

## Core scenarios

### 1. Anonymising a chat export (A)

1. A researcher has a WhatsApp chat export (`.txt`, or the `.zip`
   WhatsApp makes) or a JSONL file of chat records.
2. `id-chat anonymise exports/ --out anonymised/` parses each chat into the
   chat record format (ADR-002): turns, sender role, timestamp, text.
   Sender names become `<NAMA_n>` like any other name.
3. Recognisers find spans (patterns, then NER; ADR-003, ADR-004). Spans are
   merged, overlaps resolved toward the larger span, and each distinct
   value gets a numbered typed placeholder for that chat.
4. The output is the anonymised chat records, plus a **report with counts
   only**: chats, turns, spans per type, low-confidence spans. It never
   prints text or values.
5. No network is used at any step. The command refuses to start if a
   hosted model is configured (R4).

### 2. Scoring the anonymiser (A)

1. `id-chat score-anonymiser --set heldout` runs one config over the
   frozen held-out set.
2. It refuses if this anonymiser version already has a held-out result.
3. It writes a run record (version, config hash, set fingerprint, counts,
   per-type miss and over-redaction rates with intervals) and regenerates
   `docs/results-anonymiser.md` from the records.

### 3. Rating chats by hand (C)

1. `id-chat rating-sheet --set agreement --rater R2` writes a sheet: one
   chat per section, each agent turn numbered, a column per code. A CSV
   that opens in a spreadsheet; no app to build (ADR-009).
2. The rater fills it in alone, with the codebook open.
3. `id-chat import-ratings` checks the sheet (every turn coded, values
   yes/no, codebook hash matches) and writes pseudonymised codes.

### 4. Judging chats (C)

1. `inspect eval id_chat_research/rubric_task.py --model <local model>
   --epochs 3` runs the judge over a set: each chat is a sample, the rubric
   a scorer (ADR-007).
2. The judge sees the codebook and one chat at a time, and returns a code
   per agent turn per code, as structured output validated against a
   Pydantic model. Invalid output is retried once, then recorded as
   missing, never guessed.
3. The scorer returns per-construct scores as the `Score` value, and the
   per-turn codes, codebook hash and judge model in its metadata.

### 5. Measuring agreement (C)

1. `id-chat agreement --set agreement` reads the human codes and the
   judge's Inspect logs for the same codebook version.
2. It computes the numbers in the measurement plan and applies the
   pre-registered pass rules per code and construct.
3. It writes `docs/results-rubric.md` and the noise file D uses.

### 6. Using the rubric from elsewhere (B and D)

- **AI Flight School (B)** converts its conversation records to the chat
  record format and calls the scorer, or imports it into its own Inspect
  task. Customer turns from simulated customers are compared with real
  anonymised chats by B's own measures.
- **agent-eval-harness (D)** carries the scorer's per-construct values in
  its trial records and compares paired runs on them. D reads the noise
  file for power planning.

## Functional requirements

| # | Requirement | Priority |
|---|---|---|
| F1 | Chat record format: Pydantic model, JSONL, a version field; roles `customer`, `agent`, `system`; `source` is `synthetic`, `public` or `real` | Must |
| F2 | WhatsApp `.txt` export parser for Indonesian and English phone locales (both date formats WhatsApp writes) | Must |
| F3 | Pattern recognisers: phone, NIK, email, plate, order ID, bank account; honorific + name | Must |
| F4 | NER for names and street addresses, local model | Must |
| F5 | Consistent numbered typed placeholders per chat | Must |
| F6 | Synthetic PII generator: dev and held-out templates, seeds, exact spans | Must |
| F7 | Anonymiser scorer: per type miss, leak, over-redaction, consistency, Wilson intervals, score-once | Must |
| F8 | Codebook as a versioned YAML file: constructs, codes, definitions, Indonesian examples, sources | Must |
| F9 | Rating sheet export and import with validation | Must |
| F10 | Judge as an Inspect scorer with a local model, structured output; the same task runs any of the compared judges | Must |
| F11 | Agreement report per judge: α with bootstrap intervals, κ, prevalence, raw agreement, test–retest, sensitivity, bias, pass rules, the chosen judge | Must |
| F12 | Noise file for D | Should |
| F13 | R2: local LLM sweep for missed PII, may only add redactions | Could |
| F14 | Pseudonymised outputs that keep gender or relation hints (`<NAMA_1:pria>`) | Won't (v1): adds re-identification risk for little analytic gain |

## Non-functional requirements

| # | Requirement | Measured by |
|---|---|---|
| N1 | **Local only for anything that could touch real data.** No network calls in the anonymiser; the judge's model served on the Mac | A test that runs the anonymiser with sockets blocked; a check that refuses hosted providers for `source: real` (R4) |
| N2 | **Fits an M2 with 16 GB.** Anonymiser R1 under 2 GB RAM; each judge model ≤ 7 GB at 4-bit, loaded one at a time, with the rest of the Mac usable | Measured in spikes 1 and 2 |
| N3 | **$0.** Free libraries, local models, volunteer raters | Run records |
| N4 | **Reproducible.** Seeds, set fingerprints, codebook hashes, model file hashes in every run record | Run records |
| N5 | **No content in logs.** CLI output and logs carry counts and ids, never chat text, for any `source: real` record | A test over the CLI's output on a canary chat |
| N6 | **Readable.** The workspace code rules: ruff with complexity rules, pyright strict, `docs/guide.md` | CI |
| N7 | **Installable alone.** `pip install` of the anonymiser package pulls no judge or Inspect dependencies | CI installs it in a clean venv |

## Constraints

- **Data:** synthetic or public only, until the real-data gate. Public
  datasets only under licences that allow the use (Phase 5, ADR-004).
- **Employer IP:** no employer code, prompts, product names, templates or
  chat wording. The employer and its clients are never named, in code,
  docs, commits or test data. Synthetic chats use generic domains and are
  reviewed by Arthur for resemblance (he doesn't write them, so his
  knowledge of the real chats doesn't leak into them).
- **Stack:** the workspace's Python stack: uv, Pydantic, Typer, pytest,
  ruff, pyright; Inspect AI for the judge (ADR-007). No database: files
  and JSONL are enough for sets of this size (ADR-010).
- **Machine:** the Mac (M2, 16 GB). At most one heavy local job at a time
  (the workspace rule): no judge runs while another session is running a
  model or Docker stack.
- **Licence:** MIT for this repo. Dependencies must be compatible with
  publishing under MIT (no AGPL, no non-commercial model or data terms in
  what is shipped).
- **Language:** codebook definitions in English, with Indonesian examples;
  chats in Indonesian; the judge prompt in English with Indonesian
  examples (spike 2 checks whether an Indonesian prompt scores better).

## Data flow

```
                synthetic generator ─┐
  Claude-written chats (marked) ─────┼─► chat records (JSONL, source=synthetic)
   public NER text (if licensed) ────┘            │
                                                  ▼
                              anonymiser (patterns ─► NER ─► merge ─► placeholders)
                                                  │
                     scorer vs exact spans ◄──────┤
                                                  ▼
                                   anonymised chat records
                                                  │
           rating sheets ◄── humans               ▼
                │                 Inspect task: local judge (3 epochs) ──► per-turn codes
                ▼                                                            │
         pseudonymised codes ──────────► agreement report ◄──────────────────┘
                                                  │
                                  results docs + noise file ──► D (harness), B (Flight School)

  After the real-data gate only, on Arthur's Mac, in an encrypted folder outside synced paths:
  real exports ─► anonymiser ─► residual check by Arthur ─► judge (passing codes) ─► aggregates only
```

## Failure handling

| Failure | Behaviour |
|---|---|
| A chat export line doesn't parse | Kept as a continuation of the previous message (WhatsApp's multi-line messages); counted; never dropped silently |
| NER model missing or fails to load | The command stops with "NER model not found at …: run `id-chat fetch-models`". It never falls back to patterns-only on its own, because that raises the miss rate unannounced |
| A span overlaps another of a different type | The larger span wins; its type is the higher-risk one (NIK over phone); counted in the report |
| Judge output invalid | One retry; then that turn's codes are missing, counted, and excluded from α for that code, never filled in |
| Judge model differs from the one in the agreement result | The scorer warns, and the report marks the scores "judge not validated for this model" |
| Rating sheet has blanks or a different codebook hash | Import refuses, naming the row and what to fix |
| Held-out already scored for this version | Refused, saying which run record has the result |
