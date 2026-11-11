"""Заявка уходит письмом на почту. Если почта не настроена, заявка остаётся в базе и пишется в журнал."""
from __future__ import annotations

import logging
import smtplib
import threading
from datetime import datetime
from email.message import EmailMessage

from .config import Config
from .flow import Application

log = logging.getLogger("kovcheg_bot.mail")

KINDS = {"call": "Созвон", "order": "Заявка компании"}


def build_message(app: Application, cfg: Config) -> EmailMessage:
    when = datetime.fromtimestamp(app.created_at).strftime("%d.%m.%Y %H:%M") if app.created_at else "-"
    msg = EmailMessage()
    msg["Subject"] = "Ковчег: %s (%s)" % (KINDS.get(app.kind, app.kind), app.tag or "без тега")
    msg["From"] = cfg.mail_from
    msg["To"] = cfg.mail_to
    msg.set_content(
        "Тип: %s\nНаправление: %s\nИсточник: %s\nTelegram: %s (id %s)\nКонтакт: %s\nВремя: %s\n\nЗадача:\n%s\n"
        % (KINDS.get(app.kind, app.kind), app.tag, app.source, app.username or "-", app.uid, app.contact, when, app.task or "-"))
    return msg


def send(app: Application, cfg: Config) -> None:
    if not cfg.mail_ready:
        log.warning("Почта не настроена, заявка только в базе: %s %s %s", app.kind, app.tag, app.contact)
        return
    try:
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=20) as smtp:
            smtp.login(cfg.smtp_user, cfg.smtp_password)
            smtp.send_message(build_message(app, cfg))
    except Exception:
        log.exception("Письмо с заявкой не отправлено (заявка сохранена в базе)")


def notifier(cfg: Config):
    """Функция для Flow: отправка в отдельном потоке, чтобы бот не ждал почту."""
    def notify(app: Application) -> None:
        threading.Thread(target=send, args=(app, cfg), daemon=True).start()
    return notify
