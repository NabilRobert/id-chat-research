# id-chat-research

Open research tools for evaluating customer-facing AI chat agents on
Indonesian sales conversations. There are two tools. The first is an
**anonymiser** that removes personal data (names, +62/08 phone numbers,
NIK, addresses, plates, emails, order IDs) from WhatsApp-style chats,
measured by what it misses. The second is a **relationship rubric** that
codes the agent's turns on constructs from marketing theory: commitment
and trust (Morgan & Hunt, 1994), SERVQUAL's responsiveness, assurance and
empathy, and personalisation. It is scored by human raters and by two or
three local AI judges, and a judge is trusted only on the codes where it
agrees with people. The repo is the evaluation setup for a planned
master's thesis, and it is also a portfolio project. MIT licence.

## Status

**Planned (2026-11-04). There is no code yet.**

Building waits for enrolment and for the ethics and data gate. Real chats
are used only with written permission covering research and publication,
plus university ethics approval. They are never put in this repo and
never sent to third-party APIs. Until then, every set is synthetic or
public.

Open decisions:

- **Second rater:** who it is, and when they have about 6 hours free.
- **Model downloads:** approval for about 3 GB of NER models for the
  benchmark, and two or three judge models at about 5–8 GB each.
- **"Tools are separate":** when to ask for a written line saying these
  tools are separate from any employer's product.
- **Project 12:** whether it reuses this anonymiser instead of writing its
  own redaction script.

## Layout

| Path | What it holds |
|---|---|
| [`docs/planning/`](docs/planning/) | The plan, which is the only content so far. Read it in this order: |
| ↳ [`phase-1-problem-brief.md`](docs/planning/phase-1-problem-brief.md) | The problem, the users, the goals and the non-goals |
| ↳ [`measurement-plan.md`](docs/planning/measurement-plan.md) | The sets, metrics and pass rules, fixed before any code |
| ↳ [`phase-2-requirements-constraints.md`](docs/planning/phase-2-requirements-constraints.md) | Scenarios, requirements and data flow |
| ↳ [`phase-5-architecture-decisions.md`](docs/planning/phase-5-architecture-decisions.md) | Decisions (ADRs), with the existing tools considered and their licences |
| ↳ [`threat-model.md`](docs/planning/threat-model.md) | Privacy, judge and supply-chain threats, and their controls |
| ↳ [`slice-plan.md`](docs/planning/slice-plan.md) | Build order, prerequisites, cost and the real-data gate |

CI, `docs/guide.md` and a run command come with the first code (slice 0
in the slice plan).
