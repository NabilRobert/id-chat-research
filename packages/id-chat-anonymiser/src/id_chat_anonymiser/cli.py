"""The `id-chat` command line.

- `id-chat score --set dev` generates a synthetic set, anonymises it, prints
  the scores and writes a run record. `--set heldout` works once per
  anonymiser version and config.
- `id-chat anonymise chats.jsonl out.jsonl` anonymises chat records. It
  prints counts only, never chat text (Phase 2, N5).
"""

import time
from pathlib import Path
from typing import Annotated

import typer
from id_chat_records import read_jsonl, write_jsonl

from id_chat_anonymiser.anonymiser import Anonymiser
from id_chat_anonymiser.labels import DIRECT_IDENTIFIERS, PiiType
from id_chat_anonymiser.runs import (
    RunRecord,
    anonymiser_version,
    config_sha256,
    now,
    refuse_if_scored,
    set_sha256,
    write_record,
)
from id_chat_anonymiser.scoring import SetScore, score_set
from id_chat_anonymiser.synthetic.sets import (
    DEFAULT_TEMPLATES_DIR,
    SETS,
    build_set,
    templates_fingerprint,
)

DEFAULT_RESULTS_DIR = Path("results/anonymiser")
# Names and addresses need the NER half (slice 3); R0 doesn't try them.
NOT_YET_COVERED = frozenset({PiiType.NAMA, PiiType.ALAMAT})

app = typer.Typer(help="Research tools for Indonesian sales chats.", no_args_is_help=True)


@app.command()
def score(
    set_name: Annotated[str, typer.Option("--set", help="dev or heldout")] = "dev",
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    results_dir: Path = DEFAULT_RESULTS_DIR,
) -> None:
    """Generate a synthetic set, anonymise it, and score the anonymiser on it."""
    if set_name not in SETS:
        raise typer.BadParameter(f"unknown set {set_name!r}: use one of {sorted(SETS)}")
    spec = SETS[set_name]
    refuse_if_scored(results_dir, set_name)
    labelled = build_set(spec, templates_dir)
    anonymiser = Anonymiser()
    started = time.perf_counter()
    anonymised = [anonymiser.anonymise(chat.record) for chat in labelled]
    seconds = time.perf_counter() - started
    result = score_set(labelled, anonymised)
    record = RunRecord(
        anonymiser_version=anonymiser_version(),
        config_sha256=config_sha256(),
        set_name=set_name,
        templates_sha256=templates_fingerprint(spec, templates_dir),
        set_sha256=set_sha256(labelled),
        created_at=now(),
        seconds=round(seconds, 2),
        score=result,
    )
    typer.echo(format_score(result, seconds))
    typer.echo(f"run record: {write_record(record, results_dir)}")


@app.command()
def anonymise(input_path: Path, output_path: Path) -> None:
    """Anonymise a JSONL file of chat records into another."""
    anonymiser = Anonymiser()
    anonymised = (anonymiser.anonymise(record).record for record in read_jsonl(input_path))
    count = write_jsonl(anonymised, output_path)
    typer.echo(f"anonymised {count} chats into {output_path}")


def format_score(result: SetScore, seconds: float) -> str:
    lines = [
        f"{result.chats} chats, {result.chats / seconds:.0f} chats/s",
        "type         gold  missed  miss rate (95% upper)  leaked chars  wrong type",
    ]
    for pii_type, score in result.by_type.items():
        note = "  (not in R0: needs NER)" if pii_type in NOT_YET_COVERED else ""
        gate = "  G1" if pii_type in DIRECT_IDENTIFIERS else ""
        lines.append(
            f"{pii_type.value:<11} {score.gold:>5} {score.missed:>7}"
            f" {score.missed / max(score.gold, 1):>8.2%} ({score.miss_rate_upper_95:.2%})"
            f" {score.leaked_characters:>13} {score.wrong_type:>11}{gate}{note}"
        )
    lines.append(f"over-redaction: {result.over_redaction_rate:.3%} of characters outside PII")
    lines.append(f"look-alikes redacted: {result.negative_hits or 'none'}")
    return "\n".join(lines)
