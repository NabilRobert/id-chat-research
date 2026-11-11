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
    ("NAMA", "udah transfer, a.n [citra]"),
    ("NAMA", "Terdata a.n. [Panji Wahyuni]. Alamat untuk survei?"),
    ("NAMA", "atas nama [Zulaikha Adriansyah] ya"),
    ("NAMA", "nama saya [Budi Santoso]"),
    ("NAMA", "namanya: [luwes]"),
    ("NAMA", "saya [rahmi]"),
    ("NAMA", "ok saya [Irma Hassanah], nanti saya kabari"),
    ("NAMA", "saya sendiri [bala], nik 3201234512900001"),
    ("NAMA", "3201234512900001 ([Oman]) dan istri"),
    ("NAMA", "[rahmi] 73080444103477"),
    ("NAMA", "[Darijan Kuswandari], 7667090305348"),
    ("NAMA", "[balamantri]\n+62 896-5822-0123"),
    ("NAMA", "8120216704800325 ([Najwa Permata]) dan istri"),
    ("NAMA", "Salam kenal kak [Ulva]. Mau cash atau kredit?"),
    ("NAMA", "Pak [Budi Santoso] dan istri"),
    ("NAMA", "nama anak [Budi]"),
    ("ALAMAT", "kirim ke [Gg. Laswi No. 3] ya"),
    ("ALAMAT", "[Gang Gegerkalong Hilir No. 73 RT 01/RW 01]"),
    ("ALAMAT", "[Gang HOS. Cokroaminoto No. 1]"),
    ("ALAMAT", "[jl sudirman no 12 rt 3/rw 4]"),
]

# Cue words with no name after them: nothing may be redacted as a name.
NO_NAME = [
    "Baik. Nama anak dan NIK nya?",
    "Mandiri 51181024422",
    "transfer 1234567890",
    "kak barang yg datang salah, pesanan ORD-12345",
    "Halo kak Selamat pagi",
    "saya rasa harga cocok sekali kak",
    "saya rasa cocok",
]

# A cued name is redacted up to the name, not the chat words after it.
NAME_ENDS = [
    ("a.n citra ya kak", "citra"),
    ("namanya Budi dan istri", "Budi"),
    ("nama Gina, ktp 3201234512900001", "Gina"),
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
    "saya mau booking tipe 36/72",
    "nanti saya kabari",
    "Boleh nama pemilik dan NIK kak?",
    "Bisa kak, mohon nama, nomor hp dan alamat untuk unit diantar",
    "Siap kak, siapa namanya?",
    "rumahnya bisa atas nama berdua?",
    "harga Rp 1.500.000 (sudah termasuk pajak)",
    "dp 1.500.000 dulu",
    "lagi di jalan ke kantor 2 jam lagi",
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


@pytest.mark.parametrize(("sentence", "name"), NAME_ENDS)
def test_a_cued_name_stops_where_the_name_ends(
    anonymiser: Anonymiser, sentence: str, name: str
) -> None:
    redacted = [sentence[match.start : match.end] for match in anonymiser.find(sentence)]

    assert name in redacted
    assert all(not part.startswith(name + " ") for part in redacted)


@pytest.mark.parametrize("sentence", NO_NAME)
def test_cue_words_without_a_name_redact_no_name(anonymiser: Anonymiser, sentence: str) -> None:
    names = [match for match in anonymiser.find(sentence) if match.pii_type is PiiType.NAMA]

    assert names == []
