"""Настройки из переменных окружения (и файла .env рядом с запуском). Секреты в репозиторий не попадают."""
from __future__ import annotations

import os
from dataclasses import dataclass


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Config:
    token: str
    db_path: str = "bot.db"
    admin_id: int = 0
    policy_url: str = ""
    testers_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    mail_to: str = ""
    mail_from: str = ""

    @property
    def mail_ready(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.mail_to)

    @staticmethod
    def from_env() -> "Config":
        load_dotenv()
        env = os.environ.get
        token = env("BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit("Не задан BOT_TOKEN: впишите токен от @BotFather в файл .env (см. README).")
        return Config(
            token=token,
            db_path=env("DB_PATH", "bot.db"),
            admin_id=int(env("ADMIN_ID", "0") or 0),
            policy_url=env("POLICY_URL", ""),
            testers_url=env("TESTERS_URL", ""),
            smtp_host=env("SMTP_HOST", ""),
            smtp_port=int(env("SMTP_PORT", "465") or 465),
            smtp_user=env("SMTP_USER", ""),
            smtp_password=env("SMTP_PASSWORD", ""),
            mail_to=env("MAIL_TO", ""),
            mail_from=env("MAIL_FROM", "") or env("SMTP_USER", ""),
        )
