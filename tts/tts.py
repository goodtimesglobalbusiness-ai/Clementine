"""Text-to-speech entry point.

Delegates the actual synthesis to the active provider (see providers.py:
ElevenLabs or local Kokoro) and wraps it with disk caching and an optional
monthly character budget. Cache hits and non-metered (local) providers never
count against the budget.
"""
import hashlib
import io
from pathlib import Path

from tts import config, providers, usage

# Re-exported so callers can keep using tts.TTSError / tts.BudgetExceeded.
TTSError = providers.TTSError
BudgetExceeded = providers.BudgetExceeded

_CACHE_DIR = Path(__file__).parent / ".tts_cache"
# Only cache short strings — long messages are usually unique and would just
# churn the cache.
_CACHE_MAX_CHARS = 60


def _cache_path(token: str, text: str) -> Path:
    key = hashlib.sha256(f"{token}|{text}".encode("utf-8")).hexdigest()
    return _CACHE_DIR / f"{key}.mp3"


def synthesize(
    text: str,
    voice_id: str | None = None,
    provider: providers.Provider | None = None,
    guild_id: int | None = None,
) -> io.BytesIO:
    """Convert `text` to speech and return an in-memory audio stream.

    `provider` selects the backend (defaults to the global default); `guild_id`
    attributes metered usage to a server. Raises TTSError on failure, or
    BudgetExceeded when the monthly budget is reached. Cache hits never count.
    """
    if provider is None:
        provider = providers.active()

    cacheable = len(text) <= _CACHE_MAX_CHARS
    cache_path = _cache_path(provider.cache_token(voice_id), text) if cacheable else None
    if cache_path is not None and cache_path.exists():
        return io.BytesIO(cache_path.read_bytes())

    cap = config.MONTHLY_CHAR_BUDGET
    if provider.metered and cap and usage.get_total_usage() + len(text) > cap:
        raise BudgetExceeded(f"Monthly character budget of {cap} reached.")

    content = provider.synthesize_raw(text, voice_id)

    # Record per-guild usage for every synthesis; only metered (paid) usage
    # counts toward the global money budget.
    usage.add_usage(guild_id or 0, len(text), provider.metered)
    if cache_path is not None:
        try:
            _CACHE_DIR.mkdir(exist_ok=True)
            cache_path.write_bytes(content)
        except OSError:
            pass
    return io.BytesIO(content)
