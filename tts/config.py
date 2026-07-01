"""Centralized configuration loaded from the environment / .env file."""
import os

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


DISCORD_TOKEN = _required("DISCORD_TOKEN")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID") or None
DEV_GUILD_IDS = [g.strip() for g in (os.getenv("DEV_GUILD_ID") or "").split(",") if g.strip()]

ELEVENLABS_API_KEY = _required("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "hJivz7bKuee9e4Vm8rsK")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5")

# Curated voices users pick from via /voice set. Each maps to a provider-specific
# voice: "voice_id" for ElevenLabs, "local" for the Kokoro local server.
# Holly is the default; 3 female + 3 male.
CURATED_VOICES = [
    {"name": "Holly", "gender": "female", "voice_id": "hJivz7bKuee9e4Vm8rsK", "local": "af_heart"},
    {"name": "Sarah", "gender": "female", "voice_id": "EXAVITQu4vr4xnSDxMaL", "local": "af_sarah"},
    {"name": "Charlotte", "gender": "female", "voice_id": "XB0fDUnXU5powFXDhCwa", "local": "bf_emma"},
    {"name": "Brian", "gender": "male", "voice_id": "nPczCjzI2devNBz1zQrb", "local": "am_michael"},
    {"name": "George", "gender": "male", "voice_id": "JBFqnCBsd6RMkjVDRZzb", "local": "bm_george"},
    {"name": "Liam", "gender": "male", "voice_id": "TX3LPaxmHKxFdv7VOQHJ", "local": "am_adam"},
]

# --- TTS provider ---
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "elevenlabs").lower()
TTS_LOCAL_URL = os.getenv("TTS_LOCAL_URL", "http://127.0.0.1:8080").rstrip("/")
LOCAL_TTS_DEFAULT_VOICE = os.getenv("LOCAL_TTS_DEFAULT_VOICE", "af_heart")
TTS_LOCAL_PROXY = os.getenv("TTS_LOCAL_PROXY") or None

MAX_TTS_CHARS = int(os.getenv("MAX_TTS_CHARS", "500"))
FFMPEG_PATH = os.getenv("FFMPEG_PATH") or "ffmpeg"

# Announcement phrases
LINK_PHRASE = os.getenv("LINK_PHRASE", "A link")
LINK_VOICE_ID = os.getenv("LINK_VOICE_ID") or None
GIF_PHRASE = os.getenv("GIF_PHRASE", "A gif")
GIF_VOICE_ID = os.getenv("GIF_VOICE_ID") or None
IMAGE_PHRASE = os.getenv("IMAGE_PHRASE", "An image")
VIDEO_PHRASE = os.getenv("VIDEO_PHRASE", "A video")
FILE_PHRASE = os.getenv("FILE_PHRASE", "A file")

MONTHLY_CHAR_BUDGET = int(os.getenv("MONTHLY_CHAR_BUDGET", "0"))


def _int_set(name: str) -> set[int]:
    raw = os.getenv(name, "")
    return {int(x) for x in raw.replace(",", " ").split() if x.strip()}


AUTOJOIN_VOICE_CHANNEL_IDS = _int_set("AUTOJOIN_VOICE_CHANNEL_IDS")
AUTOREAD_FALLBACK_CHANNEL_IDS = _int_set("AUTOREAD_FALLBACK_CHANNEL_IDS")

RATE_LIMIT_MESSAGES = int(os.getenv("RATE_LIMIT_MESSAGES", "5"))
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "10"))

# --- Premium tiering ---
PREMIUM_TTS_PROVIDER = os.getenv("PREMIUM_TTS_PROVIDER", "elevenlabs").lower()
PREMIUM_GUILD_IDS = _int_set("PREMIUM_GUILD_IDS")
PREMIUM_MONTHLY_CHAR_ALLOWANCE = int(os.getenv("PREMIUM_MONTHLY_CHAR_ALLOWANCE", "100000"))
FREE_MONTHLY_CHAR_ALLOWANCE = int(os.getenv("FREE_MONTHLY_CHAR_ALLOWANCE", "50000"))

# --- Stripe billing (premium subscriptions) ---
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY") or None
STRIPE_PRICE_MONTHLY = os.getenv("STRIPE_PRICE_MONTHLY") or None
STRIPE_PRICE_YEARLY = os.getenv("STRIPE_PRICE_YEARLY") or None
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET") or None
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://clementine.gg/")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://clementine.gg/")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8090"))
PREMIUM_BILLING_ENABLED = bool(
    STRIPE_API_KEY and (STRIPE_PRICE_MONTHLY or STRIPE_PRICE_YEARLY)
)
