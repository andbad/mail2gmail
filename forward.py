import imaplib
import smtplib
import email
import email.utils
import email.header
import sys
import os
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

IMAP_HOST         = os.environ.get("IMAP_HOST", "")
IMAP_USER         = os.environ.get("IMAP_USER", "")
IMAP_PASS         = os.environ.get("IMAP_PASS", "")
IMAP_PORT         = int(os.environ.get("IMAP_PORT", "993"))

SMTP_HOST         = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER         = os.environ.get("SMTP_USER", "")
SMTP_PASS         = os.environ.get("SMTP_PASS", "")
DEST              = os.environ.get("DEST", "")

FETCH_SPAM        = os.environ.get("FETCH_SPAM", "false").lower() == "true"
SPAM_FOLDER       = os.environ.get("SPAM_FOLDER", "Spam")
DELETE_AFTER_DAYS = int(os.environ.get("DELETE_AFTER_DAYS", "0"))
INTERVAL_SEC      = int(os.environ.get("INTERVAL_SEC", "600"))

def log(msg, error=False):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = sys.stderr if error else sys.stdout
    print(f"[{ts}] {msg}", file=out)

def check_config():
    required = {"IMAP_HOST": IMAP_HOST, "IMAP_USER": IMAP_USER, "IMAP_PASS": IMAP_PASS,
                "SMTP_USER": SMTP_USER, "SMTP_PASS": SMTP_PASS, "DEST": DEST}
    missing = [k for k, v in required.items() if not v]
    if missing:
        log(f"Error: missing environment variables: {', '.join(missing)}", error=True)
        sys.exit(1)

def decode_header_value(value):
    if not value:
        return ""
    parts = email.header.decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded).strip()

def format_addr(value):
    decoded = decode_header_value(value)
    name, addr = email.utils.parseaddr(decoded)
    if addr:
        return f"{name} <{addr}>" if name else addr
    addresses = email.utils.getaddresses([decoded])
    if addresses:
        n, a = addresses[0]
        return f"{n} <{a}>" if n and a else (a or decoded)
    return decoded

def make_banner_text(from_addr, orig_to, orig_date, orig_subj, folder=None):
    folder_line = f"Folder:  {folder}\n" if folder else ""
    return (
        "-------- Forwarded message --------\n"
        f"From:    {from_addr}\n"
        f"To:      {orig_to}\n"
        f"Date:    {orig_date}\n"
        f"Subject: {orig_subj}\n"
        f"{folder_line}"
        "-----------------------------------\n\n"
    )

def make_banner_html(from_addr, orig_to, orig_date, orig_subj, folder=None):
    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    folder_line = f'<b>Folder:</b> {esc(folder)}<br>' if folder else ""
    return (
        '<div style="border:1px solid #ccc;padding:8px;margin-bottom:12px;'
        'font-family:monospace;font-size:13px;color:#555;">'
        '<b>-------- Forwarded message --------</b><br>'
        f'<b>From:</b> {esc(from_addr)}<br>'
        f'<b>To:</b> {esc(orig_to)}<br>'
        f'<b>Date:</b> {esc(orig_date)}<br>'
        f'<b>Subject:</b> {esc(orig_subj)}<br>'
        f'{folder_line}'
        '<b>-----------------------------------</b>'
        '</div>'
    )

def decode_part(part):
    charset = part.get_content_charset() or "utf-8"
    return part.get_payload(decode=True).decode(charset, errors="replace")

def send_message(smtp, msg, folder=None, is_spam=False):
    from_raw  = msg.get("From", IMAP_USER)
    to_raw    = msg.get("To", "")
    orig_date = msg.get("Date", "")
    orig_subj = decode_header_value(msg.get("Subject", "(no subject)"))
    from_addr = format_addr(from_raw)
    orig_to   = format_addr(to_raw)

    display_subj = f"[ ** SPAM ** ] {orig_subj}" if is_spam else orig_subj

    banner_text = make_banner_text(from_addr, orig_to, orig_date, orig_subj, folder)
    banner_html = make_banner_html(from_addr, orig_to, orig_date, orig_subj, folder)

    new_msg = MIMEMultipart("alternative")
    new_msg["From"]     = from_raw
    new_msg["To"]       = DEST
    new_msg["Subject"]  = display_subj
    new_msg["Reply-To"] = from_addr
    if orig_date:
        new_msg["Date"] = orig_date

    body_text = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = part.get("Content-Disposition", "")
            if "attachment" in cd:
                continue
            if ct == "text/plain" and not body_text:
                body_text = decode_part(part)
            elif ct == "text/html" and not body_html:
                body_html = decode_part(part)
    else:
        ct = msg.get_content_type()
        if ct == "text/html":
            body_html = decode_part(msg)
        else:
            body_text = decode_part(msg)

    if not body_text and body_html:
        body_text = "[HTML message - see below]\n"

    if body_text:
        new_msg.attach(MIMEText(banner_text + body_text, "plain", "utf-8"))
    if body_html:
        if "<body" in body_html.lower():
            insert_pos = body_html.lower().find("<body")
            close_tag  = body_html.find(">", insert_pos)
            body_html  = body_html[:close_tag+1] + banner_html + body_html[close_tag+1:]
        else:
            body_html = banner_html + body_html
        new_msg.attach(MIMEText(body_html, "html", "utf-8"))

    if not body_text and not body_html:
        new_msg.attach(MIMEText(banner_text + "[Empty body]", "plain", "utf-8"))

    smtp.sendmail(SMTP_USER, DEST, new_msg.as_bytes())
    log(f"Forwarded: {orig_subj} | From: {from_addr}")

def delete_old_messages(imap, folder):
    if DELETE_AFTER_DAYS <= 0:
        return
    imap.select(folder)
    date_str = (datetime.now() - timedelta(days=DELETE_AFTER_DAYS)).strftime("%d-%b-%Y")
    _, data = imap.search(None, f'BEFORE {date_str}')
    ids = data[0].split()
    if not ids:
        log(f"[{folder}] No messages to delete.")
        return
    for num in ids:
        imap.store(num, "+FLAGS", "\\Deleted")
    imap.expunge()
    log(f"[{folder}] Deleted {len(ids)} messages older than {date_str}.")

def process_folder(imap, smtp, folder, label=None, is_spam=False):
    try:
        status, _ = imap.select(folder)
        if status != "OK":
            log(f"Folder '{folder}' not found, skipping.")
            return
    except Exception as e:
        log(f"Error selecting folder '{folder}': {e}", error=True)
        return

    _, data = imap.search(None, "UNSEEN")
    ids = data[0].split()

    if not ids:
        log(f"[{folder}] No new messages.")
        return

    log(f"[{folder}] Found {len(ids)} new message(s).")
    for num in ids:
        try:
            _, msg_data = imap.fetch(num, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            send_message(smtp, msg, folder=label, is_spam=is_spam)
            imap.store(num, "+FLAGS", "\\Seen")
        except Exception as e:
            log(f"Error processing message {num}: {e}", error=True)

def run():
    check_config()
    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        imap.login(IMAP_USER, IMAP_PASS)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)

            process_folder(imap, smtp, "INBOX")

            if FETCH_SPAM:
                process_folder(imap, smtp, SPAM_FOLDER, label=f"SPAM ({SPAM_FOLDER})", is_spam=True)

            if DELETE_AFTER_DAYS > 0:
                log(f"Deleting messages older than {DELETE_AFTER_DAYS} days...")
                delete_old_messages(imap, "INBOX")
                if FETCH_SPAM:
                    delete_old_messages(imap, SPAM_FOLDER)

        imap.logout()

    except Exception as e:
        log(f"Error: {e}", error=True)

if __name__ == "__main__":
    run()
