"""Envío del resumen por email (SMTP, por defecto Gmail).

Variables de entorno:
  EMAIL_TO       destinatario(s), separados por coma
  SMTP_USER      cuenta que envía (ej. tu Gmail)
  SMTP_PASSWORD  contraseña de aplicación de Gmail (no la contraseña normal)
  SMTP_HOST      opcional, default smtp.gmail.com
  SMTP_PORT      opcional, default 465 (SSL)
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def email_configured() -> bool:
    return all(os.environ.get(k) for k in ("EMAIL_TO", "SMTP_USER", "SMTP_PASSWORD"))


def send_email(subject: str, text: str, html: str | None = None) -> bool:
    if not email_configured():
        print("[email] faltan EMAIL_TO / SMTP_USER / SMTP_PASSWORD: no se envía mail")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"SkyCheck <{os.environ['SMTP_USER']}>"
    msg["To"] = os.environ["EMAIL_TO"]
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=60) as s:
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as s:
            s.starttls(context=ctx)
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
    print(f"[email] resumen enviado a {msg['To']}")
    return True
