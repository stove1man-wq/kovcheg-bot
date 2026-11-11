"""Адаптер Telegram (aiogram 3): превращает события в вызовы Flow и рисует ответы кнопками."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from . import mailer
from .config import Config
from .flow import Flow, Reply, User
from .storage import SqliteStore

log = logging.getLogger("kovcheg_bot")


def keyboard(reply: Reply):
    if not reply.rows:
        return None
    rows = []
    for row in reply.rows:
        rows.append([InlineKeyboardButton(text=b.label, url=b.url) if b.url
                     else InlineKeyboardButton(text=b.label, callback_data=b.data) for b in row])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send(message: Message, replies):
    for reply in replies:
        await message.answer(reply.text, reply_markup=keyboard(reply), disable_web_page_preview=True)


def build(cfg: Config):
    store = SqliteStore(cfg.db_path)
    flow = Flow(store, notify=mailer.notifier(cfg), policy_url=cfg.policy_url, testers_url=cfg.testers_url)
    router = Router()

    def who(obj) -> User:
        return User(obj.from_user.id, obj.from_user.username or "")

    @router.message(CommandStart())
    async def on_start(message: Message, command: CommandObject):
        await send(message, flow.start(who(message), command.args or ""))

    @router.message(Command("delete"))
    async def on_delete(message: Message):
        await send(message, flow.delete(who(message)))

    @router.message(Command("privacy"))
    async def on_privacy(message: Message):
        await send(message, flow.privacy())

    @router.message(Command("stats"))
    async def on_stats(message: Message):
        if not cfg.admin_id or message.from_user.id != cfg.admin_id:
            return
        stats = store.stats()
        text = "Интерес по направлениям:\n" + ("\n".join("%s: %d" % kv for kv in sorted(stats.items())) or "пока пусто")
        await message.answer(text)

    @router.message(Command("apps"))
    async def on_apps(message: Message):
        if not cfg.admin_id or message.from_user.id != cfg.admin_id:
            return
        apps = store.recent_applications(10)
        lines = ["%s | %s | %s | %s" % (a.kind, a.tag, a.contact, (a.task or "-")[:80]) for a in apps]
        await message.answer("Последние заявки:\n" + ("\n".join(lines) or "пока пусто"))

    @router.callback_query()
    async def on_button(query: CallbackQuery):
        await query.answer()
        if query.message is None:
            return
        await send(query.message, flow.button(who(query), query.data or ""))

    @router.message(F.text)
    async def on_text(message: Message):
        await send(message, flow.text(who(message), message.text or ""))

    dp = Dispatcher()
    dp.include_router(router)
    return Bot(cfg.token), dp


async def run(cfg: Config) -> None:
    bot, dp = build(cfg)
    me = await bot.get_me()
    log.info("Бот запущен: @%s", me.username)
    await dp.start_polling(bot)
