"""SQLite persistence for conversations and messages (local file only)."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

from utils.text import DEFAULT_TITLE, now_iso

log = logging.getLogger(__name__)


@dataclass
class Conversation:
    id: int
    title: str
    created_at: str
    updated_at: str


@dataclass
class Message:
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: str
    context: str | None = None
    attachments: list[str] = field(default_factory=list)


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    context TEXT,
    attachments TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
"""


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class Database:
    def __init__(self, path: str | Path):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    # -- conversations -------------------------------------------------
    def create_conversation(self, title: str = DEFAULT_TITLE) -> Conversation:
        ts = now_iso()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO conversations(title, created_at, updated_at) VALUES (?,?,?)",
                (title, ts, ts),
            )
            self._conn.commit()
            return Conversation(cur.lastrowid, title, ts, ts)

    def get_conversation(self, conv_id: int) -> Conversation | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
        return Conversation(**dict(r)) if r else None

    def list_conversations(self, query: str | None = None) -> list[Conversation]:
        with self._lock:
            if query and query.strip():
                pat = _like(query.strip())
                rows = self._conn.execute(
                    "SELECT * FROM conversations c WHERE c.title LIKE ? ESCAPE '\\' "
                    "OR EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id=c.id "
                    "AND m.content LIKE ? ESCAPE '\\') "
                    "ORDER BY c.updated_at DESC, c.id DESC",
                    (pat, pat),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM conversations ORDER BY updated_at DESC, id DESC"
                ).fetchall()
        return [Conversation(**dict(r)) for r in rows]

    def rename_conversation(self, conv_id: int, title: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE conversations SET title=? WHERE id=?", (title, conv_id))
            self._conn.commit()

    def delete_conversation(self, conv_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
            self._conn.commit()

    def clear_all(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM messages")
            self._conn.execute("DELETE FROM conversations")
            self._conn.commit()

    # -- messages ------------------------------------------------------
    def add_message(
        self,
        conv_id: int,
        role: str,
        content: str,
        context: str | None = None,
        attachments: list[str] | None = None,
    ) -> Message:
        ts = now_iso()
        att = json.dumps(attachments) if attachments else None
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages(conversation_id, role, content, context, attachments, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (conv_id, role, content, context, att, ts),
            )
            self._conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (ts, conv_id))
            self._conn.commit()
            return Message(cur.lastrowid, conv_id, role, content, ts, context, attachments or [])

    def get_messages(self, conv_id: int) -> list[Message]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (conv_id,)
            ).fetchall()
        out = []
        for r in rows:
            try:
                att = json.loads(r["attachments"]) if r["attachments"] else []
            except ValueError:
                att = []
            out.append(
                Message(r["id"], r["conversation_id"], r["role"], r["content"],
                        r["created_at"], r["context"], att)
            )
        return out

    def delete_messages_from(self, conv_id: int, message_id: int) -> None:
        """Delete the given message and every later message in the conversation."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM messages WHERE conversation_id=? AND id>=?", (conv_id, message_id)
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
