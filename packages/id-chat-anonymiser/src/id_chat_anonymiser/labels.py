"""Labelled chats: a chat record plus where its personal data is.

The generator writes these, and the scorer compares the anonymiser's
redactions against them. A span is a character range inside one turn's
text. Gold spans are personal data that must be redacted; negative spans
are prices, products and the like that must not be (measurement plan, A).
"""

from enum import StrEnum

from id_chat_records import ChatRecord
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PiiType(StrEnum):
    """The kinds of personal data, named as their placeholders are (`<TELEPON_1>`)."""

    NAMA = "NAMA"
    TELEPON = "TELEPON"
    NIK = "NIK"
    ALAMAT = "ALAMAT"
    PLAT = "PLAT"
    EMAIL = "EMAIL"
    ID_PESANAN = "ID_PESANAN"
    REKENING = "REKENING"


# The types the zero-miss gate covers (G1). Names and addresses need the NER
# half (slice 3); order IDs are scored but carry no gate.
DIRECT_IDENTIFIERS = frozenset(
    {PiiType.TELEPON, PiiType.NIK, PiiType.EMAIL, PiiType.PLAT, PiiType.REKENING}
)


# The types the NER half (R1) finds; the patterns don't try them.
NER_TYPES = frozenset({PiiType.NAMA, PiiType.ALAMAT})


class NegativeKind(StrEnum):
    """Text that looks like data but must stay readable (the hard negatives)."""

    HARGA = "HARGA"
    PRODUK = "PRODUK"
    TANGGAL = "TANGGAL"
    KM = "KM"
    TAHUN = "TAHUN"
    PROMO = "PROMO"


class Span(BaseModel):
    """A character range [start, end) in one turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_index: int = Field(ge=0)
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def _end_is_after_start(self) -> "Span":
        if self.end <= self.start:
            raise ValueError(f"span end {self.end} must be after its start {self.start}")
        return self


class GoldSpan(Span):
    """Personal data the anonymiser must redact."""

    pii_type: PiiType


class NegativeSpan(Span):
    """Look-alike text the anonymiser must leave alone."""

    kind: NegativeKind


class LabelledChat(BaseModel):
    """A chat with its gold and negative spans, and the template it came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record: ChatRecord
    template_id: str
    gold: tuple[GoldSpan, ...]
    negatives: tuple[NegativeSpan, ...]
