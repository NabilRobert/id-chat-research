"""What the rule-based recognisers redact, and what they must leave alone.

Each case is a sentence as someone might type it in a chat. The value
between the brackets must be fully hidden, under that type.
"""

import pytest
from id_chat_anonymiser.anonymiser import Anonymiser
from id_chat_anonymiser.labels import PiiType

REDACTED = [
    ("TELEPON", "wa aja ke [081234567890] kak"),
    ("TELEPON", "no hp [0812-3456-7890]"),
    ("TELEPON", "no hp [0812 3456 7890]"),
    ("TELEPON", "no hp [0812.3456.789]"),
    ("TELEPON", "hubungi [+62 812-3456-7890]"),
    ("TELEPON", "hubungi [+6281234567890]"),
    ("TELEPON", "hubungi [6281234567890]"),
    ("TELEPON", "hubungi [+62-812-3456-7890]"),
    ("TELEPON", "kantor [(021) 555-1234]"),
    ("TELEPON", "kantor [021-5551234]"),
    ("TELEPON", "hp[081234567890]kak"),
    ("NIK", "nik [3201234512900001]"),
    ("NIK", "ktp [3201 2345 1290 0001]"),
    ("NIK", "ktp [3201.2345.1290.0001]"),
    ("EMAIL", "email [budi.santoso99@gmail.com] ya"),
    ("EMAIL", "kirim ke [dewi_lestari@yahoo.co.id]"),
    ("EMAIL", "email [budi99@gmail] aja"),
    ("PLAT", "plat [B 1234 XYZ]"),
    ("PLAT", "plat [B1234XYZ]"),
    ("PLAT", "plat [b 1234 xyz]"),
    ("PLAT", "plat [AB-12-CD]"),
    ("PLAT", "plat [B 1234] dinas"),
    ("ID_PESANAN", "pesanan [INV/20261105/MPL/123456789]"),
    ("ID_PESANAN", "order [ORD-88231]"),
    ("ID_PESANAN", "invoice [INV/2026/11/000123]"),
    ("ID_PESANAN", "no [TRX202611050001]"),
    ("REKENING", "transfer ke BCA [1234567890]"),
    ("REKENING", "rek mandiri [123-00-1234567-8]"),
    ("REKENING", "dari [123456789012] (BRI)"),
    ("REKENING", "imei [356938035643809]"),
]

LEFT_ALONE = [
    "harga Rp 25.500.000 nett",
    "Rp25.500.000 aja kak",
    "dp 25jt, cicilan 1,5 jt",
    "Rp1500000000 untuk tipe 45/90",
    "Vario 160 dan CBR 250 RR ready",
    "AC 1 PK, TV LED 43 inch, Galaxy A55",
    "km 45.231 km, tahun 2021",
    "tgl 05/11/2026 jam 10.30",
    "2026-11-05 jam 14.00",
    "pakai kode HEMAT50 atau NOV11",
    "rumah tipe 36/72 di cluster Anggrek",
]


def _case(sentence: str) -> tuple[str, int, int]:
    start = sentence.index("[")
    end = sentence.index("]") - 1
    return sentence.replace("[", "").replace("]", ""), start, end


@pytest.fixture(scope="module")
def anonymiser() -> Anonymiser:
    return Anonymiser()


@pytest.mark.parametrize(("pii_type", "sentence"), REDACTED)
def test_the_value_is_fully_redacted_as_its_type(
    anonymiser: Anonymiser, pii_type: str, sentence: str
) -> None:
    text, start, end = _case(sentence)

    covering = [
        match for match in anonymiser.find(text) if match.start <= start and match.end >= end
    ]

    assert covering, f"{text[start:end]!r} not fully redacted in {text!r}"
    assert covering[0].pii_type is PiiType(pii_type)


@pytest.mark.parametrize("sentence", LEFT_ALONE)
def test_look_alikes_are_left_readable(anonymiser: Anonymiser, sentence: str) -> None:
    redacted = [sentence[match.start : match.end] for match in anonymiser.find(sentence)]

    assert redacted == []
