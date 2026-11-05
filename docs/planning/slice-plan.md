# Slice Plan and Cost Model

Every slice uses synthetic or public data. Every slice costs $0.

## Prerequisites

| # | Prerequisite | Needed for | Who |
|---|---|---|---|
| P1 | Arthur OKs Phases 1, 2 and 5, the measurement plan and the threat model | Slice 0 | Arthur |
| P2 | The GitHub repo `id-chat-research` exists | Pushing anything | Arthur |
| P3 | Model downloads approved, with sizes stated first (three NER candidates ~3 GB for the benchmark, then one kept; two or three judges at ~5–8 GB each) | Slices 3 and 6 | Arthur |
| P4 | A second rater who hasn't seen the design, with about 6 hours over two weeks | Slice 5 | Arthur |
| P5 | Arthur's time: review synthetic sets for resemblance to work (~2 h), and check that each of the 150 bias pairs keeps the behaviour the same (~2–3 h at about a minute per pair); rate calibration and agreement sets (~6 h) | Slices 1, 4, 5 | Arthur |
| P6 | A written line from the employer that the thesis tools are separate from its product | The real-data gate | Arthur |

## Spikes (local, $0)

| # | Question | Method | Pass | Time |
|---|---|---|---|---|
| 1 | Does Presidio with custom Indonesian pattern recognisers and a Hugging Face NER model run on the M2, and how fast? | Install in a scratch venv; 20 generated chats; measure RAM and chats/s | Under 2 GB RAM; recorded in ADR-003/004 | 2 h |
| 2 | Does each judge from ADR-006 run on the M2, and which prompt language works? | Qwen3.5-9B, Sailor2-8B and Gemma-4-12B on 5 calibration chats, English vs Indonesian prompt; tokens/s, peak RAM and valid output | Two or three judges kept and one prompt language chosen, recorded in ADR-006; each ≤ 7 GB RAM, or Gemma swapped for Apertus | 4 h |
| 3 | Does Inspect's local provider return valid structured output from the chosen model? | One chat through an Inspect task | Valid Pydantic output on 5/5 | 1 h |
| 4 | Licences of the Indonesian NER datasets and models | Read the dataset cards and papers | Recorded in ADR-004 | 1 h |

Each spike stays in a `spike/` branch or a scratch folder; only its finding
is committed, in the ADR.

## Slices

**Evaluation first:** each tool's scorer and sets come before the tool.
Each new test is mutation-checked once. Each slice updates
`docs/guide.md`.

| Slice | Delivers | Done when | Cost |
|---|---|---|---|
| **0. Scaffold** | uv workspace with two packages; README with layout; CI (ruff with complexity rules, pyright strict, pytest, gitleaks, the `source: real` check, the employer-terms check I1, a licence check); the chat record format (F1); the WhatsApp parser (F2) | CI green; parser tests cover both date formats and multi-line messages; R3 and R4 tests pass | $0 |
| **1. The PII sets** | Generator (F6) with dev and held-out templates; hard cases and hard negatives written by Claude; Arthur's review; fingerprints | Held-out templates committed and fingerprinted **before** any recogniser; counts meet the measurement plan (≥1,000 per direct identifier type) | $0 |
| **2. Patterns baseline (R0)** | Pattern recognisers (F3); span merging; placeholders (F5); the scorer (F7); `docs/results-anonymiser.md` | Held-out scored once for R0; G1 met for direct identifiers or the gap written up; name/address target written into the measurement plan | $0 |
| **3. NER (R1) and the CLI** | NER for names and addresses (F4), model pinned by hash; `id-chat anonymise`; `fetch-models` | R1 scored once on held-out; G1 and G3 met; name/address target met or the gap written up; no-network and no-content tests pass | $0 |
| **4. Codebook and chat sets** | Codebook v1 (F8) with sources; calibration, agreement, sensitivity and bias sets written by Claude to plans; Arthur's resemblance review; fingerprints | Every code has a definition, an Indonesian yes and no example, and a source; agreement set frozen | $0 |
| **5. Human ratings** | Rating sheet export/import (F9); calibration rounds; codebook v2; agreement set rated by R1 and R2 | Human–human α per code reported with intervals; codes failing G4 rewritten (and re-rated) or dropped | Raters' time |
| **6. The judges** | Inspect task and scorer (F10); each judge run over the agreement, sensitivity and bias sets, one at a time; agreement report (F11) with a column per judge; bias results | Pre-registered pass rules applied to every judge and one chosen; `docs/results-rubric.md` published from run records; J1–J4 tests pass | $0 |
| **7. Interfaces handed over** | Noise file (F12); a tagged release of the chat record format and scorer; notes to Project 10 and Project 2 sessions with the interface | Each owning session has the interface note and a working import example | $0 |
| **8. Real-data runbook (no real data)** | The runbook: encrypted volume, Claude Code deny rule, sync checks, commands, residual check, aggregate-only outputs, publication checklist; a dry run with canary chats | The dry run shows no canary text in any output, log or Claude-readable path | $0 |
| **9. Evidence and write-up** | Results from run records; JOURNEY; README numbers; portfolio entry with the portfolio session | Every number traces to a run record; privacy and employer-terms checks pass | $0 |
| **10. R2: LLM sweep (Could)** | Local model pass that may only add redactions (F13) | R2 scored once; adopted only if it lowers misses without breaking G3 | $0 |

**Order:** slices 0–3 (A) before 4–6 (C), as the build order A → C → B → D
says. Slices 4 and 1 can overlap, since writing chat sets needs no code.

## The real-data gate

**Not a slice.** Real chats enter only when **all** of these hold, and
Arthur records each in the private notes:

1. Written permission from the data owner covering **research and
   publication** of aggregate results, with the scope stated.
2. University ethics approval for the study (expected after enrolment;
   settled 2026-11-04 that nothing real comes before it).
3. The employer's written line that the tools are separate (P6).
4. Slices 3, 6 and 8 done: G1 and G3 met, the judge's passing codes
   known, the runbook dry-run clean.
5. The threat model's R-rows marked Done.

Then Arthur, not a Claude session, runs the runbook. The first real run
is the residual check (measurement plan) and a judge–human check on a
real sample, before any analysis.

## Cost model

| Item | Cost |
|---|---|
| Libraries, models, datasets | $0 (licences permitting; Phase 5) |
| Judge runs | $0: local. Two or three judges × ~460 chats (agreement, sensitivity, bias) × 3 epochs, one judge at a time; speed measured in spike 2 |
| Raters | Volunteer time: Arthur ~10–11 h, R2 ~6 h |
| Disk | Up to ~24 GB of models during slice 6, outside the repo; judges not chosen can be deleted after it |
| Hosted models | None. No budget requested |

## Hand-off to B and D (owned elsewhere)

| Part | Owner | Starts when | Needs from here |
|---|---|---|---|
| **B. Simulated-customer realism** | Project 10 (AI Flight School) session | After slice 7 | Chat record format; anonymiser (for real chats after the gate); rubric scorer as an optional realism feature |
| **D. Paired multi-turn comparisons with power planning** | Project 2 (agent-eval-harness) session | After slice 7 | Scorer values per construct in trial records; the noise file |

These are sent as messages to those sessions at slice 7, not before, so
paused sessions aren't woken early (the three-sessions rule).
