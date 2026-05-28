import email
import email.header
import email.utils
import os
import smtplib
import sys
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

from fetch import check_source_config, fetch, _log as log

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
DEST = os.environ.get("DEST", "")


def check_config():
    check_source_config()
    required = {"SMTP_USER": SMTP_USER, "SMTP_PASS": SMTP_PASS, "DEST": DEST}
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
    folder_line = f"Folder: {folder}\n" if folder else ""
    return (
        "-------- Forwarded message --------\n"
        f"From: {from_addr}\n"
        f"To: {orig_to}\n"
        f"Date: {orig_date}\n"
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


def send_message(smtp, raw_bytes, folder=None, is_spam=False):
    msg = email.message_from_bytes(raw_bytes)

    from_raw = msg.get("From", "")
    to_raw = msg.get("To", "")
    orig_date = msg.get("Date", "")
    orig_subj = decode_header_value(msg.get("Subject", "(no subject)"))
    from_addr = format_addr(from_raw)
    orig_to = format_addr(to_raw)
    display_subj = f"[ ** SPAM ** ] {orig_subj}" if is_spam else orig_subj

    banner_text = make_banner_text(from_addr, orig_to, orig_date, orig_subj, folder)
    banner_html = make_banner_html(from_addr, orig_to, orig_date, orig_subj, folder)

    body_text = ""
    body_html = ""
    attachments = []  # list of MIMEBase parts

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = part.get("Content-Disposition", "")
            # Collect attachments
            if "attachment" in cd:
                filename = part.get_filename() or "attachment"
                filename = decode_header_value(filename)
                payload = part.get_payload(decode=True)
                if payload:
                    att = MIMEBase(*ct.split("/", 1))
                    att.set_payload(payload)
                    encoders.encode_base64(att)
                    att.add_header("Content-Disposition", "attachment", filename=filename)
                    attachments.append(att)
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

    # Build the text/html alternative part
    alternative = MIMEMultipart("alternative")
    if body_text:
        alternative.attach(MIMEText(banner_text + body_text, "plain", "utf-8"))
    if body_html:
        if "<body" in body_html.lower():
            insert_pos = body_html.lower().find("<body")
            close_tag = body_html.find(">", insert_pos)
            body_html = body_html[:close_tag + 1] + banner_html + body_html[close_tag + 1:]
        else:
            body_html = banner_html + body_html
        alternative.attach(MIMEText(body_html, "html", "utf-8"))
    if not body_text and not body_html:
        alternative.attach(MIMEText(banner_text + "[Empty body]", "plain", "utf-8"))

    # Wrap in multipart/mixed only when there are attachments
    if attachments:
        outer = MIMEMultipart("mixed")
        outer.attach(alternative)
        for att in attachments:
            outer.attach(att)
        payload_msg = outer
    else:
        payload_msg = alternative

    payload_msg["From"] = from_raw
    payload_msg["To"] = DEST
    payload_msg["Subject"] = display_subj
    payload_msg["Reply-To"] = from_addr
    if orig_date:
        payload_msg["Date"] = orig_date

    smtp.sendmail(SMTP_USER, DEST, payload_msg.as_bytes())

    att_note = f" ({len(attachments)} attachment(s))" if attachments else ""
    log(f"Forwarded: {orig_subj} | From: {from_addr}{att_note}")
    return True


def run():
    check_config()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)

        def callback_imap(raw_bytes, folder, is_spam):
            return send_message(smtp, raw_bytes, folder=folder, is_spam=is_spam)

        def callback_pop3(raw_bytes):
            return send_message(smtp, raw_bytes, folder=None, is_spam=False)

        fetch(callback_imap, callback_pop3)


if __name__ == "__main__":
    run()
