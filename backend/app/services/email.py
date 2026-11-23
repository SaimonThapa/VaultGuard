"""Outbound email. Prints to the backend log unless SMTP is fully configured, so teammates and the
instructor need no mail setup. The log line is the only place an OTP code is ever written."""

import logging
import smtplib
from email.message import EmailMessage

from app import config

logger = logging.getLogger("vaultguard")

PURPOSE_TEXT = dict(
    [
        ("verify_email", "verify your email address"),
        ("reset_password", "reset your account password"),
        ("recover_master", "recover your master key"),
        ("reset_vault", "reset your vault"),
    ]
)


def send_email(to: str, subject: str, body: str) -> None:
    smtp_ready = all([config.SMTP_HOST, config.SMTP_USER, config.SMTP_PASSWORD, config.SMTP_FROM])
    if not smtp_ready:
        logger.info("[EMAIL] to=%s subject=%s body=%s", to, subject, body)
        return
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = config.SMTP_FROM, to, subject
    message.set_content(body)
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(message)


def send_otp(to: str, purpose: str, code: str) -> None:
    send_email(
        to,
        "Your VaultGuard code",
        f"Use this code to {PURPOSE_TEXT[purpose]}: {code}\n"
        f"It expires in {config.OTP_TTL_MINUTES} minutes. "
        "If you didn't ask for it, ignore this email.",
    )
