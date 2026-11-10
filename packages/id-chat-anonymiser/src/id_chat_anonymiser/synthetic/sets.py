"""The named synthetic sets: which templates, which seed, how big.

Sizes come from the measurement plan (A): about 2,000 dev chats, and a
held-out set of at least 1,500 chats with at least 1,000 of each direct
identifier, so that zero misses bounds the miss rate below about 0.3%.
"""

from dataclasses import dataclass
from pathlib import Path

from id_chat_anonymiser.labels import LabelledChat
from id_chat_anonymiser.synthetic.templates import fingerprint, generate_set, load_templates

DEFAULT_TEMPLATES_DIR = Path("data/templates")
MIN_PER_DIRECT_TYPE = 1_000


@dataclass(frozen=True)
class SetSpec:
    name: str
    seed: int
    min_chats: int

    def templates_path(self, templates_dir: Path) -> Path:
        return templates_dir / f"{self.name}.yaml"


SETS = {
    "dev": SetSpec(name="dev", seed=1101, min_chats=2_000),
    "heldout": SetSpec(name="heldout", seed=2202, min_chats=1_500),
}


def build_set(spec: SetSpec, templates_dir: Path) -> list[LabelledChat]:
    templates = load_templates(spec.templates_path(templates_dir))
    return generate_set(templates, spec.name, spec.seed, spec.min_chats, MIN_PER_DIRECT_TYPE)


def templates_fingerprint(spec: SetSpec, templates_dir: Path) -> str:
    return fingerprint(spec.templates_path(templates_dir))
