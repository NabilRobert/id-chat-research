"""Plugging an NER model into Presidio, next to the pattern recognisers.

R1 is R0 plus one of these. Presidio runs it on each turn like any other
recogniser, so its spans go through the same overlap merging and
placeholder numbering as the patterns' (anonymiser.py).
"""

from typing import Protocol

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from id_chat_anonymiser.labels import NER_TYPES
from id_chat_anonymiser.ner.models import Runtime, find_model, model_spec
from id_chat_anonymiser.ner.spans import NerSpan
from id_chat_anonymiser.recognisers import LANGUAGE


class NerFinder(Protocol):
    def find(self, text: str) -> list[NerSpan]: ...


class NerRecogniser(EntityRecognizer):
    def __init__(self, finder: NerFinder, model_key: str) -> None:
        self._finder = finder
        super().__init__(
            supported_entities=sorted(pii_type.value for pii_type in NER_TYPES),
            name=f"ner-{model_key}",
            supported_language=LANGUAGE,
        )

    def load(self) -> None:
        """The model is loaded before construction; nothing to do here."""

    def analyze(
        self,
        text: str,
        entities: list[str],  # noqa: ARG002  (Presidio's signature; it filters by entity itself)
        nlp_artifacts: NlpArtifacts | None = None,  # noqa: ARG002
    ) -> list[RecognizerResult]:
        return [
            RecognizerResult(span.pii_type.value, span.start, span.end, span.score)
            for span in self._finder.find(text)
            if span.end > span.start
        ]


def load_ner_recogniser(model_key: str) -> NerRecogniser:
    """Load a fetched, hash-checked model from the cache; never downloads."""
    spec = model_spec(model_key)
    folder = find_model(spec)
    finder: NerFinder
    if spec.runtime is Runtime.GLINER:
        from id_chat_anonymiser.ner.gliner_finder import GlinerFinder

        finder = GlinerFinder(spec, folder)
    else:
        from id_chat_anonymiser.ner.token_classifier import TokenClassifier

        finder = TokenClassifier(spec, folder)
    return NerRecogniser(finder, model_key)
