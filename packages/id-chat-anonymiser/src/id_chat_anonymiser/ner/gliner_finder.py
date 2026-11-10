"""Running GLiNER, the zero-shot candidate, over one text.

GLiNER is asked for the label prompts in the model spec ("person",
"street address") and returns character spans itself. It keeps only the
first `max_len` words of a text (384 for this model) and drops the rest
without an error, so the text is cut into overlapping word windows here;
otherwise the end of a long message would never be checked.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from id_chat_anonymiser.ner.models import ModelSpec
from id_chat_anonymiser.ner.spans import NerSpan

# GLiNER counts words with this pattern; punctuation marks count as words too.
GLINER_WORD = re.compile(r"\w+(?:[-_]\w+)*|\S")
MAX_WINDOW_WORDS = 300
WINDOW_OVERLAP_WORDS = 30
# GLiNER's own default; the token classifiers use the same floor (MIN_SPAN_SCORE).
MIN_SCORE = 0.5


def word_windows(text: str) -> Iterator[tuple[int, str]]:
    """(character offset, window text) pairs that together cover all of `text`."""
    words = list(GLINER_WORD.finditer(text))
    if len(words) <= MAX_WINDOW_WORDS:
        yield 0, text
        return
    step = MAX_WINDOW_WORDS - WINDOW_OVERLAP_WORDS
    for first in range(0, len(words), step):
        last = min(first + MAX_WINDOW_WORDS, len(words)) - 1
        start, end = words[first].start(), words[last].end()
        yield start, text[start:end]
        if last == len(words) - 1:
            return


class GlinerFinder:
    def __init__(self, spec: ModelSpec, folder: Path) -> None:
        from gliner import GLiNER  # pyright: ignore[reportMissingTypeStubs]

        self._model = cast(Any, GLiNER).from_pretrained(str(folder), local_files_only=True)
        self._labels = spec.labels

    def find(self, text: str) -> list[NerSpan]:
        spans: list[NerSpan] = []
        for offset, window in word_windows(text):
            entities = cast(
                list[dict[str, Any]],
                self._model.predict_entities(window, list(self._labels), threshold=MIN_SCORE),
            )
            spans.extend(
                NerSpan(
                    start=offset + int(entity["start"]),
                    end=offset + int(entity["end"]),
                    pii_type=self._labels[str(entity["label"])],
                    score=float(entity["score"]),
                )
                for entity in entities
            )
        return spans
