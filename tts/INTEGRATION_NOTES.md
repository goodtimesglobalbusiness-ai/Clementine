# TTS Integration into Clementine

## Overview

This document describes the migration of the discord-tts-bot functionality into Clementine as a modular TTS subsystem.

## Architecture

### Module Structure

```
Clementine/
├── tts/
│   ├── __init__.py
│   ├── config.py         # TTS-specific config (merged from discord-tts-bot)
│   ├── billing.py        # Stripe integration (unified with Clementine billing)
│   ├── providers.py      # ElevenLabs + Kokoro backends
│   ├── tts.py            # Synthesis entry point + caching
│   └── cogs/
│       └── voice.py      # Voice cog: /say, /voice, /autoread, /pronounce, /usage
│
├── cogs/
│   ├── admin.py          # Clementine admin commands (existing)
│   ├── premium.py        # Unified premium/billing cog (merged)
│   └── ... (other Clementine cogs)
│
├── bot.py                # Main bot entrypoint (loads all cogs)
├── config.py             # Clementine global config
├── PRICING.md            # Unified pricing documentation
└── requirements.txt      # Python dependencies
```

### Key Design Decisions

1. **Separate TTS module** — Keeps voice/TTS concerns isolated from admin features
2. **Unified billing** — Single `/premium` cog handles both admin + TTS subscription
3. **Shared config** — TTS config merged with Clementine's env/dotenv system
4. **Watchdog integration** — Clementine's existing watchdog monitors TTS reliability

## Configuration

### New Environment Variables

Add these to `.env` alongside existing Clementine vars:

```bash
# TTS providers
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_VOICE_ID=hJivz7bKuee9e4Vm8rsK
ELEVENLABS_MODEL=eleven_turbo_v2_5

# Local Kokoro TTS (optional)
TTS_PROVIDER=elevenlabs              # or "local" for Kokoro
TTS_LOCAL_URL=http://127.0.0.1:8080  # Kokoro server URL
TTS_LOCAL_PROXY=                      # optional Tailscale proxy

# TTS limits
MAX_TTS_CHARS=500
RATE_LIMIT_MESSAGES=5
RATE_LIMIT_SECONDS=10
MONTHLY_CHAR_BUDGET=0                # 0 = unlimited

# Premium tiers
PREMIUM_TTS_PROVIDER=elevenlabs
PREMIUM_MONTHLY_CHAR_ALLOWANCE=100000
FREE_MONTHLY_CHAR_ALLOWANCE=50000

# Billing (shared with admin features)
STRIPE_API_KEY=sk_...
STRIPE_PRICE_MONTHLY=price_...
STRIPE_PRICE_YEARLY=price_...
STRIPE_WEBHOOK_SECRET=whsec_...
WEBHOOK_PORT=8090
```

## Integration Points

### 1. Bot Initialization

**bot.py** loads TTS cog during `setup_hook()`:

```python
async def setup_hook(self):
    # Load TTS voice cog
    await self.load_extension("tts.cogs.voice")
    # Load unified premium/billing cog
    await self.load_extension("cogs.premium")  # handles both admin + TTS
    # ... other cogs
```

### 2. Premium/Billing Unification

**cogs/premium.py** now handles:
- `/premium subscribe` — upgrades server to Pro (both admin + TTS)
- `/premium manage` — opens Stripe portal
- `/premium status` — shows both admin + TTS feature status
- Webhook events from Stripe → entitlement store

### 3. Voice Cog Dependencies

The TTS voice cog requires:
- `config` — TTS + global config
- `providers.py` — TTS backend selection
- `tts.py` — synthesis function
- `premium.py` — check if guild is premium
- `usage.py` — track per-guild usage
- `settings.py` — store per-user voice prefs
- `moderation.py` — content filtering

These are either merged into Clementine or imported as-is from discord-tts-bot.

## Migration Checklist

- [ ] Copy `tts/` module files to Clementine
- [ ] Copy TTS-related files: `settings.py`, `usage.py`, `moderation.py`, `premium.py`
- [ ] Update `requirements.txt` with TTS deps (elevenlabs, requests, discord.py[voice])
- [ ] Merge TTS config into `.env.example`
- [ ] Update `bot.py` to load TTS cog
- [ ] Test `/say`, `/voice`, `/autoread` commands
- [ ] Test `/premium subscribe` flow with Stripe
- [ ] Verify watchdog monitors TTS without issues
- [ ] Update README with TTS features

## Pricing Integration

See **PRICING.md** for the unified pricing model:

- **Free:** Local Kokoro TTS + basic admin
- **Pro ($9.99/mo):** ElevenLabs TTS + premium admin
- **Enterprise:** Custom SLA + dedicated instance

Billing is **per guild** (one subscription per server), shared between admin + TTS features.

## Uptime & Reliability

Clementine's watchdog system (**watchdog.ps1**, Windows Service) ensures:

1. **Bot heartbeat** — detects zombie connections
2. **Auto-restart** — exits & relaunches on gateway silence
3. **Log rotation** — prevents disk bloat
4. **PID tracking** — prevents duplicate processes

TTS inherits this infrastructure — no additional monitoring needed.

## Testing

### Unit Tests (Recommended)

```bash
python -m pytest tests/tts/ -v
```

### Manual Testing

1. **Local Kokoro:**
   ```bash
   /say hello world  # Should speak via Kokoro (free)
   ```

2. **ElevenLabs (Pro):**
   - Enable STRIPE_API_KEY + upgrade guild
   - `/say hello world` should speak via ElevenLabs

3. **Auto-read:**
   - `/autoread on` in target channel
   - Post messages — bot should read them aloud

4. **Billing:**
   - `/premium subscribe` — opens Stripe
   - Complete checkout → webhook confirms → features unlock

## Known Limitations

1. **Kokoro latency** — Local TTS has a ~500-2000ms delay depending on hardware
2. **ElevenLabs rate limits** — 100 requests/minute on free tier
3. **Bandwidth** — Voice playback requires active VoiceClient (bot must be in voice channel)

## Future Enhancements

- [ ] Custom voice training (ElevenLabs partnership)
- [ ] Real-time transcription (voice → text)
- [ ] TTS webhook events (for external integrations)
- [ ] Multi-language auto-detection
- [ ] Voice effect plugins (speed, pitch, effects)
