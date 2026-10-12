"""Transactional e-mail delivery for password flows (HU_DN_01_06 / HU_DN_01_10)."""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings
from app.modules.auth.domain.errors import EmailSendFailedError
from app.modules.auth.domain.ports import TransactionalEmailSender

logger = logging.getLogger("dashnode.mail")


class SmtpTransactionalEmailSender(TransactionalEmailSender):
    def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            raise EmailSendFailedError()
        message = EmailMessage()
        message["Subject"] = "Restablecer contraseña — DashNode"
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to_email
        message.set_content(
            "Recibió este correo porque se solicitó restablecer su contraseña en DashNode.\n\n"
            f"Abra el siguiente enlace (válido por tiempo limitado):\n{reset_url}\n\n"
            "Si usted no realizó esta solicitud, ignore este mensaje."
        )
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as client:
                if settings.SMTP_USE_TLS:
                    client.starttls()
                username = settings.SMTP_USERNAME
                password = (
                    settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else None
                )
                if username and password:
                    client.login(username, password)
                client.send_message(message)
        except OSError as error:
            logger.warning("SMTP delivery failed: %s", type(error).__name__)
            raise EmailSendFailedError from error


class LoggingTransactionalEmailSender(TransactionalEmailSender):
    """Development fallback when SMTP is not configured: simulates successful delivery."""

    def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        logger.info("Password reset requested for %s (link omitted from logs)", to_email.split("@")[0])
