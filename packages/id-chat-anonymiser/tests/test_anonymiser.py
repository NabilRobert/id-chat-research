"""The anonymiser end to end: placeholders, numbering, merging, failing closed."""

import logging
import socket
from typing import Any

import pytest
from id_chat_anonymiser.anonymiser import (
    PRESIDIO_LOGGER,
    Anonymiser,
    PatternSkippedError,
    merge_overlapping,
)
from id_chat_anonymiser.labels import PiiType
from id_chat_records import ChatRecord, Source, Turn
from presidio_analyzer import RecognizerResult


def _chat(*texts: str, chat_id: str = "chat-1") -> ChatRecord:
    roles = ("customer", "agent")
    turns = tuple(
        Turn.model_validate({"index": index, "role": roles[index % 2], "text": text})
        for index, text in enumerate(texts)
    )
    return ChatRecord(chat_id=chat_id, source=Source.SYNTHETIC, domain="vehicles", turns=turns)


@pytest.fixture(scope="module")
def anonymiser() -> Anonymiser:
    return Anonymiser()


def test_values_become_numbered_typed_placeholders_in_reading_order(
    anonymiser: Anonymiser,
) -> None:
    chat = _chat("hp 081234567890 atau 081399998888", "email budi@gmail.com")

    result = anonymiser.anonymise(chat)

    texts = [turn.text for turn in result.record.turns]
    assert texts == ["hp <TELEPON_1> atau <TELEPON_2>", "email <EMAIL_1>"]


def test_two_spellings_of_one_number_share_a_placeholder(anonymiser: Anonymiser) -> None:
    chat = _chat("wa 0812-3456-7890", "siap, saya hubungi +62 812 3456 7890")

    result = anonymiser.anonymise(chat)

    assert [redaction.placeholder for redaction in result.redactions] == ["<TELEPON_1>"] * 2


def test_numbering_restarts_for_each_chat(anonymiser: Anonymiser) -> None:
    first = anonymiser.anonymise(_chat("hp 081234567890"))
    second = anonymiser.anonymise(_chat("hp 081399998888", chat_id="chat-2"))

    assert first.record.turns[0].text == second.record.turns[0].text == "hp <TELEPON_1>"


def test_everything_but_the_text_is_kept(anonymiser: Anonymiser) -> None:
    chat = _chat("nik 3201234512900001")

    result = anonymiser.anonymise(chat)

    assert result.record.chat_id == chat.chat_id
    assert result.record.source is Source.SYNTHETIC
    assert result.redactions[0].pii_type is PiiType.NIK


def test_partly_overlapping_matches_merge_into_one_redaction() -> None:
    results = [
        RecognizerResult("TELEPON", start=3, end=17, score=0.4),
        RecognizerResult("REKENING", start=0, end=10, score=0.8),
    ]

    merged = merge_overlapping(results)

    assert [(match.start, match.end, match.pii_type) for match in merged] == [
        (0, 17, PiiType.REKENING)
    ]


def test_it_runs_with_the_network_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the anonymiser tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    result = Anonymiser().anonymise(_chat("email budi@gmail.com, hp +62 812 3456 7890"))

    assert result.record.turns[0].text == "email <EMAIL_1>, hp <TELEPON_1>"


def test_a_skipped_pattern_raises_instead_of_failing_open(
    anonymiser: Anonymiser, monkeypatch: pytest.MonkeyPatch
) -> None:
    def analyse_with_a_timeout(*_args: Any, **_kwargs: Any) -> list[RecognizerResult]:
        logging.getLogger(PRESIDIO_LOGGER).warning("Regex pattern 'x' timed out, skipping.")
        return []

    monkeypatch.setattr(anonymiser._analyzer, "analyze", analyse_with_a_timeout)  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(PatternSkippedError, match="timed out"):
        anonymiser.find("hp 081234567890")


def test_a_pattern_type_beats_a_more_confident_ner_type_on_overlap() -> None:
    email = RecognizerResult("EMAIL", 0, 18, 0.5)
    name_inside_email = RecognizerResult("NAMA", 0, 10, 0.99)

    merged = merge_overlapping([name_inside_email, email])

    assert [(match.start, match.end, match.pii_type) for match in merged] == [
        (0, 18, PiiType.EMAIL)
    ]
