"""The chat record: one conversation between a customer and an agent.

Every tool in this repo reads and writes this shape, and so do the
projects that feed it (AI Flight School's simulated chats, the thesis's
anonymised real chats). Phase 5, ADR-002 fixes the fields.

`source` is required and has no default. It is how code tells a real
customer's chat from a synthetic one, and so how the judge refuses to send
real text to a hosted model (threat model, R4). Records are stored one per
line in JSONL; `read_jsonl` and `write_jsonl` do that.
"""

from collections.abc import Iterable, Iterator
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

# Bumped only when a field changes meaning or a required field is added.
FORMAT_VERSION = "1"


class Source(StrEnum):
    """Where a chat came from. Only `real` chats hold real people's data."""

    SYNTHETIC = "synthetic"
    PUBLIC = "public"
    REAL = "real"


class Role(StrEnum):
    """Who wrote a turn."""

    CUSTOMER = "customer"
    AGENT = "agent"
    SYSTEM = "system"


class Turn(BaseModel):
    """One message in a chat."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0, description="Position in the chat, counting from 0")
    role: Role
    text: str = Field(min_length=1)
    timestamp: datetime | None = None


class ChatRecord(BaseModel):
    """One chat, with where it came from and, optionally, how it ended."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: Literal["1"] = FORMAT_VERSION
    chat_id: str = Field(min_length=1)
    source: Source
    domain: str = Field(min_length=1, description="For example vehicles, electronics, property")
    turns: tuple[Turn, ...] = Field(min_length=1)
    outcome: dict[str, JsonValue] | None = Field(
        default=None,
        description="Free key-value facts about how the chat ended, for the thesis's Stage 1",
    )

    @model_validator(mode="after")
    def _turns_are_numbered_in_order(self) -> Self:
        for expected_index, turn in enumerate(self.turns):
            if turn.index != expected_index:
                raise ValueError(
                    f"turn indexes must run 0, 1, 2, ... in order: position {expected_index} "
                    f"has index {turn.index}"
                )
        return self


def read_jsonl(path: Path) -> Iterator[ChatRecord]:
    """Yield the records in a JSONL file, naming the line of any invalid one."""
    with path.open(encoding="utf-8") as lines:
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                yield ChatRecord.model_validate_json(line)
            except ValueError as error:
                message = f"{path}:{line_number} is not a valid chat record: {error}"
                raise ValueError(message) from error


def write_jsonl(records: Iterable[ChatRecord], path: Path) -> int:
    """Write records one per line and return how many were written."""
    count = 0
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(record.model_dump_json(exclude_none=True) + "\n")
            count += 1
    return count
