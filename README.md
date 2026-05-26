# imap2gmail

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/andthebad)
[![GitHub Release](https://img.shields.io/github/v/release/andbad/imap2gmail)](https://github.com/andbad/imap2gmail/releases)
[![GitHub commit activity](https://img.shields.io/github/commit-activity/y/andbad/imap2gmail)](https://github.com/andbad/imap2gmail/commits/main)

**DISCLAIMER: This software is entirely vibe-coded, so be gentle with me.**

A lightweight Docker container that periodically fetches emails from an external IMAP account and delivers them to Gmail.

Useful as a replacement for Gmail's **"Check mail from other accounts"** (POP3) feature, which is being discontinued.

---

## Two modes

| | `forward` (default) | `import` |
|---|---|---|
| **How it works** | IMAP fetch → re-send via SMTP | IMAP fetch → Gmail API insert |
| **Appears in Gmail as** | Forwarded message | Original email (original sender, date, headers) |
| **Setup complexity** | Simple — just a Gmail App Password | Moderate — requires a Google Cloud project |
| **Preserves original sender** | Partial (Reply-To is set) | ✅ Fully |
| **Preserves original date** | ✅ | ✅ |
| **Preserves all headers** | ❌ | ✅ |
| **Requires Google Cloud** | ❌ | ✅ |

---

## Mode: `forward` (default)

Fetches unread messages from any IMAP server and re-sends them to Gmail via SMTP.

### Quick start

**1. Create your `docker-compose.yml`:**

```yaml
services:
  imap2gmail:
    image: ghcr.io/andbad/imap2gmail:latest
    restart: unless-stopped
    environment:
      - MODE=forward
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

**2. Start:**

```bash
docker compose up -d
docker compose logs -f
```

### Gmail App Password

Gmail requires an App Password when 2FA is enabled.

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Create a new App Password (e.g. "imap2gmail")
3. Use the generated 16-character password as `SMTP_PASS`

### Environment variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `IMAP_HOST` | — | ✅ | IMAP server hostname |
| `IMAP_PORT` | `993` | | IMAP port (SSL) |
| `IMAP_USER` | — | ✅ | IMAP username / email address |
| `IMAP_PASS` | — | ✅ | IMAP password |
| `SMTP_HOST` | `smtp.gmail.com` | | SMTP server hostname |
| `SMTP_PORT` | `587` | | SMTP port (STARTTLS) |
| `SMTP_USER` | — | ✅ | SMTP username (your Gmail address) |
| `SMTP_PASS` | — | ✅ | Gmail App Password |
| `DEST` | — | ✅ | Destination email address |
| `FETCH_SPAM` | `false` | | Set to `true` to also forward the spam folder |
| `SPAM_FOLDER` | `Spam` | | Spam folder name on source server |
| `DELETE_AFTER_DAYS` | `0` | | Delete source messages older than X days (`0` = disabled) |
| `INTERVAL_SEC` | `600` | | Seconds between each check |

---

## Mode: `import`

Fetches unread messages from any IMAP server and inserts them **directly into Gmail** using the Gmail API. Emails appear as originals — original sender, date, subject, and all headers are fully preserved.

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
   - Download the JSON file

4. Configure the OAuth consent screen:
   - Navigate to **APIs & Services → OAuth consent screen**
   - Under **Test users**, click **+ Add users** and add your Gmail address

### Step 2 — Set up the credentials directory

```bash
mkdir credentials
mv ~/Downloads/client_secret_*.json credentials/credentials.json
```

### Step 3 — Authorize (one time only)

Run the authorization script. It will print a URL, ask you to open it in your browser, and then ask you to paste back the redirect URL:

```bash
docker run --rm -it \
  -v ./credentials:/credentials \
  ghcr.io/andbad/imap2gmail:latest \
  python /auth.py
```

**What to do:**

1. The script prints a long Google URL — open it in your browser
2. Sign in with your Gmail account and click **Allow**
3. Your browser will show an error page saying _"localhost refused to connect"_ — **this is expected**
4. Copy the full URL from the browser address bar (it starts with `http://localhost/...`)
5. Paste it in the terminal and press Enter
6. The script saves `token.json` in your `credentials/` directory

The token is valid indefinitely and refreshes automatically. You will never need to repeat this step unless you revoke access.

### Step 4 — Start the container

```yaml
services:
  imap2gmail:
    image: ghcr.io/andbad/imap2gmail:latest
    restart: unless-stopped
    volumes:
      - ./credentials:/credentials
    environment:
      - MODE=import
      - IMAP_HOST=imap.yourprovider.com
      - IMAP_PORT=993
      - IMAP_USER=you@yourprovider.com
      - IMAP_PASS=your_imap_password
```

```bash
docker compose up -d
docker compose logs -f
```

### Environment variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `IMAP_HOST` | — | ✅ | IMAP server hostname |
| `IMAP_PORT` | `993` | | IMAP port (SSL) |
| `IMAP_USER` | — | ✅ | IMAP username / email address |
| `IMAP_PASS` | — | ✅ | IMAP password |
| `GMAIL_CREDENTIALS_FILE` | `/credentials/credentials.json` | ✅ | Path to OAuth2 credentials JSON |
| `GMAIL_TOKEN_FILE` | `/credentials/token.json` | | Path where the OAuth2 token is stored |
| `GMAIL_LABEL_INBOX` | `true` | | Add `INBOX` label so messages appear in inbox |
| `GMAIL_LABEL_SPAM` | `SPAM` | | Gmail label applied to spam messages |
| `FETCH_SPAM` | `false` | | Set to `true` to also import the spam folder |
| `SPAM_FOLDER` | `Spam` | | Spam folder name on source server |
| `DELETE_AFTER_DAYS` | `0` | | Delete source messages older than X days (`0` = disabled) |
| `INTERVAL_SEC` | `600` | | Seconds between each check |

---

## Upgrade

```bash
docker compose pull
docker compose up -d
```

## Available tags

| Tag | Description |
|---|---|
| `latest` | Latest stable release |
| `v2.0.0` | Specific version |
| `v2.0` | Latest patch of v2.0 |

---

## License

[GNU General Public License v3.0](LICENSE)
