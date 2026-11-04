# Measurement Plan

Written before any architecture decision or code, so the numbers can't be
shaped to fit the tools. For each tool it answers: what set, how it is
labelled, what baseline, which numbers are reported, and what passes.

**Every set here is synthetic or public.** Real chats enter only after the
real-data gate ([slice plan](slice-plan.md#the-real-data-gate)), and the
gate's checks on real data are described at the end.

---

## A. The anonymiser

### What counts as PII here

| Type | Placeholder | Examples | Kept, not redacted |
|---|---|---|---|
| Person name | `<NAMA_n>` | "Dewi", "pak Budi Santoso", "kak dew", "mas Anto" | Honorifics ("pak", "kak") stay outside the placeholder: "pak `<NAMA_1>`" |
| Phone number | `<TELEPON_n>` | `+62 812-3456-7890`, `081234567890`, `62812…`, `0812 3456 7890`, `(021) 555-1234` | — |
| NIK | `<NIK_n>` | 16 digits, possibly spaced or dotted | — |
| Street address | `<ALAMAT_n>` | "Jl. Melati No. 5 RT 03/RW 07, Kel. …", "Perum Griya Asri Blok C2/14" | City, regency and province alone ("Bekasi", "Jawa Barat") stay: they are needed for analysis and identify no one on their own |
| Vehicle plate | `<PLAT_n>` | `B 1234 XYZ`, `D1234ABC`, `AB 12 CD` | — |
| Email | `<EMAIL_n>` | — | — |
| Order or account ID | `<ID_PESANAN_n>` | "INV/2026/11/000123", "ORD-88231" | — |
| Bank account / card number | `<REKENING_n>` | 10–16 digits next to a bank name | — |

`n` numbers each distinct value within one chat, so "Dewi" is `<NAMA_1>`
every time and a second person is `<NAMA_2>`. That keeps the rubric's
personalisation codes working on anonymised chats ("the agent used the
customer's name").

**Hard negatives** (must **not** be redacted): prices ("Rp 25.500.000",
"25jt", "250rb"), dates and times, product and model names ("Vario 160",
"iPhone 15", "Xpander"), brand names that look like names ("Honda",
"Daihatsu", "Sharp"), quantities, kilometre readings, years, promo codes,
shop branch names, and the sales agent's job title.

### The sets

| Set | Made by | Size | Labels | Use |
|---|---|---|---|---|
| **Dev, generated** | Template generator, dev templates, Faker `id_ID` | ~2,000 chats | Exact spans, by construction | Writing and tuning recognisers |
| **Held-out, generated** | The same generator, **separate held-out templates** written before any recogniser, different seeds | ~1,500 chats, with **≥1,000 of each direct identifier type** | Exact spans | Scored once per version |
| **Hard cases, written** | Claude, by hand: typos, nicknames, numbers split across messages, numbers in words ("nol delapan satu dua…"), lower case, code-mixing, names that are also words ("Bunga", "Indah"), lists of prices | ~200 chats | Spans marked by hand, checked by a script that every span occurs in the text | Half dev, half held-out |
| **Hard negatives, written** | Claude | ~100 chats with no PII and many prices, products and brands | No spans | Over-redaction on clean text |
| **External synthetic** | Indonesian rows of `ai4privacy/pii-masking-openpii-1.5m` (CC-BY-4.0), written by someone else (Phase 5, ADR-004) | All Indonesian rows, mapped to our types | The dataset's spans | Tests whether recognisers only work on our own templates' style. Reported apart; downloaded by script, never committed |
| **Public NER text** | SINGGALANG (free use, citation requested; ADR-004) | A sample of 1,000 sentences | Person and location spans from the dataset (silver standard) | Names in formal text: a secondary check, reported apart |

**Why separate held-out templates:** if the held-out set used the dev
templates, a recogniser tuned on dev would be scored on sentences it has
already seen with different values. The held-out templates are written
first, frozen and fingerprinted, and nobody looks at their output while
writing recognisers.

**Domains:** vehicles (motorbikes and cars), electronics, property and
insurance, in roughly equal parts (settled). Each chat has 6–30 messages,
WhatsApp export format (`[dd/mm/yy hh.mm.ss] Sender: text`), with the
sender names themselves PII.

**Synthetic values:** names from Faker's `id_ID` lists and an added list of
common nicknames; phone numbers with real Indonesian prefixes and random
subscriber digits; NIKs with valid structure (province and regency codes,
birth date with +40 for women) and random serials; plates with real
regional letters. They are random, so they are tied to no real person's
data (threat model, P8).

### Configurations scored

| Config | What runs | Cost |
|---|---|---|
| **R0: patterns only** | Regular expressions and checksums/structure checks for phone, NIK, email, plate, IDs, accounts; a word list for honorific + name | $0, CPU, in CI |
| **R1: R0 + NER** | R0 plus a local Indonesian NER model for names and addresses (Phase 5, ADR-004) | $0, local |
| **R2: R1 + local LLM sweep** (Could) | R1, then a local model asked to point out anything personal R1 left; it may only add redactions | $0, local, slow |

### What is reported

Per type, and overall, on the held-out set:

| Number | Definition |
|---|---|
| **Miss rate** (the one that matters) | Gold PII values **not fully covered** by a redaction, over all gold values. A partial redaction that leaves any 3+ consecutive digits of a number, or any whole word of a name or street, is a **miss** |
| **Leaked characters** | Characters of gold PII left visible, over all gold PII characters: shows how bad the misses are |
| **Over-redaction rate** | Non-PII characters redacted, over all non-PII characters |
| **Hard-negative hits** | Prices, products and brands redacted, counted by kind, on the hard-negative set |
| **Wrong type** | Redacted, but under the wrong placeholder type: reported, not counted as a miss |
| **Consistency** | Chats where one value got two numbers, or two values shared one |
| **Intervals** | 95% Wilson intervals; with zero misses, the upper bound (about 3/N) is stated |
| **Speed** | Chats per second on the M2, per config |

Each report names the anonymiser version (package version plus a hash of
the recogniser config), the set fingerprint and the config, from a
committed run record. Results go to `docs/results-anonymiser.md`.

**Scored once per version:** a second held-out run for the same version
is refused, as in mcp-gateway's `score.py`. Misses found on held-out
become new dev templates, never edits to held-out.

### Pass

- **Direct identifiers** (phone, NIK, email, plate, account): **0 misses**
  on held-out (G1). Fixed now, because it decides whether the tool may
  touch real data.
- **Names and addresses:** the target is set after R0 is scored, written
  into this file before R1 is built, and never lowered afterwards.
- **Hard negatives:** 0 prices or product names redacted (G3).

---

## C. The relationship rubric

### Constructs and codes

Each **agent** turn gets yes/no codes (settled: behaviours per turn).
Codes sum into construct scores per chat (share of agent turns, or
present at least once, set per code in the codebook). The codebook v1 is
drafted in slice 4 from the sources below; this table fixes the
constructs, not the final wording.

| Construct | Source | Example codes (draft) |
|---|---|---|
| **Trust: communication** | Morgan & Hunt (1994): timely, relevant, credible information builds trust | Answers the question actually asked; gives specific information (price, stock, terms) instead of a deflection; corrects or follows up an earlier statement |
| **Trust: no opportunistic behaviour** | Morgan & Hunt (1994) | Makes no unverifiable claim or false scarcity; no pressure to decide now; discloses a condition the customer would care about (fees, waiting time) |
| **Commitment: relationship benefits** | Morgan & Hunt (1994) | Offers a benefit of continuing (after-sales service, follow-up, loyalty terms); invites a next step without pressure |
| **Responsiveness** | Parasuraman, Zeithaml & Berry (1988), SERVQUAL | Replies to every customer question in the turn; offers to help further; (real chats only) reply delay from timestamps, computed, not judged |
| **Assurance** | SERVQUAL | Shows product knowledge; courteous form of address; gives a reason to be confident (warranty, authorised-seller status, documented policy) |
| **Empathy** | SERVQUAL | Acknowledges the customer's situation or concern; adapts to a stated constraint (budget, timing) |
| **Personalisation** | Surprenant & Solomon (1987): personalisation in the service encounter | Uses the customer's name; refers back to something the customer said earlier; tailors the offer to stated needs |

Customer turns are not coded in v1. Reply delay is measured from
timestamps, not judged, and only exists for real chats.

### The sets

| Set | Made by | Size | Use |
|---|---|---|---|
| **Calibration** | Claude-written chats | 20 chats | Raters learn the codebook; disagreements discussed; the codebook revised. Never scored for agreement |
| **Agreement** | Claude-written chats with **planned behaviour levels**: each chat is written to a plan saying which codes should appear on which turns | ~100 chats, ~6 agent turns each (~600 units per code) | Both humans and the judge code every turn independently. Frozen and fingerprinted before rating starts |
| **Sensitivity pairs** | Claude: 30 pairs of chats identical except for one behaviour in one turn | 60 chats | Does the judge (and do the raters) see the one difference? |

All three sets are synthetic, use the four domains, and are marked
`source: synthetic` in every record and report. Written in Indonesian,
informal WhatsApp register with code-mixing, and checked by Arthur for
anything resembling his workplace (he reviews but doesn't write them,
settled).

**The plan is not the truth.** The planned levels check that the set
covers every code at useful rates, and give the sensitivity test its
answer. Agreement is measured against **people**, not against the plan,
because a chat written to show empathy may not read as empathic.

### How the ratings are made

1. Arthur and the second rater rate the calibration set separately, then
   compare and discuss. The codebook is revised (v2). At most two rounds.
2. The codebook version is frozen (a hash of the file).
3. Each rates the agreement set alone, in a rating sheet that shows one
   chat at a time, without the plan, the judge's codes or the other
   rater's.
4. The judge codes the agreement set **3 times** with different seeds,
   at the codebook version both humans used.
5. Raters are recorded by pseudonym (`R1`, `R2`).

### What is reported

| Number | Definition |
|---|---|
| **Human–human α, per code** | Krippendorff's α (nominal) between R1 and R2 over agent turns, with a bootstrap 95% interval (resampling chats, 2,000 draws) |
| **Judge–human α, per code** | α between the judge's majority code and each human, and α with the judge added as a third rater |
| **Raw agreement and prevalence, per code** | Because α is low for rare codes even when raters almost always agree; a code with prevalence under 5% is flagged. A code with no variation at all (everyone always says no) has **undefined** α and can't pass, even though Inspect's α returns 1.0 there (Phase 5, ADR-008) |
| **Per construct** | α on the chat-level construct score (interval level), human–human and judge–human |
| **Judge test–retest** | Agreement of the judge with itself across the 3 runs, per code; and the spread of construct scores per chat |
| **Sensitivity** | On the pairs: share where the judge's construct score moved in the planned direction; the same for each human |
| **Cohen's κ** | For the two humans, per code, for readers who expect it. α is the main number |
| **Cost and speed** | Seconds per chat for the judge on the M2; hours per rater |

Results go to `docs/results-rubric.md`, from committed run records.
The raters' raw sheets stay out of git (`ratings/raw/`); the committed
file holds pseudonymised codes only.

### Pass (pre-registered)

Thresholds follow Krippendorff (2004): α ≥ 0.800 is reliable, α ≥ 0.667
allows tentative conclusions.

- **A code is usable** if human–human α ≥ 0.667. A code below that is
  rewritten for the next codebook version or dropped, and the drop is
  reported (G4).
- **The judge may score a code** if judge–human α ≥ 0.667 **and** is at
  most 0.10 below the human–human α for that code (G5). Otherwise that
  code is scored by people only, and reports say so.
- **A construct is judge-scored** only if every code in it passes.
- These rules are fixed now and not changed after the numbers are seen.
  A new codebook version means a new agreement set rating, reported
  beside the old.

### What D needs from C

For D's power calculation (Project 2): the judge's test–retest standard
deviation per construct, and the judge–human gap. They are written to a
results file with the codebook and model versions, so D's sample size
accounts for judge noise.

---

## The real-data gate: what is checked on real chats

Not a slice; listed so the gate's checks are fixed now. After written
permission (research **and** publication) and ethics approval:

1. Arthur runs the anonymiser locally on the real chats (runbook, slice
   8). No Claude session, hosted model or synced folder sees them (threat
   model, R1–R4).
2. **Residual check:** Arthur reads a random sample of 100 anonymised
   chats, plus every chat where the anonymiser's confidence was low, and
   counts misses. The miss count and its interval are reported. Any
   missed direct identifier stops the process: fix, re-score held-out
   for the new version, re-run.
3. The rubric runs on the anonymised chats with the local judge, on the
   codes that passed G5.
4. Only aggregates leave the encrypted folder: counts, rates, model
   coefficients. Cells under 5 chats are suppressed.

## What this can't show

- **Synthetic chats are not real chats.** The anonymiser's misses on real
  chats will be higher; step 2 above measures that, on a sample.
- **The held-out templates were written by the same people as the dev
  ones.** Separate templates reduce, but don't remove, the overlap in
  style.
- **Two raters is the minimum.** α with two raters has wide intervals;
  the intervals are reported, not hidden.
- **Claude wrote the rubric's chats and suggests codes.** Agreement
  between people and a model judge may be inflated on text a model wrote.
  On real chats, the judge–human check is repeated on a sample before
  trusting it there.
- **The constructs come from surveys of customers' perceptions.** Codes
  of an agent's behaviour are a proxy for those perceptions, not the
  perceptions themselves. Whether they relate to outcomes is Stage 1's
  question.

## agent-eval-harness and Inspect AI: where they fit

- **Inspect AI** runs the judge (slice 6): each chat is a sample, the
  rubric a scorer, epochs give the 3 judge runs, and the local model is
  served through Inspect's provider for it (Phase 5).
- **The harness's run-record and score-once habits** (and mcp-gateway's
  `score.py`) are reused for both tools. Its `compare` gate is pass/fail
  over tasks, so continuous construct scores need D's extension, which
  is Project 2's work.
