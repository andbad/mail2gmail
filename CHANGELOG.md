# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.2.0] - 2026-05-28

### Added

- `requirements.txt` with pinned dependency versions, replacing the inline
  `pip install` list in the Dockerfile. Enables reproducible builds and
  automated dependency tracking.
- Dependabot configuration (`.github/dependabot.yml`) for automated weekly
  PRs on both `pip` and `docker` ecosystems.
- `TZ` environment variable in all `docker-compose.example.yml` service
  definitions (default: `Europe/Rome`). Fixes log timestamps showing UTC
  instead of local time on hosts with a non-UTC timezone.

### Changed

- `Dockerfile`: now installs dependencies via `COPY requirements.txt` +
  `pip install -r`, instead of a single inline `pip install` command.

---

## [3.1.0] - 2026-05-28

### Added

- **Attachment forwarding in `forward` mode**: attachments are now included in
  forwarded messages instead of being silently discarded. The outgoing message
  uses `multipart/mixed` (body as `multipart/alternative` + attachments as
  `MIMEBase` parts). Attachment count is reported in the forwarded log line.
- **Exponential backoff with jitter on connection failures**: IMAP and POP3
  connection attempts are now retried automatically using
  [tenacity](https://github.com/jd/tenacity). On transient network errors the
  connector waits before retrying (default: up to 5 attempts, 10–120 s
  between retries) and logs each attempt. After all retries are exhausted the
  error is re-raised and the cycle ends normally, resuming at the next
  `INTERVAL_SEC` tick.
- New optional environment variables to tune retry behaviour:
  - `RETRY_MAX_ATTEMPTS` (default: `5`)
  - `RETRY_WAIT_MIN` (default: `10` seconds)
  - `RETRY_WAIT_MAX` (default: `120` seconds)
- `tenacity==8.*` added as a Docker image dependency.

### Fixed

- Forwarded messages with attachments no longer silently drop them.

---

## [3.0.0] - 2026-05-27

### Added

- **POP3 support** (`SOURCE_PROTOCOL=pop3`): fetches messages from any POP3S
  server. Processed Message-IDs are tracked in a local state file
  (`POP3_STATE_FILE`) so messages are not re-downloaded across restarts.
- `POP3_HOST`, `POP3_PORT`, `POP3_USER`, `POP3_PASS`, `POP3_STATE_FILE`
  environment variables (all override the corresponding `IMAP_*` defaults when
  `SOURCE_PROTOCOL=pop3`).
- POP3 support for `DELETE_AFTER_DAYS`: deletes messages from the server and
  removes their IDs from the local state file.
- Comparison table in README documenting IMAP vs POP3 and `forward` vs
  `import` feature matrix.

### Changed

- Project renamed from `imap2gmail` to `mail2gmail` to reflect multi-protocol
  support.
- `fetch.py` refactored into a unified dispatch layer (`fetch()`) supporting
  both IMAP and POP3 backends.
- All `IMAP_*` environment variables remain fully backward-compatible.

### Migration from imap2gmail (v2)

No code changes required. Update the image reference in `docker-compose.yml`:

```
# Before
image: ghcr.io/andbad/imap2gmail:latest

# After
image: ghcr.io/andbad/mail2gmail:latest
```

---

## [2.0.0] - 2026-05-26

### Added

- **New `import` mode** (`MODE=import`): emails are inserted directly into Gmail via the Gmail API (`messages.insert`), preserving all original headers — sender, recipient, date, subject, and full MIME structure — exactly as received. No SMTP involved.
- `import.py`: new script implementing the Gmail API import flow.
- `auth.py`: dedicated one-time OAuth2 authorization script. Runs inside Docker with no local dependencies required. Prints the Google authorization URL, waits for the user to paste back the redirect URL from the browser address bar, and saves `token.json` automatically.
- OAuth2 authentication flow with automatic token refresh. Token is persisted to disk and reused across restarts.
- Deduplication: messages that are already in Gmail (detected via Gmail API 400 response on duplicate Message-ID) are skipped and marked as seen on the source server.
- `GMAIL_CREDENTIALS_FILE` and `GMAIL_TOKEN_FILE` environment variables to configure OAuth2 credentials paths.
- `GMAIL_LABEL_INBOX` variable to control whether imported messages are added to the inbox.
- `GMAIL_LABEL_SPAM` variable to set the Gmail label applied to spam messages in import mode.
- `MODE` environment variable to select between `forward` (default) and `import`.
- Google API dependencies (`google-api-python-client`, `google-auth-oauthlib`) added to Docker image.
- `docker-compose.example.yml` now documents both modes side by side.
- `.gitignore` entry for `credentials/` directory to prevent accidental commit of OAuth2 secrets.

### Changed

- `Dockerfile`: now installs Google API Python libraries; runs either `forward.py` or `import.py` based on `MODE`.
- `README.md`: restructured to document both modes with a comparison table and detailed step-by-step OAuth2 setup guide, including exact browser behaviour during authorization (`ERR_SOCKET_NOT_CONNECTED` is expected).

### Notes on OAuth2 authorization

The standard `run_local_server` approach does not work inside Docker because the container's loopback interface is not reachable from the host browser. `auth.py` uses a copy/paste URL flow instead: the user opens the Google authorization URL manually, and after granting access pastes the full redirect URL (including the `?code=` parameter) back into the terminal. No port mapping or local Python installation required.

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
