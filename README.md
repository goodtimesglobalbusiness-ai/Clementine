# Clementine
Clementine Discord Full Spectrum Admin that doubles down in communit awareness.

Clementine excels in user functionality at all levels of discord membership

# Clementine — A Modular, Production‑Ready Discord Bot

Clementine is a modern Discord bot built for reliability, modularity, and 24/7 uptime.  
It includes a full operational stack:

- Slash‑command Discord bot (`bot.py`)
- Clean restart controller (`rc.ps1`)
- Self‑healing watchdog with timestamped logging + rotation (`watchdog.ps1`)
- Optional Windows Service integration for automatic startup (`service-install.ps1`)

Clementine is designed for developers who want a bot that **never goes down**, even if Discord, Python, or Windows misbehaves.

---

## Features

### Discord Bot
- Slash‑command architecture  
- Modular command structure  
- Environment‑based configuration  
- Clean shutdown and restart support  

### Operational Tools
- **rc.ps1** — Safely restarts the bot, kills stale processes, and writes a PID file  
- **watchdog.ps1** — Monitors the bot and restarts it automatically  
- **Log rotation** — Keeps logs small and organized  
- **Windows Service support** — Run Clementine in the background with auto‑start  

---

## Folder Structure

```
Clementine/
│
├── bot.py
├── .env
│
├── rc.ps1
├── watchdog.ps1
├── watchdog.log
│
├── service-install.ps1
└── service-uninstall.ps1
```

---

## Setup

### 1. Install Dependencies

```
pip install -r requirements.txt
```

Make sure your `.env` file contains:

```
DISCORD_TOKEN=your_token_here
```

---

## Running the Bot (Development Mode)

```
python bot.py
```

---

## Restarting the Bot (Safe Mode)

Use the restart controller:

```
.\rc.ps1
```

This script:

- Stops any existing Clementine process  
- Removes stale PID files  
- Starts a fresh instance  
- Writes the new PID to `clementine.pid`  

---

## Watchdog (Auto‑Restart System)

The watchdog monitors Clementine every 5 seconds and restarts it if:

- The bot crashes  
- The PID file is missing  
- The process is dead  
- The system restarts  

### Start watchdog manually:

```
.\watchdog.ps1
```

### Logging

The watchdog writes timestamped logs to:

```
watchdog.log
```

When the log reaches **5 MB**, it rotates:

```
watchdog.log.1
watchdog.log.2
...
watchdog.log.5
```

Oldest logs are deleted automatically.

---

## Running Clementine as a Windows Service

This is the recommended production setup.

### Install the service:

```
.\service-install.ps1
```

This creates:

- Service name: **ClementineWatchdog**
- Startup type: **Automatic**
- Behavior: Runs watchdog → watchdog runs bot

### Start the service:

```
Start-Service ClementineWatchdog
```

### Stop the service:

```
Stop-Service ClementineWatchdog
```

### Check status:

```
Get-Service ClementineWatchdog
```

### Uninstall the service:

```
.\service-uninstall.ps1
```

---

## Logs

### Watchdog Logs
```
watchdog.log
watchdog.log.1
watchdog.log.2
...
```

### Bot Logs (optional)
If you enable logging in `rc.ps1`, Clementine can also write:

```
clementine.log
```

---

## Uptime Strategy

Clementine is designed for **continuous operation**:

1. `watchdog.ps1` ensures the bot is always running  
2. Log rotation prevents disk bloat  
3. Windows Service ensures startup on boot  
4. `rc.ps1` guarantees clean restarts with no duplicate processes  

This stack gives Clementine **true production reliability**.

---

## Contributing

Pull requests are welcome.  
For major changes, open an issue to discuss what you’d like to modify.

---

## License

MIT License  
Copyright (c) 2026

