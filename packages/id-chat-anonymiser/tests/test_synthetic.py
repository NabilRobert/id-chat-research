"""The synthetic set generator: exact labels, repeatable sets, a frozen held-out."""

from collections import Counter
from pathlib import Path

import pytest
from id_chat_anonymiser.labels import DIRECT_IDENTIFIERS, PiiType
from id_chat_anonymiser.synthetic.sets import SETS, build_set, templates_fingerprint
from id_chat_anonymiser.synthetic.templates import Template, fill_template, generate_set
from id_chat_anonymiser.synthetic.values import NIK_PROVINCE_CODES, ValueMaker
from id_chat_records import Source

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "data" / "templates"
# Pinned when the held-out templates were written, before any recogniser
# existed (measurement plan, A). Changing heldout.yaml fails this test on
# purpose: a miss on held-out becomes a dev template instead.
HELDOUT_TEMPLATES_SHA256 = "4f42e33c41d2de75434e7475b9d63c75cae370aaf3db1e0c2c0c8bd40af5a21c"


def _template(*texts: str) -> Template:
    turns = [{"customer" if index % 2 == 0 else "agent": text} for index, text in enumerate(texts)]
    return Template.model_validate({"id": "test", "domain": "vehicles", "turns": turns})


def test_heldout_templates_are_frozen() -> None:
    assert templates_fingerprint(SETS["heldout"], TEMPLATES_DIR) == HELDOUT_TEMPLATES_SHA256


def test_each_gold_span_covers_exactly_the_value_put_in_the_slot() -> None:
    template = _template("no saya {TELEPON} ya", "siap, NIK nya?", "{NIK}, a.n. {NAMA}")

    chat = fill_template(template, ValueMaker(seed=1), "chat-1")

    texts = [turn.text for turn in chat.record.turns]
    covered = {span.pii_type: texts[span.turn_index][span.start : span.end] for span in chat.gold}
    assert texts[0] == f"no saya {covered[PiiType.TELEPON]} ya"
    assert texts[2] == f"{covered[PiiType.NIK]}, a.n. {covered[PiiType.NAMA]}"


def test_a_repeated_slot_gets_the_same_value_and_a_numbered_slot_a_new_one() -> None:
    template = _template("{NAMA} dan {NAMA#2}", "halo {NAMA}")

    chat = fill_template(template, ValueMaker(seed=3), "chat-1")

    texts = [turn.text for turn in chat.record.turns]
    names = [texts[span.turn_index][span.start : span.end] for span in chat.gold]
    assert names[0] == names[2]
    assert names[0] != names[1]


def test_look_alikes_are_labelled_as_negatives_not_gold() -> None:
    chat = fill_template(_template("{PRODUK} harga {HARGA}"), ValueMaker(seed=1), "chat-1")

    assert chat.gold == ()
    assert [span.kind.value for span in chat.negatives] == ["PRODUK", "HARGA"]


def test_generated_chats_are_marked_synthetic() -> None:
    chat = fill_template(_template("{EMAIL}"), ValueMaker(seed=1), "chat-1")

    assert chat.record.source is Source.SYNTHETIC


def test_the_same_seed_gives_the_same_set() -> None:
    first = build_set(SETS["dev"], TEMPLATES_DIR)
    second = build_set(SETS["dev"], TEMPLATES_DIR)

    assert first == second


def test_the_heldout_set_has_enough_of_each_direct_identifier() -> None:
    chats = build_set(SETS["heldout"], TEMPLATES_DIR)

    counts = Counter(span.pii_type for chat in chats for span in chat.gold)
    assert len(chats) >= SETS["heldout"].min_chats
    assert all(counts[kind] >= 1_000 for kind in DIRECT_IDENTIFIERS), counts


def test_templates_that_never_use_a_direct_identifier_are_refused() -> None:
    with pytest.raises(ValueError, match="rarely or never use"):
        generate_set([_template("{TELEPON}")], "test", seed=1, min_chats=5, min_per_direct_type=1)


def test_a_generated_nik_has_a_province_code_and_a_valid_birth_date() -> None:
    values = ValueMaker(seed=5)

    for _ in range(200):
        nik = values.nik().replace(" ", "")
        day, month = int(nik[6:8]), int(nik[8:10])
        assert len(nik) == 16
        assert nik[:2] in NIK_PROVINCE_CODES
        assert 1 <= day <= 31 or 41 <= day <= 71
        assert 1 <= month <= 12
