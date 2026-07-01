"""Pluggable TTS backends.

Each provider turns text into raw audio bytes (MP3 or WAV — FFmpeg auto-detects
either). The caching/budget/usage logic lives in tts.py and wraps these.

Select the active backend with TTS_PROVIDER ("elevenlabs" | "local").
"""
import requests

from tts import config, premium, usage


class TTSError(RuntimeError):
    """Raised when a provider fails to synthesize."""


class BudgetExceeded(TTSError):
    """Raised by tts.synthesize when the monthly budget is reached."""


class Provider:
    # Whether calls cost money and should count against MONTHLY_CHAR_BUDGET.
    metered = False

    def cache_token(self, voice_id: str | None) -> str:
        """A short string identifying provider+voice, for cache key isolation."""
        raise NotImplementedError

    def synthesize_raw(self, text: str, voice_id: str | None) -> bytes:
        raise NotImplementedError


class ElevenLabsProvider(Provider):
    metered = True
    _API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"

    def _voice(self, voice_id: str | None) -> str:
        return voice_id or config.ELEVENLABS_VOICE_ID

    def cache_token(self, voice_id: str | None) -> str:
        return f"el:{self._voice(voice_id)}:{config.ELEVENLABS_MODEL}"

    def synthesize_raw(self, text: str, voice_id: str | None) -> bytes:
        voice = self._voice(voice_id)
        resp = requests.post(
            f"{self._API_BASE}/{voice}",
            json={
                "text": text,
                "model_id": config.ELEVENLABS_MODEL,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            headers={
                "xi-api-key": config.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise TTSError(f"ElevenLabs API error {resp.status_code}: {resp.text[:300]}")
        return resp.content


class LocalProvider(Provider):
    """Talks to the Kokoro HTTP server (see local_tts_server/)."""

    metered = False

    def _voice(self, voice_id: str | None) -> str:
        # Translate a curated ElevenLabs id to its Kokoro voice name.
        for v in config.CURATED_VOICES:
            if v["voice_id"] == voice_id:
                return v.get("local", config.LOCAL_TTS_DEFAULT_VOICE)
        return config.LOCAL_TTS_DEFAULT_VOICE

    def cache_token(self, voice_id: str | None) -> str:
        return f"local:{self._voice(voice_id)}"

    def synthesize_raw(self, text: str, voice_id: str | None) -> bytes:
        proxies = None
        if config.TTS_LOCAL_PROXY:
            proxies = {"http": config.TTS_LOCAL_PROXY, "https": config.TTS_LOCAL_PROXY}
        resp = requests.post(
            f"{config.TTS_LOCAL_URL}/tts",
            json={"text": text, "voice": self._voice(voice_id)},
            timeout=60,
            proxies=proxies,
        )
        if resp.status_code != 200:
            raise TTSError(f"Local TTS error {resp.status_code}: {resp.text[:300]}")
        return resp.content


_ELEVENLABS = ElevenLabsProvider()
_LOCAL = LocalProvider()
_REGISTRY = {"elevenlabs": _ELEVENLABS, "local": _LOCAL}


def get(name: str) -> Provider:
    return _REGISTRY.get(name, _ELEVENLABS)


def active() -> Provider:
    """The default provider (for guilds that aren't premium)."""
    return get(config.TTS_PROVIDER)


def for_guild(guild_id: int) -> Provider:
    """Premium guilds get ElevenLabs; everyone else gets the default.

    Premium = in the env allowlist (complimentary) or an active subscription.
    A premium guild that has used up its monthly character allowance falls back
    to the default (free/local) provider until the month resets.
    """
    if guild_id in config.PREMIUM_GUILD_IDS or premium.is_premium(guild_id):
        allowance = config.PREMIUM_MONTHLY_CHAR_ALLOWANCE
        if allowance and usage.get_guild_usage(guild_id) >= allowance:
            return get(config.TTS_PROVIDER)
        return get(config.PREMIUM_TTS_PROVIDER)
    return get(config.TTS_PROVIDER)
