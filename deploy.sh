#!/usr/bin/env bash
# Запуск и обновление бота на сервере одной командой:  bash deploy.sh
# Токен вводится в терминале (не отображается) и сохраняется только в .env с правами 600.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo ">> Первый запуск: настройка"
  read -r -s -p "Токен бота от @BotFather (ввод не виден): " TOKEN; echo
  [ -n "$TOKEN" ] || { echo "Токен пустой, выход."; exit 1; }
  read -r -p "Ваш числовой Telegram-id (@userinfobot): " ADMIN
  read -r -p "Ссылка на политику [https://kovcheg-systems.ru/privacy.html]: " POLICY
  POLICY="${POLICY:-https://kovcheg-systems.ru/privacy.html}"
  umask 077
  cat > .env <<EOF
BOT_TOKEN=$TOKEN
ADMIN_ID=${ADMIN:-0}
POLICY_URL=$POLICY
TESTERS_URL=
DB_PATH=/data/bot.db
SMTP_HOST=
SMTP_PORT=465
SMTP_USER=
SMTP_PASSWORD=
MAIL_TO=
MAIL_FROM=
EOF
  chmod 600 .env
  echo ">> .env создан"
fi

echo ">> Сборка"
docker build -q -t kovcheg-bot .
docker rm -f kovcheg-bot >/dev/null 2>&1 || true
docker run -d --name kovcheg-bot --restart=always --env-file .env -v kovcheg-data:/data kovcheg-bot >/dev/null
sleep 3
echo ">> Статус:"; docker ps --filter name=kovcheg-bot --format '{{.Names}} {{.Status}}'
echo ">> Журнал:"; docker logs --tail 5 kovcheg-bot 2>&1 | cut -c1-160
