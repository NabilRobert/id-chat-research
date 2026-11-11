"""The scorer's rules: what counts as a miss, a wrong type, over-redaction."""

from pathlib import Path

import pytest
from id_chat_anonymiser import name_address_patterns, runs
from id_chat_anonymiser.anonymiser import AnonymisedChat, Redaction
from id_chat_anonymiser.labels import GoldSpan, LabelledChat, NegativeKind, NegativeSpan, PiiType
from id_chat_anonymiser.runs import AlreadyScoredError, config_sha256, record_path, refuse_if_scored
from id_chat_anonymiser.scoring import is_missed, score_set, wilson_interval
from id_chat_records import ChatRecord, Source, Turn

TEXT = "hp 0812-3456-7890 harga Rp 25jt"
PHONE = (3, 17)
PRICE = (24, 31)


def _labelled() -> LabelledChat:
    turn = Turn.model_validate({"index": 0, "role": "customer", "text": TEXT})
    record = ChatRecord(chat_id="c", source=Source.SYNTHETIC, domain="vehicles", turns=(turn,))
    gold = GoldSpan(turn_index=0, start=PHONE[0], end=PHONE[1], pii_type=PiiType.TELEPON)
    price = NegativeSpan(turn_index=0, start=PRICE[0], end=PRICE[1], kind=NegativeKind.HARGA)
    return LabelledChat(record=record, template_id="t", gold=(gold,), negatives=(price,))


def _anonymised(*spans: tuple[int, int, PiiType]) -> AnonymisedChat:
    labelled = _labelled()
    redactions = tuple(
        Redaction(turn_index=0, start=start, end=end, pii_type=pii_type, placeholder="<X_1>")
        for start, end, pii_type in spans
    )
    return AnonymisedChat(record=labelled.record, redactions=redactions)


def test_a_fully_hidden_number_is_not_a_miss() -> None:
    assert not is_missed("0812-3456-7890", 0, set(range(14)), PiiType.TELEPON)


def test_three_visible_digits_make_a_miss() -> None:
    assert is_missed("0812-3456-7890", 0, set(range(11)), PiiType.TELEPON)


def test_a_visible_country_code_alone_is_tolerated() -> None:
    assert not is_missed("+62 812-3456", 0, set(range(3, 12)), PiiType.TELEPON)


def test_a_whole_visible_word_makes_a_miss() -> None:
    assert is_missed("Budi Santoso", 0, set(range(4)), PiiType.NAMA)


def test_a_partial_redaction_counts_as_a_miss_with_its_leaked_characters() -> None:
    partial = _anonymised((PHONE[0] + 5, PHONE[1], PiiType.TELEPON))

    result = score_set([_labelled()], [partial])

    phone = result.by_type[PiiType.TELEPON]
    assert (phone.missed, phone.leaked_characters) == (1, 4)


def test_a_hidden_value_under_another_type_is_a_wrong_type_not_a_miss() -> None:
    wrong = _anonymised((*PHONE, PiiType.REKENING))

    phone = score_set([_labelled()], [wrong]).by_type[PiiType.TELEPON]

    assert (phone.missed, phone.wrong_type) == (0, 1)


def test_redacting_a_price_counts_as_a_look_alike_hit_and_over_redaction() -> None:
    too_much = _anonymised((*PHONE, PiiType.TELEPON), (*PRICE, PiiType.REKENING))

    result = score_set([_labelled()], [too_much])

    assert result.negative_hits == {"HARGA": 1}
    assert result.redacted_outside_gold == PRICE[1] - PRICE[0]


def test_wilson_upper_bound_with_zero_misses_is_about_three_over_n() -> None:
    _, upper = wilson_interval(0, 1_000)

    assert upper == pytest.approx(0.0038, abs=0.0002)


def test_heldout_is_scored_only_once(tmp_path: Path) -> None:
    existing = record_path(tmp_path, "heldout", config_sha256())
    existing.write_text("{}", encoding="utf-8")

    with pytest.raises(AlreadyScoredError, match="already scored"):
        refuse_if_scored(tmp_path, "heldout")


def test_dev_may_be_scored_again(tmp_path: Path) -> None:
    record_path(tmp_path, "dev", config_sha256()).write_text("{}", encoding="utf-8")

    refuse_if_scored(tmp_path, "dev")


def test_precision_counts_redactions_off_gold_of_their_type() -> None:
    one_right_one_wrong = _anonymised((*PHONE, PiiType.TELEPON), (*PRICE, PiiType.TELEPON))

    precision = score_set([_labelled()], [one_right_one_wrong]).precision_by_type[PiiType.TELEPON]

    assert (precision.redactions, precision.on_gold_of_type) == (2, 1)
    assert precision.precision == 0.5


def test_heldout_scored_with_rules_alone_does_not_block_an_ner_run(tmp_path: Path) -> None:
    record_path(tmp_path, "heldout", config_sha256()).write_text("{}", encoding="utf-8")

    refuse_if_scored(tmp_path, "heldout", ner_model="nusabert")


def test_each_ner_model_has_its_own_config_hash_and_record_name(tmp_path: Path) -> None:
    nusabert = record_path(tmp_path, "dev", config_sha256("nusabert"), "nusabert")
    gliner = record_path(tmp_path, "dev", config_sha256("gliner"), "gliner")

    assert config_sha256("nusabert") != config_sha256("gliner") != config_sha256()
    assert "r1-nusabert" in nusabert.name
    assert nusabert != gliner


def test_editing_the_name_and_address_patterns_changes_the_config_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    edited = tmp_path / "name_address_patterns.py"
    edited.write_text("# an edited rule\n", encoding="utf-8")
    real_source_file = runs._source_file  # pyright: ignore[reportPrivateUsage]
    before = config_sha256()

    monkeypatch.setattr(
        runs,
        "_source_file",
        lambda module: edited if module is name_address_patterns else real_source_file(module),
    )

    assert config_sha256() != before
