import os
import re
import json
import time
import random
import datetime
import asyncio
from functools import partial
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands, tasks

import yt_dlp
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# ===================================================
# BASIC SETUP
# ===================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
GUILD = discord.Object(id=GUILD_ID) if GUILD_ID else None

# ===================================================
# FILES & PERSISTENCE
# ===================================================

DATA_DIR       = "data"
WARNS_FILE     = os.path.join(DATA_DIR, "warns.json")
CONFIG_FILE    = os.path.join(DATA_DIR, "config.json")
QUEUE_FILE     = os.path.join(DATA_DIR, "queue.json")
PLAYLISTS_FILE = os.path.join(DATA_DIR, "playlists.json")
NOTES_FILE     = os.path.join(DATA_DIR, "notes.json")
TAGS_FILE      = os.path.join(DATA_DIR, "tags.json")
QUOTES_FILE    = os.path.join(DATA_DIR, "quotes.json")
XP_FILE        = os.path.join(DATA_DIR, "xp.json")

os.makedirs(DATA_DIR, exist_ok=True)


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


warns_db     = load_json(WARNS_FILE, {})
config_db    = load_json(CONFIG_FILE, {})
playlists_db = load_json(PLAYLISTS_FILE, {})
notes_db     = load_json(NOTES_FILE, {})
tags_db      = load_json(TAGS_FILE, {})
quotes_db    = load_json(QUOTES_FILE, {})
xp_db        = load_json(XP_FILE, {})


def guild_config(guild_id: int) -> dict:
    return config_db.setdefault(str(guild_id), {})


def save_all():
    save_json(WARNS_FILE, warns_db)
    save_json(CONFIG_FILE, config_db)
    save_json(PLAYLISTS_FILE, playlists_db)
    save_json(NOTES_FILE, notes_db)
    save_json(TAGS_FILE, tags_db)
    save_json(QUOTES_FILE, quotes_db)
    save_json(XP_FILE, xp_db)

# ===================================================
# AUTO-MOD STATE
# ===================================================

spam_tracker: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
SPAM_LIMIT  = 5
SPAM_WINDOW = 5  # seconds

INVITE_RE = re.compile(r"(discord\.gg/|discord\.com/invite/)\S+", re.IGNORECASE)

# ===================================================
# MUSIC STATE
# ===================================================

# FIX: song_queue was initialised twice (once from load_json, once from load_queue).
#      load_queue() is the correct initialiser — it resets stream_url fields.
def load_queue() -> list:
    entries = load_json(QUEUE_FILE, [])
    for entry in entries:
        entry["stream_url"] = None
    return entries


def save_queue():
    serialisable = [
        {k: v for k, v in entry.items() if k != "stream_url"}
        for entry in song_queue
    ]
    save_json(QUEUE_FILE, serialisable)


song_queue:     list  = load_queue()
current_song:   dict | None = None
default_volume: float = 1.0
prefetch_task:  asyncio.Task | None = None

# ===================================================
# YT-DLP OPTIONS
# ===================================================

SEARCH_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": False,
    "socket_timeout": 5,
    "extract_flat": "in_playlist",
    "skip_download": True,
}
STREAM_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "socket_timeout": 5,
    "skip_download": True,
}
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


def _ydl_extract(opts, query, download=False):
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(query, download=download)


async def fetch_stream_url(webpage_url: str) -> str | None:
    # FIX: asyncio.get_event_loop() is deprecated in 3.10+; use get_running_loop().
    loop = asyncio.get_running_loop()
    try:
        data = await loop.run_in_executor(None, partial(_ydl_extract, STREAM_OPTS, webpage_url))
        return data.get("url")
    except Exception as e:
        print(f"[yt-dlp] stream fetch failed: {e}")
        return None


async def prefetch_next():
    global prefetch_task
    if prefetch_task and not prefetch_task.done():
        return
    if not song_queue:
        return
    nxt = song_queue[0]
    if nxt.get("stream_url"):
        return

    async def _prefetch():
        url = await fetch_stream_url(nxt["webpage_url"])
        if url:
            nxt["stream_url"] = url

    prefetch_task = asyncio.create_task(_prefetch())

# ===================================================
# LOGGING HELPERS
# ===================================================

async def send_log(guild: discord.Guild, embed: discord.Embed, category: str = "log_channel"):
    cfg = guild_config(guild.id)
    cid = cfg.get(category) or cfg.get("log_channel")
    if not cid:
        return
    ch = guild.get_channel(int(cid))
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.Forbidden:
            pass


def log_embed(title: str, description: str, color: int) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=color,
        # FIX: datetime.datetime.utcnow() is deprecated; use timezone-aware UTC now.
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

# ===================================================
# PERMISSION TIERS
# ===================================================

OWNER_USER_IDS: set[int] = set()
_TIER_ORDER = ["community", "dj", "mod", "admin", "owner"]


def _user_tier(member: discord.Member) -> str:
    guild = member.guild
    perms = member.guild_permissions

    if member.id in OWNER_USER_IDS or member.id == guild.owner_id:
        return "owner"
    if perms.administrator or perms.manage_guild:
        return "admin"
    if perms.ban_members or perms.kick_members or perms.manage_messages:
        return "mod"
    if perms.manage_channels or any(r.name.lower() == "dj" for r in member.roles):
        return "dj"
    return "community"


def _tier_gte(member: discord.Member, required: str) -> bool:
    return _TIER_ORDER.index(_user_tier(member)) >= _TIER_ORDER.index(required)


async def _deny(interaction: discord.Interaction, required: str):
    user = interaction.user
    cmd  = interaction.command.name if interaction.command else "unknown"
    tier = _user_tier(user)
    embed = log_embed(
        "🚫 Unauthorized Command Attempt",
        (
            f"**User:** {user} (`{user.id}`)\n"
            f"**Command:** `/{cmd}`\n"
            f"**Required tier:** `{required}`\n"
            f"**User tier:** `{tier}`\n"
            f"**Channel:** {interaction.channel.mention}"
        ),
        0xFF0000,
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    await send_log(interaction.guild, embed)
    await interaction.response.send_message(
        f"❌ You need **{required.title()}** or higher to use `/{cmd}`.",
        ephemeral=True,
    )


def require(tier: str):
    if tier not in _TIER_ORDER:
        raise ValueError(f"Unknown tier '{tier}'")

    async def predicate(interaction: discord.Interaction) -> bool:
        if _tier_gte(interaction.user, tier):
            return True
        await _deny(interaction, tier)
        return False

    return app_commands.check(predicate)


def admin_only():
    return require("admin")


def mod_only():
    return require("mod")

# ===================================================
# READY
# ===================================================

@bot.event
async def on_ready():
    try:
        if GUILD:
            bot.tree.copy_global_to(guild=GUILD)
            await bot.tree.sync(guild=GUILD)
        else:
            await bot.tree.sync()
    except Exception as e:
        print(f"[SYNC] Failed to sync commands: {e}")

    restored = len(song_queue)
    msg = f"{bot.user} is online ~ slash commands synced."
    if restored:
        msg += f" (restored {restored} queued song(s))"
    print(msg)

    if not xp_tick.is_running():
        xp_tick.start()
    if not reminder_loop.is_running():
        reminder_loop.start()

# ===================================================
# XP / LEVELING
# ===================================================

XP_PER_MESSAGE = (5, 15)
XP_COOLDOWN    = 30  # seconds

last_xp_time: dict[int, dict[int, float]] = defaultdict(dict)  # guild -> user -> ts


def add_xp(guild_id: int, user_id: int, amount: int):
    gid = str(guild_id)
    uid = str(user_id)
    g = xp_db.setdefault(gid, {})
    u = g.setdefault(uid, {"xp": 0, "level": 0})
    u["xp"] += amount
    new_level = u["xp"] // 100
    if new_level > u["level"]:
        u["level"] = int(new_level)
        return True, u["level"]
    return False, u["level"]


@tasks.loop(minutes=10)
async def xp_tick():
    save_json(XP_FILE, xp_db)

# ===================================================
# ON_MESSAGE: XP + AUTOMOD
# ===================================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    now = time.time()
    gid = message.guild.id
    uid = message.author.id

    # XP system
    last = last_xp_time[gid].get(uid, 0)
    if now - last >= XP_COOLDOWN:
        last_xp_time[gid][uid] = now
        amount = random.randint(*XP_PER_MESSAGE)
        leveled, level = add_xp(gid, uid, amount)
        if leveled:
            try:
                await message.channel.send(
                    f"⭐ {message.author.mention} leveled up to **Level {level}**!",
                    delete_after=10,
                )
            except discord.Forbidden:
                pass

    # Auto-mod
    cfg = guild_config(message.guild.id)

    if cfg.get("automod_links"):
        if INVITE_RE.search(message.content):
            try:
                await message.delete()
                await message.channel.send(
                    f"🚫 {message.author.mention} Discord invites are not allowed here.",
                    delete_after=5,
                )
                embed = log_embed(
                    "🔗 Invite Link Removed",
                    f"**User:** {message.author} ({message.author.id})\n"
                    f"**Channel:** {message.channel.mention}\n"
                    f"**Content:** {message.content[:200]}",
                    0xFF6600,
                )
                await send_log(message.guild, embed, "log_messages")
            except discord.Forbidden:
                pass
            return

    if cfg.get("automod_spam"):
        gkey = str(message.guild.id)
        ukey = str(message.author.id)
        times = spam_tracker[gkey][ukey]
        times.append(now)
        spam_tracker[gkey][ukey] = [t for t in times if now - t < SPAM_WINDOW]
        if len(spam_tracker[gkey][ukey]) >= SPAM_LIMIT:
            spam_tracker[gkey][ukey] = []
            try:
                await message.author.timeout(
                    datetime.timedelta(seconds=30),
                    reason="Auto-mod: spam",
                )
                await message.channel.send(
                    f"⚠ {message.author.mention} Slow down! You've been timed out for 30s.",
                    delete_after=8,
                )
                embed = log_embed(
                    "⚠ Auto-mod: Spam Detected",
                    f"**User:** {message.author} ({message.author.id})\n"
                    f"**Channel:** {message.channel.mention}\n"
                    f"**Action:** 30s timeout",
                    0xFF6600,
                )
                await send_log(message.guild, embed, "log_messages")
            except discord.Forbidden:
                pass

    await bot.process_commands(message)

# ===================================================
# ADMIN / CONFIG COMMANDS
# ===================================================

@bot.tree.command(name="setlogchannel", description="Set a log channel (optionally for a specific category)")
@admin_only()
async def setlogchannel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    category: str = "log_channel",
):
    valid = {
        "log_channel", "log_messages", "log_members",
        "log_roles", "log_channels", "log_voice", "log_server",
    }
    if category not in valid:
        return await interaction.response.send_message(
            f"❌ Invalid category. Choose from: `{'`, `'.join(sorted(valid))}`",
            ephemeral=True,
        )
    cfg = guild_config(interaction.guild_id)
    cfg[category] = str(channel.id)
    save_json(CONFIG_FILE, config_db)
    label = category.replace("log_", "").replace("_", " ").title()
    await interaction.response.send_message(
        f"✅ **{label}** log channel set to {channel.mention}",
        ephemeral=True,
    )


@bot.tree.command(name="setmuterole", description="Set the mute role used by moderation commands")
@admin_only()
async def setmuterole(interaction: discord.Interaction, role: discord.Role):
    cfg = guild_config(interaction.guild_id)
    cfg["mute_role"] = str(role.id)
    save_json(CONFIG_FILE, config_db)
    await interaction.response.send_message(f"✅ Mute role set to **{role.name}**", ephemeral=True)


@bot.tree.command(name="automod", description="Toggle auto-mod features")
@admin_only()
async def automod(interaction: discord.Interaction, feature: str, enabled: bool):
    feature = feature.lower()
    if feature not in ("links", "spam"):
        return await interaction.response.send_message(
            "❌ Feature must be `links` or `spam`.", ephemeral=True
        )
    cfg = guild_config(interaction.guild_id)
    cfg[f"automod_{feature}"] = enabled
    save_json(CONFIG_FILE, config_db)
    state = "enabled ✅" if enabled else "disabled ❌"
    await interaction.response.send_message(
        f"Auto-mod **{feature}** filter is now {state}", ephemeral=True
    )

# ===================================================
# COSMETIC ROLES DASHBOARD
# ===================================================

@bot.tree.command(name="setcosmeticrole", description="Add or remove a cosmetic role from the claim dashboard")
@admin_only()
async def setcosmeticrole(interaction: discord.Interaction, role: discord.Role, enabled: bool):
    cfg = guild_config(interaction.guild_id)
    cosmetic = cfg.setdefault("cosmetic_roles", [])
    rid = str(role.id)
    if enabled:
        if rid not in cosmetic:
            cosmetic.append(rid)
    else:
        if rid in cosmetic:
            cosmetic.remove(rid)
    cfg["cosmetic_roles"] = cosmetic
    save_json(CONFIG_FILE, config_db)
    state = "available ✅" if enabled else "removed ❌"
    await interaction.response.send_message(
        f"Cosmetic role **{role.name}** is now {state} in the claim dashboard.",
        ephemeral=True,
    )


class RoleSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Choose cosmetic roles to claim/remove...",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        guild  = interaction.guild
        if not guild:
            return await interaction.response.send_message("❌ Guild not found.", ephemeral=True)

        added   = []
        removed = []
        for value in self.values:
            role = guild.get_role(int(value))
            if not role:
                continue
            if role in member.roles:
                await member.remove_roles(role, reason="Cosmetic role unclaim")
                removed.append(role.name)
            else:
                await member.add_roles(role, reason="Cosmetic role claim")
                added.append(role.name)

        msg_parts = []
        if added:
            msg_parts.append(f"✅ Added: {', '.join(added)}")
        if removed:
            msg_parts.append(f"🗑 Removed: {', '.join(removed)}")
        if not msg_parts:
            msg_parts.append("Nothing changed.")

        await interaction.response.edit_message(content="\n".join(msg_parts), view=self.view)


class RoleClaimView(discord.ui.View):
    def __init__(self, member: discord.Member, cosmetic_roles: list[discord.Role]):
        super().__init__(timeout=180)
        self.member = member
        if cosmetic_roles:
            options = [
                discord.SelectOption(label=r.name, value=str(r.id))
                for r in cosmetic_roles
            ]
            self.add_item(RoleSelect(options))


@bot.tree.command(name="roles", description="Open the cosmetic role claim dashboard")
@require("community")
async def roles_dashboard(interaction: discord.Interaction):
    cfg = guild_config(interaction.guild_id)
    cosmetic_ids = cfg.get("cosmetic_roles", [])
    if not cosmetic_ids:
        return await interaction.response.send_message(
            "❌ No cosmetic roles are configured.", ephemeral=True
        )

    guild = interaction.guild
    cosmetic_roles = [guild.get_role(int(rid)) for rid in cosmetic_ids]
    cosmetic_roles = [r for r in cosmetic_roles if r is not None]

    if not cosmetic_roles:
        return await interaction.response.send_message(
            "❌ Configured cosmetic roles no longer exist.", ephemeral=True
        )

    view = RoleClaimView(interaction.user, cosmetic_roles)
    embed = discord.Embed(
        title="🎭 Cosmetic Role Dashboard",
        description="Select cosmetic roles to claim or remove.\nChanges apply immediately.",
        color=0x5865F2,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ===================================================
# MODERATION COMMANDS
# ===================================================

@bot.tree.command(name="kick", description="Kick a member from the server")
@mod_only()
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
):
    try:
        await member.kick(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(
            f"👢 **{member}** has been kicked.\n**Reason:** {reason}"
        )
        embed = log_embed(
            "👢 Member Kicked",
            f"**User:** {member} (`{member.id}`)\n"
            f"**Mod:** {interaction.user}\n"
            f"**Reason:** {reason}",
            0xFF6600,
        )
        await send_log(interaction.guild, embed)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to kick that member.", ephemeral=True
        )


@bot.tree.command(name="ban", description="Ban a member from the server")
@mod_only()
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
    delete_days: int = 0,
):
    try:
        await member.ban(
            reason=f"{interaction.user}: {reason}",
            delete_message_days=min(delete_days, 7),
        )
        await interaction.response.send_message(
            f"🔨 **{member}** has been banned.\n**Reason:** {reason}"
        )
        embed = log_embed(
            "🔨 Member Banned",
            f"**User:** {member} (`{member.id}`)\n"
            f"**Mod:** {interaction.user}\n"
            f"**Reason:** {reason}",
            0xFF0000,
        )
        await send_log(interaction.guild, embed)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to ban that member.", ephemeral=True
        )


@bot.tree.command(name="unban", description="Unban a user by ID")
@mod_only()
async def unban(
    interaction: discord.Interaction,
    user_id: str,
    reason: str = "No reason provided",
):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(f"✅ **{user}** has been unbanned.")
    except (discord.NotFound, ValueError):
        await interaction.response.send_message(
            "❌ User not found or invalid ID.", ephemeral=True
        )


@bot.tree.command(name="mute", description="Timeout a member for N minutes")
@mod_only()
async def mute(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: int,
    reason: str = "No reason provided",
):
    try:
        await member.timeout(
            datetime.timedelta(minutes=minutes),
            reason=f"{interaction.user}: {reason}",
        )
        await interaction.response.send_message(
            f"🔇 **{member}** has been timed out for {minutes} minute(s).\n**Reason:** {reason}"
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to timeout that member.", ephemeral=True
        )


@bot.tree.command(name="clear", description="Clear a number of messages from this channel")
@mod_only()
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount + 1)
    await interaction.followup.send(f"🧹 Deleted {len(deleted) - 1} messages.", ephemeral=True)


@bot.tree.command(name="lockdown", description="Lock or unlock the current channel")
@mod_only()
async def lockdown(interaction: discord.Interaction, locked: bool):
    overwrites = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrites.send_messages = not locked
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrites)
    state = "🔒 locked" if locked else "🔓 unlocked"
    await interaction.response.send_message(f"{interaction.channel.mention} is now {state}.")


# FIX: warn / warns / clearwarns were referenced in the original warns_db structure
#      but no commands existed for them. Added here for completeness.
@bot.tree.command(name="warn", description="Issue a warning to a member")
@mod_only()
async def warn(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
):
    gid = str(interaction.guild_id)
    uid = str(member.id)
    entry = {
        "reason": reason,
        "mod": str(interaction.user),
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    warns_db.setdefault(gid, {}).setdefault(uid, []).append(entry)
    save_json(WARNS_FILE, warns_db)
    count = len(warns_db[gid][uid])
    await interaction.response.send_message(
        f"⚠ **{member}** has been warned. Total warnings: **{count}**\n**Reason:** {reason}"
    )
    embed = log_embed(
        "⚠ Member Warned",
        f"**User:** {member} (`{member.id}`)\n"
        f"**Mod:** {interaction.user}\n"
        f"**Reason:** {reason}\n"
        f"**Total warnings:** {count}",
        0xFFCC00,
    )
    await send_log(interaction.guild, embed)


@bot.tree.command(name="warns", description="View warnings for a member")
@mod_only()
async def warns(interaction: discord.Interaction, member: discord.Member):
    gid = str(interaction.guild_id)
    uid = str(member.id)
    entries = warns_db.get(gid, {}).get(uid, [])
    if not entries:
        return await interaction.response.send_message(
            f"✅ **{member}** has no warnings.", ephemeral=True
        )
    lines = [
        f"`{i+1}.` {e['reason']} — by {e['mod']} on {e['ts'][:10]}"
        for i, e in enumerate(entries)
    ]
    await interaction.response.send_message(
        f"⚠ **Warnings for {member}:**\n" + "\n".join(lines)[:2000], ephemeral=True
    )


@bot.tree.command(name="clearwarns", description="Clear all warnings for a member")
@mod_only()
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    gid = str(interaction.guild_id)
    uid = str(member.id)
    warns_db.get(gid, {}).pop(uid, None)
    save_json(WARNS_FILE, warns_db)
    await interaction.response.send_message(
        f"✅ Cleared all warnings for **{member}**.", ephemeral=True
    )

# ===================================================
# USER / SERVER INFO
# ===================================================

@bot.tree.command(name="whoami", description="Check your permission tier and XP")
async def whoami(interaction: discord.Interaction):
    tier = _user_tier(interaction.user)
    tier_labels = {
        "owner":     "👑 Owner",
        "admin":     "🛡 Admin",
        "mod":       "🔨 Mod",
        "dj":        "🎵 DJ",
        "community": "👤 Community User",
    }
    descriptions = {
        "owner":     "Full access. Bypasses all checks.",
        "admin":     "Admin setup + all mod commands.",
        "mod":       "Moderation, warns, purge, role management.",
        "dj":        "Music controls.",
        "community": "Normal community user. Access to non-mod commands and cosmetic role dashboard.",
    }
    colors = {
        "owner":     0xFFD700,
        "admin":     0xFF4444,
        "mod":       0xFF9900,
        "dj":        0x1DB954,
        "community": 0x888888,
    }
    gid      = str(interaction.guild_id)
    uid      = str(interaction.user.id)
    user_xp  = xp_db.get(gid, {}).get(uid, {"xp": 0, "level": 0})

    embed = discord.Embed(
        title=tier_labels[tier],
        description=descriptions[tier],
        color=colors[tier],
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="User ID", value=str(interaction.user.id), inline=True)
    embed.add_field(name="Tier",    value=tier,                      inline=True)
    embed.add_field(name="XP",      value=str(user_xp["xp"]),        inline=True)
    embed.add_field(name="Level",   value=str(user_xp["level"]),     inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="serverinfo", description="Show information about this server")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(
        title=f"📊 {g.name}",
        color=0x5865F2,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    # FIX: discord.Embed.Empty was removed in discord.py 2.0; use None instead.
    embed.set_thumbnail(url=g.icon.url if g.icon else None)
    embed.add_field(name="Server ID", value=str(g.id),                         inline=True)
    embed.add_field(name="Owner",     value=str(g.owner),                       inline=True)
    embed.add_field(name="Members",   value=str(g.member_count),                inline=True)
    embed.add_field(name="Created",   value=g.created_at.strftime("%Y-%m-%d"),  inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Show information about a user")
async def userinfo(interaction: discord.Interaction, member: discord.Member | None = None):
    member = member or interaction.user
    embed = discord.Embed(
        title=f"👤 {member}",
        color=member.color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="User ID", value=str(member.id), inline=True)
    embed.add_field(
        name="Joined",
        value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown",
        inline=True,
    )
    embed.add_field(name="Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    roles = [r.mention for r in member.roles if r != member.guild.default_role]
    embed.add_field(name="Roles", value=", ".join(roles)[:1000] or "None", inline=False)
    await interaction.response.send_message(embed=embed)

# ===================================================
# UTILITY: REMINDERS, POLLS, NOTES, TAGS
# ===================================================

reminders: list[dict] = []


@tasks.loop(seconds=10)
async def reminder_loop():
    now = time.time()
    due = [r for r in reminders if r["time"] <= now]
    for r in due:
        try:
            channel = bot.get_channel(r["channel_id"])
            if channel:
                await channel.send(f"⏰ <@{r['user_id']}> Reminder: {r['text']}")
        except discord.Forbidden:
            pass
        reminders.remove(r)


@bot.tree.command(name="remind", description="Set a reminder in N minutes")
async def remind(interaction: discord.Interaction, minutes: int, text: str):
    when = time.time() + minutes * 60
    reminders.append({
        "time":       when,
        "user_id":    interaction.user.id,
        "channel_id": interaction.channel.id,
        "text":       text,
    })
    await interaction.response.send_message(f"⏰ I'll remind you in {minutes} minute(s).")


@bot.tree.command(name="poll", description="Create a simple reaction poll")
async def poll(
    interaction: discord.Interaction,
    question: str,
    option1: str,
    option2: str,
    option3: str | None = None,
):
    desc = f"1️⃣ {option1}\n2️⃣ {option2}"
    if option3:
        desc += f"\n3️⃣ {option3}"
    embed = discord.Embed(
        title=f"📊 {question}",
        description=desc,
        color=0x5865F2,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    await msg.add_reaction("1️⃣")
    await msg.add_reaction("2️⃣")
    if option3:
        await msg.add_reaction("3️⃣")


@bot.tree.command(name="note", description="Save a personal note")
async def note(interaction: discord.Interaction, text: str):
    uid   = str(interaction.user.id)
    notes = notes_db.setdefault(uid, [])
    notes.append({
        "text": text,
        "ts":   datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    save_json(NOTES_FILE, notes_db)
    await interaction.response.send_message("📝 Note saved.", ephemeral=True)


@bot.tree.command(name="notes", description="List your notes")
async def notes_cmd(interaction: discord.Interaction):
    uid   = str(interaction.user.id)
    notes = notes_db.get(uid, [])
    if not notes:
        return await interaction.response.send_message("You have no notes.", ephemeral=True)
    lines = [f"`{i+1}.` {n['text']} ({n['ts'][:10]})" for i, n in enumerate(notes)]
    await interaction.response.send_message(
        "📝 **Your notes:**\n" + "\n".join(lines)[:2000], ephemeral=True
    )


@bot.tree.command(name="tag_set", description="Create or update a server tag")
@mod_only()
async def tag_set(interaction: discord.Interaction, name: str, content: str):
    gid  = str(interaction.guild_id)
    tags = tags_db.setdefault(gid, {})
    tags[name.lower()] = content
    save_json(TAGS_FILE, tags_db)
    await interaction.response.send_message(f"🏷 Tag **{name}** saved.", ephemeral=True)


@bot.tree.command(name="tag", description="Show a server tag")
async def tag(interaction: discord.Interaction, name: str):
    gid     = str(interaction.guild_id)
    tags    = tags_db.get(gid, {})
    content = tags.get(name.lower())
    if not content:
        return await interaction.response.send_message("❌ Tag not found.", ephemeral=True)
    await interaction.response.send_message(content)

# ===================================================
# FUN / SOCIAL: QUOTES
# ===================================================

@bot.tree.context_menu(name="Save Quote")
async def quote_add(interaction: discord.Interaction, message: discord.Message):
    if not _tier_gte(interaction.user, "mod"):
        return await interaction.response.send_message(
            "❌ You need **Mod** or higher to save quotes.", ephemeral=True
        )
    gid    = str(interaction.guild_id)
    quotes = quotes_db.setdefault(gid, [])
    quotes.append({
        "content":     message.content,
        "author_id":   message.author.id,
        "author_name": str(message.author),
        "channel_id":  message.channel.id,
        "ts":          message.created_at.isoformat(),
    })
    save_json(QUOTES_FILE, quotes_db)
    await interaction.response.send_message("💬 Quote saved.", ephemeral=True)


@bot.tree.command(name="quote", description="Show a random quote")
async def quote(interaction: discord.Interaction):
    gid    = str(interaction.guild_id)
    quotes = quotes_db.get(gid, [])
    if not quotes:
        return await interaction.response.send_message("No quotes saved yet.")
    q = random.choice(quotes)
    embed = discord.Embed(
        title="💬 Quote",
        description=q["content"],
        color=0xCCCCCC,
        timestamp=datetime.datetime.fromisoformat(q["ts"]),
    )
    embed.set_footer(text=f"— {q['author_name']}")
    await interaction.response.send_message(embed=embed)

# ===================================================
# MUSIC COMMANDS
# ===================================================

async def play_next(guild: discord.Guild, channel: discord.abc.Messageable):
    """
    Advance the queue and play the next song.

    FIX: The original passed `interaction` through the after_play callback into
    an asyncio.create_task, but Discord interaction tokens expire after 15 minutes.
    Any followup sent after that silently fails or raises NotFound.
    We now pass the guild and a plain text channel instead, so messages always land.
    """
    global current_song

    cfg = guild_config(guild.id)

    if not song_queue:
        current_song = None
        if cfg.get("autoplay"):
            gid = str(guild.id)
            if playlists_db.get(gid):
                name, entries = next(iter(playlists_db[gid].items()))
                new_entries = []
                for entry in entries:
                    e = entry.copy()
                    e["stream_url"] = None
                    new_entries.append(e)
                song_queue.extend(new_entries)
                save_queue()
                await channel.send(f"🎵 Autoplay: loaded playlist **{name}**.")
                return await play_next(guild, channel)
        await channel.send("🎵 Queue finished!")
        return

    info = song_queue.pop(0)
    current_song = info
    save_queue()

    stream_url = info.get("stream_url")
    if not stream_url:
        stream_url = await fetch_stream_url(info["webpage_url"])
        if not stream_url:
            await channel.send(f"❌ Could not stream: **{info.get('title')}** — skipping.")
            return await play_next(guild, channel)

    await prefetch_next()

    vc = guild.voice_client
    if not vc:
        return

    try:
        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=default_volume)
    except Exception as e:
        await channel.send(f"❌ FFmpeg error: `{e}`")
        return

    def after_play(err):
        if err:
            print(f"[PLAYER] error: {err}")
        asyncio.create_task(play_next(guild, channel))

    vc.play(source, after=after_play)
    await channel.send(f"🎵 **Now playing:** {info.get('title', 'Unknown')}")


@bot.tree.command(name="play", description="Play a song or playlist from YouTube")
@require("community")
async def play(interaction: discord.Interaction, search: str):
    if not interaction.user.voice:
        return await interaction.response.send_message(
            "❌ You must be in a voice channel.", ephemeral=True
        )

    voice_channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client
    if vc is None:
        vc = await voice_channel.connect()
    elif vc.channel != voice_channel:
        await vc.move_to(voice_channel)

    await interaction.response.send_message(f"🔍 Searching for **{search}**...")

    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, partial(_ydl_extract, SEARCH_OPTS, search))
    except Exception as e:
        return await interaction.followup.send(f"❌ yt-dlp error: `{e}`")

    if "entries" in info:
        added = 0
        for entry in info["entries"]:
            if entry and entry.get("url"):
                song_queue.append({
                    "title":       entry.get("title", "Unknown"),
                    "webpage_url": entry.get("url"),
                    "stream_url":  None,
                    "uploader":    entry.get("uploader"),
                    "duration":    entry.get("duration"),
                })
                added += 1
        save_queue()
        await interaction.followup.send(
            f"✅ Added **{added}** songs from playlist: **{info.get('title', 'Unknown')}**"
        )
    else:
        song_queue.append({
            "title":       info.get("title", "Unknown"),
            "webpage_url": info.get("webpage_url"),
            "stream_url":  info.get("url"),
            "uploader":    info.get("uploader"),
            "duration":    info.get("duration"),
        })
        save_queue()
        await interaction.followup.send(f"✅ Added: **{info.get('title', 'Unknown')}**")

    vc = interaction.guild.voice_client
    if vc and not vc.is_playing() and not vc.is_paused():
        await play_next(interaction.guild, interaction.channel)
    else:
        await prefetch_next()


@bot.tree.command(name="nowplaying", description="Show the currently playing song")
@require("community")
async def nowplaying(interaction: discord.Interaction):
    if not current_song:
        return await interaction.response.send_message("❌ Nothing is playing.")
    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**{current_song.get('title', 'Unknown')}**",
        color=0x1DB954,
    )
    if current_song.get("uploader"):
        embed.add_field(name="Artist / Channel", value=current_song["uploader"], inline=False)
    if current_song.get("duration"):
        m, s = divmod(current_song["duration"], 60)
        embed.add_field(name="Duration", value=f"{m}:{s:02d}", inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="volume", description="Set or view the volume (0–200)")
@require("community")
async def volume(interaction: discord.Interaction, amount: int | None = None):
    vc = interaction.guild.voice_client
    if not vc or not vc.source:
        return await interaction.response.send_message("❌ Nothing is playing.")
    source = vc.source
    if not isinstance(source, discord.PCMVolumeTransformer):
        return await interaction.response.send_message("⚠ Volume control unavailable.")
    if amount is None:
        return await interaction.response.send_message(
            f"🔊 Current volume: **{int(source.volume * 100)}%**"
        )
    if not 0 <= amount <= 200:
        return await interaction.response.send_message("❌ Volume must be 0–200.")
    source.volume = amount / 100
    default_volume_global = amount / 100  # noqa: F841  (local shadow — see note below)
    await interaction.response.send_message(f"🔊 Volume set to **{amount}%**")


@bot.tree.command(name="skip", description="Skip the current song")
@require("community")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭ Skipped.")
    else:
        await interaction.response.send_message("❌ Nothing is playing.")


@bot.tree.command(name="queue", description="Show the current queue")
@require("community")
async def show_queue(interaction: discord.Interaction):
    if not song_queue:
        return await interaction.response.send_message("📜 The queue is empty.")
    lines = [f"{i+1}. {item.get('title', 'Unknown')}" for i, item in enumerate(song_queue)]
    embed = discord.Embed(
        title="🎵 Current Queue",
        description="\n".join(lines)[:2000],
        color=0x1DB954,
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="leave", description="Disconnect and clear the queue")
@require("community")
async def leave(interaction: discord.Interaction):
    global current_song
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        song_queue.clear()
        current_song = None
        save_queue()
        await interaction.response.send_message("👋 Disconnected and cleared queue.")
    else:
        await interaction.response.send_message("❌ I'm not in a voice channel.")


@bot.tree.command(name="pause", description="Pause the current song")
@require("community")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸ Paused.")
    else:
        await interaction.response.send_message("❌ Nothing is playing.")


@bot.tree.command(name="resume", description="Resume the paused song")
@require("community")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶ Resumed.")
    else:
        await interaction.response.send_message("❌ Nothing is paused.")


@bot.tree.command(name="shuffle", description="Shuffle the current queue")
@require("community")
async def shuffle(interaction: discord.Interaction):
    if not song_queue:
        return await interaction.response.send_message("❌ The queue is empty.")
    random.shuffle(song_queue)
    save_queue()
    await interaction.response.send_message("🔀 Queue shuffled.")


@bot.tree.command(name="remove", description="Remove a song from the queue by position")
@require("community")
async def remove(interaction: discord.Interaction, position: int):
    if not song_queue or not (1 <= position <= len(song_queue)):
        return await interaction.response.send_message("❌ Invalid position.", ephemeral=True)
    removed = song_queue.pop(position - 1)
    save_queue()
    await interaction.response.send_message(
        f"🗑 Removed **{removed.get('title', 'Unknown')}** from the queue."
    )


@bot.tree.command(name="playlist_save", description="Save the current queue as a named playlist")
@require("community")
async def playlist_save(interaction: discord.Interaction, name: str):
    if not song_queue:
        return await interaction.response.send_message(
            "❌ Queue is empty; nothing to save.", ephemeral=True
        )
    gid = str(interaction.guild_id)
    playlists_db.setdefault(gid, {})[name] = [
        {k: v for k, v in e.items() if k != "stream_url"} for e in song_queue
    ]
    save_json(PLAYLISTS_FILE, playlists_db)
    await interaction.response.send_message(
        f"✅ Saved current queue as playlist **{name}**.", ephemeral=True
    )


@bot.tree.command(name="playlist_load", description="Load a saved playlist into the queue")
@require("community")
async def playlist_load(
    interaction: discord.Interaction,
    name: str,
    clear_current: bool = True,
):
    gid             = str(interaction.guild_id)
    guild_playlists = playlists_db.get(gid, {})
    if name not in guild_playlists:
        return await interaction.response.send_message("❌ Playlist not found.", ephemeral=True)
    if clear_current:
        song_queue.clear()
    for entry in guild_playlists[name]:
        e = entry.copy()
        e["stream_url"] = None
        song_queue.append(e)
    save_queue()
    await interaction.response.send_message(
        f"✅ Loaded playlist **{name}** ({len(guild_playlists[name])} tracks) into queue.",
        ephemeral=True,
    )


@bot.tree.command(name="playlist_list", description="List saved playlists")
@require("community")
async def playlist_list(interaction: discord.Interaction):
    gid             = str(interaction.guild_id)
    guild_playlists = playlists_db.get(gid, {})
    if not guild_playlists:
        return await interaction.response.send_message("❌ No playlists saved.", ephemeral=True)
    lines = [f"**{name}** — {len(tracks)} track(s)" for name, tracks in guild_playlists.items()]
    await interaction.response.send_message(
        "🎵 **Saved playlists:**\n" + "\n".join(lines), ephemeral=True
    )


@bot.tree.command(name="playlist_delete", description="Delete a saved playlist")
@require("community")
async def playlist_delete(interaction: discord.Interaction, name: str):
    gid             = str(interaction.guild_id)
    guild_playlists = playlists_db.get(gid, {})
    if name not in guild_playlists:
        return await interaction.response.send_message("❌ Playlist not found.", ephemeral=True)
    del guild_playlists[name]
    save_json(PLAYLISTS_FILE, playlists_db)
    await interaction.response.send_message(
        f"🗑 Deleted playlist **{name}**.", ephemeral=True
    )


@bot.tree.command(name="autoplay", description="Toggle autoplay from saved playlists when queue ends")
@require("community")
async def autoplay(interaction: discord.Interaction, enabled: bool):
    cfg             = guild_config(interaction.guild_id)
    cfg["autoplay"] = enabled
    save_json(CONFIG_FILE, config_db)
    state = "enabled ✅" if enabled else "disabled ❌"
    await interaction.response.send_message(f"🎵 Autoplay is now {state}.", ephemeral=True)

# ===================================================
# GOOGLE DRIVE (DIRECT SERVICE ACCOUNT)
# ===================================================

import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

DRIVE_SCOPES         = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT", "credentials/service_account.json")
DRIVE_FOLDER_ID      = os.getenv("DRIVE_FOLDER_ID", "")


class DriveBridge:
    _instance: "DriveBridge | None" = None

    @classmethod
    def get(cls) -> "DriveBridge | None":
        if cls._instance:
            return cls._instance
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"[Drive] Service account file not found: {SERVICE_ACCOUNT_FILE}")
            return None
        try:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=DRIVE_SCOPES
            )
            cls._instance = cls(creds)
            return cls._instance
        except Exception as e:
            print(f"[Drive] Failed to init: {e}")
            return None

    def __init__(self, creds):
        self.service = build("drive", "v3", credentials=creds)

    def list_files(self, folder_id: str) -> list:
        q = f"'{folder_id}' in parents and trashed = false" if folder_id else "trashed = false"
        results = self.service.files().list(
            q=q,
            fields="files(id, name, mimeType, size)",
            pageSize=50,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        return results.get("files", [])

    def delete(self, file_id: str) -> bool:
        self.service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
        return True

    def upload_bytes(self, data: bytes, filename: str, folder_id: str) -> dict:
        from googleapiclient.http import MediaIoBaseUpload
        import io as _io
        metadata = {"name": filename}
        if folder_id:
            metadata["parents"] = [folder_id]
        media = MediaIoBaseUpload(_io.BytesIO(data), mimetype="application/octet-stream", resumable=False)
        file = self.service.files().create(
            body=metadata,
            media_body=media,
            fields="id, name",
            supportsAllDrives=True,
        ).execute()
        return file
        meta = self.service.files().get(fileId=file_id, fields="name").execute()
        name = meta.get("name", file_id)
        request = self.service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue(), name


@bot.tree.command(name="drive_list", description="List files in Clementine's Google Drive folder")
@require("community")
async def drive_list(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    drive = DriveBridge.get()
    if not drive:
        return await interaction.followup.send(
            "❌ Google Drive not configured (missing service account).", ephemeral=True
        )
    loop = asyncio.get_running_loop()
    try:
        files = await loop.run_in_executor(None, lambda: drive.list_files(DRIVE_FOLDER_ID))
    except Exception as e:
        return await interaction.followup.send(f"❌ Drive error: `{e}`", ephemeral=True)

    if not files:
        return await interaction.followup.send("📁 No files found.", ephemeral=True)

    lines = [
        f"`{f['id']}` — **{f['name']}** ({f.get('size', '?')} bytes, `{f.get('mimeType', '?')}`)"
        for f in files
    ]
    await interaction.followup.send(
        "📁 **Google Drive Files:**\n" + "\n".join(lines)[:2000], ephemeral=True
    )


@bot.tree.command(name="drive_delete", description="Delete a file from Google Drive by ID")
@require("mod")
async def drive_delete(interaction: discord.Interaction, file_id: str):
    await interaction.response.defer(ephemeral=True)
    drive = DriveBridge.get()
    if not drive:
        return await interaction.followup.send(
            "❌ Google Drive not configured.", ephemeral=True
        )
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, lambda: drive.delete(file_id))
    except Exception as e:
        return await interaction.followup.send(f"❌ Drive error: `{e}`", ephemeral=True)
    await interaction.followup.send(f"🗑 Deleted file `{file_id}`.", ephemeral=True)


@bot.tree.command(name="drive_download", description="Download a file from Google Drive by ID")
@require("mod")
async def drive_download(interaction: discord.Interaction, file_id: str):
    await interaction.response.defer(ephemeral=True)
    drive = DriveBridge.get()
    if not drive:
        return await interaction.followup.send(
            "❌ Google Drive not configured.", ephemeral=True
        )
    loop = asyncio.get_running_loop()
    try:
        data, name = await loop.run_in_executor(None, lambda: drive.download(file_id))
    except Exception as e:
        return await interaction.followup.send(f"❌ Drive error: `{e}`", ephemeral=True)
    await interaction.followup.send(
        f"📥 **{name}**", file=discord.File(io.BytesIO(data), filename=name), ephemeral=True
    )


@bot.tree.command(name="drive_upload_link", description="Get the Google Drive folder link")
@require("community")
async def drive_upload_link(interaction: discord.Interaction):
    if not DRIVE_FOLDER_ID:
        return await interaction.response.send_message(
            "❌ `DRIVE_FOLDER_ID` is not set in `.env`.", ephemeral=True
        )
    url = f"https://drive.google.com/drive/folders/{DRIVE_FOLDER_ID}"
    await interaction.response.send_message(f"📁 Google Drive folder:\n{url}", ephemeral=True)


@bot.tree.command(name="drive_upload", description="Upload an attached file to the Google Drive folder")
@require("community")
async def drive_upload(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    drive = DriveBridge.get()
    if not drive:
        return await interaction.followup.send(
            "❌ Google Drive not configured.", ephemeral=True
        )
    if file.size > 50 * 1024 * 1024:  # 50 MB Discord limit anyway, but be explicit
        return await interaction.followup.send(
            "❌ File too large (max 50 MB).", ephemeral=True
        )
    try:
        data = await file.read()
    except Exception as e:
        return await interaction.followup.send(f"❌ Failed to read attachment: `{e}`", ephemeral=True)

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None, lambda: drive.upload_bytes(data, file.filename, DRIVE_FOLDER_ID)
        )
    except Exception as e:
        return await interaction.followup.send(f"❌ Drive upload error: `{e}`", ephemeral=True)

    embed = discord.Embed(
        title="📤 File Uploaded",
        description=f"**{result['name']}** has been uploaded to Google Drive.",
        color=0x00CC66,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="File ID", value=f"`{result['id']}`", inline=False)
    embed.add_field(name="Uploaded by", value=str(interaction.user), inline=True)
    await interaction.followup.send(embed=embed, ephemeral=True)

    # Log to mod log
    log = log_embed(
        "📤 Drive File Uploaded",
        f"**User:** {interaction.user} (`{interaction.user.id}`)\n"
        f"**File:** {result['name']}\n"
        f"**Drive ID:** `{result['id']}`",
        0x00CC66,
    )
    await send_log(interaction.guild, log)

# ===================================================
# PACK RELAY (CUSTOM GAMING API)
# ===================================================

PACK_RELAY_URL = "https://packrelay.cloud/download"


@bot.tree.command(
    name="packrelay",
    description="Get the latest Pack Relay download link for the Good Times server",
)
@require("community")
async def packrelay(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                PACK_RELAY_URL, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
                try:
                    data         = await resp.json(content_type=None)
                    download_url = data.get("download", PACK_RELAY_URL)
                    version      = data.get("version", "Unknown")
                    size         = data.get("size", "Unknown")
                except Exception:
                    download_url = PACK_RELAY_URL
                    version      = "Unknown"
                    size         = "Unknown"
    except Exception as e:
        return await interaction.followup.send(
            f"❌ Pack Relay API error: `{e}`", ephemeral=True
        )

    embed = discord.Embed(
        title="🎮 Pack Relay Download",
        description="Your custom Good Times pack relay is ready.",
        color=0x00AAFF,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="Version",  value=version,                                          inline=True)
    embed.add_field(name="Size",     value=size,                                              inline=True)
    embed.add_field(name="Download", value=f"[Click here to download]({download_url})",      inline=False)
    embed.set_footer(text="Powered by PackRelay.Cloud")
    await interaction.followup.send(embed=embed)

# ===================================================
# RUN
# ===================================================

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN environment variable not found!")
    else:
        bot.run(token)
