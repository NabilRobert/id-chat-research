"""Turning a token classifier's per-token labels into character spans.

A token classifier labels sub-word tokens with BIO tags ("B-PER", "I-PER",
"O"). Turning those into names and addresses is where off-by-one leaks
happen, so it is done here, once, for every token model, and tested
without any model:

1. Tokens with no gap between them form one word ("Puspa" + "sari"). A
   word takes its first token's label, so a name is never cut mid-word and
   half left visible.
2. Words merge into a span while the tags continue it: an "I-" tag of the
   same type, or a "B-" tag the model put on the next word of one name.
   Only a change of type, or an "O", ends a span.
3. Trailing commas and the like are trimmed off the span.

Labels the model has but this project doesn't redact (cities, dates,
organisations) map to nothing and act as "O".
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from id_chat_anonymiser.labels import PiiType

OUTSIDE = "O"
TRAILING_PUNCTUATION = ",;:!?\"')"


@dataclass(frozen=True)
class TokenPrediction:
    """One token's best label, its probability, and its [start, end) in the text."""

    label: str
    score: float
    start: int
    end: int


@dataclass(frozen=True)
class NerSpan:
    start: int
    end: int
    pii_type: PiiType
    score: float


@dataclass
class _Word:
    start: int
    end: int
    label: str
    score: float


def _words(tokens: Sequence[TokenPrediction], text: str) -> list[_Word]:
    words: list[_Word] = []
    for token in tokens:
        # Byte-level tokenisers can count the space before a word as part of
        # its first token; without this, every word would look glued on.
        start = token.start
        while start < token.end and text[start].isspace():
            start += 1
        if start == token.end:
            continue  # special tokens ([CLS], padding) and bare spaces cover no text
        if words and start <= words[-1].end:
            words[-1].end = max(words[-1].end, token.end)
            continue
        words.append(_Word(start, token.end, token.label, token.score))
    return words


def _entity(label: str) -> str:
    return label.split("-", 1)[1] if "-" in label else label


def decode_bio(
    tokens: Sequence[TokenPrediction], label_map: Mapping[str, PiiType], text: str
) -> list[NerSpan]:
    """Spans of the mapped entity types, in reading order."""
    spans: list[NerSpan] = []
    current: list[_Word] = []
    current_type: PiiType | None = None
    for word in _words(tokens, text):
        pii_type = None if word.label == OUTSIDE else label_map.get(_entity(word.label))
        if pii_type is not None and pii_type is current_type:
            current.append(word)
            continue
        if current_type is not None:
            spans.append(_span(current, current_type, text))
        current, current_type = ([word], pii_type) if pii_type is not None else ([], None)
    if current_type is not None:
        spans.append(_span(current, current_type, text))
    return spans


def _span(words: list[_Word], pii_type: PiiType, text: str) -> NerSpan:
    start, end = words[0].start, words[-1].end
    while end > start and text[end - 1] in TRAILING_PUNCTUATION:
        end -= 1
    score = sum(word.score for word in words) / len(words)
    return NerSpan(start=start, end=end, pii_type=pii_type, score=score)
