# PRD: Amsterdam Concert Tracker — Single‑User Telegram Bot

**Document owner:** (you)
**Version:** 1.0
**Last updated:** 2026-02-15 (Europe/Amsterdam)
**Status:** Draft (implementation-ready)

---

## 1) Summary

Build a **single-user Telegram bot** that checks for **newly posted concert events in the Netherlands** (focus: **Amsterdam venues + Ticketmaster NL**) and **notifies one Telegram user** when an event matches an artist from a **favorite artists list** hosted as a **GitHub .txt** file (one artist per line).

Core characteristics:

* **Daily automated check** at a configurable time (default **~09:00 Europe/Amsterdam**, DST-safe)
* **Sources monitored**: Ticketmaster NL + venue websites (**Paradiso, Melkweg, AFAS Live, Ziggo Dome**)
* **Vague matching**: case-insensitive **substring contains**
* **Deduping**: notify only once per **(artist, venue, date)** (date can be **TBA**)
* **Persistence**: **SQLite** for settings + notification history
* **Operational reliability**: rate limiting + retries/backoff

---

## 2) Problem Statement

Concerts are announced across multiple channels (Ticketmaster and venue sites). Manually checking each site daily for favorite artists is time-consuming and easy to miss. A lightweight bot that proactively notifies the user about matches reduces effort and improves discovery.

---

## 3) Goals and Success Metrics

### Goals

1. Detect newly posted or newly discoverable events from the monitored sources.
2. Match events against a user-supplied favorite artists list with forgiving logic.
3. Notify the user **once** per match key and avoid repeated spam across days.
4. Run reliably as a daily scheduled task in **Europe/Amsterdam** time.

### Success metrics (MVP)

* **Functional**

  * ≥ 95% of daily runs complete successfully (no crash, graceful handling of partial failures).
  * 0 duplicate notifications for the same `(artist, venue, date)` during a 30-day period (unless user resets history).
* **User experience**

  * Setup completed in < 2 minutes.
  * Notifications contain enough info to act: artist/title, venue, date or TBA, and a link.

---

## 4) Non-Goals (Out of Scope for MVP)

* Multi-user support, subscriptions, or group chat support.
* Geo filtering beyond “Netherlands” (no radius/city coordinates).
* Perfect entity resolution (“The National” vs “National”, false positives).
* Ticket purchasing, price tracking, or inventory monitoring.
* Push notifications for updates to previously notified events (optional later).

---

## 5) Users & Personas

### Primary user (single user)

* A concert-goer based in NL who cares about announcements and presales.
* Wants a simple daily digest of matches; no need for complex UI.

### Constraints

* Single Telegram user ID authorized.
* Bot should ignore / deny other users by default.

---

## 6) Assumptions & Dependencies

* The artists list is accessible via HTTPS from a GitHub-hosted raw URL and formatted as:

  * plain text `.txt`
  * one artist name per line
* Ticketmaster NL and venue sites expose event listings in a parseable form (HTML or API).
* The deployment environment supports:

  * persistent filesystem for SQLite
  * outbound HTTPS
  * scheduled tasks or an always-on process (preferred)

---

## 7) User Experience Overview

### First run / onboarding flow

1. User sends `/start`
2. Bot explains purpose and asks sequentially for:

   1. **Artists list URL** (GitHub `.txt`)
   2. **Location**: default “Netherlands” (NL); for MVP only NL is supported
   3. **Daily check time**: default **09:00** in Europe/Amsterdam
3. Bot confirms settings and shows next run time + supported sources.

### Day-to-day experience

* At scheduled time daily:

  1. bot fetches the artists list
  2. checks each source
  3. sends a message per match (or a digest—see Notifications section for approach)
* User can update settings anytime via commands.

---

## 8) Functional Requirements

### 8.1 Telegram Bot Commands

**Required**

* `/start`

  * If first run: onboarding wizard
  * Else: show current settings + next run time + quick actions
* `/help`

  * Show commands and how matching works
* `/settings`

  * Show current settings (artists URL, location, check time)
* `/set_artists_url <url>`

  * Validate URL format and fetch once to confirm it’s reachable and non-empty
* `/set_time <HH:MM>`

  * Validate time and store it in Europe/Amsterdam
* `/set_location NL`

  * For MVP accept only NL; store anyway for future extensibility
* `/run_now`

  * Manually triggers a full run (fetch artists → check sources → notify)
* `/status`

  * Show last run timestamp, success/failure, counts: events scanned, matches found, notifications sent
* `/reset_history`

  * Clears dedupe history (with a confirmation step)

**Nice-to-have**

* `/sources` → list monitored sources
* `/dry_run` → run and report matches without sending notifications (useful for debugging)
* `/export_history` → send a small CSV/text summary of notified keys

---

### 8.2 Settings Management

**Settings stored in SQLite**

* `artists_list_url` (string, required)
* `location` (string, default `NL`)
* `check_time_local` (string `HH:MM`, default `09:00`)
* `timezone` (string, fixed `Europe/Amsterdam`)
* `authorized_user_id` (int, set on first successful /start or via env var)

**Behavior**

* Settings can be updated any time.
* Changes take effect from the next scheduled run (except `/run_now` uses current settings immediately).

---

### 8.3 Sources to Monitor

**MVP sources**

1. **Ticketmaster (NL)**
2. **Venue sites**

   * Paradiso
   * Melkweg
   * AFAS Live
   * Ziggo Dome

**Implementation requirement**

* Each source is implemented as a “connector” with a standard interface:

  * `fetch_events() -> List[Event]`
* Connectors must support:

  * retries/backoff
  * basic rate limiting
  * stable parsing & defensive coding

---

### 8.4 Event Data Model (normalized)

Each fetched event should be normalized into:

* `source` (enum/string: ticketmaster, paradiso, melkweg, afaslive, ziggodome)
* `title` (string) — headline as shown on site
* `venue` (string) — normalized venue name if possible
* `date_raw` (string) — whatever the site shows (“TBA”, “2026-04-01”, “April 2026”)
* `date_normalized` (string) — one of:

  * ISO date `YYYY-MM-DD` when confidently known
  * `TBA` when unknown/placeholder
  * optionally `YYYY-MM` if only month is known (**MVP can map this to `TBA` unless you want a third state**)
* `url` (string) — canonical event link
* `status` (string, optional) — presale/placeholder/confirmed if detectable
* `fetched_at` (timestamp)

---

### 8.5 Matching Logic

**Matching method (as specified)**

* Case-insensitive substring match:

  * For each favorite artist line `A`:

    * match if `A` is contained within the event title (or event artist field if available)
* Example:

  * Favorite: `Taylor Swift`
  * Event title: `Kanye West and Taylor Swift`
  * ✅ match

**Normalization**

* Apply `casefold()` (or equivalent) to handle case-insensitive matching robustly.
* Trim whitespace on artist lines; ignore empty lines.
* Treat all event “states” as valid matches:

  * TBA dates
  * placeholders
  * presales
  * confirmed

**Tradeoff accepted (MVP)**

* False positives are possible and acceptable (e.g., short names matching parts of words). A future iteration can add optional word-boundary matching toggles.

---

### 8.6 Deduping & Notification Rules

**Dedup key**

* Notify **only once** per `(artist_from_list, venue, date_normalized)`.

Where:

* `artist_from_list` = the artist string that matched (the line from the list)
* `venue` = normalized venue (or best available from the event page)
* `date_normalized` = `YYYY-MM-DD` or `TBA`

**Notes**

* If an event changes from `TBA` to a real date, the key changes → **a new notification is allowed** (it is a new `(artist, venue, date)` combo).
* If multiple sources list the same event, dedupe still applies based on the key (even if URLs differ).

**History storage**

* Store enough information to prevent repeats:

  * the key fields
  * the first time seen and notified
  * event URL and title for reference

---

### 8.7 Notification Content

**Notification message includes:**

* Matched artist (from favorites)
* Event title
* Venue
* Date (or “TBA”)
* Source name
* Link

**Example format (simple)**

> 🎵 Match found: **Taylor Swift**
> **Event:** Kanye West and Taylor Swift
> **Venue:** Ziggo Dome
> **Date:** TBA
> **Source:** Ticketmaster NL
> 🔗 <link>

**Notification batching (decision for MVP)**

* Default: send **one message per match**.
* If > N matches in a run (e.g., N=10), send a **digest summary** plus individual links to reduce spam (nice-to-have, but recommended).

---

### 8.8 Scheduling

**Requirement**

* Runs automatically **daily** at configured time in **Europe/Amsterdam**, DST-safe.

**Behavior**

* Scheduler triggers at local time; handles DST transitions correctly.
* If the bot was offline at scheduled time:

  * On next start, run immediately if last run missed by > X hours (e.g., 6h), or run at next scheduled time (implementation choice; document it).

---

### 8.9 Artists List Fetch Rule

**Requirement**

* Bot fetches the artists file **daily before** checking events.

**Behavior**

* On every scheduled run (and `/run_now`), do:

  1. Fetch artists list URL
  2. Parse and validate
  3. Proceed to fetch events
* If fetch fails:

  * Use last successfully cached list if available (recommended) OR fail the run (less reliable)
  * MVP recommendation: **fallback to cached** and notify user that the list fetch failed.

---

### 8.10 Reliability: Rate Limiting + Retries/Backoff

**Minimum**

* Per-source rate limiting (e.g., 1 request/sec, configurable)
* Retries for transient failures:

  * retry 2–4 times with exponential backoff (e.g., 1s, 2s, 4s, 8s)
* Timeouts:

  * connect timeout (e.g., 5–10s)
  * read timeout (e.g., 15–30s)
* Identify bot responsibly with a User-Agent string (for venue scraping)

**Failure handling**

* If one source fails, the run continues for other sources.
* At end of run, bot reports partial failure in `/status` and optionally sends a short warning message (configurable).

---

## 9) Data Persistence (SQLite)

### 9.1 Tables

**`settings`**

* `key` TEXT PRIMARY KEY
* `value` TEXT NOT NULL
* Example keys:

  * `artists_list_url`
  * `location`
  * `check_time_local`
  * `timezone`
  * `authorized_user_id`
  * `last_run_at`
  * `last_run_status`
  * `last_run_summary_json` (optional)

**`notification_history`**

* `id` INTEGER PRIMARY KEY AUTOINCREMENT
* `artist` TEXT NOT NULL
* `venue` TEXT NOT NULL
* `date_normalized` TEXT NOT NULL  -- `YYYY-MM-DD` or `TBA`
* `event_title` TEXT
* `event_url` TEXT
* `source` TEXT
* `first_seen_at` DATETIME NOT NULL
* `notified_at` DATETIME NOT NULL
* Unique index on `(artist, venue, date_normalized)`

**Optional: `runs`** (recommended for debugging)

* `id` INTEGER PK
* `started_at`, `finished_at`
* `status` (success/partial_failure/failure)
* `events_scanned_total`
* `matches_total`
* `notifications_sent`
* `errors_json` (per source)

### 9.2 Dedup Queries (conceptual)

* Before sending a notification, check:

  * Does `(artist, venue, date_normalized)` exist in `notification_history`?
  * If not, insert and notify.

---

## 10) Security & Access Control

* Bot is **single-user**:

  * Store `authorized_user_id`
  * If any other user messages the bot:

    * respond politely: “This bot is private.”
    * do not reveal settings or data
* Store Telegram bot token via environment variable/config secret (never in DB).

---

## 11) Observability & Supportability

**Logging**

* Per run:

  * start/end timestamps
  * per source: requests made, events parsed, parse errors
  * matches found and notified
* Log levels: INFO, WARNING, ERROR

**User-facing status**

* `/status` should include:

  * last run time (local)
  * last run outcome
  * number of events scanned per source
  * number of matches + number notified
  * last error summary if any

---

## 12) Edge Cases & Handling

1. **Artists list URL is unreachable**

   * Use cached list if available; warn user.
2. **Artists list contains duplicates / empty lines**

   * Deduplicate artists and ignore blanks.
3. **Event has no date or ambiguous date**

   * Store `date_normalized = TBA`.
4. **Venue missing / inconsistent naming**

   * Use connector default venue name (e.g., Paradiso connector sets venue “Paradiso” if not explicitly present).
5. **Event title includes multiple artists**

   * Substring match should still trigger.
6. **Site HTML changes**

   * Connector should fail gracefully and not crash full run.
7. **Too many matches in one day**

   * Optional digest fallback to reduce spam.

---

## 13) UX Copy Requirements (tone)

* Polite, short, and actionable.
* Clear prompts during onboarding:

  * “Send the URL to your GitHub-hosted .txt list (one artist per line).”
  * “Daily check time? Send HH:MM (Europe/Amsterdam). Default is 09:00.”
* When errors occur: explain what happened and what was done (retry used? cached list used?).

---

## 14) Acceptance Criteria (MVP)

**Setup**

* [ ] `/start` triggers onboarding if settings missing
* [ ] User can set artists list URL, NL location, and check time
* [ ] Settings persist across restarts

**Daily run**

* [ ] At configured time (Europe/Amsterdam), bot fetches artists list then checks all sources
* [ ] Matching is case-insensitive substring match
* [ ] Matches trigger notification with required fields and link
* [ ] Dedupe prevents repeated notifications for same `(artist, venue, date_normalized)`

**Robustness**

* [ ] Per-source failures do not break the entire run
* [ ] Retries/backoff and basic rate limiting are present
* [ ] SQLite stores notification history and prevents duplicates

**Security**

* [ ] Only the authorized Telegram user receives notifications and can run commands

---

## 15) Implementation Notes (Guidance, not requirements)

* Recommended structure:

  * `bot/` (Telegram handlers)
  * `scheduler/` (daily job)
  * `sources/` (connectors per site)
  * `storage/` (SQLite repository)
  * `matcher/` (matching + dedupe)
* Prefer official APIs where available; otherwise scrape responsibly.
* Keep connectors isolated so a site change only affects one module.

---

## 16) Risks & Mitigations

* **Risk:** Venue HTML changes break scraping
  **Mitigation:** Connector isolation + monitoring via `/status` + quick patchability
* **Risk:** Rate limits / blocking
  **Mitigation:** Conservative request pace, caching, retries, and user-agent identification
* **Risk:** False positives due to substring matching
  **Mitigation:** Accept for MVP; add optional strict matching mode later
* **Risk:** Ticketmaster access constraints
  **Mitigation:** Use official API if feasible; otherwise resilient scraping with backoff

---

## 17) Open Questions (recorded for later, not blocking MVP)

1. Ticketmaster NL: should implementation use an official API key or scraping only?
2. Notification style: always per-match, or default daily digest?
3. Should the bot notify on “updates” (e.g., TBA → real date) separately, or rely solely on dedupe key changes (current PRD allows new notification due to key change)?
4. Should the bot cache fetched venue pages/events to reduce load?

---

If you want, I can also produce:

* a concrete **SQLite schema** (DDL statements),
* a command-by-command **Telegram conversation script** (exact bot messages),
* or a suggested **module/API design** for connectors and the scheduler.
