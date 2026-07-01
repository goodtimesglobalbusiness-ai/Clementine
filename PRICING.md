# Clementine Pricing & Features

**Clementine** is a unified Discord admin + text-to-speech bot with flexible, transparent pricing. All tiers include core admin features plus TTS capabilities.

---

## Pricing Tiers

### 🆓 Free Tier
**Cost:** $0/month

**Included:**
- Full Discord admin commands (user management, role automation, audit logs)
- Local TTS (Kokoro voices) — **no per-character cost**
  - 6 curated voices (3 female, 3 male)
  - Auto-read text channels aloud
  - Custom pronunciations
  - Per-user voice selection
- **Monthly cap:** 50,000 characters (free usage tracking)
- Auto-join voice channels
- Message content filtering & moderation
- Accessibility captions (experimental live transcription)

**Perfect for:**
- Small Discord communities
- Servers that don't need premium voice quality
- Cost-conscious teams

---

### ⭐ Pro Tier
**Cost:** $9.99/month or $99.99/year (save 17%)

**Included (all of Free, plus):**
- **ElevenLabs Premium TTS** — high-quality natural voices
  - Unlimited voice selection from ElevenLabs library
  - Natural prosody and emotional range
  - Multilingual support (English, Spanish, French, German, Italian, Portuguese, Dutch, Turkish, Polish, Swedish, Danish, etc.)
- **Monthly character allowance:** 100,000 characters (metered against ElevenLabs cost)
- Priority support
- Manage billing portal (Stripe integration)
- Auto-subscribe new guild members to TTS features
- Advanced rate limiting controls

**Perfect for:**
- Growing communities with accessibility needs
- Content creators and streamers
- Teams using TTS for notifications and announcements
- Non-English speaking servers

---

### 🚀 Enterprise (Custom)
**Cost:** Custom pricing (contact sales)

**Included (all of Pro, plus):**
- Dedicated Clementine bot instance
- Custom branding & voice integration
- SLA uptime guarantee (99.9%)
- Priority 24/7 support
- Custom voice training (ElevenLabs partnership)
- Webhook integration for external systems
- Advanced analytics & usage reporting
- White-label deployment options

**Perfect for:**
- Large enterprises
- Mission-critical bots
- Servers with 100K+ members
- Custom integrations with other services

---

## Feature Comparison

| Feature | Free | Pro | Enterprise |
|---------|------|-----|------------|
| **Discord Admin Commands** | ✅ | ✅ | ✅ |
| **Local TTS (Kokoro)** | ✅ | ✅ | ✅ |
| **ElevenLabs Premium TTS** | ❌ | ✅ | ✅ |
| **Monthly Character Limit** | 50K | 100K | Unlimited |
| **Voice Selection** | 6 curated | Unlimited | Unlimited + custom |
| **Auto-read Text Channels** | ✅ | ✅ | ✅ |
| **Custom Pronunciations** | ✅ | ✅ | ✅ |
| **Accessibility Features** | ✅ (basic) | ✅ (enhanced) | ✅ (full) |
| **Content Filtering** | ✅ | ✅ | ✅ |
| **Billing Portal** | ❌ | ✅ | ✅ |
| **Priority Support** | ❌ | ✅ | ✅ (24/7) |
| **SLA Uptime** | No | No | 99.9% |
| **Custom Voices** | ❌ | ❌ | ✅ |
| **Webhooks & APIs** | ❌ | Limited | ✅ |

---

## Billing Details

### How Pricing Works

**Pro Tier:**
- Charged **per guild (Discord server)**
- All features shared across members
- One billing admin manages subscription

**Character Counting:**
- Messages read by the bot count toward monthly character limit
- Cached short phrases don't count against the limit
- Link/attachment announcements are metered separately
- `/say` command text counts in real-time

**Overage Handling:**
- Free tier: auto-read pauses when over 50K characters
- Pro tier: downgrades to Kokoro (local) voices for additional reads
- No surprise charges — you always know your usage

### How to Upgrade

1. **In Discord:** Run `/premium subscribe` (Manage Server permission required)
2. **Stripe Checkout:** Complete your subscription in-browser
3. **Instant activation:** Pro features unlock immediately
4. **Manage anytime:** Use `/premium manage` to adjust, pause, or cancel

### Cancellation

- Cancel anytime — no lock-in periods
- Refunds available within 30 days (full refund on yearly plans)
- Downgrade to Free seamlessly
- Access to Stripe billing portal for full control

---

## Why Unified Billing?

Clementine combines admin tools + TTS under one pricing model because:

1. **Simplicity** — One subscription, one invoice per server
2. **Value** — Get admin + TTS features together
3. **Flexibility** — Upgrade only the features you use
4. **Transparency** — No hidden per-character costs at scale

---

## FAQ

**Q: Can I use both Kokoro and ElevenLabs voices?**
A: Yes! Pro servers can pick either for any message. We recommend Kokoro for high-volume auto-read (free) and ElevenLabs for premium announcements.

**Q: What happens if I hit my character limit?**
A: **Free:** auto-read pauses until next month. **Pro:** you keep reading, but in Kokoro voices. No overage charges.

**Q: Is the local TTS server included?**
A: No — the local TTS server (Kokoro) is self-hosted on your infrastructure. Clementine connects to it; you run it on a Mac Mini or other machine.

**Q: Can I use Clementine for commercial purposes?**
A: Yes — both Free and Pro tiers allow commercial use (streaming, business servers, etc.). Enterprise plans offer additional compliance features.

**Q: Do you offer student/nonprofit discounts?**
A: Contact sales@clementine.gg with details. We offer 50% off Pro for verified nonprofit/educational servers.

---

## Questions?

📧 Email: support@clementine.gg  
💬 Discord: [Clementine Support Server](https://discord.gg/clementine)  
🌐 Web: [clementine.gg](https://clementine.gg)
