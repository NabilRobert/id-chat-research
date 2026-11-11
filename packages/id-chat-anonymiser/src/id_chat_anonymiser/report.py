"""The R0/R1 comparison table on the results page, built from run records.

`id-chat compare results/anonymiser/dev-*.json` prints one Markdown row
per record, so the table in docs/results-anonymiser.md is regenerated from
the records rather than copied by hand.
"""

from collections.abc import Sequence
from pathlib import Path

from id_chat_anonymiser.labels import DIRECT_IDENTIFIERS, PiiType
from id_chat_anonymiser.runs import RunRecord
from id_chat_anonymiser.scoring import SetScore

HEADER = (
    "| Config | Chats | Names missed (95% upper) | Name precision "
    "| Addresses missed (95% upper) | Address precision | Direct identifiers missed "
    "| Look-alikes redacted | Over-redaction | Chats/s |\n"
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
)


def load_records(paths: Sequence[Path]) -> list[RunRecord]:
    return [RunRecord.model_validate_json(path.read_text(encoding="utf-8")) for path in paths]


def _missed(score: SetScore, pii_type: PiiType) -> str:
    type_score = score.by_type.get(pii_type)
    if type_score is None:
        return "—"
    rate = type_score.missed / max(type_score.gold, 1)
    upper = type_score.miss_rate_upper_95
    return f"{type_score.missed:,} of {type_score.gold:,}: {rate:.1%} ({upper:.1%})"


def _precision(score: SetScore, pii_type: PiiType) -> str:
    precision = score.precision_by_type.get(pii_type)
    return f"{precision.precision:.1%}" if precision else "—"


def comparison_row(record: RunRecord) -> str:
    score = record.score
    config = "R0 patterns" if record.ner_model is None else f"R1 + {record.ner_model}"
    direct_missed = sum(
        type_score.missed
        for pii_type, type_score in score.by_type.items()
        if pii_type in DIRECT_IDENTIFIERS
    )
    cells = [
        config,
        f"{score.chats:,}",
        _missed(score, PiiType.NAMA),
        _precision(score, PiiType.NAMA),
        _missed(score, PiiType.ALAMAT),
        _precision(score, PiiType.ALAMAT),
        str(direct_missed),
        str(sum(score.negative_hits.values())),
        f"{score.over_redaction_rate:.2%}",
        f"{score.chats / record.seconds:.1f}",
    ]
    return "| " + " | ".join(cells) + " |"


def comparison_table(records: Sequence[RunRecord]) -> str:
    return "\n".join([HEADER, *(comparison_row(record) for record in records)])
