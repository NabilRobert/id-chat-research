"""The anonymiser: find personal data in a chat and replace it with placeholders.

Flow for one chat (see docs/guide.md):
1. Presidio's `AnalyzerEngine` runs the recognisers over each turn.
2. Overlapping matches merge into one redaction covering all of them.
3. Each distinct value gets a numbered typed placeholder (`<TELEPON_1>`),
   the same number every time it recurs in the chat.

Presidio needs a spaCy pipeline even for patterns-only work, and spaCy has
no trained Indonesian one, so a blank Indonesian pipeline (a tokeniser,
no download) is used (ADR-003). Merging and numbering are done here rather
than by presidio-anonymizer: it trims one of two partly overlapping
matches, which can leave part of a number visible, and it reports
redactions in output positions, while the scorer needs input positions.

The value-to-number map lives in memory for one chat and is never written
(threat model, P6, P7).
"""

import logging
from dataclasses import dataclass

import spacy
from id_chat_records import ChatRecord, Turn
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import SpacyNlpEngine
from pydantic import BaseModel, ConfigDict

from id_chat_anonymiser.labels import PiiType
from id_chat_anonymiser.recognisers import LANGUAGE, all_recognisers

PRESIDIO_LOGGER = "presidio-analyzer"


class Redaction(BaseModel):
    """One redacted range [start, end) of a turn's original text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_index: int
    start: int
    end: int
    pii_type: PiiType
    placeholder: str


class AnonymisedChat(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record: ChatRecord
    redactions: tuple[Redaction, ...]


class PatternSkippedError(RuntimeError):
    """Presidio skipped a pattern (it timed out), so some text went unchecked."""


class _BlankIndonesianNlpEngine(SpacyNlpEngine):
    def __init__(self) -> None:
        super().__init__(models=[{"lang_code": LANGUAGE, "model_name": "blank"}])

    def load(self) -> None:
        self.nlp = {LANGUAGE: spacy.blank(LANGUAGE)}


class _SkippedPatternWatcher(logging.Handler):
    """Notices Presidio's "timed out, skipping" warning, which would fail open."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.skipped = False

    def emit(self, record: logging.LogRecord) -> None:
        if "timed out" in record.getMessage():
            self.skipped = True


@dataclass
class _Match:
    start: int
    end: int
    pii_type: PiiType
    score: float


def merge_overlapping(results: list[RecognizerResult]) -> list[_Match]:
    """Union overlapping matches; the merged match takes the best-scoring type."""
    ordered = sorted(results, key=lambda result: (result.start, -result.end))
    merged: list[_Match] = []
    for result in ordered:
        match = _Match(result.start, result.end, PiiType(result.entity_type), result.score)
        if merged and match.start < merged[-1].end:
            previous = merged[-1]
            if match.score > previous.score:
                previous.pii_type, previous.score = match.pii_type, match.score
            previous.end = max(previous.end, match.end)
            continue
        merged.append(match)
    return merged


def normalise(value: str, pii_type: PiiType) -> str:
    """The form two spellings of one value share: "+62 812-3" and "08123" match."""
    if pii_type in (PiiType.EMAIL, PiiType.NAMA, PiiType.ALAMAT, PiiType.PLAT):
        return "".join(value.lower().split()).replace("-", "")
    digits = "".join(character for character in value if character.isalnum()).lower()
    if pii_type is PiiType.TELEPON and digits.startswith("62"):
        return "0" + digits[2:]
    return digits


class _Numberer:
    """Hands out `<TYPE_n>` placeholders for one chat."""

    def __init__(self) -> None:
        self._numbers: dict[tuple[PiiType, str], int] = {}
        self._counts: dict[PiiType, int] = {}

    def placeholder(self, value: str, pii_type: PiiType) -> str:
        key = (pii_type, normalise(value, pii_type))
        if key not in self._numbers:
            self._counts[pii_type] = self._counts.get(pii_type, 0) + 1
            self._numbers[key] = self._counts[pii_type]
        return f"<{pii_type.value}_{self._numbers[key]}>"


class Anonymiser:
    """Builds the Presidio engine once; `anonymise` is then called per chat."""

    def __init__(self) -> None:
        nlp_engine = _BlankIndonesianNlpEngine()
        nlp_engine.load()
        registry = RecognizerRegistry(supported_languages=[LANGUAGE])
        for recogniser in all_recognisers():
            registry.add_recognizer(recogniser)
        self._analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine, registry=registry, supported_languages=[LANGUAGE]
        )
        self._watcher = _SkippedPatternWatcher()
        logging.getLogger(PRESIDIO_LOGGER).addHandler(self._watcher)

    def find(self, text: str) -> list[_Match]:
        self._watcher.skipped = False
        results = self._analyzer.analyze(text, language=LANGUAGE)
        if self._watcher.skipped:
            raise PatternSkippedError(
                "a recogniser timed out, so this text was not fully checked: "
                "split very long messages, or raise REGEX_TIMEOUT_SECONDS"
            )
        return merge_overlapping(results)

    def anonymise(self, record: ChatRecord) -> AnonymisedChat:
        numberer = _Numberer()
        turns: list[Turn] = []
        redactions: list[Redaction] = []
        for turn in record.turns:
            turn_redactions = self._redactions_for(turn, numberer)
            redactions.extend(turn_redactions)
            turns.append(turn.model_copy(update={"text": _replace(turn.text, turn_redactions)}))
        anonymised = record.model_copy(update={"turns": tuple(turns)})
        return AnonymisedChat(record=anonymised, redactions=tuple(redactions))

    def _redactions_for(self, turn: Turn, numberer: _Numberer) -> list[Redaction]:
        # Numbered in reading order, so the first value in a chat is _1.
        return [
            Redaction(
                turn_index=turn.index,
                start=match.start,
                end=match.end,
                pii_type=match.pii_type,
                placeholder=numberer.placeholder(
                    turn.text[match.start : match.end], match.pii_type
                ),
            )
            for match in self.find(turn.text)
        ]


def _replace(text: str, redactions: list[Redaction]) -> str:
    # From the end backwards, so earlier positions stay valid.
    for redaction in reversed(redactions):
        text = text[: redaction.start] + redaction.placeholder + text[redaction.end :]
    return text
