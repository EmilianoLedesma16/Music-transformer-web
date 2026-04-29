import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SUPABASE_URL    = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY    = os.environ.get("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "bytebeat")

_client = None


def _get_client():
    global _client
    if _client is None:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def upload_file(local_path: str, storage_path: str,
                content_type: str = "application/octet-stream") -> str | None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase no configurado, omitiendo subida de %s", local_path)
        return None
    try:
        data = Path(local_path).read_bytes()
        _get_client().storage.from_(SUPABASE_BUCKET).upload(
            storage_path, data,
            {"content-type": content_type, "upsert": "true"},
        )
        return _get_client().storage.from_(SUPABASE_BUCKET).get_public_url(storage_path)
    except Exception as exc:
        logger.error("Error subiendo a Supabase (%s): %s", storage_path, exc)
        return None
