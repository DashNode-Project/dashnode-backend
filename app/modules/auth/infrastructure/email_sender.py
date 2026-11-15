"""Transactional e-mail delivery for password flows (HU_DN_01_06 / HU_DN_01_10)."""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings
from app.modules.auth.domain.errors import EmailSendFailedError
from app.modules.auth.domain.ports import TransactionalEmailSender

logger = logging.getLogger("dashnode.mail")


class SmtpTransactionalEmailSender(TransactionalEmailSender):
    def _deliver(self, message: EmailMessage) -> None:
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            raise EmailSendFailedError()
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

    def verify_connection(self) -> None:
        """Open and authenticate the SMTP session without sending a message."""
        if not settings.SMTP_HOST:
            raise EmailSendFailedError()
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
                client.noop()
        except OSError as error:
            logger.warning("SMTP probe failed: %s", type(error).__name__)
            raise EmailSendFailedError from error

    def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Restablecer contraseña — DashNode"
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to_email
        message.set_content(
            "Recibió este correo porque se solicitó restablecer su contraseña en DashNode.\n\n"
            f"Abra el siguiente enlace (válido por tiempo limitado):\n{reset_url}\n\n"
            "Si usted no realizó esta solicitud, ignore este mensaje."
        )
        self._deliver(message)

    def send_account_activation(self, *, to_email: str, activation_url: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Activar cuenta — DashNode"
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to_email
        message.set_content(
            "Se creó una cuenta para usted en DashNode.\n\n"
            "Active su cuenta y establezca su contraseña con este enlace (válido 24 horas):\n"
            f"{activation_url}\n\n"
            "Si usted no esperaba este correo, ignore este mensaje."
        )
        self._deliver(message)

    def send_developer_invitation(
        self, *, to_email: str, invitation_url: str, verification_code: str
    ) -> None:
        message = EmailMessage()
        message["Subject"] = "Invitación de desarrollador — DashNode"
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to_email
        message.set_content(
            "Un gerente solicitó crear su cuenta de desarrollador en DashNode.\n\n"
            "La solicitud vence en 24 horas. Abra el enlace y autorice o rechace la creación.\n"
            f"{invitation_url}\n\n"
            f"Código de verificación: {verification_code}\n\n"
            "No comparta este código. Si usted no esperaba este correo, rechace la solicitud."
        )
        self._deliver(message)


class LoggingTransactionalEmailSender(TransactionalEmailSender):
    """Development fallback when SMTP is not configured: simulates successful delivery."""

    def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        logger.info(
            "Password reset requested for %s (link omitted from logs)", to_email.split("@")[0]
        )

    def send_account_activation(self, *, to_email: str, activation_url: str) -> None:
        logger.info("Account activation for %s (link omitted from logs)", to_email.split("@")[0])

    def send_developer_invitation(
        self, *, to_email: str, invitation_url: str, verification_code: str
    ) -> None:
        logger.info(
            "Developer invitation for %s (code and link omitted from logs)",
            to_email.split("@")[0],
        )
