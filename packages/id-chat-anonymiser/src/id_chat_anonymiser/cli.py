"""The `id-chat` command line.

- `id-chat score --set dev` generates a synthetic set, anonymises it, prints
  the scores and writes a run record. `--ner MODEL` adds an NER model (R1).
  `--set heldout` works once per anonymiser version and config.
  `--limit N` scores the first N dev chats as a quick smoke run and writes
  no record.
- `id-chat fetch-models` downloads the pinned NER models (the only command
  that uses the network).
- `id-chat anonymise chats.jsonl out.jsonl` anonymises chat records. It
  prints counts only, never chat text (Phase 2, N5).
- `id-chat compare RECORD...` prints the results page's comparison table
  from run records.
"""

import time
from pathlib import Path
from typing import Annotated

import typer
from id_chat_records import read_jsonl, write_jsonl
from presidio_analyzer import EntityRecognizer

from id_chat_anonymiser.anonymiser import Anonymiser
from id_chat_anonymiser.labels import DIRECT_IDENTIFIERS, NER_TYPES
from id_chat_anonymiser.report import comparison_table, load_records
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
    SetSpec,
    build_set,
    templates_fingerprint,
)

DEFAULT_RESULTS_DIR = Path("results/anonymiser")

app = typer.Typer(help="Research tools for Indonesian sales chats.", no_args_is_help=True)

NerOption = Annotated[
    str | None, typer.Option("--ner", help="NER model for names and addresses (R1)")
]


def _recognisers(ner_model: str | None) -> list[EntityRecognizer]:
    if ner_model is None:
        return []
    # Imported here so R0 runs without the `ner` extra installed.
    from id_chat_anonymiser.ner.recogniser import load_ner_recogniser

    return [load_ner_recogniser(ner_model)]


def _chosen_set(set_name: str, limit: int | None) -> SetSpec:
    if set_name not in SETS:
        raise typer.BadParameter(f"unknown set {set_name!r}: use one of {sorted(SETS)}")
    if limit is not None and set_name != "dev":
        # A partial look at held-out would still be a look; it is scored whole, once.
        raise typer.BadParameter("--limit is for dev smoke runs only")
    return SETS[set_name]


@app.command()
def score(
    set_name: Annotated[str, typer.Option("--set", help="dev or heldout")] = "dev",
    ner_model: NerOption = None,
    limit: Annotated[int | None, typer.Option(help="score only the first N dev chats")] = None,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    results_dir: Path = DEFAULT_RESULTS_DIR,
) -> None:
    """Generate a synthetic set, anonymise it, and score the anonymiser on it."""
    spec = _chosen_set(set_name, limit)
    refuse_if_scored(results_dir, set_name, ner_model)
    labelled = build_set(spec, templates_dir)[:limit]
    anonymiser = Anonymiser(_recognisers(ner_model))
    started = time.perf_counter()
    anonymised = [anonymiser.anonymise(chat.record) for chat in labelled]
    seconds = time.perf_counter() - started
    result = score_set(labelled, anonymised)
    typer.echo(format_score(result, seconds, ner_model))
    if limit is not None:
        typer.echo("smoke run: no run record written")
        return
    record = RunRecord(
        anonymiser_version=anonymiser_version(),
        config_sha256=config_sha256(ner_model),
        ner_model=ner_model,
        set_name=set_name,
        templates_sha256=templates_fingerprint(spec, templates_dir),
        set_sha256=set_sha256(labelled),
        created_at=now(),
        seconds=round(seconds, 2),
        score=result,
    )
    typer.echo(f"run record: {write_record(record, results_dir)}")


@app.command("fetch-models")
def fetch_models(
    model: Annotated[str | None, typer.Option(help="one model; all three if left out")] = None,
) -> None:
    """Download the pinned NER models into the Hugging Face cache and check their hashes."""
    from id_chat_anonymiser.ner.models import MODELS, fetch_model, model_spec

    for spec in [model_spec(model)] if model else MODELS.values():
        typer.echo(f"{spec.key}: {fetch_model(spec)}")


@app.command()
def anonymise(input_path: Path, output_path: Path, ner_model: NerOption = None) -> None:
    """Anonymise a JSONL file of chat records into another."""
    anonymiser = Anonymiser(_recognisers(ner_model))
    anonymised = (anonymiser.anonymise(record).record for record in read_jsonl(input_path))
    count = write_jsonl(anonymised, output_path)
    typer.echo(f"anonymised {count} chats into {output_path}")


@app.command()
def compare(records: list[Path]) -> None:
    """Print a Markdown comparison table of run records (R0 and each R1 model)."""
    typer.echo(comparison_table(load_records(records)))


def format_score(result: SetScore, seconds: float, ner_model: str | None = None) -> str:
    config = "R0 (patterns)" if ner_model is None else f"R1 (patterns + {ner_model})"
    lines = [
        f"{config}: {result.chats} chats, {result.chats / seconds:.1f} chats/s",
        "type         gold  missed  miss rate (95% upper)  precision  leaked chars  wrong type",
    ]
    for pii_type, score in result.by_type.items():
        precision = result.precision_by_type.get(pii_type)
        note = "  (needs NER)" if pii_type in NER_TYPES and ner_model is None else ""
        gate = "  G1" if pii_type in DIRECT_IDENTIFIERS else ""
        lines.append(
            f"{pii_type.value:<11} {score.gold:>5} {score.missed:>7}"
            f" {score.missed / max(score.gold, 1):>8.2%} ({score.miss_rate_upper_95:.2%})"
            f" {precision.precision if precision else 1.0:>14.2%}"
            f" {score.leaked_characters:>13} {score.wrong_type:>11}{gate}{note}"
        )
    lines.append(f"over-redaction: {result.over_redaction_rate:.3%} of characters outside PII")
    lines.append(f"look-alikes redacted: {result.negative_hits or 'none'}")
    return "\n".join(lines)
