# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Clementine is a single-file Discord bot ("Full Spectrum Admin") built on `discord.py`. All bot logic lives in `clem2_0.py`; `bot.py` is a thin entry point that imports and runs it.

## Running the bot

There is no build step — this is a plain Python script.

```bash
pip install -r requirements.txt   # currently empty; see "Dependencies" below
python bot.py
```

On Windows, `clem.bat` runs `scripts/rc.ps1 start`, which kills any previously-tracked bot process (PID stored in `.clem-pids`) and starts a fresh `python bot.py`. Note `scripts/rc.ps1` hardcodes `$botPath = "C:\Users\zonef\Desktop\github\main\Clementine"` — update this path if the checkout location differs (it does not match this repo's actual location under `Desktop\Clementine`).

`scripts/cs.ps1` is a read-only helper that prints the folder tree and sanity-checks that `bot.py`, `requirements.txt`, and `.env` exist.

There are no automated tests, lint config, or CI in this repo.

### Dependencies

`requirements.txt` is currently empty. The code actually imports: `discord.py` (with `app_commands`/`tasks`), `yt_dlp`, `aiohttp`, `python-dotenv`, `google-api-python-client`, and `google-auth` (`google.oauth2.service_account`). `ffmpeg` must also be installed and on `PATH` for music playback (`discord.FFmpegPCMAudio`).

### Environment variables (`.env`, loaded via `python-dotenv`)

- `DISCORD_TOKEN` — required; bot exits immediately if missing.
- `CLIENT_ID`, `CLEM_TOKEN` — present in `.env` but not read anywhere in `clem2_0.py` currently.
- `GUILD_ID` — optional; if set, slash commands sync instantly to that one guild (`bot.tree.copy_global_to` + guild-scoped `sync`) instead of the slow global sync.
- `GOOGLE_SERVICE_ACCOUNT` — path to the Drive service account JSON (defaults to `credentials/service_account.json`).
- `DRIVE_FOLDER_ID` — target Google Drive folder for the `/drive_*` commands.

## Architecture (all in `clem2_0.py`)

The file is organized into clearly banner-commented sections, in this order: setup, persistence, automod state, music state, yt-dlp options, logging helpers, permission tiers, `on_ready`, XP/leveling, `on_message`, then command groups (admin/config, cosmetic roles, moderation, user/server info, utility, quotes, music, Google Drive, pack relay).

### Persistence

Simple JSON files under `data/`, loaded once into module-level dicts at import time and mutated in place:

- `warns.json`, `config.json` (per-guild settings, keyed by guild ID string), `playlists.json`, `notes.json`, `tags.json`, `quotes.json`, `xp.json`, plus `queue.json` for the music queue.
- `load_json`/`save_json` are the only I/O primitives; there is no locking or async I/O — writes are synchronous and happen inline in command handlers immediately after mutating the in-memory dict.
- `guild_config(guild_id)` is the standard way to get/create a guild's config sub-dict from `config_db`.
- The song queue is special-cased: `load_queue()` strips `stream_url` on load (URLs expire and must be refetched), and `save_queue()` strips it again before writing, since it's a runtime-only field.

### Permission tiers

A single tier system gates every command, defined by `_user_tier()`: `community < dj < mod < admin < owner`, derived from Discord guild permissions (not roles you assign per-command) except for `owner`, which also checks `guild.owner_id`, and `dj`, which additionally checks for a role literally named `"dj"`. Commands declare their floor with the `@require("tier")` decorator (or the `@admin_only()` / `@mod_only()` shortcuts), implemented as an `app_commands.check`. A denied attempt logs an embed via `send_log` and replies ephemerally — there's no silent failure path, so if you add a new command it should almost always carry one of these decorators.

### Logging

`send_log(guild, embed, category="log_channel")` looks up a per-guild channel ID from `config_db` (falling back to the generic `log_channel` if a specific category like `log_messages` isn't set) and sends the embed there. Categories are configured via `/setlogchannel`. `log_embed(title, description, color)` is the standard embed factory (UTC timestamp).

### Music playback

State is module-level globals: `song_queue`, `current_song`, `default_volume`, `prefetch_task`. Playback flow: `/play` resolves a search/URL via `yt_dlp` (run in an executor thread since it's blocking), appends to `song_queue`, and kicks off `play_next()` if nothing is currently playing. `play_next()` pops the queue, lazily fetches the actual stream URL if not already prefetched, starts `FFmpegPCMAudio`, and schedules itself again via the `after_play` callback — this is a self-perpetuating async chain, not a loop. `prefetch_next()` fires a background task to resolve the *next* song's stream URL while the current one plays, to hide yt-dlp latency. Autoplay (`cfg["autoplay"]`) reloads a saved playlist when the queue empties.

Note the `after_play` callback intentionally captures `guild`/`channel` rather than the original `interaction`, since interaction tokens expire after 15 minutes and would break follow-ups on long queues (see comment in `play_next`).

### Google Drive integration

`DriveBridge` is a lazy singleton (`DriveBridge.get()`) wrapping a Google service-account-authenticated Drive v3 client. Returns `None` if the credentials file is missing, so every `/drive_*` command must check for that. All Drive API calls are blocking and are dispatched via `loop.run_in_executor`.

### Adding a new slash command

Follow the existing pattern: `@bot.tree.command(name=..., description=...)`, a permission decorator (`@require(tier)`, `@admin_only()`, or `@mod_only()`) unless it's intentionally open to everyone, and — if it mutates persisted state — a `save_json(...)` call before responding. Use `interaction.response.send_message` for simple replies; use `interaction.response.defer()` + `interaction.followup.send(...)` for anything that awaits a slow external call (yt-dlp, Drive, HTTP requests) so the interaction doesn't time out.

## Data files ignored by git

Per `.gitignore`, `credentials/`, `.env`, `data/config.json`, and all of `data/*.json` are untracked (runtime/secret state). `warns.json` and `queue.json` are also explicitly ignored at the repo root pattern (redundant with `data/*.json` but kept for clarity).
