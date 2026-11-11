"""The three NER candidates (ADR-004), pinned, and fetching them.

Each model is pinned to a Hugging Face commit, and each weight and
tokenizer file to its SHA-256 (threat model, S1). Small config files are
pinned by the commit alone: the cache names each snapshot folder after its
commit, and that name is checked. GLiNER also reads its backbone's
tokenizer and config by repo name and branch, so that repo is a pinned
support download, checked the same way. Weights live in the Hugging Face cache, never
in the repo. `fetch_model` is the only function that touches the network;
`find_model` loads from the cache and checks the hashes again, so a model
swapped on disk fails closed.

Each model's labels map to this project's placeholder types. Labels left
out are never redacted: cities and provinces (GPE, LOCATION) stay, as the
measurement plan says, and so do dates, organisations and products.
"""

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from id_chat_anonymiser.labels import PiiType

HASH_CHUNK_BYTES = 1 << 20


class Runtime(StrEnum):
    TORCH = "torch"
    ONNX = "onnx"
    GLINER = "gliner"


@dataclass(frozen=True)
class RepoPin:
    """Files of one Hugging Face repo at one commit."""

    repo: str
    commit: str
    # Path in the repo -> SHA-256, or None for small files pinned by the commit alone.
    files: Mapping[str, str | None]
    # Set when a library looks the repo up by branch; the branch must resolve to `commit`.
    branch: str | None = None


@dataclass(frozen=True)
class ModelSpec:
    key: str
    pin: RepoPin
    runtime: Runtime
    weights: str
    labels: Mapping[str, PiiType]
    support: tuple[RepoPin, ...] = ()


NUSABERT = ModelSpec(
    key="nusabert",
    pin=RepoPin(
        repo="cahya/NusaBert-ner-v1.3",
        commit="befa8724547d50be5fdeed7670a0f28e2a934ea9",
        files={
            "config.json": "c1e01cee4475e12d276b887cb29041f54a9201d3e9c112cc5c7d8bd793d72632",
            "model.safetensors": "60cab610f37b5f22886b4d92115969fd27d9efa9ed6b4a3ae0c1dd95af4dab97",
            "tokenizer.json": "0e05898c4dee0acac91f6fa16044850964cbd5ea9e2ac01417d12f350f8c41a7",
        },
    ),
    runtime=Runtime.TORCH,
    weights="model.safetensors",
    # FAC covers roads and buildings; GPE (cities, provinces) is left out on purpose.
    labels={"PER": PiiType.NAMA, "FAC": PiiType.ALAMAT, "LOC": PiiType.ALAMAT},
)

HORIZON = ModelSpec(
    key="horizon",
    pin=RepoPin(
        repo="Horizon-Labs/pii-redactor-base",
        commit="ef0eff8e63c1711ec0c997c5ca9ea3b78a068684",
        files={
            "config.json": None,
            "onnx/model_quantized.onnx": (
                "ceaeb170adb26d595d9061fe6be8a63239dd5bbffd23bb135ebd308ea8ceac35"
            ),
            "tokenizer.json": "ac6fc8196d1db9ef82e68f6088e8d77d711b8c6f07589cec7d9d59c4adfc9a1e",
        },
    ),
    runtime=Runtime.ONNX,
    # The int8 export: half the size, 99.86% token agreement per its own check.
    weights="onnx/model_quantized.onnx",
    labels={"PERSON": PiiType.NAMA, "STREET_ADDRESS": PiiType.ALAMAT},
)

GLINER = ModelSpec(
    key="gliner",
    pin=RepoPin(
        repo="urchade/gliner_multi-v2.1",
        commit="443d26d654e0324125a96bebd8e796c14ff2efe6",
        files={
            "gliner_config.json": None,
            "model.safetensors": "2100142f31627531497850659dcb3821c99d5e71c08a8e01a98e4b11ef32a199",
        },
    ),
    runtime=Runtime.GLINER,
    weights="model.safetensors",
    # GLiNER is zero-shot: these are the prompts it is asked to find.
    labels={"person": PiiType.NAMA, "street address": PiiType.ALAMAT},
    # gliner loads the backbone's tokenizer and config (not its weights) by name and branch.
    support=(
        RepoPin(
            repo="microsoft/mdeberta-v3-base",
            commit="a0484667b22365f84929a935b5e50a51f71f159d",
            files={
                "config.json": None,
                "tokenizer_config.json": None,
                "spm.model": "13c8d666d62a7bc4ac8f040aab68e942c861f93303156cc28f5c7e885d86d6e3",
            },
            branch="main",
        ),
    ),
)

MODELS: dict[str, ModelSpec] = {spec.key: spec for spec in (NUSABERT, HORIZON, GLINER)}


class ModelNotFetchedError(RuntimeError):
    """The model's files are not in the local cache."""


class ModelHashError(RuntimeError):
    """A model file's SHA-256 differs from its pin."""


def model_spec(key: str) -> ModelSpec:
    if key not in MODELS:
        raise KeyError(f"unknown NER model {key!r}: use one of {sorted(MODELS)}")
    return MODELS[key]


def fetch_model(spec: ModelSpec) -> Path:
    """Download the pinned files (once; later calls reuse the cache) and check them."""
    for pin in spec.support:
        _check_pin(pin, _download(pin, local_files_only=False), spec.key)
    return _check_pin(spec.pin, _download(spec.pin, local_files_only=False), spec.key)


def find_model(spec: ModelSpec) -> Path:
    """The cached, checked model folder. Never downloads."""
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        for pin in spec.support:
            _check_pin(pin, _download(pin, local_files_only=True), spec.key)
        return _check_pin(spec.pin, _download(spec.pin, local_files_only=True), spec.key)
    except LocalEntryNotFoundError as error:
        raise ModelNotFetchedError(
            f"{spec.key} is not downloaded: {_fetch_hint(spec.key)}"
        ) from error


def _download(pin: RepoPin, *, local_files_only: bool) -> Path:
    # Imported late: only R1 needs huggingface_hub. Its overloads are partly untyped.
    import huggingface_hub

    download = huggingface_hub.snapshot_download  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    folder = cast(Callable[..., str], download)(
        pin.repo,
        revision=pin.branch or pin.commit,
        allow_patterns=list(pin.files),
        local_files_only=local_files_only,
    )
    return Path(folder)


def _check_pin(pin: RepoPin, folder: Path, model_key: str) -> Path:
    if folder.name != pin.commit:
        raise ModelHashError(
            f"{model_key}: {pin.repo} resolved to commit {folder.name}, not the pinned "
            f"{pin.commit}. Upstream moved; review the change before updating the pin."
        )
    verify_files(pin, folder, model_key)
    return folder


def verify_files(pin: RepoPin, folder: Path, model_key: str) -> None:
    for name, expected in pin.files.items():
        path = folder / name
        if not path.is_file():
            raise ModelNotFetchedError(
                f"{model_key} is missing {pin.repo}/{name}: {_fetch_hint(model_key)}"
            )
        if expected is not None and file_sha256(path) != expected:
            raise ModelHashError(
                f"{model_key}: {pin.repo}/{name} does not match its pinned SHA-256. Delete it "
                "from the Hugging Face cache and fetch it again; if it still differs, the "
                "upstream file changed and the pin needs review."
            )


def _fetch_hint(model_key: str) -> str:
    return f"run `uv run id-chat fetch-models --model {model_key}`"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
