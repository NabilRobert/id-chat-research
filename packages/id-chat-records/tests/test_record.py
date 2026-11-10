"""The chat record format: what it accepts, what it refuses, and JSONL round trips."""

from pathlib import Path
from typing import Any

import pytest
from id_chat_records import ChatRecord, Role, Source, read_jsonl, write_jsonl
from pydantic import ValidationError


def _record_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "chat_id": "vehicles-0001",
        "source": "synthetic",
        "domain": "vehicles",
        "turns": [
            {"index": 0, "role": "customer", "text": "kak, Vario 160 masih ada?"},
            {"index": 1, "role": "agent", "text": "Masih ada kak, mau warna apa?"},
        ],
    }
    fields.update(overrides)
    return fields


def test_a_valid_record_is_accepted_with_format_version_1() -> None:
    record = ChatRecord.model_validate(_record_fields())

    assert record.format_version == "1"
    assert record.source is Source.SYNTHETIC
    assert record.turns[1].role is Role.AGENT


def test_source_is_required() -> None:
    fields = _record_fields()
    del fields["source"]

    with pytest.raises(ValidationError, match="source"):
        ChatRecord.model_validate(fields)


def test_an_unknown_source_is_refused() -> None:
    with pytest.raises(ValidationError, match="source"):
        ChatRecord.model_validate(_record_fields(source="scraped"))


def test_turn_indexes_out_of_order_are_refused() -> None:
    turns = [
        {"index": 1, "role": "customer", "text": "halo"},
        {"index": 0, "role": "agent", "text": "halo kak"},
    ]

    with pytest.raises(ValidationError, match="position 0 has index 1"):
        ChatRecord.model_validate(_record_fields(turns=turns))


def test_a_chat_with_no_turns_is_refused() -> None:
    with pytest.raises(ValidationError, match="turns"):
        ChatRecord.model_validate(_record_fields(turns=[]))


def test_an_empty_message_is_refused() -> None:
    turns = [{"index": 0, "role": "customer", "text": ""}]

    with pytest.raises(ValidationError, match="text"):
        ChatRecord.model_validate(_record_fields(turns=turns))


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError, match="customer_name"):
        ChatRecord.model_validate(_record_fields(customer_name="Dewi"))


def test_outcome_holds_nested_json() -> None:
    outcome = {"stop_marker": "###DONE###", "customer_behaviours": ["price_first", "haggling"]}

    record = ChatRecord.model_validate(_record_fields(outcome=outcome))

    assert record.outcome == outcome


def test_records_round_trip_through_jsonl(tmp_path: Path) -> None:
    timestamped_turns = [
        {"index": 0, "role": "customer", "text": "halo", "timestamp": "2026-11-05T09:30:00+07:00"}
    ]
    records = [
        ChatRecord.model_validate(_record_fields()),
        ChatRecord.model_validate(_record_fields(chat_id="vehicles-0002", turns=timestamped_turns)),
    ]
    path = tmp_path / "chats.jsonl"

    written = write_jsonl(records, path)

    assert written == 2
    assert list(read_jsonl(path)) == records


def test_an_invalid_line_is_named_by_its_line_number(tmp_path: Path) -> None:
    path = tmp_path / "chats.jsonl"
    valid_line = ChatRecord.model_validate(_record_fields()).model_dump_json()
    path.write_text(valid_line + "\n" + '{"chat_id": "x"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"chats\.jsonl:2 is not a valid chat record"):
        list(read_jsonl(path))
