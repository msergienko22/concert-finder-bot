# Amsterdam Concert Tracker

Single-user Telegram bot that checks for newly posted concert events in the Netherlands (Amsterdam venues + Ticketmaster NL) and notifies you when an event matches an artist from your GitHub-hosted favorites list.

## Features

- Daily automated check at a configurable time (default 09:00 Europe/Amsterdam, DST-safe)
- If the bot was offline at the scheduled time, it runs once on next startup when the last run was more than 6 hours ago (catch-up)
- Sources: Ticketmaster NL, Paradiso, Melkweg, AFAS Live, Ziggo Dome
- Case-insensitive substring matching against your artists list
- Deduping: one notification per (artist, venue, date)
- SQLite persistence for settings and notification history
- Rate limiting and retries with exponential backoff

## Setup

1. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN`.
2. Install: `pip install -r requirements.txt`
3. Run: `python main.py`
4. Send `/start` to your bot and complete onboarding (artists list URL, location NL, daily check time).

## What to do next

1. **Get a bot token** — In Telegram, open [@BotFather](https://t.me/BotFather), send `/newbot`, follow the prompts. Copy the token.
2. **Create your artists list** — Create a `.txt` file with one artist per line (e.g. in a GitHub repo). Use the **raw** URL (e.g. `https://raw.githubusercontent.com/you/repo/main/artists.txt`). You’ll paste this in the bot during onboarding.
3. **Set the token** — Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN` to the token from step 1.
4. **Run the bot** — Either:
   - **Local / Docker:** `docker compose up -d` (or `pip install -r requirements.txt` then `python main.py`).
   - **Cloud:** Follow [DEPLOY.md](DEPLOY.md) (e.g. Railway or Oracle Free).
5. **Onboard in Telegram** — Open your bot in Telegram, send `/start`, then send the artists list URL when asked. Choose NL and set your daily check time (e.g. `09:00`).
6. **Test** — Send `/run_now` to trigger a check. Use `/status` to see the last run and `/help` for all commands.

After that, the bot will run daily at your set time and message you when it finds matches.

## Running 24/7

To have the bot run always (daily checks at your set time without keeping a terminal open), use one of these:

### Option A: Docker (recommended)

On your laptop or any server with Docker installed:

```bash
# Create .env with TELEGRAM_BOT_TOKEN first, then:
docker compose up -d
```

The bot keeps running in the background and restarts automatically if it crashes. Data is stored in a Docker volume. To view logs: `docker compose logs -f`.

### Option B: Deploy to a cloud server

Run the same Docker setup on a small VPS or free-tier host so it’s always on. See **[DEPLOY.md](DEPLOY.md)** for step-by-step suggestions:

- **Railway** — Easiest: connect repo, set `TELEGRAM_BOT_TOKEN`, deploy (~$5/mo after trial).
- **Oracle Cloud Free Tier** — Free always-on VM: sign up, create VM, SSH, Docker, `docker compose up -d`.
- **VPS (Hetzner, DigitalOcean, etc.)** — SSH in, clone repo, `.env`, then `docker compose up -d` or the systemd service.

### Option C: Systemd (Linux server or Raspberry Pi)

On a Linux machine that’s always on (e.g. home server, Raspberry Pi):

1. Copy the unit file and edit paths/user:
   ```bash
   sudo cp deploy/concert-tracker.service /etc/systemd/system/
   sudo nano /etc/systemd/system/concert-tracker.service
   ```
   Set `User`, `WorkingDirectory`, `EnvironmentFile`, and `ExecStart` (path to your Python and `main.py`).

2. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable concert-tracker
   sudo systemctl start concert-tracker
   ```
3. Logs: `journalctl -u concert-tracker -f`

## Commands

- `/start` — Onboarding or show settings
- `/help` — Commands and how matching works
- `/settings` — Current settings
- `/set_artists_url <url>` — Set GitHub .txt artists list URL
- `/set_time <HH:MM>` — Daily check time (Europe/Amsterdam)
- `/set_location NL` — Location (MVP: NL only)
- `/run_now` — Trigger a full run manually
- `/status` — Last run time, counts, errors
- `/reset_history` — Clear dedupe history (with confirmation)

## Artists list

Host a plain text file (e.g. on GitHub) with one artist per line. Use the raw URL (e.g. `https://raw.githubusercontent.com/.../artists.txt`).
