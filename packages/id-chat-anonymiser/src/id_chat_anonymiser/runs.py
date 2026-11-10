"""Run records: what was scored, with which anonymiser, on which set, once.

Each scoring run writes a JSON record naming the anonymiser version, a hash
of the recogniser code, and fingerprints of the templates and the generated
set, so every number in docs/results-anonymiser.md traces to a record.
A held-out set is scored once per anonymiser version and config: a second
run is refused, as in mcp-gateway's eval/score.py.

R0 is the patterns alone; R1 adds an NER model, whose code and pins
(ner/) join the config hash and whose key joins the file name.
"""

import hashlib
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from types import ModuleType

from pydantic import BaseModel, ConfigDict

from id_chat_anonymiser import anonymiser, ner, recognisers, reference
from id_chat_anonymiser.labels import LabelledChat
from id_chat_anonymiser.scoring import SetScore

SCORED_ONCE_SETS = frozenset({"heldout"})
# Enough misses per type to see their patterns; every value is synthetic.
MAX_EXAMPLES_PER_TYPE = 50
SHORT_HASH_LENGTH = 12


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anonymiser_version: str
    config_sha256: str
    # None for R0 (patterns only); the NER model's key for R1.
    ner_model: str | None = None
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


def _source_file(module: ModuleType) -> Path:
    if module.__file__ is None:
        raise RuntimeError(f"{module.__name__} has no source file to hash")
    return Path(module.__file__)


def config_sha256(ner_model: str | None = None) -> str:
    """A hash of the code (and, for R1, the model pins) that decides what is redacted."""
    paths = [_source_file(module) for module in (recognisers, anonymiser, reference)]
    if ner_model is not None:
        paths.extend(sorted(_source_file(ner).parent.glob("*.py")))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    if ner_model is not None:
        digest.update(ner_model.encode("utf-8"))
    return digest.hexdigest()


def set_sha256(chats: list[LabelledChat]) -> str:
    digest = hashlib.sha256()
    for chat in chats:
        digest.update(chat.model_dump_json().encode("utf-8"))
    return digest.hexdigest()


def record_path(
    results_dir: Path, set_name: str, config_hash: str, ner_model: str | None = None
) -> Path:
    short_hash = config_hash[:SHORT_HASH_LENGTH]
    config_name = "r0" if ner_model is None else f"r1-{ner_model}"
    return results_dir / f"{set_name}-v{anonymiser_version()}-{config_name}-{short_hash}.json"


def refuse_if_scored(results_dir: Path, set_name: str, ner_model: str | None = None) -> None:
    path = record_path(results_dir, set_name, config_sha256(ner_model), ner_model)
    if set_name in SCORED_ONCE_SETS and path.exists():
        raise AlreadyScoredError(
            f"{set_name} was already scored for this anonymiser ({path}). "
            "Change the recognisers (a new config hash) or the version to score it again."
        )


def write_record(record: RunRecord, results_dir: Path) -> Path:
    for examples in record.score.missed_examples.values():
        del examples[MAX_EXAMPLES_PER_TYPE:]
    results_dir.mkdir(parents=True, exist_ok=True)
    path = record_path(results_dir, record.set_name, record.config_sha256, record.ner_model)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def now() -> datetime:
    return datetime.now(UTC)
