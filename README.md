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

**First slice built (2026-11-09):** the chat record format (tag `v0.1.0`)
and the rule-based half of the anonymiser. On 1,704 held-out synthetic
chats it missed **none** of 1,000+ each of phone numbers, NIKs, emails,
plates and account numbers, and redacted no price or product name
([results](docs/results-anonymiser.md)).

**NER half built (2026-11-11):** R1 adds a local NER model for names and
addresses. Of three candidates compared on 2,000 dev chats, **NusaBert**
leads: 5% of addresses and 25% of names missed, with 98% of its name
redactions correct ([results](docs/results-anonymiser.md#r1-the-three-ner-candidates-on-dev-2026-11-11)).
It is scored on held-out once Arthur sets the names and addresses
targets. Everything so far is synthetic.

The rubric and the judges come later. Real chats wait for enrolment and
the ethics and data gate: written permission covering research and
publication, plus university ethics approval. They are never put in this
repo and never sent to third-party APIs.

Open decisions:

- **Second rater:** who it is, and when they have about 6 hours free.
- **Names and addresses targets:** the miss rates R1 must meet on
  held-out, set before it is scored there.
- **Judge models:** two or three at about 5–8 GB each, not yet approved.
- **"Tools are separate":** when to ask for a written line saying these
  tools are separate from any employer's product.
- **Project 12:** whether it reuses this anonymiser instead of writing its
  own redaction script.

## Run it

Needs [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync
uv run id-chat score --set dev        # generate 2,000 synthetic chats, anonymise, score
uv run id-chat anonymise in.jsonl out.jsonl
make check                            # lint, types, tests, secrets: what CI runs
```

The NER half (R1) is optional:

```bash
uv sync --group ner                   # torch, transformers, onnxruntime, gliner
uv run id-chat fetch-models           # about 2.5 GB, pinned by hash; the only download
uv run id-chat score --set dev --ner nusabert   # or horizon, gliner; --limit 100 to smoke
```

To use the chat record format from another project:

```toml
"id-chat-records @ git+https://github.com/NabilRobert/id-chat-research@v0.1.0#subdirectory=packages/id-chat-records"
```

## Layout

| Path | What it holds |
|---|---|
| [`packages/id-chat-records/`](packages/id-chat-records/) | `ChatRecord`: the chat format every tool reads and writes (Pydantic, JSONL). Depends only on Pydantic |
| [`packages/id-chat-anonymiser/`](packages/id-chat-anonymiser/) | The anonymiser (`recognisers.py`, `anonymiser.py`), its optional NER half (`ner/`), the synthetic set generator (`synthetic/`), the scorer (`scoring.py`, `runs.py`, `report.py`) and the `id-chat` CLI |
| [`data/templates/`](data/templates/) | Chat templates for the dev and held-out sets. `heldout.yaml` is frozen |
| [`results/anonymiser/`](results/anonymiser/) | Run records behind every published number |
| [`docs/guide.md`](docs/guide.md) | How a run flows through the code, a glossary, where to change things |
| [`docs/results-anonymiser.md`](docs/results-anonymiser.md) | The anonymiser's scores and what they do and don't show |
| [`docs/planning/`](docs/planning/) | The plan. Read in this order: |
| ↳ [`phase-1-problem-brief.md`](docs/planning/phase-1-problem-brief.md) | The problem, the users, the goals and the non-goals |
| ↳ [`measurement-plan.md`](docs/planning/measurement-plan.md) | The sets, metrics and pass rules, fixed before any code |
| ↳ [`phase-2-requirements-constraints.md`](docs/planning/phase-2-requirements-constraints.md) | Scenarios, requirements and data flow |
| ↳ [`phase-5-architecture-decisions.md`](docs/planning/phase-5-architecture-decisions.md) | Decisions (ADRs), with the existing tools considered and their licences |
| ↳ [`threat-model.md`](docs/planning/threat-model.md) | Privacy, judge and supply-chain threats, and their controls |
| ↳ [`slice-plan.md`](docs/planning/slice-plan.md) | Build order, prerequisites, cost and the real-data gate |
| [`docs/third-party.md`](docs/third-party.md) | Licences of what this repo depends on |
