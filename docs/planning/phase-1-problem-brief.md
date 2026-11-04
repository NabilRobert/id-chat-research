# Phase 1: Problem Brief

**Project:** open research tools for evaluating customer-facing AI chat
agents on Indonesian sales conversations. It is the fifteenth portfolio
piece. It is also the evaluation setup for a planned master's thesis on
theory-grounded AI agents for sales conversations.

The repo is `id-chat-research` (MIT). It holds two tools:

- **(A) The anonymiser:** removes personal data from WhatsApp-style
  Indonesian sales chats.
- **(C) The relationship rubric:** scores the agent's side of a chat on
  constructs from marketing theory, with an AI judge that is trusted
  only after it agrees with human raters.

Two related parts live in other projects (see [Interfaces](#interfaces)):
**(B)** simulated-customer realism, in AI Flight School (Project 10), and
**(D)** paired multi-turn comparisons with power planned in advance, in
agent-eval-harness (Project 2). The build order is A → C → B → D.

**Measurement comes first.** The [measurement plan](measurement-plan.md)
fixes the sets, the baselines and the numbers before any architecture
decision or code.

## Problem

**For the research:**
- **Real sales chats can't be studied until they are anonymised.** No
  ethics board approves raw chat logs, and Indonesia's personal data
  protection law (UU PDP, Law 27/2022) applies to them. An anonymiser
  with a measured miss rate is the first thing an ethics application can
  point to.
- **Indonesian chats are hard to anonymise with standard tools.** Phone
  numbers come as `+62 812-…`, `0812…` or `62812…`. NIKs are 16 digits
  with a structure. Plates look like `B 1234 XYZ`. Addresses are written
  "Jl. Melati No. 5 RT 03/RW 07". Names are often one word, lower case,
  or nicknames ("kak Dewi", "pak Budi", "gan"). Most PII tools ship
  recognisers for English and for US or EU identifiers.
- **"Metrics from papers" need to be defensible.** Relationship-marketing
  constructs (commitment and trust, service quality, personalisation)
  were built for surveys, not for chat transcripts. Turning them into
  codes a person can apply to a chat, and checking that two people agree,
  is what makes them usable. An AI judge's scores are only worth
  something once its agreement with people is measured.

**For the portfolio:**
- Earlier projects measure agents on tasks with right answers (SQL
  results, refunds, rules). None measures **soft qualities** of a
  conversation, where the right answer is people's judgement.
- None measures a **privacy tool** by the failure that matters: what it
  misses.
- It reuses the harness, Inspect AI and AI Flight School, and feeds them,
  so it shows the pieces fit together.

## Users

| Party | Who | Wants |
|---|---|---|
| **Arthur, as researcher** | Running the thesis's three stages | Anonymised chats he may analyse; scores he can defend to a supervisor and reviewers |
| **A second rater** | One person who hasn't seen the design (settled) | A clear codebook and a rating sheet that takes a few hours |
| **Ethics board and data owner** | The university's ethics committee; the company that owns the logs | A measured miss rate, a documented local-only process, no raw data leaving the machine |
| **Other researchers and builders** | Anyone working on Indonesian chat data | A pip-installable anonymiser and a reusable, validated rubric |
| **Reviewer / hiring team** | AI and tech people generally | Measured numbers, honest limits, privacy handled by design |

## Existing tools (summary; details in Phase 5)

| Tool | What it is | Where this differs |
|---|---|---|
| **Microsoft Presidio** | Open PII detection and anonymisation framework, pluggable recognisers | Ships no Indonesian recognisers. Candidate **engine** for A (ADR-003), with Indonesian recognisers added and measured |
| **Indonesian NER models** (IndoBERT fine-tunes and others) | Find person, place and organisation names | Not trained on informal chat, and not measured for PII misses. Candidates for the name and address part of A |
| **Krippendorff's α implementations** (including Inspect AI's own) | Agreement statistics | Reused, not rebuilt (ADR-008) |
| **SERVQUAL and its successors** | Survey instruments for service quality | Surveys of customers, not codes for transcripts. C turns them into observable behaviours |

**The angle:** Indonesian chat specifics, measured by misses; and a rubric
validated against people before it is trusted.

## Goals and how they're measured

Targets for the anonymiser's names and addresses are set **after** the
baseline (measurement plan). The gates for direct identifiers and for the
judge are fixed now, because they decide whether real data may be used.

| # | Goal | Target | Measured by |
|---|---|---|---|
| G1 | The anonymiser misses no direct identifier | **0** missed phone numbers, NIKs, emails, plates or account numbers on the held-out set, with at least 1,000 of each, so the 95% upper bound on the miss rate is at most 0.3% | Measurement plan, A |
| G2 | It rarely misses a name or address | Miss rate with its interval; target set after the baseline | Measurement plan, A |
| G3 | It doesn't wreck the chat | Over-redaction rate, and **0** prices or product names redacted on the hard-negative set | Measurement plan, A |
| G4 | The codebook is reliable between people | Krippendorff's α ≥ 0.667 per code between the two humans; codes below are rewritten or dropped, and reported | Measurement plan, C |
| G5 | The judge is trusted only where it agrees with people | Per code: judge–human α ≥ 0.667 **and** not more than 0.10 below the human–human α. Codes that fail are scored by people only | Measurement plan, C |
| G6 | Nothing real leaves the machine | **0** code paths that send a record marked real to a network; **0** real rows in git | Tests and the threat model |
| G7 | Costs nothing | $0: local models, free libraries, volunteer rater time | Run records |

## Non-goals

- **Real chat logs in any slice.** They come only after the real-data
  gate (written permission covering research **and** publication, plus
  university ethics approval). That gate is not a slice; see the
  [slice plan](slice-plan.md#the-real-data-gate). Arthur expects it after
  enrolment, not before (settled 2026-11-04).
- **Building the thesis agent (Stage 2).** This repo measures agents; it
  doesn't build the one being studied.
- **Simulated customers and their realism (B)**, and **paired comparisons
  and power planning (D).** Their owners build them; this repo provides
  the interfaces they use.
- **Images, voice notes and attachments in chats.** Text only.
  Attachments are replaced by a typed placeholder.
- **Re-identification-proof publishing of anonymised chats.** Anonymised
  real chats are never published; only aggregate results are
  (threat model).
- **Outcome prediction** (which behaviours lead to sales). That is the
  thesis's Stage 1 analysis, run on the rubric's output.

## Interfaces

What this repo provides to the other two parts. Their internals are
planned by their own sessions.

| Provides | To | Form |
|---|---|---|
| The **chat record format** (one chat: turns, roles, timestamps, source, domain, optional outcome) | B, D, the thesis | A Pydantic model and JSONL, versioned (ADR-002) |
| **Anonymised chats** with consistent typed placeholders (`<NAMA_1>`) | B (personas from real chats, after the gate) | The anonymiser's output, local only |
| **The rubric as an Inspect scorer** returning per-construct scores, with per-turn codes in metadata | D (as a comparison metric), B (as a realism feature) | `@scorer` plus a CLI over JSONL (ADR-007) |
| **The judge's noise numbers**: test–retest spread per construct, and judge–human gap | D's power calculation | A results file with the codebook and model versions |

## Decisions

Settled with Arthur, 2026-11-04:

1. **Repo:** one repo, `id-chat-research`, with the anonymiser and the
   rubric as two packages (ADR-001).
2. **Raters:** Arthur plus one other person who hasn't seen the design.
3. **Judge:** local open models only, $0 (ADR-006). Two or three are
   compared on the same sets, with bias tests, because judge–human
   agreement is a thesis result (RQ2); one is chosen by a pre-registered
   rule, and that one may later read real logs. (Changed the same day
   from "one judge picked in a spike".)
4. **Synthetic domains:** several generic ones (vehicles, electronics,
   property, insurance), nothing resembling Arthur's workplace.
5. **Rubric unit:** yes/no behaviour codes per agent turn, summed into
   construct scores per chat (ADR-005).
6. **Synthetic chats:** a template generator with Faker's Indonesian
   locale for A (labels exact by construction), and chats written by
   Claude with planned behaviour levels for C, kept apart and labelled
   synthetic everywhere.
7. **Real data:** not before enrolment; the gate stays undated.
8. **Licence:** MIT.

Arthur accepted the other ADRs in Phase 5 as recommended, the same day.
The open questions are at the end of
[Phase 5](phase-5-architecture-decisions.md#open-questions).

## Cost of doing nothing

The thesis can't start Stage 1: no anonymiser means no ethics approval,
and no validated rubric means Stage 3's metrics are open to the first
reviewer who asks "who checked the judge?". The fallback topic (the
statistical reliability of agent evaluations) needs neither tool.
