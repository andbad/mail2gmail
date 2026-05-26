import imaplib
import email
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
IMAP_HOST         = os.environ.get("IMAP_HOST", "")
IMAP_USER         = os.environ.get("IMAP_USER", "")
IMAP_PASS         = os.environ.get("IMAP_PASS", "")
IMAP_PORT         = int(os.environ.get("IMAP_PORT", "993"))

FETCH_SPAM        = os.environ.get("FETCH_SPAM", "false").lower() == "true"
SPAM_FOLDER       = os.environ.get("SPAM_FOLDER", "Spam")
DELETE_AFTER_DAYS = int(os.environ.get("DELETE_AFTER_DAYS", "0"))
INTERVAL_SEC      = int(os.environ.get("INTERVAL_SEC", "600"))

# Gmail API OAuth2 — credentials.json path and token storage
CREDENTIALS_FILE  = os.environ.get("GMAIL_CREDENTIALS_FILE", "/credentials/credentials.json")
TOKEN_FILE        = os.environ.get("GMAIL_TOKEN_FILE", "/credentials/token.json")

GMAIL_LABEL_INBOX = os.environ.get("GMAIL_LABEL_INBOX", "true").lower() == "true"
GMAIL_LABEL_SPAM  = os.environ.get("GMAIL_LABEL_SPAM", "SPAM")  # Gmail label for spam, or empty

SCOPES = ["https://www.googleapis.com/auth/gmail.insert"]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log(msg, error=False):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = sys.stderr if error else sys.stdout
    print(f"[{ts}] {msg}", file=out, flush=True)

# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------
def check_config():
    required = {
        "IMAP_HOST": IMAP_HOST,
        "IMAP_USER": IMAP_USER,
        "IMAP_PASS": IMAP_PASS,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        log(f"Error: missing environment variables: {', '.join(missing)}", error=True)
        sys.exit(1)
    if not Path(CREDENTIALS_FILE).exists():
        log(f"Error: credentials file not found at {CREDENTIALS_FILE}", error=True)
        log("See README for how to create a Google Cloud project and download credentials.json", error=True)
        sys.exit(1)

# ---------------------------------------------------------------------------
# Gmail API auth
# ---------------------------------------------------------------------------
def get_gmail_service():
    creds = None
    token_path = Path(TOKEN_FILE)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log("Refreshing Gmail OAuth2 token...")
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            print("\n" + "="*60)
            print("OAuth2 authorization required.")
            print("Open this URL in your browser:")
            print("  http://localhost:8080")
            print("(the container must be started with -p 8080:8080)")
            print("="*60)
            creds = flow.run_local_server(port=8080, open_browser=False)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        log(f"Token saved to {TOKEN_FILE}")

    return build("gmail", "v1", credentials=creds)

# ---------------------------------------------------------------------------
# Insert a single raw RFC822 message into Gmail
# ---------------------------------------------------------------------------
def insert_message(service, raw_bytes, label_ids):
    """
    Upload raw RFC822 bytes to Gmail via messages.insert.
    Preserves all original headers (From, To, Date, Subject, etc.).
    internalDateSource=dateHeader uses the email's own Date: header.
    """
    encoded = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")
    body = {"raw": encoded, "labelIds": label_ids}

    try:
        result = (
            service.users()
            .messages()
            .insert(userId="me", body=body, internalDateSource="dateHeader")
            .execute()
        )
        return result.get("id")
    except HttpError as e:
        # 400 with "Invalid argument" often means duplicate Message-ID
        if e.resp.status == 400:
            raise DuplicateMessageError(str(e)) from e
        raise

class DuplicateMessageError(Exception):
    pass

# ---------------------------------------------------------------------------
# Process a single IMAP folder
# ---------------------------------------------------------------------------
def process_folder(imap, service, folder, label_ids, is_spam=False):
    try:
        status, _ = imap.select(folder)
        if status != "OK":
            log(f"Folder '{folder}' not found, skipping.")
            return 0
    except Exception as e:
        log(f"Error selecting folder '{folder}': {e}", error=True)
        return 0

    _, data = imap.search(None, "UNSEEN")
    ids = data[0].split()
    if not ids:
        log(f"[{folder}] No new messages.")
        return 0

    log(f"[{folder}] Found {len(ids)} new message(s).")
    imported = 0

    for num in ids:
        try:
            _, msg_data = imap.fetch(num, "(RFC822)")
            raw_bytes = msg_data[0][1]

            # Extract subject for logging only
            msg = email.message_from_bytes(raw_bytes)
            subject = msg.get("Subject", "(no subject)")
            sender  = msg.get("From", "unknown")

            gmail_id = insert_message(service, raw_bytes, label_ids)
            imap.store(num, "+FLAGS", "\\Seen")
            log(f"[{folder}] Imported: {subject!r} | From: {sender} → Gmail ID: {gmail_id}")
            imported += 1

        except DuplicateMessageError:
            log(f"[{folder}] Skipped duplicate (Message-ID already in Gmail): msg {num}")
            imap.store(num, "+FLAGS", "\\Seen")  # mark seen so we don't retry forever
        except Exception as e:
            log(f"[{folder}] Error processing message {num}: {e}", error=True)

    return imported

# ---------------------------------------------------------------------------
# Delete old messages on source server
# ---------------------------------------------------------------------------
def delete_old_messages(imap, folder):
    if DELETE_AFTER_DAYS <= 0:
        return
    imap.select(folder)
    cutoff = (datetime.now() - timedelta(days=DELETE_AFTER_DAYS)).strftime("%d-%b-%Y")
    _, data = imap.search(None, f"BEFORE {cutoff}")
    ids = data[0].split()
    if not ids:
        log(f"[{folder}] No messages to delete (older than {cutoff}).")
        return
    for num in ids:
        imap.store(num, "+FLAGS", "\\Deleted")
    imap.expunge()
    log(f"[{folder}] Deleted {len(ids)} message(s) older than {cutoff}.")

# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------
def run():
    check_config()
    service = get_gmail_service()

    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        imap.login(IMAP_USER, IMAP_PASS)
    except Exception as e:
        log(f"IMAP connection failed: {e}", error=True)
        sys.exit(1)

    try:
        inbox_labels = ["INBOX", "UNREAD"] if GMAIL_LABEL_INBOX else ["UNREAD"]
        total = process_folder(imap, service, "INBOX", label_ids=inbox_labels)

        if FETCH_SPAM:
            spam_labels = [GMAIL_LABEL_SPAM] if GMAIL_LABEL_SPAM else []
            process_folder(imap, service, SPAM_FOLDER, label_ids=spam_labels, is_spam=True)

        if DELETE_AFTER_DAYS > 0:
            log(f"Deleting messages older than {DELETE_AFTER_DAYS} days from source...")
            delete_old_messages(imap, "INBOX")
            if FETCH_SPAM:
                delete_old_messages(imap, SPAM_FOLDER)

        log(f"Done. {total} message(s) imported.")
    finally:
        try:
            imap.logout()
        except Exception:
            pass


if __name__ == "__main__":
    run()
