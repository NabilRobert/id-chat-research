"""Turning per-token labels into spans: whole words, joined names, no leaks.

No model is loaded: the tokens are written by hand, as a tokenizer and a
classifier would produce them.
"""

import numpy as np
from id_chat_anonymiser.labels import PiiType
from id_chat_anonymiser.ner.spans import NerSpan, TokenPrediction, decode_bio
from id_chat_anonymiser.ner.token_classifier import predictions

LABELS = {"PER": PiiType.NAMA, "FAC": PiiType.ALAMAT}


def _tokens(text: str, *pieces: tuple[str, str]) -> list[TokenPrediction]:
    """Tokens for consecutive pieces of `text`, each with its label."""
    tokens: list[TokenPrediction] = []
    position = 0
    for piece, label in pieces:
        start = text.index(piece, position)
        tokens.append(TokenPrediction(label=label, score=0.9, start=start, end=start + len(piece)))
        position = start + len(piece)
    return tokens


def _texts(text: str, spans: list[NerSpan]) -> list[tuple[str, PiiType]]:
    return [(text[span.start : span.end], span.pii_type) for span in spans]


def test_a_name_split_into_sub_words_is_redacted_whole() -> None:
    text = "saya Puspasari ya"
    tokens = _tokens(text, ("saya", "O"), ("Puspa", "B-PER"), ("sari", "O"), ("ya", "O"))

    assert _texts(text, decode_bio(tokens, LABELS, text)) == [("Puspasari", PiiType.NAMA)]


def test_first_and_last_name_tagged_b_b_join_into_one_name() -> None:
    text = "a.n Budi Santoso"
    tokens = _tokens(text, ("a.n", "O"), ("Budi", "B-PER"), ("Santoso", "B-PER"))

    assert _texts(text, decode_bio(tokens, LABELS, text)) == [("Budi Santoso", PiiType.NAMA)]


def test_a_word_tagged_outside_ends_the_name() -> None:
    text = "Budi dan Ani"
    tokens = _tokens(text, ("Budi", "B-PER"), ("dan", "O"), ("Ani", "B-PER"))

    assert _texts(text, decode_bio(tokens, LABELS, text)) == [
        ("Budi", PiiType.NAMA),
        ("Ani", PiiType.NAMA),
    ]


def test_labels_not_mapped_such_as_cities_are_not_redacted() -> None:
    text = "Jl. Melati 5 Bekasi"
    tokens = _tokens(
        text, ("Jl.", "B-FAC"), ("Melati", "I-FAC"), ("5", "I-FAC"), ("Bekasi", "B-GPE")
    )

    assert _texts(text, decode_bio(tokens, LABELS, text)) == [("Jl. Melati 5", PiiType.ALAMAT)]


def test_a_space_counted_into_a_token_does_not_glue_words_together() -> None:
    text = "kak Dewi oke"
    # Byte-level tokenizers can report " Dewi" (with its space) as the token.
    tokens = [
        TokenPrediction("O", 0.9, 0, 3),
        TokenPrediction("B-PER", 0.9, 3, 8),
        TokenPrediction("O", 0.9, 8, 12),
    ]

    assert _texts(text, decode_bio(tokens, LABELS, text)) == [("Dewi", PiiType.NAMA)]


def test_trailing_comma_is_trimmed_and_special_tokens_ignored() -> None:
    text = "Dewi, 0812"
    tokens = [
        TokenPrediction("O", 1.0, 0, 0),
        TokenPrediction("B-PER", 0.9, 0, 4),
        TokenPrediction("I-PER", 0.9, 4, 5),
        TokenPrediction("O", 1.0, 6, 10),
    ]

    assert _texts(text, decode_bio(tokens, LABELS, text)) == [("Dewi", PiiType.NAMA)]


def test_predictions_take_each_tokens_most_likely_label() -> None:
    logits = np.array([[0.0, 5.0], [5.0, 0.0]], dtype=np.float32)

    tokens = predictions(logits, [(0, 4), (5, 8)], {0: "O", 1: "B-PER"})

    assert [token.label for token in tokens] == ["B-PER", "O"]
    assert tokens[0].score > 0.99
