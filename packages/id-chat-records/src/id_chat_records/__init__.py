"""The chat record format shared by id-chat-research and the projects that feed it."""

from id_chat_records.record import (
    FORMAT_VERSION,
    ChatRecord,
    Role,
    Source,
    Turn,
    read_jsonl,
    write_jsonl,
)

__all__ = ["FORMAT_VERSION", "ChatRecord", "Role", "Source", "Turn", "read_jsonl", "write_jsonl"]
