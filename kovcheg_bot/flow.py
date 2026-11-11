"""Логика диалога без привязки к Telegram: событие на входе, список ответов на выходе. Проверяется тестами."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol

from . import texts as T

# Состояния ожидания текста от человека.
ST_IDLE = "idle"
ST_TASK = "await_task"
ST_CONTACT = "await_contact"


@dataclass
class Button:
    label: str
    data: str = ""
    url: str = ""


@dataclass
class Reply:
    text: str
    rows: List[List[Button]] = field(default_factory=list)


@dataclass
class User:
    id: int
    username: str = ""


@dataclass
class Profile:
    uid: int
    username: str = ""
    consent: bool = False
    source: str = "direct"
    segment: str = ""       # human / biz
    product: str = ""       # код продукта из texts.PRODUCTS
    tag: str = ""           # b2c_barabashka и т.п.
    answer: str = ""        # ответ на уточняющий вопрос
    state: str = ST_IDLE
    task: str = ""
    created_at: float = 0.0


@dataclass
class Application:
    uid: int
    username: str
    kind: str               # call / order
    tag: str
    source: str
    task: str
    contact: str
    created_at: float = 0.0


class Store(Protocol):
    def get(self, uid: int) -> Optional[Profile]: ...
    def save(self, profile: Profile) -> None: ...
    def delete(self, uid: int) -> bool: ...
    def add_application(self, app: Application) -> None: ...


class Flow:
    """Один экземпляр на бота. notify вызывается, когда создана заявка (письмо на почту)."""

    def __init__(self, store: Store, notify: Optional[Callable[[Application], None]] = None,
                 policy_url: str = "", testers_url: str = "", now: Callable[[], float] = time.time):
        self.store = store
        self.notify = notify or (lambda app: None)
        self.policy_url = policy_url
        self.testers_url = testers_url
        self.now = now
        self._pending_source: Dict[int, str] = {}   # откуда пришёл человек, пока нет согласия (в памяти, на диск не пишем)

    # ---- входы ----

    def start(self, user: User, payload: str = "") -> List[Reply]:
        self._pending_source[user.id] = self._clean_source(payload)
        profile = self.store.get(user.id)
        if profile is not None and profile.consent:
            profile.state = ST_IDLE
            self.store.save(profile)
            return [Reply(T.WHO, self._who_rows())]
        return [self._welcome()]

    def button(self, user: User, data: str) -> List[Reply]:
        if data == "restart":
            return self.start(user)
        if data == "no":
            self._pending_source.pop(user.id, None)
            return [Reply(T.DECLINED)]
        if data == "ok":
            return self._consent(user)

        profile = self.store.get(user.id)
        if profile is None or not profile.consent:
            return [self._welcome()]   # без согласия дальше не идём

        if data in ("seg:human", "seg:biz"):
            profile.segment = data.split(":")[1]
            self.store.save(profile)
            codes = T.HUMAN_PRODUCTS if profile.segment == "human" else T.BIZ_PRODUCTS
            rows = [[Button(T.PRODUCTS[c][0], "p:" + c)] for c in codes]
            return [Reply(T.PICK_PRODUCT, rows)]

        if data.startswith("p:"):
            code = data[2:]
            if code not in T.PRODUCTS:
                return [Reply(T.IDLE, self._menu_rows())]
            _, tag, intro, question, options = T.PRODUCTS[code]
            profile.product, profile.tag = code, tag
            self.store.save(profile)
            rows = [[Button(o, "a:%s:%d" % (code, i))] for i, o in enumerate(options)]
            return [Reply(intro + "\n\n" + question, rows)]

        if data.startswith("a:"):
            return self._answered(profile, data)

        if data == "f:call":
            return self._start_application(profile, "call")
        if data == "f:order":
            return self._start_application(profile, "order")
        if data == "f:chat":
            text = T.CHAT_OK.format(url=self.testers_url) if self.testers_url else T.CHAT_SOON
            return [Reply(text)]
        if data == "f:wait":
            return [Reply(T.WAIT_OK)]
        return [Reply(T.IDLE, self._menu_rows())]

    def text(self, user: User, text: str) -> List[Reply]:
        profile = self.store.get(user.id)
        text = (text or "").strip()
        if profile is None or not profile.consent or profile.state == ST_IDLE or not text:
            return [Reply(T.IDLE, self._menu_rows())]
        profile.username = user.username or profile.username
        if profile.state == ST_TASK:
            profile.task = text[:2000]
            if user.username:
                return self._finish_application(profile, contact="@" + user.username)
            profile.state = ST_CONTACT
            self.store.save(profile)
            return [Reply(T.ASK_CONTACT)]
        if profile.state == ST_CONTACT:
            return self._finish_application(profile, contact=text[:300])
        return [Reply(T.IDLE, self._menu_rows())]

    def delete(self, user: User) -> List[Reply]:
        self._pending_source.pop(user.id, None)
        return [Reply(T.DELETED if self.store.delete(user.id) else T.NOTHING_TO_DELETE)]

    def privacy(self) -> List[Reply]:
        return [Reply(T.PRIVACY, [[Button(T.POLICY_BUTTON, url=self.policy_url)]] if self.policy_url else [])]

    # ---- внутреннее ----

    def _welcome(self) -> Reply:
        rows = [[Button(T.CONSENT_BUTTON, "ok")], [Button(T.DECLINE_BUTTON, "no")]]
        if self.policy_url:
            rows.insert(0, [Button(T.POLICY_BUTTON, url=self.policy_url)])
        return Reply(T.WELCOME, rows)

    def _consent(self, user: User) -> List[Reply]:
        profile = self.store.get(user.id) or Profile(uid=user.id, created_at=self.now())
        profile.username = user.username
        profile.consent = True
        profile.source = self._pending_source.pop(user.id, profile.source or "direct")
        profile.state = ST_IDLE
        self.store.save(profile)
        return [Reply(T.WHO, self._who_rows())]

    def _answered(self, profile: Profile, data: str) -> List[Reply]:
        try:
            _, code, idx = data.split(":")
            options = T.PRODUCTS[code][4]
            profile.answer = options[int(idx)]
        except (ValueError, KeyError, IndexError):
            return [Reply(T.IDLE, self._menu_rows())]
        profile.product, profile.tag = code, T.PRODUCTS[code][1]
        self.store.save(profile)
        rows = [[Button(T.FINAL_CALL, "f:call")], [Button(T.FINAL_CHAT, "f:chat")]]
        if profile.segment == "biz":
            rows.insert(0, [Button(T.FINAL_ORDER, "f:order")])
        rows.append([Button(T.FINAL_WAIT, "f:wait")])
        return [Reply(T.FINAL.format(product=T.PRODUCTS[code][0].split(" (")[0]), rows)]

    def _start_application(self, profile: Profile, kind: str) -> List[Reply]:
        profile.task = ""
        if kind == "order":
            profile.state = ST_TASK
            self.store.save(profile)
            return [Reply(T.ASK_TASK)]
        # Созвон: задачу не спрашиваем, нужен только контакт.
        profile.task = "Хочет созвон (20 мин). Ответ: " + (profile.answer or "-")
        if profile.username:
            return self._finish_application(profile, contact="@" + profile.username, kind=kind)
        profile.state = ST_CONTACT
        self.store.save(profile)
        return [Reply(T.ASK_CONTACT)]

    def _finish_application(self, profile: Profile, contact: str, kind: Optional[str] = None) -> List[Reply]:
        kind = kind or ("order" if profile.task and not profile.task.startswith("Хочет созвон") else "call")
        profile.state = ST_IDLE
        self.store.save(profile)
        app = Application(uid=profile.uid, username=profile.username, kind=kind, tag=profile.tag,
                          source=profile.source, task=profile.task, contact=contact, created_at=self.now())
        self.store.add_application(app)
        try:
            self.notify(app)
        except Exception:   # письмо не ушло: заявка сохранена, человеку об этом знать незачем
            pass
        return [Reply(T.APPLICATION_OK if kind == "order" else T.CALL_OK)]

    @staticmethod
    def _who_rows() -> List[List[Button]]:
        return [[Button(T.WHO_HUMAN, "seg:human")], [Button(T.WHO_BIZ, "seg:biz")]]

    @staticmethod
    def _menu_rows() -> List[List[Button]]:
        return [[Button(T.MENU_BUTTON, "restart")]]

    @staticmethod
    def _clean_source(payload: str) -> str:
        payload = (payload or "").strip()
        return payload[:40] if payload and all(c.isalnum() or c in "_-" for c in payload) else "direct"
