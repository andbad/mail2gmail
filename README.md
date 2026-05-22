<a href="https://www.buymeacoffee.com/andthebad" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>
![GitHub Release](https://img.shields.io/github/v/release/andbad/imap2gmail)
![GitHub commit activity](https://img.shields.io/github/commit-activity/y/andbad/imap2gmail)

# imap2gmail

**DISCLAIMER: This software is entirely vibe-coded, so be gentle with me.**

A lightweight Docker container that periodically fetches emails from an external IMAP account and forwards them to Gmail.

Useful as a replacement for Gmail's **"Check mail from other accounts"** (POP3) feature, which is being discontinued.

---

## Features

- Fetches unread messages from any IMAP server every N seconds
- Forwards messages to Gmail preserving original sender, date, and subject
- Forwarding banner in both plain text and HTML with original metadata
- `Reply-To` set to the original sender
- Optional: fetch and forward the spam folder (tagged `[ ** SPAM ** ]` in subject)
- Optional: auto-delete messages on source server older than X days
- Multi-arch image: `linux/amd64` and `linux/arm64`

---

## Usage

No build required. Pull the image directly from GitHub Container Registry.

**1. Create your `docker-compose.yml`:**

```yaml
services:
  imap2gmail:
    image: ghcr.io/YOUR_GITHUB_USERNAME/imap2gmail:latest
    restart: unless-stopped
    environment:
      - IMAP_HOST=imap.yourprovider.com
      - IMAP_PORT=993
      - IMAP_USER=you@yourprovider.com
      - IMAP_PASS=your_imap_password
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USER=you@gmail.com
      - SMTP_PASS=your_gmail_app_password
      - DEST=you@gmail.com
      - FETCH_SPAM=false
      - SPAM_FOLDER=Spam
      - DELETE_AFTER_DAYS=0
      - INTERVAL_SEC=600
```

**2. Start:**

```bash
docker compose up -d
docker compose logs -f
```

---

## Environment variables

| Variable             | Default          | Required | Description                                               |
|----------------------|------------------|----------|-----------------------------------------------------------|
| `IMAP_HOST`          | —                | ✅       | IMAP server hostname                                      |
| `IMAP_PORT`          | `993`            |          | IMAP port (SSL)                                           |
| `IMAP_USER`          | —                | ✅       | IMAP username / email address                             |
| `IMAP_PASS`          | —                | ✅       | IMAP password                                             |
| `SMTP_HOST`          | `smtp.gmail.com` |          | SMTP server hostname                                      |
| `SMTP_PORT`          | `587`            |          | SMTP port (STARTTLS)                                      |
| `SMTP_USER`          | —                | ✅       | SMTP username (your Gmail address)                        |
| `SMTP_PASS`          | —                | ✅       | Gmail App Password (see below)                            |
| `DEST`               | —                | ✅       | Destination email address                                 |
| `FETCH_SPAM`         | `false`          |          | Set to `true` to also forward the spam folder             |
| `SPAM_FOLDER`        | `Spam`           |          | Spam folder name on source server (`Spam`, `Junk`, etc.)  |
| `DELETE_AFTER_DAYS`  | `0`              |          | Delete source messages older than X days (`0` = disabled) |
| `INTERVAL_SEC`       | `600`            |          | Seconds between each check                                |

---

## Gmail App Password

Gmail requires an App Password when 2FA is enabled.

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Create a new App Password (e.g. "imap2gmail")
3. Use the generated 16-character password as `SMTP_PASS`

---

## Available tags

| Tag       | Description              |
|-----------|--------------------------|
| `latest`  | Latest stable release    |
| `v1.0.0`  | Specific version         |
| `v1.0`    | Latest patch of v1.0     |

---

## License

[GNU General Public License v3.0](https://github.com/andbad/imap2gmail/blob/main/LICENSE)

[buymecoffee]: https://www.buymeacoffee.com/andthebad
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/andbad/homeassistant-carwings.svg?style=for-the-badge
[commits]: https://github.com/andbad/imap2gmail/commits/main
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://github.com/indomus/forum
[license-shield]: https://img.shields.io/github/license/andbad/homeassistant-carwings.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-andbad-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/andbad/homeassistant-carwings.svg?style=for-the-badge
[releases]: https://github.com/andbad/imap2gmail/releases
[hacs-repo-badge]: https://my.home-assistant.io/badges/hacs_repository.svg


