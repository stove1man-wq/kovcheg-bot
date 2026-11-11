"""Хранилища: в памяти (для тестов) и SQLite (рабочее). Данные человека удаляются командой /delete."""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import asdict, fields
from typing import Dict, List, Optional

from .flow import Application, Profile


class MemoryStore:
    def __init__(self) -> None:
        self.profiles: Dict[int, Profile] = {}
        self.applications: List[Application] = []

    def get(self, uid: int) -> Optional[Profile]:
        p = self.profiles.get(uid)
        return Profile(**asdict(p)) if p else None

    def save(self, profile: Profile) -> None:
        self.profiles[profile.uid] = Profile(**asdict(profile))

    def delete(self, uid: int) -> bool:
        existed = uid in self.profiles or any(a.uid == uid for a in self.applications)
        self.profiles.pop(uid, None)
        self.applications = [a for a in self.applications if a.uid != uid]
        return existed

    def add_application(self, app: Application) -> None:
        self.applications.append(app)

    def stats(self) -> Dict[str, int]:
        result: Dict[str, int] = {}
        for p in self.profiles.values():
            if p.consent and p.tag:
                result[p.tag] = result.get(p.tag, 0) + 1
        return result


_PROFILE_COLUMNS = [f.name for f in fields(Profile)]
_APP_COLUMNS = [f.name for f in fields(Application)]


class SqliteStore:
    def __init__(self, path: str) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS profiles (uid INTEGER PRIMARY KEY, username TEXT, consent INTEGER, source TEXT,"
                " segment TEXT, product TEXT, tag TEXT, answer TEXT, state TEXT, task TEXT, created_at REAL)")
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, username TEXT,"
                " kind TEXT, tag TEXT, source TEXT, task TEXT, contact TEXT, created_at REAL)")

    def get(self, uid: int) -> Optional[Profile]:
        with self._lock:
            row = self._db.execute("SELECT * FROM profiles WHERE uid=?", (uid,)).fetchone()
        if row is None:
            return None
        data = {c: row[c] for c in _PROFILE_COLUMNS}
        data["consent"] = bool(data["consent"])
        return Profile(**data)

    def save(self, profile: Profile) -> None:
        values = asdict(profile)
        values["consent"] = int(profile.consent)
        marks = ",".join("?" for _ in _PROFILE_COLUMNS)
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO profiles (%s) VALUES (%s)" % (",".join(_PROFILE_COLUMNS), marks),
                             [values[c] for c in _PROFILE_COLUMNS])

    def delete(self, uid: int) -> bool:
        with self._lock, self._db:
            a = self._db.execute("DELETE FROM profiles WHERE uid=?", (uid,)).rowcount
            b = self._db.execute("DELETE FROM applications WHERE uid=?", (uid,)).rowcount
        return bool(a or b)

    def add_application(self, app: Application) -> None:
        values = asdict(app)
        with self._lock, self._db:
            self._db.execute("INSERT INTO applications (%s) VALUES (%s)" % (",".join(_APP_COLUMNS), ",".join("?" for _ in _APP_COLUMNS)),
                             [values[c] for c in _APP_COLUMNS])

    def stats(self) -> Dict[str, int]:
        with self._lock:
            rows = self._db.execute("SELECT tag, COUNT(*) AS n FROM profiles WHERE consent=1 AND tag<>'' GROUP BY tag").fetchall()
        return {r["tag"]: r["n"] for r in rows}
