import base64
import email
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from fetch import check_source_config, fetch, _log as log

CREDENTIALS_FILE  = os.environ.get("GMAIL_CREDENTIALS_FILE", "/credentials/credentials.json")
TOKEN_FILE        = os.environ.get("GMAIL_TOKEN_FILE", "/credentials/token.json")
GMAIL_LABEL_INBOX = os.environ.get("GMAIL_LABEL_INBOX", "true").lower() == "true"
GMAIL_LABEL_SPAM  = os.environ.get("GMAIL_LABEL_SPAM", "SPAM")

SCOPES = ["https://www.googleapis.com/auth/gmail.insert"]


def check_config():
    check_source_config()
    if not Path(CREDENTIALS_FILE).exists():
        log(f"Error: credentials file not found at {CREDENTIALS_FILE}", error=True)
        log("See README for how to create a Google Cloud project and download credentials.json",
            error=True)
        sys.exit(1)


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
            # No valid token and no way to refresh — require auth.py to be run first.
            log("Error: no valid OAuth2 token found.", error=True)
            log(f"Run auth.py first to generate {TOKEN_FILE}:", error=True)
            log("  docker run --rm -it -v ./credentials:/credentials "
                "ghcr.io/andbad/mail2gmail:latest python /auth.py", error=True)
            sys.exit(1)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        log(f"Token saved to {TOKEN_FILE}")

    return build("gmail", "v1", credentials=creds)


class DuplicateMessageError(Exception):
    pass


def insert_message(service, raw_bytes, label_ids):
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
        # 400 "Invalid argument" typically means duplicate Message-ID
        if e.resp.status == 400:
            raise DuplicateMessageError(str(e)) from e
        raise


def make_callback(service, label_ids, folder_label):
    def callback(raw_bytes, folder, is_spam):
        try:
            msg = email.message_from_bytes(raw_bytes)
            subject = msg.get("Subject", "(no subject)")
            sender  = msg.get("From", "unknown")

            # For spam, use configured spam label; otherwise use the passed label_ids
            if is_spam:
                ids = [GMAIL_LABEL_SPAM] if GMAIL_LABEL_SPAM else []
            else:
                ids = label_ids

            gmail_id = insert_message(service, raw_bytes, ids)
            log(f"[{folder}] Imported: {subject!r} | From: {sender} → Gmail ID: {gmail_id}")
            return True

        except DuplicateMessageError:
            log(f"[{folder}] Skipped duplicate (Message-ID already in Gmail)")
            return True  # mark seen so we don't retry forever
        except Exception as e:
            log(f"[{folder}] Error processing message: {e}", error=True)
            return False

    return callback


def run():
    check_config()
    service = get_gmail_service()

    inbox_labels = ["INBOX", "UNREAD"] if GMAIL_LABEL_INBOX else ["UNREAD"]
    callback = make_callback(service, inbox_labels, "INBOX")

    fetch(callback)


if __name__ == "__main__":
    run()
