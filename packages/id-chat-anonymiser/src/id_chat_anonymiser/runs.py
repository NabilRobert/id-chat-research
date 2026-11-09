"""Run records: what was scored, with which anonymiser, on which set, once.

Each scoring run writes a JSON record naming the anonymiser version, a hash
of the recogniser code, and fingerprints of the templates and the generated
set, so every number in docs/results-anonymiser.md traces to a record.
A held-out set is scored once per anonymiser version and config: a second
run is refused, as in mcp-gateway's eval/score.py.
"""

import hashlib
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from id_chat_anonymiser import anonymiser, recognisers, reference
from id_chat_anonymiser.labels import LabelledChat
from id_chat_anonymiser.scoring import SetScore

SCORED_ONCE_SETS = frozenset({"heldout"})
MAX_EXAMPLES_PER_TYPE = 5
SHORT_HASH_LENGTH = 12


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anonymiser_version: str
    config_sha256: str
    set_name: str
    templates_sha256: str
    set_sha256: str
    created_at: datetime
    seconds: float
    score: SetScore


class AlreadyScoredError(RuntimeError):
    """A scored-once set already has a record for this anonymiser."""


def anonymiser_version() -> str:
    return version("id-chat-anonymiser")


def config_sha256() -> str:
    """A hash of the code that decides what is redacted."""
    digest = hashlib.sha256()
    for module in (recognisers, anonymiser, reference):
        if module.__file__ is None:
            raise RuntimeError(f"{module.__name__} has no source file to hash")
        digest.update(Path(module.__file__).read_bytes())
    return digest.hexdigest()


def set_sha256(chats: list[LabelledChat]) -> str:
    digest = hashlib.sha256()
    for chat in chats:
        digest.update(chat.model_dump_json().encode("utf-8"))
    return digest.hexdigest()


def record_path(results_dir: Path, set_name: str, config_hash: str) -> Path:
    short_hash = config_hash[:SHORT_HASH_LENGTH]
    return results_dir / f"{set_name}-v{anonymiser_version()}-{short_hash}.json"


def refuse_if_scored(results_dir: Path, set_name: str) -> None:
    path = record_path(results_dir, set_name, config_sha256())
    if set_name in SCORED_ONCE_SETS and path.exists():
        raise AlreadyScoredError(
            f"{set_name} was already scored for this anonymiser ({path}). "
            "Change the recognisers (a new config hash) or the version to score it again."
        )


def write_record(record: RunRecord, results_dir: Path) -> Path:
    for examples in record.score.missed_examples.values():
        del examples[MAX_EXAMPLES_PER_TYPE:]
    results_dir.mkdir(parents=True, exist_ok=True)
    path = record_path(results_dir, record.set_name, record.config_sha256)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def now() -> datetime:
    return datetime.now(UTC)
