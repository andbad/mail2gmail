# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-05-24

### Added
- **New `import` mode** (`MODE=import`): emails are inserted directly into Gmail via the Gmail API (`messages.insert`), preserving all original headers — sender, recipient, date, subject, and full MIME structure — exactly as received. No SMTP involved.
- `import.py`: new script implementing the Gmail API import flow.
- OAuth2 authentication flow with automatic token refresh. Token is persisted to disk and reused across restarts.
- Deduplication: messages that are already in Gmail (detected via Gmail API 400 response on duplicate Message-ID) are skipped and marked as seen on the source server.
- `GMAIL_CREDENTIALS_FILE` and `GMAIL_TOKEN_FILE` environment variables to configure OAuth2 credentials paths.
- `GMAIL_LABEL_INBOX` variable to control whether imported messages are added to the inbox.
- `GMAIL_LABEL_SPAM` variable to set the Gmail label applied to spam messages in import mode.
- `MODE` environment variable to select between `forward` (default) and `import`.
- Google API dependencies (`google-api-python-client`, `google-auth-oauthlib`) added to Docker image.
- `docker-compose.example.yml` now documents both modes side by side.

### Changed
- `Dockerfile`: now installs Google API Python libraries; runs either `forward.py` or `import.py` based on `MODE`.
- `README.md`: restructured to document both modes with a comparison table and step-by-step OAuth2 setup guide.

---

## [1.0.1] - 2026-05-22

### Fixed
- Minor stability improvements.

---

## [1.0.0] - 2026-05-20

### Added
- Initial release.
- Fetches unread messages from any IMAP server on a configurable interval.
- Forwards messages to Gmail via SMTP, preserving original sender, date, and subject via forwarding banner.
- `Reply-To` set to the original sender.
- Optional spam folder forwarding with `[ ** SPAM ** ]` subject tag.
- Optional auto-deletion of source messages older than X days.
- Multi-arch Docker image (`linux/amd64`, `linux/arm64`).
