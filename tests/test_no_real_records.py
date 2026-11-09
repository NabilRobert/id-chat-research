"""No chat record in the repo may be marked real (threat model, R3).

Real chats live only in an encrypted volume outside the workspace; this
catches one copied in by mistake, or a synthetic file mislabelled.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKIPPED_FOLDERS = {".venv", ".git", "node_modules"}


def _jsonl_files_in_repo() -> list[Path]:
    return [
        path
        for path in REPO_ROOT.rglob("*.jsonl")
        if not SKIPPED_FOLDERS.intersection(path.relative_to(REPO_ROOT).parts)
    ]


def _lines_marked_real(path: Path) -> list[int]:
    marked: list[int] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        if json.loads(line).get("source") == "real":
            marked.append(line_number)
    return marked


def test_no_record_in_the_repo_is_marked_real() -> None:
    offending = {
        str(path.relative_to(REPO_ROOT)): lines
        for path in _jsonl_files_in_repo()
        if (lines := _lines_marked_real(path))
    }

    assert offending == {}, f"records marked source=real must not be in the repo: {offending}"
