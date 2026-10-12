"""What the Node's authorization server keeps: accounts, their passkeys, invitations, sessions, clients, codes and
tokens, in one SQLite file in the home, `node/auth.sqlite`, apart from every project's map.

Every secret is kept only as its SHA-256: an invitation, a session, a code and a token are random values of 256
bits made by `secrets`, so a copy of this file signs no one in and calls nothing. Passkeys keep only their public
keys. Nothing here is portable to another domain: a passkey belongs to the name it was made for, WebAuthn's relying
party, so a moved instance enrols its people again.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from metaform.data import DataConnection, private_database

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
    created REAL NOT NULL, disabled REAL);
CREATE TABLE IF NOT EXISTS passkeys (credential_id TEXT PRIMARY KEY, account TEXT NOT NULL REFERENCES accounts(id),
    public_key BLOB NOT NULL, sign_count INTEGER NOT NULL, transports TEXT, created REAL NOT NULL, used REAL);
CREATE TABLE IF NOT EXISTS invites (hash TEXT PRIMARY KEY, account TEXT NOT NULL REFERENCES accounts(id),
    expires REAL NOT NULL, used REAL);
CREATE TABLE IF NOT EXISTS challenges (id TEXT PRIMARY KEY, challenge BLOB NOT NULL, purpose TEXT NOT NULL,
    subject TEXT, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, account TEXT NOT NULL REFERENCES accounts(id),
    csrf TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS clients (client_id TEXT PRIMARY KEY, metadata TEXT NOT NULL, kind TEXT NOT NULL,
    fetched REAL NOT NULL, fresh_until REAL NOT NULL);
CREATE TABLE IF NOT EXISTS pending (id TEXT PRIMARY KEY, client_id TEXT NOT NULL, params TEXT NOT NULL,
    expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS codes (hash TEXT PRIMARY KEY, record TEXT NOT NULL, expires REAL NOT NULL, used REAL);
CREATE TABLE IF NOT EXISTS tokens (hash TEXT PRIMARY KEY, kind TEXT NOT NULL, family TEXT NOT NULL,
    client_id TEXT NOT NULL, account TEXT NOT NULL, scopes TEXT NOT NULL, resource TEXT NOT NULL,
    expires REAL NOT NULL, revoked REAL, rotated REAL);
CREATE INDEX IF NOT EXISTS tokens_family ON tokens(family);
"""


def digest(secret: str) -> str:
    return sha256(secret.encode()).hexdigest()


def made() -> str:
    return secrets.token_urlsafe(32)  # 256 bits, above the 160 RFC 6749 section 10.10 asks of a code


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    role: str
    disabled: bool


@dataclass(frozen=True)
class Token:
    kind: str
    family: str
    client_id: str
    account: str
    scopes: tuple[str, ...]
    resource: str
    expires: float
    revoked: bool
    rotated: bool


class AuthStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.db = private_database(path)
        self.db.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Generator[DataConnection]:
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                yield self.db
            except BaseException:
                self.db.execute('ROLLBACK')
                raise
            self.db.execute('COMMIT')

    def one(self, sql: str, *args: Any) -> tuple[Any, ...] | None:
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    # ------------------------------------------------------------------------------------------------ accounts

    def account(self, name: str | None = None, *, id: str | None = None) -> Account | None:
        row = self.one('SELECT id, name, role, disabled FROM accounts WHERE ' + ('id=?' if id else 'name=?'),
                       id or (name or '').lower())
        return Account(row[0], row[1], row[2], row[3] is not None) if row else None

    def accounts(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.db.execute(
                'SELECT a.name, a.role, a.disabled, (SELECT COUNT(*) FROM passkeys p WHERE p.account=a.id) '
                'FROM accounts a ORDER BY a.created').fetchall()
        return [{'name': name, 'role': role, 'passkeys': count, **({'disabled': True} if off else {})}
                for name, role, off, count in rows]

    def add_account(self, name: str, role: str = 'member') -> Account:
        found = self.account(name)
        if found is not None:
            return found
        made_id = uuid.uuid4().hex
        with self.tx() as db:
            db.execute('INSERT INTO accounts VALUES (?, ?, ?, ?, NULL)', (made_id, name.lower(), role, time.time()))
        return Account(made_id, name.lower(), role, False)

    def disable(self, name: str) -> bool:
        account = self.account(name)
        if account is None:
            return False
        now = time.time()
        with self.tx() as db:
            db.execute('UPDATE accounts SET disabled=? WHERE id=?', (now, account.id))
            db.execute('DELETE FROM sessions WHERE account=?', (account.id,))
            db.execute('UPDATE tokens SET revoked=? WHERE account=? AND revoked IS NULL', (now, account.id))
            db.execute('UPDATE invites SET used=? WHERE account=? AND used IS NULL', (now, account.id))
        return True

    def owner_exists(self) -> bool:
        return self.one("SELECT 1 FROM accounts WHERE role='owner' AND disabled IS NULL") is not None

    # ------------------------------------------------------------------------------------------------ invites

    def invite(self, account: Account, days: float = 7, *, hashed: str | None = None,
               expires: float | None = None) -> str | None:
        """A one-time setup secret for `account`, kept as its hash; with `hashed`, import one made elsewhere."""
        secret = None if hashed else made()
        with self.tx() as db:
            db.execute('INSERT OR IGNORE INTO invites VALUES (?, ?, ?, NULL)',
                       (hashed or digest(secret or ''), account.id, expires or time.time() + days * 86400))
        return secret

    def invited(self, secret: str) -> Account | None:
        row = self.one('SELECT account FROM invites WHERE hash=? AND used IS NULL AND expires>?', digest(secret),
                       time.time())
        if row is None:
            return None
        account = self.account(id=row[0])
        return account if account and not account.disabled else None

    def use_invite(self, secret: str) -> None:
        with self.tx() as db:
            db.execute('UPDATE invites SET used=? WHERE hash=?', (time.time(), digest(secret)))

    # ------------------------------------------------------------------------------------------------ passkeys

    def add_passkey(self, account: Account, credential_id: str, public_key: bytes, sign_count: int,
                    transports: list[str]) -> None:
        with self.tx() as db:
            db.execute('INSERT INTO passkeys VALUES (?, ?, ?, ?, ?, ?, NULL)',
                       (credential_id, account.id, public_key, sign_count, json.dumps(transports), time.time()))

    def passkey(self, credential_id: str) -> tuple[Account, bytes, int] | None:
        row = self.one('SELECT account, public_key, sign_count FROM passkeys WHERE credential_id=?', credential_id)
        if row is None:
            return None
        account = self.account(id=row[0])
        return (account, row[1], row[2]) if account and not account.disabled else None

    def passkey_ids(self, account: Account) -> list[str]:
        with self.lock:
            return [row[0] for row in self.db.execute('SELECT credential_id FROM passkeys WHERE account=?',
                                                      (account.id,))]

    def used_passkey(self, credential_id: str, sign_count: int) -> None:
        with self.tx() as db:
            db.execute('UPDATE passkeys SET sign_count=?, used=? WHERE credential_id=?',
                       (sign_count, time.time(), credential_id))

    # ------------------------------------------------------------------------------------------------ challenges

    def challenge(self, challenge: bytes, purpose: str, subject: str | None, seconds: float = 300) -> str:
        made_id = made()
        with self.tx() as db:
            db.execute('DELETE FROM challenges WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO challenges VALUES (?, ?, ?, ?, ?)',
                       (digest(made_id), challenge, purpose, subject, time.time() + seconds))
        return made_id

    def take_challenge(self, made_id: str, purpose: str) -> tuple[bytes, str | None] | None:
        """The challenge, once: taken, it is gone, so a ceremony cannot be replayed."""
        with self.tx() as db:
            row = db.execute('SELECT challenge, subject FROM challenges WHERE id=? AND purpose=? AND expires>?',
                             (digest(made_id), purpose, time.time())).fetchone()
            db.execute('DELETE FROM challenges WHERE id=?', (digest(made_id),))
        return (row[0], row[1]) if row else None

    # ------------------------------------------------------------------------------------------------ sessions

    def open_session(self, account: Account, seconds: float) -> tuple[str, str]:
        session, csrf = made(), made()
        with self.tx() as db:
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES (?, ?, ?, ?, ?)',
                       (digest(session), account.id, csrf, time.time(), time.time() + seconds))
        return session, csrf

    def session(self, session: str) -> tuple[Account, str] | None:
        row = self.one('SELECT account, csrf FROM sessions WHERE hash=? AND expires>?', digest(session), time.time())
        if row is None:
            return None
        account = self.account(id=row[0])
        return (account, row[1]) if account and not account.disabled else None

    def close_session(self, session: str) -> None:
        with self.tx() as db:
            db.execute('DELETE FROM sessions WHERE hash=?', (digest(session),))

    # ------------------------------------------------------------------------------------------------ clients

    def client(self, client_id: str) -> tuple[dict[str, Any], str, float] | None:
        row = self.one('SELECT metadata, kind, fresh_until FROM clients WHERE client_id=?', client_id)
        return (json.loads(row[0]), row[1], row[2]) if row else None

    def save_client(self, client_id: str, metadata: dict[str, Any], kind: str, fresh_until: float) -> None:
        with self.tx() as db:
            db.execute('INSERT OR REPLACE INTO clients VALUES (?, ?, ?, ?, ?)',
                       (client_id, json.dumps(metadata), kind, time.time(), fresh_until))

    # ------------------------------------------------------------------------------------------------ requests

    def hold(self, client_id: str, params: dict[str, Any], seconds: float = 600) -> str:
        made_id = made()
        with self.tx() as db:
            db.execute('DELETE FROM pending WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO pending VALUES (?, ?, ?, ?)',
                       (made_id, client_id, json.dumps(params), time.time() + seconds))
        return made_id

    def held(self, made_id: str) -> tuple[str, dict[str, Any]] | None:
        row = self.one('SELECT client_id, params FROM pending WHERE id=? AND expires>?', made_id, time.time())
        return (row[0], json.loads(row[1])) if row else None

    def release(self, made_id: str) -> None:
        with self.tx() as db:
            db.execute('DELETE FROM pending WHERE id=?', (made_id,))

    # ------------------------------------------------------------------------------------------------ codes

    def add_code(self, record: dict[str, Any], seconds: float) -> str:
        code = made()
        with self.tx() as db:
            db.execute('INSERT INTO codes VALUES (?, ?, ?, NULL)',
                       (digest(code), json.dumps(record), time.time() + seconds))
        return code

    def code(self, code: str) -> tuple[dict[str, Any], float, bool] | None:
        row = self.one('SELECT record, expires, used FROM codes WHERE hash=?', digest(code))
        return (json.loads(row[0]), row[1], row[2] is not None) if row else None

    def use_code(self, code: str) -> bool:
        """Mark a code used; False when it already was, OAuth 2.1 section 4.1.3: then every token it gave is
        revoked, since a second use means it was stolen."""
        with self.tx() as db:
            changed = db.execute('UPDATE codes SET used=? WHERE hash=? AND used IS NULL',
                                 (time.time(), digest(code))).rowcount
            if not changed:
                db.execute('UPDATE tokens SET revoked=? WHERE family=? AND revoked IS NULL',
                           (time.time(), digest(code)))
        return bool(changed)

    # ------------------------------------------------------------------------------------------------ tokens

    def add_token(self, kind: str, family: str, client_id: str, account: str, scopes: list[str], resource: str,
                  seconds: float) -> tuple[str, float]:
        token, expires = made(), time.time() + seconds
        with self.tx() as db:
            db.execute('INSERT INTO tokens VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)',
                       (digest(token), kind, family, client_id, account, ' '.join(scopes), resource, expires))
        return token, expires

    def token(self, token: str) -> Token | None:
        row = self.one('SELECT kind, family, client_id, account, scopes, resource, expires, revoked, rotated '
                       'FROM tokens WHERE hash=?', digest(token))
        if row is None:
            return None
        return Token(row[0], row[1], row[2], row[3], tuple(row[4].split()), row[5], row[6], row[7] is not None,
                     row[8] is not None)

    def rotate(self, token: str) -> bool:
        """Retire a refresh token as it is used, OAuth 2.1 section 4.3.1; a retired one used again revokes its
        whole family, since only a thief would hold it."""
        with self.tx() as db:
            changed = db.execute('UPDATE tokens SET rotated=? WHERE hash=? AND rotated IS NULL AND revoked IS NULL',
                                 (time.time(), digest(token))).rowcount
            if not changed:
                row = db.execute('SELECT family FROM tokens WHERE hash=?', (digest(token),)).fetchone()
                if row:
                    db.execute('UPDATE tokens SET revoked=? WHERE family=? AND revoked IS NULL', (time.time(), row[0]))
        return bool(changed)

    def revoke_family(self, family: str) -> None:
        with self.tx() as db:
            db.execute('UPDATE tokens SET revoked=? WHERE family=? AND revoked IS NULL', (time.time(), family))
