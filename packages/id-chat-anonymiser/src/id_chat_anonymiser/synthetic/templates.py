"""Chat templates and the set generator.

A template is a short chat whose messages have slots: `{TELEPON}` for
personal data, `{HARGA}` for a look-alike that must stay, `{BANK}` for a
plain filler. The generator fills the slots with random values and records
exactly where each value landed, so the labels are exact by construction
(ADR-012). Within one chat, the same personal slot (`{NAMA}`, or `{NAMA#2}`
for a second person) always gets the same value.

Dev and held-out sets come from separate template files. The held-out file
was written and fingerprinted before any recogniser existed
(measurement plan, A).
"""

import hashlib
import random
import re
from collections import Counter
from pathlib import Path

import yaml
from id_chat_records import ChatRecord, Role, Source, Turn
from pydantic import BaseModel, ConfigDict, Field

from id_chat_anonymiser.labels import (
    DIRECT_IDENTIFIERS,
    GoldSpan,
    LabelledChat,
    NegativeKind,
    NegativeSpan,
    PiiType,
)
from id_chat_anonymiser.synthetic.values import ValueMaker

SLOT = re.compile(r"\{(?P<name>[A-Z_]+)(?:#(?P<number>\d))?\}")
PLAIN_FILLERS = {"BANK"}
# Stops a template file that lacks a type from looping forever.
MAX_CHATS_PER_REQUESTED_CHAT = 10


class Template(BaseModel):
    """One chat with slots. Each turn is a one-key mapping: role to text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    domain: str
    turns: tuple[dict[Role, str], ...] = Field(min_length=1)


def load_templates(path: Path) -> list[Template]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Template.model_validate(entry) for entry in raw]


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _ChatFiller:
    """Fills one template, remembering personal values so repeats match."""

    def __init__(self, values: ValueMaker, domain: str) -> None:
        self.values = values
        self.domain = domain
        self.pii_values: dict[tuple[PiiType, str], str] = {}
        self.gold: list[GoldSpan] = []
        self.negatives: list[NegativeSpan] = []

    def fill_turn(self, turn_index: int, text_with_slots: str) -> str:
        parts: list[str] = []
        position = 0
        for match in SLOT.finditer(text_with_slots):
            parts.append(text_with_slots[position : match.start()])
            start = sum(len(part) for part in parts)
            value = self._value_for(match, turn_index, start)
            parts.append(value)
            position = match.end()
        parts.append(text_with_slots[position:])
        return "".join(parts)

    def _value_for(self, match: re.Match[str], turn_index: int, start: int) -> str:
        name = match.group("name")
        if name in PLAIN_FILLERS:
            return self.values.bank()
        if name in NegativeKind.__members__:
            value = self.values.negative(NegativeKind(name), self.domain)
            span = NegativeSpan(
                turn_index=turn_index, start=start, end=start + len(value), kind=NegativeKind(name)
            )
            self.negatives.append(span)
            return value
        pii_type = PiiType(name)
        key = (pii_type, match.group("number") or "1")
        if key not in self.pii_values:
            self.pii_values[key] = self.values.pii(pii_type)
        value = self.pii_values[key]
        span = GoldSpan(
            turn_index=turn_index, start=start, end=start + len(value), pii_type=pii_type
        )
        self.gold.append(span)
        return value


def fill_template(template: Template, values: ValueMaker, chat_id: str) -> LabelledChat:
    filler = _ChatFiller(values, template.domain)
    turns: list[Turn] = []
    for turn_index, turn in enumerate(template.turns):
        ((role, text_with_slots),) = turn.items()
        turns.append(
            Turn(index=turn_index, role=role, text=filler.fill_turn(turn_index, text_with_slots))
        )
    record = ChatRecord(
        chat_id=chat_id, source=Source.SYNTHETIC, domain=template.domain, turns=tuple(turns)
    )
    return LabelledChat(
        record=record,
        template_id=template.id,
        gold=tuple(filler.gold),
        negatives=tuple(filler.negatives),
    )


def generate_set(
    templates: list[Template], set_name: str, seed: int, min_chats: int, min_per_direct_type: int
) -> list[LabelledChat]:
    """Fill random templates until there are enough chats and enough of each direct identifier."""
    chooser = random.Random(seed)
    values = ValueMaker(seed)
    chats: list[LabelledChat] = []
    counts: Counter[PiiType] = Counter()
    while len(chats) < min_chats or any(
        counts[kind] < min_per_direct_type for kind in DIRECT_IDENTIFIERS
    ):
        if len(chats) >= min_chats * MAX_CHATS_PER_REQUESTED_CHAT:
            short = sorted(
                kind for kind in DIRECT_IDENTIFIERS if counts[kind] < min_per_direct_type
            )
            raise ValueError(f"the templates rarely or never use {short}: add slots for them")
        chat = fill_template(chooser.choice(templates), values, f"{set_name}-{len(chats):05d}")
        counts.update(span.pii_type for span in chat.gold)
        chats.append(chat)
    return chats
