"""R1 wiring without a model: the NER recogniser beside the patterns, model pins, the CLI."""

from pathlib import Path

import pytest
from id_chat_anonymiser.anonymiser import Anonymiser
from id_chat_anonymiser.cli import app
from id_chat_anonymiser.labels import PiiType
from id_chat_anonymiser.ner.models import (
    MODELS,
    ModelHashError,
    ModelNotFetchedError,
    RepoPin,
    verify_files,
)
from id_chat_anonymiser.ner.recogniser import NerRecogniser
from id_chat_anonymiser.ner.spans import NerSpan
from id_chat_records import ChatRecord, Source, Turn
from typer.testing import CliRunner


class _FindsDewi:
    """Stands in for a model: finds every "Dewi"."""

    def find(self, text: str) -> list[NerSpan]:
        spans: list[NerSpan] = []
        start = text.find("Dewi")
        while start != -1:
            spans.append(NerSpan(start, start + 4, PiiType.NAMA, 0.95))
            start = text.find("Dewi", start + 1)
        return spans


def _chat(*texts: str) -> ChatRecord:
    turns = tuple(
        Turn.model_validate({"index": index, "role": "customer", "text": text})
        for index, text in enumerate(texts)
    )
    return ChatRecord(chat_id="c", source=Source.SYNTHETIC, domain="vehicles", turns=turns)


def test_ner_names_are_numbered_beside_the_pattern_matches() -> None:
    anonymiser = Anonymiser([NerRecogniser(_FindsDewi(), "fake")])

    result = anonymiser.anonymise(_chat("saya Dewi, hp 081234567890", "iya kak, Dewi"))

    texts = [turn.text for turn in result.record.turns]
    assert texts == ["saya <NAMA_1>, hp <TELEPON_1>", "iya kak, <NAMA_1>"]


def _pin(files: dict[str, str | None]) -> RepoPin:
    return RepoPin(repo="x/y", commit="0" * 40, files=files)


def test_a_model_file_that_differs_from_its_pin_is_refused(tmp_path: Path) -> None:
    (tmp_path / "w.bin").write_bytes(b"swapped weights")

    with pytest.raises(ModelHashError, match="pinned SHA-256"):
        verify_files(_pin({"w.bin": "0" * 64}), tmp_path, "fake")


def test_a_missing_model_file_says_how_to_fetch_it(tmp_path: Path) -> None:
    with pytest.raises(ModelNotFetchedError, match="fetch-models --model fake"):
        verify_files(_pin({"w.bin": None}), tmp_path, "fake")


def test_every_weight_and_tokenizer_file_is_pinned_by_hash() -> None:
    for spec in MODELS.values():
        assert spec.pin.files[spec.weights] is not None
        for pin in (spec.pin, *spec.support):
            assert all(pin.files[name] for name in pin.files if name.startswith("tokenizer."))
            assert all(pin.files[name] for name in pin.files if name.endswith(".model"))
            assert len(pin.commit) == 40


def test_limit_is_refused_on_heldout() -> None:
    result = CliRunner().invoke(app, ["score", "--set", "heldout", "--limit", "5"])

    assert result.exit_code != 0
    assert "dev smoke runs only" in result.output
