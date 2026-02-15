# Where to deploy (24/7)

Here are three solid options, from easiest to free-but-more-setup.

---

## 1. Railway — easiest, ~$5/month

**Best if:** You want one-click deploy and don’t mind a few dollars per month.

- Connect GitHub, push code, set `TELEGRAM_BOT_TOKEN`, done.
- Supports Docker: Railway will use your `Dockerfile` if present.
- **Cost:** Free trial credit, then Hobby plan (~$5/mo) is usually enough for this bot.
- **Docs:** [railway.app](https://railway.app) → New Project → Deploy from GitHub.

**Steps (short):**

1. Create a [Railway](https://railway.app) account and a new project.
2. “Deploy from GitHub” → select this repo.
3. Add variable: `TELEGRAM_BOT_TOKEN` = your token.
4. Optional: add `DATABASE_PATH` (e.g. `/data/bot.db`) if Railway gives you a persistent volume and you mount it; otherwise their ephemeral disk is fine for SQLite (data resets on redeploy).
5. Deploy. The bot will run 24/7.

---

## 2. Oracle Cloud Free Tier — free, always-on VM

**Best if:** You want always-on for free and are okay with a bit of setup (SSH, Docker).

- You get **always-free** VMs (e.g. 2× AMD micro or ARM instances) that don’t expire.
- Card required for signup; Always Free resources are not charged.
- **Cost:** $0 for the free tier.

**Steps (short):**

1. Sign up: [oracle.com/cloud/free](https://www.oracle.com/cloud/free).
2. Create an Always Free VM (e.g. Ubuntu 22.04) in your preferred region.
3. SSH in, install Docker:  
   `curl -fsSL https://get.docker.com | sh`
4. Clone your repo (or upload the project), create `.env` with `TELEGRAM_BOT_TOKEN`.
5. Run:  
   `docker compose up -d`  
   (from the project directory that contains `docker-compose.yml` and `.env`).

The bot runs 24/7. To survive reboots, you can add a simple systemd service that runs `docker compose up -d` on boot, or use Docker’s restart policy (already in `docker-compose.yml`).

---

## 3. Small VPS (Hetzner, DigitalOcean, etc.) — cheap and full control

**Best if:** You like having a real server and don’t mind a small monthly fee.

- **Hetzner:** from ~€4/mo, good value in the EU (fits “Europe/Amsterdam” well).
- **DigitalOcean / Linode / Vultr:** from ~$5–6/mo.
- Same idea as Oracle: SSH in, install Docker, clone repo, `.env`, `docker compose up -d`.

---

## Summary

| Option           | Cost        | Ease        | Best for                    |
|------------------|------------|------------|-----------------------------|
| **Railway**      | ~$5/mo     | Easiest     | Quick deploy, minimal ops   |
| **Oracle Free**  | $0         | Medium      | Free 24/7, some setup       |
| **VPS (e.g. Hetzner)** | ~€4/mo | Medium      | Full control, EU location   |

**Recommendation:** Start with **Railway** if you want it running in a few minutes; switch to **Oracle Cloud Free** if you prefer $0 and are fine with a one-time VM + Docker setup.
