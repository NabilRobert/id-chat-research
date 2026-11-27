"""Anonymising everything in a chat record that isn't turn text.

The recognisers only read turns, but a real export carries personal data
elsewhere too: a WhatsApp `chat_id` is the customer's number
("6281234567890@c.us"), `outcome` may hold a buyer's name or phone, and
timestamps date the chat. `Anonymiser.anonymise` uses these helpers so
its output record holds nothing the turns would not be allowed to.

- **chat_id** becomes a keyed pseudonym (HMAC-SHA256). The same id and key
  always give the same pseudonym, so a chat split across files still joins
  up; without the key it can't be reversed or recomputed from a guessed
  number. The key is never written.
- **outcome**: every key and string, and every integer (a number stored
  as an int is still a phone or NIK), is scanned with the same recognisers
  as the turns. Booleans, floats and null are kept. Two traps: a bare name
  with no cue word ("Budi Santoso") is found only by R1's NER model, as in
  a turn; and an integer of 10 or more digits reads as an account number,
  so a price stored as 1500000000 is redacted (store amounts as floats).
- **timestamps** keep the gaps between turns, which the responsiveness
  measure needs, and lose the date and time of day: the chat is moved to
  start at `TIMESTAMP_ANCHOR`.
"""

import hashlib
import hmac
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from id_chat_records import Turn
from pydantic import JsonValue

# 64 bits of the HMAC: collisions are negligible for the thousands of chats
# a study holds, and the id stays short enough to read.
PSEUDONYM_HEX_CHARACTERS = 16
PSEUDONYM_PREFIX = "chat-"
# Every anonymised chat starts here, so only the gaps between turns survive.
TIMESTAMP_ANCHOR = datetime(2000, 1, 1, tzinfo=UTC)


def pseudonymise_chat_id(chat_id: str, key: bytes) -> str:
    digest = hmac.new(key, chat_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return PSEUDONYM_PREFIX + digest[:PSEUDONYM_HEX_CHARACTERS]


def scrub_outcome(value: JsonValue, redact_text: Callable[[str], str]) -> JsonValue:
    """Run `redact_text` over every key, string and integer inside an outcome value."""
    if isinstance(value, dict):
        return {redact_text(key): scrub_outcome(item, redact_text) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_outcome(item, redact_text) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, int):
        redacted = redact_text(str(value))
        return value if redacted == str(value) else redacted
    return value


def _as_utc(moment: datetime) -> datetime:
    # A timestamp without a zone is read as UTC, so a chat that mixes the
    # two can still be shifted instead of failing on the subtraction.
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def shift_timestamps(turns: Sequence[Turn]) -> tuple[Turn, ...]:
    """Move a chat's timestamps to start at `TIMESTAMP_ANCHOR`, keeping their gaps."""
    moments = [_as_utc(turn.timestamp) for turn in turns if turn.timestamp is not None]
    if not moments:
        return tuple(turns)
    first = min(moments)
    shifted: list[Turn] = []
    for turn in turns:
        if turn.timestamp is None:
            shifted.append(turn)
            continue
        moved = TIMESTAMP_ANCHOR + (_as_utc(turn.timestamp) - first)
        shifted.append(turn.model_copy(update={"timestamp": moved}))
    return tuple(shifted)
