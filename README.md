# mail2gmail

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/andthebad) [![GitHub Release](https://img.shields.io/github/v/release/andbad/mail2gmail)](https://github.com/andbad/mail2gmail/releases) [![GitHub commit activity](https://img.shields.io/github/commit-activity/y/andbad/mail2gmail)](https://github.com/andbad/mail2gmail/commits/main)

**DISCLAIMER: This software is entirely vibe-coded, so be gentle with me.**

A lightweight Docker container that periodically fetches emails from an external IMAP or POP3 account and delivers them to Gmail.

Useful as a replacement for Gmail's **"Check mail from other accounts"** (POP3) feature, which is being discontinued.

> **Migrating from imap2gmail (v2)?** All existing `IMAP_*` environment variables continue to work unchanged. See the [migration note](#migrating-from-imap2gmail-v2).

---

## Two modes, two protocols

|                               | `forward` (default)                | `import`                                        |
| ----------------------------- | ---------------------------------- | ----------------------------------------------- |
| **How it works**              | Fetch → re-send via SMTP           | Fetch → Gmail API insert                        |
| **Appears in Gmail as**       | Forwarded message                  | Original email (original sender, date, headers) |
| **Setup complexity**          | Simple — just a Gmail App Password | Moderate — requires a Google Cloud project      |
| **Preserves original sender** | Partial (Reply-To is set)          | ✅ Fully                                         |
| **Preserves original date**   | ✅                                  | ✅                                               |
| **Preserves all headers**     | ❌                                  | ✅                                               |
| **Forwards attachments**      | ✅                                  | ✅                                               |
| **Requires Google Cloud**     | ❌                                  | ✅                                               |

Both modes support **IMAP** and **POP3** as the source protocol (set via `SOURCE_PROTOCOL`).

Both modes support **IMAP** and **POP3** as the source protocol (set via `SOURCE_PROTOCOL`).

---

## Mode: `forward` (default)

Fetches unread messages and re-sends them to Gmail via SMTP. Attachments are included in the forwarded message.

### Quick start — IMAP

```yaml
services:
  mail2gmail:
    image: ghcr.io/andbad/mail2gmail:latest
    restart: unless-stopped
    environment:
      - TZ=Europe/Rome              # set to your local timezone
      - MODE=forward
      - SOURCE_PROTOCOL=imap        # default; can be omitted
      - IMAP_HOST=imap.yourprovider.com
      - IMAP_PORT=993
      - IMAP_USER=you@yourprovider.com
      - IMAP_PASS=your_imap_password
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USER=you@gmail.com
      - SMTP_PASS=your_gmail_app_password
      - DEST=you@gmail.com
```

### Quick start — POP3

```yaml
services:
  mail2gmail:
    image: ghcr.io/andbad/mail2gmail:latest
    restart: unless-stopped
    volumes:
      - ./state:/state              # persist seen Message-IDs across restarts
    environment:
      - TZ=Europe/Rome              # set to your local timezone
      - MODE=forward
      - SOURCE_PROTOCOL=pop3
      - POP3_HOST=pop.yourprovider.com
      - POP3_PORT=995
      - POP3_USER=you@yourprovider.com
      - POP3_PASS=your_pop3_password
      - POP3_STATE_FILE=/state/pop3_seen.json
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USER=you@gmail.com
      - SMTP_PASS=your_gmail_app_password
      - DEST=you@gmail.com
```

```
docker compose up -d
docker compose logs -f
```

### Gmail App Password

Gmail requires an App Password when 2FA is enabled.

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Create a new App Password (e.g. "mail2gmail")
3. Use the generated 16-character password as `SMTP_PASS`

### Environment variables — `forward` mode

| Variable             | Default               | Required | Description                                                                                                                                          |
| -------------------- | --------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TZ`                 | —                     |          | Container timezone (e.g. `Europe/Rome`). Affects log timestamps.                                                                                     |
| `SOURCE_PROTOCOL`    | `imap`                |          | `imap` or `pop3`                                                                                                                                     |
| `IMAP_HOST`          | —                     | ✅        | IMAP server hostname (also used as POP3 host if `POP3_HOST` is not set)                                                                              |
| `IMAP_PORT`          | `993` / `995`         |          | Port (default depends on protocol)                                                                                                                   |
| `IMAP_USER`          | —                     | ✅        | Username / email address                                                                                                                             |
| `IMAP_PASS`          | —                     | ✅        | Password                                                                                                                                             |
| `POP3_HOST`          | —                     |          | POP3 server hostname (overrides `IMAP_HOST` when `SOURCE_PROTOCOL=pop3`)                                                                             |
| `POP3_PORT`          | `995`                 |          | POP3 port                                                                                                                                            |
| `POP3_USER`          | —                     |          | POP3 username (overrides `IMAP_USER`)                                                                                                                |
| `POP3_PASS`          | —                     |          | POP3 password (overrides `IMAP_PASS`)                                                                                                                |
| `POP3_STATE_FILE`    | `/tmp/pop3_seen.json` |          | Path for storing seen Message-IDs (mount a volume to persist across restarts)                                                                        |
| `SMTP_HOST`          | `smtp.gmail.com`      |          | SMTP server hostname                                                                                                                                 |
| `SMTP_PORT`          | `587`                 |          | SMTP port (STARTTLS)                                                                                                                                 |
| `SMTP_USER`          | —                     | ✅        | SMTP username (your Gmail address)                                                                                                                   |
| `SMTP_PASS`          | —                     | ✅        | Gmail App Password                                                                                                                                   |
| `DEST`               | —                     | ✅        | Destination email address                                                                                                                            |
| `FETCH_SPAM`         | `false`               |          | Also forward the spam folder (IMAP only)                                                                                                             |
| `SPAM_FOLDER`        | `Spam`                |          | Spam folder name on source server (IMAP only)                                                                                                        |
| `DELETE_AFTER_DAYS`  | `0`                   |          | Delete **seen** source messages older than X days (`0` = disabled). IMAP: server-side delete. POP3: deletes from server and removes from state file. |
| `INTERVAL_SEC`       | `600`                 |          | Seconds between each check                                                                                                                           |
| `RETRY_MAX_ATTEMPTS` | `5`                   |          | Max connection attempts before giving up for this cycle                                                                                              |
| `RETRY_WAIT_MIN`     | `10`                  |          | Minimum seconds to wait between retries                                                                                                              |
| `RETRY_WAIT_MAX`     | `120`                 |          | Maximum seconds to wait between retries (exponential backoff)                                                                                        |

---

## Mode: `import`

Fetches unread messages and inserts them **directly into Gmail** using the Gmail API. Emails appear as originals — original sender, date, subject, and all headers are fully preserved.

### Setup overview

1. Create a Google Cloud project and enable the Gmail API
2. Download `credentials.json`
3. Run the one-time authorization script to generate `token.json`
4. Start the container normally

### Step 1 — Create a Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project (or select an existing one).

2. Enable the Gmail API:
   - Navigate to **APIs & Services → Library**
   - Search for "Gmail API" and click **Enable**

3. Create OAuth2 credentials:
   - Navigate to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth client ID**
   - Application type: **Desktop app** (important: not "Web application")
   - Give it a name (e.g. "mail2gmail") and click **Create**
   - Click **Download JSON** and save the file

4. Add yourself as a test user:
   - Navigate to **APIs & Services → OAuth consent screen**
   - Under **Test users**, click **+ Add users**
   - Add the Gmail address you want to import emails into
   - Click **Save**

### Step 2 — Set up the credentials directory

```
mkdir credentials
mv ~/Downloads/client_secret_*.json credentials/credentials.json
```

### Step 3 — Authorize (one time only)

```
docker run --rm -it \
  -v ./credentials:/credentials \
  ghcr.io/andbad/mail2gmail:latest \
  python /auth.py
```

The script will print a long Google URL. Follow these steps:

1. Copy the URL and open it in your browser
2. Sign in with your Gmail account and click **Allow**
3. Your browser will show an error page — *"localhost refused to connect"* — **this is expected and normal**
4. Copy the **full URL** from the browser address bar (starts with `http://localhost/?state=...&code=...`)
5. Paste it into the terminal and press Enter

The script saves `token.json` in your `credentials/` directory. The token refreshes automatically.

> **Note:** the `credentials/` directory must never be committed to version control. Add it to your `.gitignore`.

### Step 4 — Start the container

**IMAP source:**

```yaml
services:
  mail2gmail:
    image: ghcr.io/andbad/mail2gmail:latest
    restart: unless-stopped
    volumes:
      - ./credentials:/credentials
    environment:
      - TZ=Europe/Rome              # set to your local timezone
      - MODE=import
      - SOURCE_PROTOCOL=imap        # default; can be omitted
      - IMAP_HOST=imap.yourprovider.com
      - IMAP_PORT=993
      - IMAP_USER=you@yourprovider.com
      - IMAP_PASS=your_imap_password
```

**POP3 source:**

```yaml
services:
  mail2gmail:
    image: ghcr.io/andbad/mail2gmail:latest
    restart: unless-stopped
    volumes:
      - ./credentials:/credentials
      - ./state:/state              # required — see note below
    environment:
      - TZ=Europe/Rome              # set to your local timezone
      - MODE=import
      - SOURCE_PROTOCOL=pop3
      - POP3_HOST=pop.yourprovider.com
      - POP3_PORT=995
      - POP3_USER=you@yourprovider.com
      - POP3_PASS=your_pop3_password
      - POP3_STATE_FILE=/state/pop3_seen.json
```

> **Important — mount the state volume when using POP3.** Unlike IMAP (which uses server-side `\Seen` flags), POP3 tracks already-processed
> messages in a local file (`POP3_STATE_FILE`). If that file is lost — e.g. the
> container is recreated without a volume — all messages will be re-downloaded and
> re-inserted into Gmail. Gmail API will deduplicate by Message-ID, so no actual
> duplicates will appear in your inbox, but the extra round-trips waste API quota.
> Always mount a persistent volume for `POP3_STATE_FILE`.

```
docker compose up -d
docker compose logs -f
```

### Environment variables — `import` mode

| Variable                 | Default                         | Required | Description                                                                                                                                          |
| ------------------------ | ------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TZ`                     | —                               |          | Container timezone (e.g. `Europe/Rome`). Affects log timestamps.                                                                                     |
| `SOURCE_PROTOCOL`        | `imap`                          |          | `imap` or `pop3`                                                                                                                                     |
| `IMAP_HOST`              | —                               | ✅        | Source server hostname                                                                                                                               |
| `IMAP_PORT`              | `993` / `995`                   |          | Port                                                                                                                                                 |
| `IMAP_USER`              | —                               | ✅        | Username                                                                                                                                             |
| `IMAP_PASS`              | —                               | ✅        | Password                                                                                                                                             |
| `POP3_HOST`              | —                               |          | POP3 hostname override                                                                                                                               |
| `POP3_PORT`              | `995`                           |          | POP3 port override                                                                                                                                   |
| `POP3_USER`              | —                               |          | POP3 username override                                                                                                                               |
| `POP3_PASS`              | —                               |          | POP3 password override                                                                                                                               |
| `POP3_STATE_FILE`        | `/tmp/pop3_seen.json`           |          | Seen Message-ID state (mount a volume to persist)                                                                                                    |
| `GMAIL_CREDENTIALS_FILE` | `/credentials/credentials.json` | ✅        | Path to OAuth2 credentials JSON                                                                                                                      |
| `GMAIL_TOKEN_FILE`       | `/credentials/token.json`       |          | Path where the OAuth2 token is stored                                                                                                                |
| `GMAIL_LABEL_INBOX`      | `true`                          |          | Add `INBOX` label so messages appear in inbox                                                                                                        |
| `GMAIL_LABEL_SPAM`       | `SPAM`                          |          | Gmail label applied to spam messages                                                                                                                 |
| `FETCH_SPAM`             | `false`                         |          | Also import the spam folder (IMAP only)                                                                                                              |
| `SPAM_FOLDER`            | `Spam`                          |          | Spam folder name on source server (IMAP only)                                                                                                        |
| `DELETE_AFTER_DAYS`      | `0`                             |          | Delete **seen** source messages older than X days (`0` = disabled). IMAP: server-side delete. POP3: deletes from server and removes from state file. |
| `INTERVAL_SEC`           | `600`                           |          | Seconds between each check                                                                                                                           |
| `RETRY_MAX_ATTEMPTS`     | `5`                             |          | Max connection attempts before giving up for this cycle                                                                                              |
| `RETRY_WAIT_MIN`         | `10`                            |          | Minimum seconds to wait between retries                                                                                                              |
| `RETRY_WAIT_MAX`         | `120`                           |          | Maximum seconds to wait between retries (exponential backoff)                                                                                        |

---

## Migrating from imap2gmail (v2)

No changes required. All `IMAP_*` environment variables and `MODE` values are fully backward-compatible. The only new required step is renaming the image reference in your `docker-compose.yml`:

```
# Before
image: ghcr.io/andbad/imap2gmail:latest

# After
image: ghcr.io/andbad/mail2gmail:latest
```

---

## Migrating from imap2gmail (v2)

No changes required. All `IMAP_*` environment variables and `MODE` values are fully backward-compatible. The only new required step is renaming the image reference in your `docker-compose.yml`:

```yaml
# Before
image: ghcr.io/andbad/imap2gmail:latest

# After
image: ghcr.io/andbad/mail2gmail:latest
```

---

## Upgrade

```
docker compose pull
docker compose up -d
```

## Available tags

| Tag      | Description           |
| -------- | --------------------- |
| `latest` | Latest stable release |
| `v3.2.0` | Specific version      |
| `v3.2`   | Latest patch of v3.2  |

---

## License

[GNU General Public License v3.0](https://github.com/andbad/mail2gmail/blob/main/LICENSE)
