"""Scores the anonymiser against labelled chats, by what it misses.

The rules are the measurement plan's (A):
- A gold value is **missed** unless redactions hide enough of it. Any 3 or
  more consecutive digits left visible is a miss, so a partial redaction
  like "0812-<TELEPON_1>" is one. For values made of words (names,
  addresses, emails, plates, order IDs), any whole word left visible is a
  miss too. Numbers don't use the word rule: a visible "+62" alone
  identifies no one.
- **Leaked characters**: letters and digits of gold values left visible.
- **Wrong type**: hidden, but under another type's placeholder. Reported,
  not a miss.
- **Over-redaction**: redacted characters outside every gold value, over
  all characters outside gold values.
- **Negative hits**: redactions touching a price, product, date and so on.
- **Precision per type**: redactions of a type that overlap a gold value of
  that type, over all redactions of that type. Recall is 1 minus the miss
  rate.
- Intervals are 95% Wilson intervals; with zero misses the upper bound is
  about 3/N.
"""

import math
import re
from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from id_chat_anonymiser.anonymiser import AnonymisedChat, Redaction
from id_chat_anonymiser.labels import GoldSpan, LabelledChat, PiiType

NUMBER_TYPES = frozenset({PiiType.TELEPON, PiiType.NIK, PiiType.REKENING})
WILSON_Z_95 = 1.959964
MIN_VISIBLE_DIGIT_RUN = 3
WORD = re.compile(r"\w+")
VISIBLE_DIGIT_RUN = re.compile(rf"\d{{{MIN_VISIBLE_DIGIT_RUN},}}")


class TypeScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gold: int = 0
    missed: int = 0
    wrong_type: int = 0
    gold_characters: int = 0
    leaked_characters: int = 0
    miss_rate_upper_95: float = 1.0


class TypePrecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    redactions: int = 0
    on_gold_of_type: int = 0

    @property
    def precision(self) -> float:
        return self.on_gold_of_type / self.redactions if self.redactions else 1.0


class SetScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chats: int
    by_type: dict[PiiType, TypeScore]
    redacted_outside_gold: int
    characters_outside_gold: int
    negative_hits: dict[str, int]
    missed_examples: dict[PiiType, list[str]]
    # Defaulted so run records written before precision was added still load.
    precision_by_type: dict[PiiType, TypePrecision] = {}

    @property
    def over_redaction_rate(self) -> float:
        return self.redacted_outside_gold / max(self.characters_outside_gold, 1)


def wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    """95% Wilson score interval for a proportion."""
    if trials == 0:
        return 0.0, 1.0
    proportion = successes / trials
    z_squared = WILSON_Z_95**2
    centre = (proportion + z_squared / (2 * trials)) / (1 + z_squared / trials)
    spread = math.sqrt(proportion * (1 - proportion) / trials + z_squared / (4 * trials**2))
    half_width = WILSON_Z_95 * spread / (1 + z_squared / trials)
    return max(0.0, centre - half_width), min(1.0, centre + half_width)


def hidden_characters(chat: AnonymisedChat, turn_count: int) -> list[set[int]]:
    """For each turn, the positions of the original text that a redaction hides."""
    hidden: list[set[int]] = [set() for _ in range(turn_count)]
    for redaction in chat.redactions:
        hidden[redaction.turn_index].update(range(redaction.start, redaction.end))
    return hidden


def is_missed(gold_text: str, gold_start: int, hidden: set[int], pii_type: PiiType) -> bool:
    visible = "".join(
        character if position not in hidden else " "
        for position, character in enumerate(gold_text, start=gold_start)
    )
    if VISIBLE_DIGIT_RUN.search(visible):
        return True
    if pii_type in NUMBER_TYPES:
        return False
    for word in WORD.finditer(gold_text):
        word_positions = range(gold_start + word.start(), gold_start + word.end())
        if not any(position in hidden for position in word_positions):
            return True
    return False


def _overlaps_same_type(redaction: Redaction, span: GoldSpan) -> bool:
    return (
        redaction.pii_type is span.pii_type
        and redaction.turn_index == span.turn_index
        and redaction.start < span.end
        and span.start < redaction.end
    )


def _has_right_type(span: GoldSpan, chat: AnonymisedChat) -> bool:
    return any(_overlaps_same_type(redaction, span) for redaction in chat.redactions)


class _Tally:
    """Running totals over a set; `result` turns them into a `SetScore`."""

    def __init__(self) -> None:
        self.by_type: dict[PiiType, TypeScore] = {}
        self.negative_hits: Counter[str] = Counter()
        self.redacted_outside_gold = 0
        self.characters_outside_gold = 0
        self.missed_examples: dict[PiiType, list[str]] = {}
        self.precision_by_type: dict[PiiType, TypePrecision] = {}

    def add(self, labelled: LabelledChat, anonymised: AnonymisedChat) -> None:
        texts = [turn.text for turn in labelled.record.turns]
        hidden = hidden_characters(anonymised, len(texts))
        for span in labelled.gold:
            self._add_gold(span, texts[span.turn_index], hidden[span.turn_index], anonymised)
        self._add_precision(labelled, anonymised)
        for span in labelled.negatives:
            if any(position in hidden[span.turn_index] for position in range(span.start, span.end)):
                self.negative_hits[span.kind.value] += 1
        for turn_index, text in enumerate(texts):
            gold_positions = {
                position
                for span in labelled.gold
                if span.turn_index == turn_index
                for position in range(span.start, span.end)
            }
            self.characters_outside_gold += len(text) - len(gold_positions)
            self.redacted_outside_gold += len(hidden[turn_index] - gold_positions)

    def _add_precision(self, labelled: LabelledChat, anonymised: AnonymisedChat) -> None:
        for redaction in anonymised.redactions:
            precision = self.precision_by_type.setdefault(redaction.pii_type, TypePrecision())
            precision.redactions += 1
            if any(_overlaps_same_type(redaction, span) for span in labelled.gold):
                precision.on_gold_of_type += 1

    def _add_gold(self, span: GoldSpan, text: str, hidden: set[int], chat: AnonymisedChat) -> None:
        score = self.by_type.setdefault(span.pii_type, TypeScore())
        gold_text = text[span.start : span.end]
        score.gold += 1
        score.gold_characters += sum(character.isalnum() for character in gold_text)
        score.leaked_characters += sum(
            character.isalnum() and position not in hidden
            for position, character in enumerate(gold_text, start=span.start)
        )
        if is_missed(gold_text, span.start, hidden, span.pii_type):
            score.missed += 1
            self.missed_examples.setdefault(span.pii_type, []).append(gold_text)
        elif not _has_right_type(span, chat):
            score.wrong_type += 1

    def result(self, chats: int) -> SetScore:
        for score in self.by_type.values():
            score.miss_rate_upper_95 = wilson_interval(score.missed, score.gold)[1]
        return SetScore(
            chats=chats,
            by_type=dict(sorted(self.by_type.items())),
            redacted_outside_gold=self.redacted_outside_gold,
            characters_outside_gold=self.characters_outside_gold,
            negative_hits=dict(self.negative_hits),
            missed_examples=self.missed_examples,
            precision_by_type=dict(sorted(self.precision_by_type.items())),
        )


def score_set(labelled: Sequence[LabelledChat], anonymised: Sequence[AnonymisedChat]) -> SetScore:
    tally = _Tally()
    for labelled_chat, anonymised_chat in zip(labelled, anonymised, strict=True):
        tally.add(labelled_chat, anonymised_chat)
    return tally.result(len(labelled))
