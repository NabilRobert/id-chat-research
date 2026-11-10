"""The real NER models on a few sentences. Skipped unless the models are fetched.

CI never downloads weights, so these run only locally after
`uv sync --group ner` and `uv run id-chat fetch-models`.
"""

import pytest
from id_chat_anonymiser.labels import PiiType
from id_chat_anonymiser.ner.models import MODELS, ModelNotFetchedError
from id_chat_anonymiser.ner.recogniser import NerRecogniser, load_ner_recogniser

SENTENCE = "Halo kak, saya Dewi Lestari, alamat Jl. Melati No. 5 RT 03/RW 07 Bekasi"


def _recogniser(model_key: str) -> NerRecogniser:
    try:
        return load_ner_recogniser(model_key)
    except (ModelNotFetchedError, ImportError) as error:
        pytest.skip(f"{model_key} not available: {error}")


@pytest.mark.parametrize("model_key", sorted(MODELS))
def test_model_finds_a_full_name_and_never_the_city(model_key: str) -> None:
    results = _recogniser(model_key).analyze(SENTENCE, [])

    names = [SENTENCE[r.start : r.end] for r in results if r.entity_type == PiiType.NAMA]
    found = "".join(SENTENCE[r.start : r.end] for r in results)
    assert "Dewi Lestari" in names
    assert "Bekasi" not in found
