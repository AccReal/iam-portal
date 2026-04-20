"""Async notification tasks (email via SMTP / SMS via SMSC.ru)."""

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_SMSC_API = "https://smsc.ru/sys/send.php"


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_email_notification(self, to_email: str, subject: str, html_body: str, text_body: str = ""):
    """Send an HTML email via SMTP. Retries up to 3 times on transient errors."""
    from app.config import settings  # lazy import avoids circular imports at module load

    if not settings.EMAIL_ENABLED:
        logger.info("[EMAIL DISABLED] To: %s | Subject: %s", to_email, subject)
        return {"status": "disabled", "to": to_email}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_TLS:
                server.starttls(context=context)
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, to_email, msg.as_string())

        logger.info("[EMAIL] Sent to %s | Subject: %s", to_email, subject)
        return {"status": "ok", "to": to_email}

    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("[EMAIL] Transient error sending to %s: %s. Retrying...", to_email, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def send_sms_via_smsc(self, phone: str, message: str, login: str, password: str):
    """Send SMS via SMSC.ru API. Retries up to 3 times on network errors."""
    try:
        resp = httpx.get(
            _SMSC_API,
            params={
                "login": login,
                "psw": password,
                "phones": phone,
                "mes": message,
                "fmt": 3,
                "charset": "utf-8",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            logger.error("SMSC.ru error sending SMS to %s: %s", phone, data)
            return {"status": "error", "detail": data}
        logger.info("SMSC.ru SMS sent to %s, id=%s", phone, data.get("id"))
        return {"status": "ok", "smsc_id": data.get("id")}
    except httpx.HTTPError as exc:
        logger.warning("SMSC.ru HTTP error: %s. Retrying...", exc)
        raise self.retry(exc=exc)
