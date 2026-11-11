"""Plugging an NER model into Presidio, next to the pattern recognisers.

R1 is R0 plus one of these: `NerRecogniser` around our token classifier
(NusaBert, Horizon), or Presidio's own `GLiNERRecognizer` for GLiNER.
Presidio runs it on each turn like any other recogniser, so its spans go
through the same overlap merging and placeholder numbering as the
patterns' (anonymiser.py).
"""

from pathlib import Path
from typing import Protocol

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts
from presidio_analyzer.predefined_recognizers import GLiNERRecognizer

from id_chat_anonymiser.labels import NER_TYPES
from id_chat_anonymiser.ner.models import ModelSpec, Runtime, find_model, model_spec
from id_chat_anonymiser.ner.spans import NerSpan
from id_chat_anonymiser.recognisers import LANGUAGE
from id_chat_anonymiser.reference import BANKS

# Leaves cores free for other work on the laptop; the benchmark reports speed at this setting.
CPU_THREADS = 4
# The lowest score a span may have to be redacted, for every model: GLiNER's
# default, and the default in Horizon's own redact.py.
MIN_SCORE = 0.5
# Whole spans NusaBert tags as names that name no one, seen on dev: bank
# names before an account number ("Mandiri 5118...") and the cue "a.n".
NOT_PERSONAL = frozenset({*(bank.lower() for bank in BANKS), "a.n", "a.n.", "an."})


class NerFinder(Protocol):
    def find(self, text: str) -> list[NerSpan]: ...


def names_no_one(span_text: str) -> bool:
    """Whether an NER span is safe to leave readable.

    A span with no letters ("1" in "rawat inap kelas 1", tagged as a place)
    is a number, not a name or an address; a lone house number identifies
    no one, and the patterns handle real numbers.
    """
    has_letters = any(character.isalpha() for character in span_text)
    return not has_letters or span_text.strip().lower() in NOT_PERSONAL


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
            if span.end > span.start and not names_no_one(text[span.start : span.end])
        ]


class OwnLabelsGlinerRecogniser(GLiNERRecognizer):
    """Presidio's GLiNER recogniser, asked only for our own label prompts.

    Presidio asks every recogniser for every entity type in the registry,
    and `GLiNERRecognizer` adds each requested type it doesn't know as an
    extra zero-shot prompt. Unchecked, GLiNER was also asked for "TELEPON",
    "NIK" and "REKENING" and redacted hundreds of prices (dev run,
    2026-11-11). Passing no requested entities keeps it to "person" and
    "street address".
    """

    def analyze(
        self,
        text: str,
        entities: list[str],  # noqa: ARG002  (deliberately ignored; see the class docstring)
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        return super().analyze(text, [], nlp_artifacts)


def load_ner_recogniser(model_key: str) -> EntityRecognizer:
    """Load a fetched, hash-checked model from the cache; never downloads."""
    spec = model_spec(model_key)
    folder = find_model(spec)
    if spec.runtime is Runtime.GLINER:
        return _gliner_recogniser(spec, folder)
    from id_chat_anonymiser.ner.token_classifier import TokenClassifier

    classifier = TokenClassifier(spec, folder, min_score=MIN_SCORE, threads=CPU_THREADS)
    return NerRecogniser(classifier, model_key)


def _gliner_recogniser(spec: ModelSpec, folder: Path) -> EntityRecognizer:
    # Presidio's own GLiNER recogniser: it cuts long texts into overlapping
    # chunks (GLiNER alone keeps only its first 384 words) and maps labels.
    import torch

    torch.set_num_threads(CPU_THREADS)
    return OwnLabelsGlinerRecogniser(
        name=f"ner-{spec.key}",
        supported_language=LANGUAGE,
        entity_mapping={label: pii_type.value for label, pii_type in spec.labels.items()},
        model_name=str(folder),
        threshold=MIN_SCORE,
        map_location="cpu",
        local_files_only=True,
    )
