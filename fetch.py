"""
fetch.py — shared email fetching logic for mail2gmail.

Supports two protocols:
  - IMAP (default): uses UNSEEN flag; supports folders and server-side delete.
  - POP3: tracks seen Message-IDs in a local state file; inbox only.

Environment variables:
  SOURCE_PROTOCOL   imap | pop3          (default: imap)

  # Common — IMAP_* vars are the canonical names; POP3_* aliases take
  # precedence when SOURCE_PROTOCOL=pop3 so users can have both sets.
  IMAP_HOST         hostname             (required)
  IMAP_USER         username             (required)
  IMAP_PASS         password             (required)
  IMAP_PORT         port                 (default: 993 for IMAP, 995 for POP3)

  # POP3-specific overrides
  POP3_HOST         hostname
  POP3_USER         username
  POP3_PASS         password
  POP3_PORT         port                 (default: 995)
  POP3_STATE_FILE   path                 (default: /tmp/pop3_seen.json)

  # IMAP-only
  FETCH_SPAM        true | false         (default: false)
  SPAM_FOLDER       folder name          (default: Spam)
  DELETE_AFTER_DAYS integer              (default: 0 = disabled)
"""

import email
import imaplib
import json
import os
import poplib
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SOURCE_PROTOCOL = os.environ.get("SOURCE_PROTOCOL", "imap").lower()

if SOURCE_PROTOCOL == "pop3":
    MAIL_HOST = os.environ.get("POP3_HOST") or os.environ.get("IMAP_HOST", "")
    MAIL_USER = os.environ.get("POP3_USER") or os.environ.get("IMAP_USER", "")
    MAIL_PASS = os.environ.get("POP3_PASS") or os.environ.get("IMAP_PASS", "")
    MAIL_PORT = int(os.environ.get("POP3_PORT") or os.environ.get("IMAP_PORT", "995"))
    POP3_STATE_FILE = os.environ.get("POP3_STATE_FILE", "/tmp/pop3_seen.json")
else:
    MAIL_HOST = os.environ.get("IMAP_HOST", "")
    MAIL_USER = os.environ.get("IMAP_USER", "")
    MAIL_PASS = os.environ.get("IMAP_PASS", "")
    MAIL_PORT = int(os.environ.get("IMAP_PORT", "993"))

FETCH_SPAM        = os.environ.get("FETCH_SPAM", "false").lower() == "true"
SPAM_FOLDER       = os.environ.get("SPAM_FOLDER", "Spam")
DELETE_AFTER_DAYS = int(os.environ.get("DELETE_AFTER_DAYS", "0"))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def check_source_config():
    required = {
        "IMAP_HOST (or POP3_HOST)": MAIL_HOST,
        "IMAP_USER (or POP3_USER)": MAIL_USER,
        "IMAP_PASS (or POP3_PASS)": MAIL_PASS,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        _log(f"Error: missing environment variables: {', '.join(missing)}", error=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(msg, error=False):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = sys.stderr if error else sys.stdout
    print(f"[{ts}] {msg}", file=out, flush=True)


# ---------------------------------------------------------------------------
# POP3 state — tracks processed Message-IDs across runs
# ---------------------------------------------------------------------------

def _load_pop3_state() -> set:
    try:
        data = json.loads(Path(POP3_STATE_FILE).read_text())
        return set(data.get("seen", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_pop3_state(seen: set):
    Path(POP3_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(POP3_STATE_FILE).write_text(json.dumps({"seen": list(seen)}))


# ---------------------------------------------------------------------------
# POP3 date parsing helper
# ---------------------------------------------------------------------------

def _parse_date(date_str: str):
    """
    Parse an RFC 2822 Date header into a naive local datetime.
    Returns None if the string is missing or unparseable.
    """
    if not date_str:
        return None
    try:
        ts = email.utils.parsedate_to_datetime(date_str)
        # Convert to naive UTC for comparison with datetime.now()
        return ts.replace(tzinfo=None)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# POP3 fetch
# ---------------------------------------------------------------------------

def fetch_pop3(callback):
    """
    Connect via POP3S, iterate over all messages not yet seen (tracked by
    Message-ID in POP3_STATE_FILE), call callback(raw_bytes) for each.

    callback(raw_bytes) must return True on success so the Message-ID is
    persisted as seen. Returns without raising on connection errors (logged).

    If DELETE_AFTER_DAYS > 0, messages older than that threshold are deleted
    from the server via pop.dele() and removed from the state file, keeping
    it small. Deletions are committed only on a clean pop.quit(); if an
    exception occurs before that point the server performs an implicit RSET
    and nothing is deleted.

    Notes:
      - POP3 has no folders: only INBOX is supported.
      - FETCH_SPAM is ignored for POP3.
    """
    seen = _load_pop3_state()
    new_seen = set(seen)

    try:
        pop = poplib.POP3_SSL(MAIL_HOST, MAIL_PORT)
        pop.user(MAIL_USER)
        pop.pass_(MAIL_PASS)
    except Exception as e:
        _log(f"POP3 connection failed: {e}", error=True)
        raise

    try:
        count, _ = pop.stat()
        if count == 0:
            _log("[POP3] No messages.")
            return

        # Scan all message headers once: collect new messages to process and,
        # when DELETE_AFTER_DAYS is set, all messages old enough to delete.
        new_msgs     = []  # [(index, msg_id)]
        to_delete    = []  # [(index, msg_id)]
        cutoff       = None
        if DELETE_AFTER_DAYS > 0:
            cutoff = datetime.now() - timedelta(days=DELETE_AFTER_DAYS)

        for i in range(1, count + 1):
            raw_headers = b"\r\n".join(pop.top(i, 0)[1])
            hdr = email.message_from_bytes(raw_headers)
            msg_id = hdr.get("Message-ID", "").strip()

            if not msg_id or msg_id not in seen:
                new_msgs.append((i, msg_id))

            if cutoff:
                date_str = hdr.get("Date", "")
                msg_date = _parse_date(date_str)
                if msg_date and msg_date < cutoff:
                    to_delete.append((i, msg_id))

        # Process new messages
        if not new_msgs:
            _log("[POP3] No new messages.")
        else:
            _log(f"[POP3] Found {len(new_msgs)} new message(s).")
            for i, msg_id in new_msgs:
                try:
                    raw_lines = pop.retr(i)[1]
                    raw_bytes = b"\r\n".join(raw_lines)
                    ok = callback(raw_bytes)
                    if ok and msg_id:
                        new_seen.add(msg_id)
                except Exception as e:
                    _log(f"[POP3] Error processing message {i}: {e}", error=True)

        # Delete old messages from server and state file
        if to_delete:
            deleted = 0
            for i, msg_id in to_delete:
                try:
                    pop.dele(i)
                    if msg_id in new_seen:
                        new_seen.discard(msg_id)
                    deleted += 1
                except Exception as e:
                    _log(f"[POP3] Error marking message {i} for deletion: {e}", error=True)
            _log(f"[POP3] Marked {deleted} message(s) for deletion "
                 f"(older than {DELETE_AFTER_DAYS} days).")

    finally:
        _save_pop3_state(new_seen)
        try:
            pop.quit()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# IMAP fetch
# ---------------------------------------------------------------------------

def fetch_imap(callback):
    """
    Connect via IMAP4_SSL, iterate over UNSEEN messages in INBOX (and
    optionally the spam folder), call callback(raw_bytes, folder, is_spam).

    callback(raw_bytes, folder, is_spam) must return True on success so
    the message is marked \\Seen on the server.
    """
    try:
        imap = imaplib.IMAP4_SSL(MAIL_HOST, MAIL_PORT)
        imap.login(MAIL_USER, MAIL_PASS)
    except Exception as e:
        _log(f"IMAP connection failed: {e}", error=True)
        raise

    try:
        _imap_process_folder(imap, "INBOX", callback, label="INBOX", is_spam=False)

        if FETCH_SPAM:
            _imap_process_folder(imap, SPAM_FOLDER, callback,
                                 label=f"SPAM ({SPAM_FOLDER})", is_spam=True)

        if DELETE_AFTER_DAYS > 0:
            _log(f"Deleting seen messages older than {DELETE_AFTER_DAYS} days from source...")
            _imap_delete_old(imap, "INBOX")
            if FETCH_SPAM:
                _imap_delete_old(imap, SPAM_FOLDER)
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _imap_process_folder(imap, folder, callback, label=None, is_spam=False):
    try:
        status, _ = imap.select(folder)
        if status != "OK":
            _log(f"Folder '{folder}' not found, skipping.")
            return
    except Exception as e:
        _log(f"Error selecting folder '{folder}': {e}", error=True)
        return

    _, data = imap.search(None, "UNSEEN")
    ids = data[0].split()
    if not ids:
        _log(f"[{folder}] No new messages.")
        return

    _log(f"[{folder}] Found {len(ids)} new message(s).")
    for num in ids:
        try:
            _, msg_data = imap.fetch(num, "(RFC822)")
            raw_bytes = msg_data[0][1]
            ok = callback(raw_bytes, label or folder, is_spam)
            if ok:
                imap.store(num, "+FLAGS", "\\Seen")
        except Exception as e:
            _log(f"[{folder}] Error processing message {num}: {e}", error=True)


def _imap_delete_old(imap, folder):
    try:
        imap.select(folder)
    except Exception as e:
        _log(f"Error selecting '{folder}' for deletion: {e}", error=True)
        return
    cutoff = (datetime.now() - timedelta(days=DELETE_AFTER_DAYS)).strftime("%d-%b-%Y")
    # Only delete SEEN messages — never touch unprocessed ones
    _, data = imap.search(None, f"SEEN BEFORE {cutoff}")
    ids = data[0].split()
    if not ids:
        _log(f"[{folder}] No seen messages to delete (older than {cutoff}).")
        return
    for num in ids:
        imap.store(num, "+FLAGS", "\\Deleted")
    imap.expunge()
    _log(f"[{folder}] Deleted {len(ids)} seen message(s) older than {cutoff}.")


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def fetch(callback_imap, callback_pop3=None):
    """
    Dispatch to the right protocol based on SOURCE_PROTOCOL.

    Signatures:
      callback_imap(raw_bytes, folder, is_spam) -> bool
      callback_pop3(raw_bytes)                  -> bool  (optional)

    If SOURCE_PROTOCOL=pop3 and callback_pop3 is None, callback_imap is
    called as callback_imap(raw_bytes, "POP3", False).
    """
    if SOURCE_PROTOCOL == "pop3":
        if callback_pop3 is not None:
            fetch_pop3(callback_pop3)
        else:
            fetch_pop3(lambda raw: callback_imap(raw, "POP3", False))
    else:
        fetch_imap(callback_imap)
