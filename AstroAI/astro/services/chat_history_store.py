# astro/services/chat_history_store.py
import os
import uuid
from typing import List, Dict
from urllib.parse import quote_plus

from django.contrib.auth.models import User
from django.db import transaction

from langchain_postgres import PostgresChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import psycopg

from astro.models import ChatSession  # <-- the model from step 1


# --- env & DSN ---
DB_NAME = os.environ.get("DB_NAME")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USERNAME = os.environ.get("DB_USERNAME")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST", "localhost")

_missing = [
    k
    for k, v in {
        "DB_NAME": DB_NAME,
        "DB_USERNAME": DB_USERNAME,
        "DB_PASSWORD": DB_PASSWORD,
        "DB_HOST": DB_HOST,
        "DB_PORT": DB_PORT,
    }.items()
    if not v
]
if _missing:
    raise ValueError(
        f"Missing required DB environment variables: {', '.join(_missing)}"
    )

LC_PG_URL = (
    f"postgresql://{quote_plus(DB_USERNAME)}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

TABLE_NAME = "chat_history"
_SYNC_CONN = None


def _get_sync_connection():
    """Create (once) and return a module-level psycopg sync connection."""
    global _SYNC_CONN
    if _SYNC_CONN is None:
        _SYNC_CONN = psycopg.connect(LC_PG_URL)
        # Safe to call repeatedly
        PostgresChatMessageHistory.create_tables(_SYNC_CONN, TABLE_NAME)
    return _SYNC_CONN


def _get_or_create_uuid_session_id(user: User) -> str:
    """
    Ensure the user has a UUID session_id persisted.
    - If missing: create a new ChatSession with a UUID.
    - If somehow invalid/legacy: replace with a fresh UUID.
    Returns the session_id as a string.
    """
    with transaction.atomic():
        sess, _created = ChatSession.objects.select_for_update().get_or_create(
            user=user
        )

        # `session_id` is a UUIDField, but in case legacy data was a string,
        # validate/repair defensively.
        try:
            _ = uuid.UUID(str(sess.session_id))
        except (ValueError, TypeError):
            sess.session_id = uuid.uuid4()
            sess.save(update_fields=["session_id", "updated_at"])

        return str(sess.session_id)


def get_lc_history(user: User) -> PostgresChatMessageHistory:
    """
    Return a Postgres-backed LangChain chat history bound to this user's UUID session.
    NOTE: table_name and session_id are positional-only in langchain_postgres.
    """
    conn = _get_sync_connection()
    session_id = _get_or_create_uuid_session_id(user)

    return PostgresChatMessageHistory(
        TABLE_NAME,  # positional-only
        session_id,  # positional-only (must be a UUID string)
        sync_connection=conn,  # kwarg
    )


def _to_chat_turns(
    msgs: List[BaseMessage], max_items: int = 10
) -> List[Dict[str, str]]:
    """Convert LangChain messages → [{role, content}] (tail-limited)."""

    def _role(m: BaseMessage) -> str:
        if isinstance(m, HumanMessage):
            return "user"
        if isinstance(m, AIMessage):
            return "assistant"
        if isinstance(m, SystemMessage):
            return "system"
        return getattr(m, "type", "user")

    if not max_items or max_items <= 0:
        max_items = 20

    return [{"role": _role(m), "content": m.content} for m in msgs[-max_items:]]
