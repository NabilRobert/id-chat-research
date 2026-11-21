"""Everything in a record besides turn text: chat_id, outcome and timestamps."""

from datetime import UTC, datetime, timedelta

import pytest
import typer
from id_chat_anonymiser.anonymiser import Anonymiser
from id_chat_anonymiser.cli import PSEUDONYM_KEY_VARIABLE, pseudonym_key_from_environment
from id_chat_anonymiser.metadata import TIMESTAMP_ANCHOR, pseudonymise_chat_id
from id_chat_records import ChatRecord, Source, Turn
from pydantic import JsonValue

KEY = b"k" * 32
WHATSAPP_ID = "6281234567890@c.us"


def _chat(
    *turns: tuple[str, datetime | None],
    chat_id: str = WHATSAPP_ID,
    outcome: dict[str, JsonValue] | None = None,
) -> ChatRecord:
    built = tuple(
        Turn(index=index, role="customer", text=text, timestamp=timestamp)  # pyright: ignore[reportArgumentType]
        for index, (text, timestamp) in enumerate(turns)
    )
    return ChatRecord(
        chat_id=chat_id, source=Source.REAL, domain="vehicles", turns=built, outcome=outcome
    )


@pytest.fixture(scope="module")
def anonymiser() -> Anonymiser:
    return Anonymiser(pseudonym_key=KEY)


def test_a_whatsapp_chat_id_is_replaced_by_a_pseudonym(anonymiser: Anonymiser) -> None:
    result = anonymiser.anonymise(_chat(("halo", None)))

    assert result.record.chat_id == pseudonymise_chat_id(WHATSAPP_ID, KEY)
    assert "1234567890" not in result.record.chat_id


def test_the_same_key_gives_the_same_pseudonym_and_another_key_does_not() -> None:
    same = pseudonymise_chat_id(WHATSAPP_ID, KEY)

    assert pseudonymise_chat_id(WHATSAPP_ID, KEY) == same
    assert pseudonymise_chat_id(WHATSAPP_ID, b"x" * 32) != same


def test_without_a_key_two_anonymisers_give_different_pseudonyms() -> None:
    chat = _chat(("halo", None))

    first = Anonymiser().anonymise(chat).record.chat_id
    second = Anonymiser().anonymise(chat).record.chat_id

    assert first != second


def test_identifiers_in_outcome_strings_are_redacted(anonymiser: Anonymiser) -> None:
    chat = _chat(("halo", None), outcome={"phone": "081234567890", "buyer": "a.n Budi Santoso"})

    outcome = anonymiser.anonymise(chat).record.outcome

    assert outcome == {"phone": "<TELEPON_1>", "buyer": "a.n <NAMA_1>"}


def test_an_identifier_stored_as_an_integer_is_redacted(anonymiser: Anonymiser) -> None:
    chat = _chat(("halo", None), outcome={"nik": 3201010101010001})

    outcome = anonymiser.anonymise(chat).record.outcome

    assert outcome == {"nik": "<NIK_1>"}


def test_nested_outcome_values_are_scanned(anonymiser: Anonymiser) -> None:
    chat = _chat(("halo", None), outcome={"contacts": [{"email": "budi@gmail.com"}]})

    outcome = anonymiser.anonymise(chat).record.outcome

    assert outcome == {"contacts": [{"email": "<EMAIL_1>"}]}


def test_an_identifier_used_as_an_outcome_key_is_redacted(anonymiser: Anonymiser) -> None:
    chat = _chat(("halo", None), outcome={"081234567890": "bought"})

    outcome = anonymiser.anonymise(chat).record.outcome

    assert outcome == {"<TELEPON_1>": "bought"}


def test_outcome_facts_that_identify_no_one_are_kept(anonymiser: Anonymiser) -> None:
    facts: dict[str, JsonValue] = {"purchased": True, "days": 3, "rating": 4.5, "note": None}
    chat = _chat(("halo", None), outcome=facts)

    assert anonymiser.anonymise(chat).record.outcome == facts


def test_a_phone_in_the_turns_and_the_outcome_shares_a_placeholder(
    anonymiser: Anonymiser,
) -> None:
    chat = _chat(
        ("wa 081399998888 atau 081234567890", None), outcome={"phone": "+62 812-3456-7890"}
    )

    result = anonymiser.anonymise(chat).record

    assert result.turns[0].text == "wa <TELEPON_1> atau <TELEPON_2>"
    assert result.outcome == {"phone": "<TELEPON_2>"}


def test_timestamps_keep_the_gaps_but_lose_the_date(anonymiser: Anonymiser) -> None:
    start = datetime(2026, 11, 3, 21, 14, tzinfo=UTC)
    chat = _chat(("halo", start), ("ada kak", None), ("siap", start + timedelta(minutes=7)))

    turns = anonymiser.anonymise(chat).record.turns

    assert [turn.timestamp for turn in turns] == [
        TIMESTAMP_ANCHOR,
        None,
        TIMESTAMP_ANCHOR + timedelta(minutes=7),
    ]


def test_a_chat_mixing_zoned_and_unzoned_timestamps_is_still_shifted(
    anonymiser: Anonymiser,
) -> None:
    chat = _chat(
        ("halo", datetime(2026, 11, 3, 21, 0)),  # no zone: the case under test
        ("siap", datetime(2026, 11, 3, 21, 5, tzinfo=UTC)),
    )

    turns = anonymiser.anonymise(chat).record.turns

    assert turns[1].timestamp == TIMESTAMP_ANCHOR + timedelta(minutes=5)


def test_a_short_pseudonym_key_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PSEUDONYM_KEY_VARIABLE, "short")

    with pytest.raises(typer.BadParameter, match="shorter than 32 characters"):
        pseudonym_key_from_environment()


def test_a_long_enough_pseudonym_key_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PSEUDONYM_KEY_VARIABLE, "a" * 32)

    assert pseudonym_key_from_environment() == b"a" * 32
