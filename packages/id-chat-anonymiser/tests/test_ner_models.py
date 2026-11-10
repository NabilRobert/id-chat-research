"""The real NER models on a few sentences. Skipped unless the models are fetched.

CI never downloads weights, so these run only locally after
`uv sync --group ner` and `uv run id-chat fetch-models`.
"""

import pytest
from id_chat_anonymiser.anonymiser import Anonymiser
from id_chat_anonymiser.labels import PiiType
from id_chat_anonymiser.ner.models import MODELS, ModelNotFetchedError
from id_chat_anonymiser.ner.recogniser import load_ner_recogniser

SENTENCE = "Halo kak, saya Dewi Lestari, alamat Jl. Melati No. 5 RT 03/RW 07 Bekasi"


def _r1(model_key: str) -> Anonymiser:
    try:
        return Anonymiser([load_ner_recogniser(model_key)])
    except (ModelNotFetchedError, ImportError) as error:
        pytest.skip(f"{model_key} not available: {error}")


@pytest.mark.parametrize("model_key", sorted(MODELS))
def test_model_finds_a_full_name_and_never_the_city(model_key: str) -> None:
    matches = _r1(model_key).find(SENTENCE)

    names = [SENTENCE[m.start : m.end] for m in matches if m.pii_type is PiiType.NAMA]
    found = "".join(SENTENCE[m.start : m.end] for m in matches)
    assert "Dewi Lestari" in names
    assert "Bekasi" not in found


@pytest.mark.parametrize("model_key", sorted(MODELS))
def test_a_name_at_the_end_of_a_very_long_message_is_found(model_key: str) -> None:
    text = "motornya bagus kak, harganya juga oke " * 300 + "saya Dewi Lestari"

    matches = _r1(model_key).find(text)

    assert any(text[m.start : m.end] == "Dewi Lestari" for m in matches)
