"""The comparison table is built from run records, one row per config."""

from datetime import UTC, datetime
from pathlib import Path

from id_chat_anonymiser.cli import app
from id_chat_anonymiser.labels import PiiType
from id_chat_anonymiser.report import comparison_row
from id_chat_anonymiser.runs import RunRecord
from id_chat_anonymiser.scoring import SetScore, TypePrecision, TypeScore
from typer.testing import CliRunner


def _record(ner_model: str | None) -> RunRecord:
    score = SetScore(
        chats=200,
        by_type={
            PiiType.NAMA: TypeScore(gold=100, missed=12, miss_rate_upper_95=0.2),
            PiiType.TELEPON: TypeScore(gold=50, missed=1, miss_rate_upper_95=0.1),
            PiiType.EMAIL: TypeScore(gold=40, missed=2, miss_rate_upper_95=0.1),
        },
        redacted_outside_gold=5,
        characters_outside_gold=1_000,
        negative_hits={"HARGA": 3, "PRODUK": 1},
        missed_examples={},
        precision_by_type={PiiType.NAMA: TypePrecision(redactions=100, on_gold_of_type=90)},
    )
    return RunRecord(
        anonymiser_version="0.1.0",
        config_sha256="0" * 64,
        ner_model=ner_model,
        set_name="dev",
        templates_sha256="1" * 64,
        set_sha256="2" * 64,
        created_at=datetime(2026, 11, 10, tzinfo=UTC),
        seconds=100.0,
        score=score,
    )


def test_a_row_sums_direct_identifier_misses_and_look_alike_hits() -> None:
    row = comparison_row(_record("nusabert"))

    cells = [cell.strip() for cell in row.strip("|").split("|")]
    assert cells[0] == "R1 + nusabert"
    assert cells[2] == "12 of 100: 12.0% (20.0%)"
    assert cells[3] == "90.0%"
    assert cells[4] == "—"
    assert cells[6:] == ["3", "4", "0.50%", "2.0"]


def test_compare_prints_one_row_per_record(tmp_path: Path) -> None:
    paths = []
    for name, ner_model in (("r0", None), ("r1", "gliner")):
        path = tmp_path / f"{name}.json"
        path.write_text(_record(ner_model).model_dump_json(), encoding="utf-8")
        paths.append(str(path))

    result = CliRunner().invoke(app, ["compare", *paths])

    assert result.exit_code == 0
    assert "| R0 patterns |" in result.output
    assert "| R1 + gliner |" in result.output
