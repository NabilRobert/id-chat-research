"""Indonesian pattern recognisers: the rule-based half of the anonymiser (R0).

Each is a Presidio `PatternRecognizer` (ADR-003) for one placeholder type.
They were written against the dev templates and what Indonesian chats
commonly contain, never against held-out output.

Two choices favour privacy over tidiness:
- Structure checks (a NIK's region and birth date) only raise a match's
  score; a 16-digit number that fails them is still redacted.
- `long_number_recogniser` redacts any run of 10 to 16 digits the others
  missed, typed as an account number. Prices, dates and kilometre readings
  use dots or slashes, so they don't match it.

Presidio's own phone recogniser (libphonenumber) runs too, restricted to
Indonesia, because its default regions leave Indonesia out. Presidio's
email recogniser isn't used: its validation calls tldextract, which
fetches the public suffix list over the network on first use (N1).
"""

import re
from typing import cast

from presidio_analyzer import EntityRecognizer, Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts
from presidio_analyzer.predefined_recognizers import PhoneRecognizer

from id_chat_anonymiser.labels import PiiType
from id_chat_anonymiser.name_address_patterns import name_patterns, street_patterns
from id_chat_anonymiser.reference import (
    BANKS,
    NIK_PROVINCE_CODES,
    NIK_WOMAN_DAY_OFFSET,
    PLATE_REGIONS,
)

LANGUAGE = "id"
NIK_DIGITS = 16
MAX_DAY_OF_MONTH = 31
MONTHS_IN_YEAR = 12

# Longest region codes first, so "AB 1234 CD" isn't read as region "A".
_REGIONS = "|".join(sorted(PLATE_REGIONS, key=len, reverse=True))
_BANK_WORDS = "|".join([*BANKS, "rekening", "rek", "norek", "no rek"])
# Thousands in groups of three after a dot, not starting with 0: a price.
# Indonesian phone numbers start with 0, 62 or +62.
PRICE_SHAPED = re.compile(r"[1-9]\d{0,2}(?:\.\d{3})+")


def _pattern_recogniser(pii_type: PiiType, patterns: list[Pattern]) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=pii_type.value, supported_language=LANGUAGE, patterns=patterns
    )


class IndonesianPhoneRecogniser(PhoneRecognizer):
    """libphonenumber restricted to Indonesia, which never takes a price for a phone.

    It reads "1.500.000" as a short Indonesian number, so prices from
    Rp 1 to 2 million were redacted as phones.
    """

    def __init__(self) -> None:
        super().__init__(  # pyright: ignore[reportUnknownMemberType]  (untyped defaults)
            supported_language=LANGUAGE,
            supported_entity=PiiType.TELEPON.value,
            supported_regions=("ID",),
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        # Presidio types the argument as required but defaults it to None.
        results = super().analyze(text, entities, cast(NlpArtifacts, nlp_artifacts))
        return [
            result
            for result in results
            if not PRICE_SHAPED.fullmatch(text[result.start : result.end])
        ]


def phone_recognisers() -> list[EntityRecognizer]:
    mobile = Pattern(
        "mobile",
        r"(?<![\d+])(?:\+62|62|0)[ \-.]?\(?8\d{1,2}\)?(?:[ \-.]?\d{2,5}){2,3}(?!\d)",
        0.7,
    )
    landline = Pattern(
        "landline",
        r"(?<!\w)(?:\(0\d{1,3}\)[ \-.]?|0\d{1,3}[ \-])\d{3,4}[ \-.]?\d{3,4}(?!\w)",
        0.6,
    )
    return [
        _pattern_recogniser(PiiType.TELEPON, [mobile, landline]),
        IndonesianPhoneRecogniser(),
    ]


class NikRecogniser(PatternRecognizer):
    """16 digits, plain or in groups of four; the structure check raises the score."""

    def __init__(self) -> None:
        nik = Pattern("nik", r"(?<!\d)\d{4}([ .\-]?)\d{4}\1\d{4}\1\d{4}(?!\d)", 0.6)
        super().__init__(
            supported_entity=PiiType.NIK.value, supported_language=LANGUAGE, patterns=[nik]
        )

    def validate_result(self, pattern_text: str) -> bool | None:
        """True for a NIK-shaped number; None (keep the match) otherwise."""
        digits = "".join(character for character in pattern_text if character.isdigit())
        if len(digits) != NIK_DIGITS or digits[:2] not in NIK_PROVINCE_CODES:
            return None
        day = int(digits[6:8])
        if day > NIK_WOMAN_DAY_OFFSET:
            day -= NIK_WOMAN_DAY_OFFSET
        month = int(digits[8:10])
        if 1 <= day <= MAX_DAY_OF_MONTH and 1 <= month <= MONTHS_IN_YEAR:
            return True
        return None


def email_recogniser() -> PatternRecognizer:
    email = Pattern("email", r"[\w.%+\-]+@[\w\-]+(?:\.[\w\-]+)*\.[a-z]{2,}", 0.9)
    # People often drop the ending: "budi99@gmail".
    no_ending = Pattern(
        "email without .com", r"[\w.%+\-]+@(?:gmail|yahoo|ymail|hotmail|outlook|icloud)\b", 0.7
    )
    return _pattern_recogniser(PiiType.EMAIL, [email, no_ending])


def plate_recogniser() -> PatternRecognizer:
    plate = Pattern("plate", rf"\b(?:{_REGIONS})[ \-]?\d{{1,4}}[ \-]?[A-Z]{{1,3}}\b", 0.6)
    # Some plates have no letters after the number; then a word like "plat" must come first.
    after_plate_word = Pattern(
        "after a plate word",
        rf"(?<=\b(?:plat|nopol|no\.? ?pol)\W{{0,3}})(?:{_REGIONS})[ \-]?\d{{1,4}}\b",
        0.6,
    )
    return _pattern_recogniser(PiiType.PLAT, [plate, after_plate_word])


def order_id_recogniser() -> PatternRecognizer:
    invoice = Pattern("invoice path", r"\bINV/(?:\w+/)+\d{3,}\b", 0.9)
    prefixed = Pattern("prefixed code", r"\b(?:INV|ORD|TRX|SO|PO)[\-/]?\d{5,}\b", 0.8)
    return _pattern_recogniser(PiiType.ID_PESANAN, [invoice, prefixed])


def account_recogniser() -> PatternRecognizer:
    number = r"\d(?:[ \-]?\d){9,15}"
    after_bank = Pattern(
        "after a bank word", rf"(?<=\b(?:{_BANK_WORDS})\b[^\d\n]{{0,20}}){number}(?!\d)", 0.8
    )
    before_bank = Pattern(
        "before a bank name", rf"(?<!\d){number}(?=\s*\(?(?:{'|'.join(BANKS)})\b)", 0.8
    )
    return _pattern_recogniser(PiiType.REKENING, [after_bank, before_bank])


def long_number_recogniser() -> PatternRecognizer:
    # Not after "Rp": a price in plain digits ("Rp1500000000") stays readable.
    long_number = Pattern(
        "long number", r"(?<![\d.,/])(?<!rp ?)\d(?:[ \-]?\d){9,15}(?![\d.,/])", 0.3
    )
    return _pattern_recogniser(PiiType.REKENING, [long_number])


def all_recognisers() -> list[EntityRecognizer]:
    return [
        *phone_recognisers(),
        NikRecogniser(),
        email_recogniser(),
        plate_recogniser(),
        order_id_recogniser(),
        account_recogniser(),
        long_number_recogniser(),
        _pattern_recogniser(PiiType.NAMA, name_patterns()),
        _pattern_recogniser(PiiType.ALAMAT, street_patterns()),
    ]
