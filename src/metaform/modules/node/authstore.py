"""What the Node's authorization server keeps: accounts, their passkeys, invitations, sessions, clients, codes and
tokens, in one SQLite file in the home, `node/auth.sqlite`, apart from every project's map.

Every secret is kept only as its SHA-256: an invitation, a session, a code and a token are random values of 256
bits made by `secrets`, so a copy of this file signs no one in and calls nothing. Passkeys keep only their public
keys. Nothing here is portable to another domain: a passkey belongs to the name it was made for, WebAuthn's relying
party, so a moved instance enrols its people again.

Each account row also carries its `generation`, the number every signed token names (tokens.py): bumping it signs the
account out everywhere. Its one pending invitation is on the row too, as a hash and an expiry.

`BrokerStore` is the store of the broker role at metaform.ing, which keeps nothing on disk but the accounts and their
passkeys' public keys: its tokens are signed (tokens.py), and its sign-in challenges, sessions, consent requests and
client metadata are held in memory, lost on a restart by design, which costs anyone mid-sign-in a retry. Opened on a
file that holds any of a self-hosted Node's tables (a migrated store, or one a command opened the other way), it drops
them, so the file never keeps more than the accounts and passkeys. `open_store` picks the right one from the role the
server last ran as, so a command run beside a broker (`metaform node signout`) opens the broker's store.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from metaform import home
from metaform.data import DataConnection, private_database

DURABLE = """
CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
    created REAL NOT NULL, disabled REAL, generation INTEGER NOT NULL DEFAULT 0, invite_sha256 TEXT,
    invite_expires REAL);
CREATE TABLE IF NOT EXISTS passkeys (credential_id TEXT PRIMARY KEY, account TEXT NOT NULL REFERENCES accounts(id),
    public_key BLOB NOT NULL, sign_count INTEGER NOT NULL, transports TEXT, created REAL NOT NULL, used REAL);
"""
# What only a self-hosted Node keeps on disk; the broker holds the same in memory, or needs none of it.
SCHEMA = """
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
# Everything a self-hosted Node's store may hold beside the accounts and passkeys, the old invitations table included.
SELF_HOSTED_TABLES = ('invites', 'challenges', 'sessions', 'clients', 'pending', 'codes', 'tokens')
# Refresh-token marks kept across restarts when the operator sets node_refresh_replay to durable: grant ids and
# counters, no secret (tokens.Families).
FAMILIES = """
CREATE TABLE IF NOT EXISTS families (family TEXT PRIMARY KEY, seq INTEGER NOT NULL, revoked INTEGER NOT NULL,
    expires REAL NOT NULL);
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
    transient = SCHEMA  # the tables kept on disk beside the accounts; the broker keeps none

    def __init__(self, path: Path) -> None:
        if home.is_home_path(path):
            home.mkdir_private(path.parent)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.db = private_database(path)
        self.families_ready = False
        self.db.executescript(DURABLE)
        self._migrate()
        if self.transient:
            self.db.executescript(self.transient)

    def _migrate(self) -> None:
        """An account table from before generations and invitations on the row: the columns are added, and each
        account's newest unused invitation moves onto its row. The old invites table is left as it was."""
        with self.lock:
            columns = {row[1] for row in self.db.execute('PRAGMA table_info(accounts)')}
            if 'generation' not in columns:
                self.db.execute('ALTER TABLE accounts ADD COLUMN generation INTEGER NOT NULL DEFAULT 0')
            if 'invite_sha256' not in columns:
                self.db.execute('ALTER TABLE accounts ADD COLUMN invite_sha256 TEXT')
                self.db.execute('ALTER TABLE accounts ADD COLUMN invite_expires REAL')
                old = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='invites'").fetchone()
                if old is not None:
                    for hashed, account, expires in self.db.execute(
                            'SELECT hash, account, expires FROM invites WHERE used IS NULL AND expires>? '
                            'ORDER BY expires', (time.time(),)).fetchall():
                        self.db.execute('UPDATE accounts SET invite_sha256=?, invite_expires=? WHERE id=?',
                                        (hashed, expires, account))

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
            db.execute('INSERT INTO accounts (id, name, role, created) VALUES (?, ?, ?, ?)',
                       (made_id, name.lower(), role, time.time()))
        return Account(made_id, name.lower(), role, False)

    def disable(self, name: str) -> bool:
        account = self.account(name)
        if account is None:
            return False
        now = time.time()
        with self.tx() as db:
            db.execute("UPDATE accounts SET disabled=?, generation=generation+1, invite_sha256='' WHERE id=?",
                       (now, account.id))
        self.forget(account.id)
        self.revoke_account(account.id, now)
        return True

    def revoke_account(self, account_id: str, now: float) -> None:
        with self.tx() as db:
            db.execute('UPDATE tokens SET revoked=? WHERE account=? AND revoked IS NULL', (now, account_id))

    def forget(self, account_id: str) -> None:
        """Every session of the account ends, as its generation moved."""
        with self.tx() as db:
            db.execute('DELETE FROM sessions WHERE account=?', (account_id,))

    def generation(self, account_id: str) -> tuple[int, bool] | None:
        row = self.one('SELECT generation, disabled FROM accounts WHERE id=?', account_id)
        return (int(row[0]), row[1] is not None) if row else None

    def bump_generation(self, account_id: str) -> int:
        """Sign the account out everywhere: every token naming the old generation stops working."""
        with self.tx() as db:
            db.execute('UPDATE accounts SET generation=generation+1 WHERE id=?', (account_id,))
            row = db.execute('SELECT generation FROM accounts WHERE id=?', (account_id,)).fetchone()
        self.forget(account_id)
        return int(row[0]) if row else 0

    def owner_exists(self) -> bool:
        return self.one("SELECT 1 FROM accounts WHERE role='owner' AND disabled IS NULL") is not None

    # ------------------------------------------------------------------------------------------------ invites

    def invite(self, account: Account, days: float = 7, *, hashed: str | None = None,
               expires: float | None = None) -> str | None:
        """A one-time setup secret for `account`, kept as its hash on the account's row, replacing any earlier one;
        with `hashed`, import one made elsewhere, only onto a row that never held one, so the owner's first link is
        not brought back once used."""
        secret = None if hashed else made()
        until = expires or time.time() + days * 86400
        with self.tx() as db:
            if hashed:
                db.execute('UPDATE accounts SET invite_sha256=?, invite_expires=? WHERE id=? AND invite_sha256 IS NULL',
                           (hashed, until, account.id))
            else:
                db.execute('UPDATE accounts SET invite_sha256=?, invite_expires=? WHERE id=?',
                           (digest(secret or ''), until, account.id))
        return secret

    def invited(self, secret: str) -> Account | None:
        if not secret:
            return None
        row = self.one('SELECT id FROM accounts WHERE invite_sha256=? AND invite_expires>? AND disabled IS NULL',
                       digest(secret), time.time())
        return self.account(id=row[0]) if row else None

    def use_invite(self, secret: str) -> None:
        with self.tx() as db:
            db.execute("UPDATE accounts SET invite_sha256='' WHERE invite_sha256=?", (digest(secret),))

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

    # ------------------------------------------------------------------------------------------------ families

    def _families(self) -> None:
        with self.lock:
            if not self.families_ready:
                self.db.executescript(FAMILIES)
                self.families_ready = True

    def family(self, family: str) -> tuple[int, bool] | None:
        """A refresh family's mark, with node_refresh_replay durable (tokens.Families)."""
        self._families()
        with self.lock:
            row = self.db.execute('SELECT seq, revoked FROM families WHERE family=? AND expires>?',
                                  (family, time.time())).fetchone()
        return (int(row[0]), bool(row[1])) if row else None

    def save_family(self, family: str, seq: int, revoked: bool, expires: float) -> None:
        self._families()
        with self.tx() as db:
            db.execute('DELETE FROM families WHERE expires<?', (time.time(),))
            db.execute('INSERT OR REPLACE INTO families VALUES (?, ?, ?, ?)', (family, seq, int(revoked), expires))


class BrokerStore(AuthStore):
    """The broker's store: accounts and passkeys on disk, everything else in this process's memory. Challenges,
    sessions, consent requests and client metadata documents live here until they expire or the process stops.

    `families` says what to do with the refresh marks table (tokens.Families): True keeps it (node_refresh_replay
    durable), False drops it, None, for a command that does not know the setting, leaves it as it is."""

    transient = ''
    CLIENTS_HELD = 1024  # client metadata documents kept, the least recently used dropped first

    def __init__(self, path: Path, families: bool | None = None) -> None:
        super().__init__(path)
        with self.lock:
            for table in SELF_HOSTED_TABLES + (('families',) if families is False else ()):
                self.db.execute(f'DROP TABLE IF EXISTS {table}')
            self.db.execute('DROP INDEX IF EXISTS tokens_family')
        self.memory_lock = threading.Lock()
        self.challenges: dict[str, tuple[bytes, str, str | None, float]] = {}
        self.sessions: dict[str, tuple[str, str, int, float]] = {}
        self.clients: OrderedDict[str, tuple[dict[str, Any], str, float]] = OrderedDict()
        self.pending: dict[str, tuple[str, dict[str, Any], float]] = {}

    @staticmethod
    def _prune(held: dict[str, Any], now: float) -> None:
        for key, value in list(held.items()):
            if value[-1] < now:
                held.pop(key, None)

    def forget(self, account_id: str) -> None:
        with self.memory_lock:
            for key, (account, _, _, _) in list(self.sessions.items()):
                if account == account_id:
                    self.sessions.pop(key, None)

    def revoke_account(self, account_id: str, now: float) -> None:
        return None  # its tokens name a generation that has moved on

    def add_passkey(self, account: Account, credential_id: str, public_key: bytes, sign_count: int,
                    transports: list[str]) -> None:
        with self.tx() as db:  # no times kept: the key and its counter are all a passkey check needs
            db.execute('INSERT INTO passkeys VALUES (?, ?, ?, ?, ?, 0, NULL)',
                       (credential_id, account.id, public_key, sign_count, json.dumps(transports)))

    def used_passkey(self, credential_id: str, sign_count: int) -> None:
        with self.tx() as db:
            db.execute('UPDATE passkeys SET sign_count=? WHERE credential_id=?', (sign_count, credential_id))

    def challenge(self, challenge: bytes, purpose: str, subject: str | None, seconds: float = 300) -> str:
        made_id = made()
        with self.memory_lock:
            self._prune(self.challenges, time.time())
            self.challenges[digest(made_id)] = (challenge, purpose, subject, time.time() + seconds)
        return made_id

    def take_challenge(self, made_id: str, purpose: str) -> tuple[bytes, str | None] | None:
        with self.memory_lock:
            found = self.challenges.pop(digest(made_id), None)
        if found is None or found[1] != purpose or found[3] < time.time():
            return None
        return found[0], found[2]

    def open_session(self, account: Account, seconds: float) -> tuple[str, str]:
        """A session names the generation it was opened under, as every token does: signing the account out
        everywhere, from this process or from `metaform node signout` in another, ends it at its next use."""
        session, csrf = made(), made()
        current = self.generation(account.id)
        with self.memory_lock:
            self._prune(self.sessions, time.time())
            self.sessions[digest(session)] = (account.id, csrf, current[0] if current else -1, time.time() + seconds)
        return session, csrf

    def session(self, session: str) -> tuple[Account, str] | None:
        with self.memory_lock:
            found = self.sessions.get(digest(session))
        if found is None or found[3] < time.time():
            return None
        current = self.generation(found[0])
        account = self.account(id=found[0])
        if current is None or current[0] != found[2] or account is None or account.disabled:
            with self.memory_lock:
                self.sessions.pop(digest(session), None)
            return None
        return account, found[1]

    def close_session(self, session: str) -> None:
        with self.memory_lock:
            self.sessions.pop(digest(session), None)

    def client(self, client_id: str) -> tuple[dict[str, Any], str, float] | None:
        with self.memory_lock:
            found = self.clients.get(client_id)
            if found is not None:
                self.clients.move_to_end(client_id)
            return found

    def save_client(self, client_id: str, metadata: dict[str, Any], kind: str, fresh_until: float) -> None:
        """Held while fresh, and at most CLIENTS_HELD at once: a document dropped early is fetched again on its
        client's next request, so the bound costs a fetch, never a sign-in."""
        with self.memory_lock:
            self._prune(self.clients, time.time())
            self.clients[client_id] = (metadata, kind, fresh_until)
            self.clients.move_to_end(client_id)
            while len(self.clients) > self.CLIENTS_HELD:
                self.clients.popitem(last=False)

    def hold(self, client_id: str, params: dict[str, Any], seconds: float = 600) -> str:
        made_id = made()
        with self.memory_lock:
            self._prune(self.pending, time.time())
            self.pending[made_id] = (client_id, params, time.time() + seconds)
        return made_id

    def held(self, made_id: str) -> tuple[str, dict[str, Any]] | None:
        with self.memory_lock:
            found = self.pending.get(made_id)
        return (found[0], found[1]) if found is not None and found[2] > time.time() else None

    def release(self, made_id: str) -> None:
        with self.memory_lock:
            self.pending.pop(made_id, None)


def role_file(path: Path) -> Path:
    """Beside the store: the role the server last ran as, written by `metaform node auth`."""
    return path.parent / 'role'


def open_store(path: Path, broker: bool | None = None, families: bool | None = None) -> AuthStore:
    """The store at `path` as its server uses it: a broker's (BrokerStore) or a self-hosted Node's (AuthStore). With
    `broker` None, as for a command run beside the server, the role the server last ran as decides."""
    if broker is None:
        try:
            broker = role_file(path).read_text(encoding='utf-8').strip() == 'broker'
        except OSError:
            broker = False
    return BrokerStore(path, families) if broker else AuthStore(path)
