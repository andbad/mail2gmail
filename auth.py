"""
One-time OAuth2 authorization script.
Run this once to generate token.json, then use import.py normally.

Usage:
  docker run --rm -it \\
    -v ./credentials:/credentials \\
    ghcr.io/andbad/mail2gmail:latest \\
    python /auth.py
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google_auth_oauthlib.flow import InstalledAppFlow

CREDENTIALS_FILE = os.environ.get("GMAIL_CREDENTIALS_FILE", "/credentials/credentials.json")
TOKEN_FILE       = os.environ.get("GMAIL_TOKEN_FILE",        "/credentials/token.json")
SCOPES           = ["https://www.googleapis.com/auth/gmail.insert"]
REDIRECT_URI     = "http://localhost"

if not Path(CREDENTIALS_FILE).exists():
    print(f"Error: credentials.json not found at {CREDENTIALS_FILE}")
    print("Mount your credentials directory with: -v ./credentials:/credentials")
    sys.exit(1)

# Ensure http://localhost is in redirect_uris.
# NOTE: this modifies credentials.json in-place on the mounted volume if
# http://localhost is not already listed. This is intentional and harmless —
# the file is only used locally and the change is idempotent.
creds_data = json.loads(Path(CREDENTIALS_FILE).read_text())
key = "installed" if "installed" in creds_data else "web"
redirect_uris = creds_data[key].get("redirect_uris", [])
if REDIRECT_URI not in redirect_uris:
    redirect_uris.append(REDIRECT_URI)
    creds_data[key]["redirect_uris"] = redirect_uris
    Path(CREDENTIALS_FILE).write_text(json.dumps(creds_data))
    print(f"(Added '{REDIRECT_URI}' to redirect_uris in {CREDENTIALS_FILE})")

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
flow.redirect_uri = REDIRECT_URI
auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

print()
print("=" * 60)
print("STEP 1 — Open this URL in your browser:")
print()
print(auth_url)
print()
print("=" * 60)
print("STEP 2 — Sign in with your Google account and click Allow.")
print()
print("STEP 3 — Your browser will show an error page")
print("         ('localhost refused to connect' or similar).")
print("         That is expected.")
print("         Copy the FULL URL from the browser address bar")
print("         and paste it below.")
print("=" * 60)
print()

redirect_url = input("Paste the full redirect URL here: ").strip()

try:
    parsed = urlparse(redirect_url)
    code = parse_qs(parsed.query)["code"][0]
except (KeyError, IndexError):
    print()
    print("Error: could not find 'code' in the URL.")
    print("Make sure you copied the full URL from the address bar.")
    sys.exit(1)

flow.fetch_token(code=code)
creds = flow.credentials

Path(TOKEN_FILE).parent.mkdir(parents=True, exist_ok=True)
Path(TOKEN_FILE).write_text(creds.to_json())

print()
print(f"token.json saved to {TOKEN_FILE}")
print("You can now run the container normally (without this script).")
