"""Signed tokens: what lets a Node's authorization server keep no token on disk.

Every token the broker role issues is a JWT signed with the Node's own Ed25519 key (EdDSA, RFC 8037), named by `kid`
and published at `/.well-known/jwks.json`, so whoever checks one needs the key set and nothing else: no table, no
introspection call. Each token says what it is in its `typ` header, so one kind is never accepted as another: `at+jwt`
an access token (RFC 9068), `rt+jwt` a refresh token, `code+jwt` an authorization code, `mf-assert+jwt` the broker's
statement of who is calling, which the person's own machine checks, `client-id+jwt` a client id the broker issued by
dynamic registration, which is the client's registered metadata itself.

What a signed token cannot do by itself is be taken back. Two small things held here do that:

- `Generations`: each account carries a generation number, the only token state on disk. Every token names the
  generation it was issued under, and a token whose generation is not the account's current one is refused, so
  bumping it ("sign out everywhere") ends every token, session and tunnel of the account at once and after a restart.
  The number is read once per account and kept for `GENERATION_SECONDS`, so the check costs no read per request and a
  bump made by another process (`metaform node signout` on the host) reaches the server within that time. It ends
  what this server issued, not what a copy of its key can forge, since a forger writes any generation it likes: a key
  that may have been copied is ended by revoking the key itself (`Keys.rotate(revoke_old=True)`).
- `Families`: a refresh token belongs to a family, the grant it came from, and carries a sequence number. The highest
  number issued per family is kept, in memory by default: a refresh token presented below the mark was already used
  once, which only a thief does, so the family is revoked and both holders sign in again (OAuth 2.1 section 4.3.1).
  After a restart the marks are empty, so a refresh token retired before the restart can be used once more; with
  `node_refresh_replay` at `durable` the marks are kept in the store (grant ids and counters, no secret) and that gap
  closes. Revoking one grant (RFC 7009) is held the same way.

DPoP (RFC 9449) binds the local service's tokens to a key it made at login, so its token alone, copied out of a log,
is useless: `dpop_key` checks a proof and returns the key's thumbprint (RFC 7638), which the token names in `cnf.jkt`.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from jwt.algorithms import OKPAlgorithm

ALGORITHM = 'EdDSA'
CLI_CLIENT = 'metaform-cli'  # the local service, `metaform cloud login`: built in, a public client with no redirect
DEVICE_GRANT = 'urn:ietf:params:oauth:grant-type:device_code'
TUNNEL_SCOPE = 'tunnel:connect'
ACCESS, REFRESH, CODE, ASSERTION, CLIENT_ID = 'at+jwt', 'rt+jwt', 'code+jwt', 'mf-assert+jwt', 'client-id+jwt'
ACCESS_SECONDS = 600  # ten minutes: a stolen access token is short-lived and bound to one resource
REFRESH_SECONDS = 30 * 86400  # sliding
REFRESH_CAP_SECONDS = 90 * 86400  # from the passkey sign-in that started the grant, however often it was refreshed
CODE_SECONDS = 300
ASSERTION_SECONDS = 60
GENERATION_SECONDS = 30.0
DPOP_SKEW = 60  # a DPoP proof older or newer than this is refused
DPOP_ALGORITHMS = ('ES256', 'EdDSA')
CLOCK_LEEWAY = 5
RELOAD_SECONDS = 5.0  # how often a running server looks for keys rotated or revoked by `metaform node rotate-key`


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def body_hash(body: bytes) -> str:
    """The request body's SHA-256 as an assertion names it, `bh`, so a statement for one request fits no other."""
    return b64(hashlib.sha256(body).digest())


def thumbprint(jwk: dict[str, Any]) -> str:
    """The JWK thumbprint of RFC 7638: the required members only, in lexical order, without whitespace."""
    members = {'EC': ('crv', 'kty', 'x', 'y'), 'OKP': ('crv', 'kty', 'x'), 'RSA': ('e', 'kty', 'n')}.get(
        str(jwk.get('kty')))
    if members is None or any(not isinstance(jwk.get(name), str) for name in members):
        raise ValueError('Not a public key this server knows.')
    canonical = json.dumps({name: jwk[name] for name in members}, separators=(',', ':'), sort_keys=True)
    return b64(hashlib.sha256(canonical.encode()).digest())


# ---------------------------------------------------------------------------------------------------- keys

class Keys:
    """The Node's signing keys in `<home>/node/keys/`, each private key a PEM file the owner alone reads. The newest
    signs; a retired key stays in the key set until the longest token it signed, a refresh token at its cap, has
    expired, so a rotation ends no one's session. A key that may have been stolen is revoked instead: its file is
    deleted and it leaves the key set at once, so every token it signed, and every token forged with it, is refused.

    `metaform node rotate-key` runs in its own process: a running server sees the change on disk within
    `RELOAD_SECONDS`, so neither a rotation nor a revocation waits for a restart."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.lock = threading.RLock()
        self.private: dict[str, ed25519.Ed25519PrivateKey] = {}
        self.current = ''
        self.retired: dict[str, float] = {}
        self.stamp: tuple[float, ...] = ()
        self.looked = 0.0
        self.load()
        if not self.current:
            self.rotate()

    @property
    def index(self) -> Path:
        return self.folder / 'keys.json'

    def _stamp(self) -> tuple[float, ...]:
        """What changes on disk when the keys do: the index and every key file, by modification time."""
        try:
            return tuple(sorted(path.stat().st_mtime_ns for path in [self.index, *self.folder.glob('*.pem')]))
        except OSError:
            return ()

    def load(self) -> None:
        with self.lock:
            try:
                kept = cast(dict[str, Any], json.loads(self.index.read_text(encoding='utf-8')))
            except (OSError, ValueError):
                kept = {}
            self.private = {}
            for path in sorted(self.folder.glob('*.pem')):
                with contextlib.suppress(OSError, ValueError):
                    loaded = serialization.load_pem_private_key(path.read_bytes(), password=None)
                    if isinstance(loaded, ed25519.Ed25519PrivateKey):
                        self.private[path.stem] = loaded
            current = str(kept.get('current') or '')
            self.current = current if current in self.private else ''
            retired = cast(dict[str, Any], kept.get('retired') or {})
            self.retired = {kid: float(when) for kid, when in retired.items() if kid in self.private}
            self.stamp = self._stamp()
            self.looked = time.monotonic()

    def fresh(self) -> None:
        """Read the keys again when another process changed them, looking at most every `RELOAD_SECONDS`."""
        if time.monotonic() - self.looked < RELOAD_SECONDS:
            return
        with self.lock:
            self.looked = time.monotonic()
            if self._stamp() != self.stamp:
                self.load()

    def _save(self) -> None:
        written = self.index.with_suffix('.tmp')
        descriptor = os.open(written, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump({'current': self.current, 'retired': self.retired}, handle)
        os.replace(written, self.index)
        self.stamp = self._stamp()

    def rotate(self, revoke_old: bool = False) -> str:
        """A new signing key. The one it replaces is kept for checking until its tokens have all expired, or, with
        `revoke_old`, removed at once with every other older key: what to do when a key may have been copied."""
        with self.lock:
            self.folder.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(OSError):
                self.folder.chmod(0o700)
            kid = secrets.token_urlsafe(9)
            key = ed25519.Ed25519PrivateKey.generate()
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
            descriptor = os.open(self.folder / f'{kid}.pem', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(pem)
            if self.current:
                self.retired[self.current] = time.time()
            self.private[kid] = key
            self.current = kid
            if revoke_old:
                for old in [name for name in self.private if name != kid]:
                    self._drop(old)
            self.prune()
            self._save()
            return kid

    def _drop(self, kid: str) -> None:
        self.retired.pop(kid, None)
        self.private.pop(kid, None)
        with contextlib.suppress(OSError):
            (self.folder / f'{kid}.pem').unlink()

    def prune(self, now: float | None = None) -> None:
        moment = now or time.time()
        for kid, since in list(self.retired.items()):
            if since + REFRESH_CAP_SECONDS + 86400 < moment:
                self._drop(kid)

    def signing(self) -> tuple[str, ed25519.Ed25519PrivateKey]:
        self.fresh()
        with self.lock:
            return self.current, self.private[self.current]

    def public(self, kid: str) -> ed25519.Ed25519PublicKey | None:
        self.fresh()
        with self.lock:
            key = self.private.get(kid)
        return key.public_key() if key is not None else None

    def derive(self, kid: str, label: str) -> str | None:
        """A secret only this server can make again, from key `kid` and `label`: a dynamically registered client's
        secret, so it is never stored. None once that key is gone, which ends the secret with it."""
        self.fresh()
        with self.lock:
            key = self.private.get(kid)
        if key is None:
            return None
        raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                serialization.NoEncryption())
        return b64(hmac.new(raw, label.encode(), hashlib.sha256).digest())

    def jwks(self) -> dict[str, Any]:
        """The key set, RFC 7517: every key that may still have signed a live token."""
        self.fresh()
        with self.lock:
            listed = [{**OKPAlgorithm.to_jwk(key.public_key(), as_dict=True), 'kid': kid,
                       'alg': ALGORITHM, 'use': 'sig'} for kid, key in self.private.items()]
        return {'keys': listed}


class Signer:
    """Mints and checks this issuer's tokens. A check is the signature, the `typ`, the issuer, the audience when one is
    given and the expiry; what a token's claims mean is the caller's to judge."""

    def __init__(self, keys: Keys, issuer: str) -> None:
        self.keys = keys
        self.issuer = issuer

    def mint(self, typ: str, claims: dict[str, Any], seconds: float, *, now: float | None = None) -> str:
        moment = int(now or time.time())
        kid, key = self.keys.signing()
        payload = {'iss': self.issuer, 'iat': moment, 'exp': moment + int(seconds), 'jti': secrets.token_urlsafe(16),
                   **claims}
        return jwt.encode(payload, key, algorithm=ALGORITHM, headers={'kid': kid, 'typ': typ})

    def read(self, token: str, typ: str, audience: str | None = None) -> dict[str, Any] | None:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return None
        if header.get('typ') != typ or header.get('alg') != ALGORITHM:
            return None
        key = self.keys.public(str(header.get('kid') or ''))
        if key is None:
            return None
        try:
            claims = jwt.decode(token, key, algorithms=[ALGORITHM], issuer=self.issuer, audience=audience,
                                leeway=CLOCK_LEEWAY, options={'verify_aud': audience is not None,
                                                             'require': ['exp', 'iat', 'iss', 'jti']})
        except jwt.PyJWTError:
            return None
        return claims


# ---------------------------------------------------------------------------------------------------- revocation

class AccountState(Protocol):
    def generation(self, account_id: str) -> tuple[int, bool] | None: ...

    def bump_generation(self, account_id: str) -> int: ...


class Generations:
    """Each account's current generation and whether it is disabled, read from the store once per account and kept
    for `ttl` seconds; a bump made here is seen here at once, and `listeners` hear it (the broker closes tunnels)."""

    def __init__(self, store: AccountState, ttl: float = GENERATION_SECONDS) -> None:
        self.store = store
        self.ttl = ttl
        self.lock = threading.Lock()
        self.held: dict[str, tuple[int, bool, float]] = {}
        self.listeners: list[Callable[[str], None]] = []

    def current(self, account_id: str) -> tuple[int, bool] | None:
        now = time.monotonic()
        with self.lock:
            kept = self.held.get(account_id)
        if kept is not None and kept[2] > now:
            return kept[0], kept[1]
        found = self.store.generation(account_id)
        if found is None:
            return None
        with self.lock:
            self.held[account_id] = (found[0], found[1], now + self.ttl)
        return found

    def valid(self, account_id: str, generation: Any) -> bool:
        found = self.current(account_id)
        return found is not None and not found[1] and isinstance(generation, int) and generation == found[0]

    def bump(self, account_id: str) -> int:
        made = self.store.bump_generation(account_id)
        self.forget(account_id)
        for listener in list(self.listeners):
            with contextlib.suppress(Exception):
                listener(account_id)
        return made

    def forget(self, account_id: str) -> None:
        with self.lock:
            self.held.pop(account_id, None)


class FamilyStore(Protocol):
    def family(self, family: str) -> tuple[int, bool] | None: ...

    def save_family(self, family: str, seq: int, revoked: bool, expires: float) -> None: ...


class Families:
    """The highest refresh sequence issued per grant, and the grants revoked one by one, each kept until its last token
    expires. In memory by default; with a `durable` store as well, so the marks outlive a restart."""

    def __init__(self, durable: FamilyStore | None = None) -> None:
        self.durable = durable
        self.lock = threading.Lock()
        self.marks: dict[str, tuple[int, float]] = {}
        self.revoked_until: dict[str, float] = {}

    def _prune(self, now: float) -> None:
        for family, (_, until) in list(self.marks.items()):
            if until < now:
                self.marks.pop(family, None)
        for family, until in list(self.revoked_until.items()):
            if until < now:
                self.revoked_until.pop(family, None)

    def revoked(self, family: str) -> bool:
        with self.lock:
            if self.revoked_until.get(family, 0) > time.time():
                return True
        found = self.durable.family(family) if self.durable is not None else None
        return bool(found and found[1])

    def revoke(self, family: str, until: float) -> None:
        with self.lock:
            self.revoked_until[family] = max(until, self.revoked_until.get(family, 0))
            mark = self.marks.get(family, (0, until))[0]
        if self.durable is not None:
            self.durable.save_family(family, mark, True, until)

    def mark(self, family: str) -> int | None:
        with self.lock:
            kept = self.marks.get(family)
        if kept is not None:
            return kept[0]
        found = self.durable.family(family) if self.durable is not None else None
        return found[0] if found is not None else None

    def start(self, family: str, expires: float) -> None:
        """A new grant, its first refresh token numbered 0."""
        with self.lock:
            self._prune(time.time())
            self.marks[family] = (0, expires)
        if self.durable is not None:
            self.durable.save_family(family, 0, False, expires)

    def advance(self, family: str, seq: int, expires: float) -> bool:
        """Spend refresh token `seq` of the family: True when it is the newest one issued (or the mark was lost in a
        restart), and the next is numbered seq + 1; False when it was already spent, which revokes the family."""
        known = self.mark(family)
        with self.lock:
            if self.revoked_until.get(family, 0) > time.time():
                return False
            if known is not None and seq != known:
                stale = True
            else:
                stale = False
                self.marks[family] = (seq + 1, expires)
        if stale:
            self.revoke(family, expires)
            return False
        if self.durable is not None:
            self.durable.save_family(family, seq + 1, False, expires)
        return True


# ---------------------------------------------------------------------------------------------------- DPoP

class Replay:
    """Values seen once, each kept until it expires: DPoP proof ids, used authorization codes, assertion ids."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.seen: dict[str, float] = {}

    def first(self, value: str, until: float) -> bool:
        now = time.time()
        with self.lock:
            if len(self.seen) > 1024:
                for key, expiry in list(self.seen.items()):
                    if expiry < now:
                        self.seen.pop(key, None)
            if self.seen.get(value, 0) > now:
                return False
            self.seen[value] = until
            return True


def dpop_key(proof: str | None, method: str, url: str, replay: Replay, access_token: str | None = None) -> str | None:
    """The thumbprint of the key that signed a valid DPoP proof for this request, RFC 9449 section 4.3; None when the
    proof is missing or fails any check: its type, its algorithm, a public key in its header, the method and URL it
    was made for, its age, its id seen once, and with an access token the token's hash."""
    if not proof:
        return None
    try:
        header = jwt.get_unverified_header(proof)
    except jwt.PyJWTError:
        return None
    jwk: Any = header.get('jwk')
    if header.get('typ') != 'dpop+jwt' or header.get('alg') not in DPOP_ALGORITHMS or not isinstance(jwk, dict):
        return None
    public = cast(dict[str, Any], jwk)
    if 'd' in public:  # a private key in a header is a client's mistake that must not be rewarded
        return None
    try:
        key = jwt.PyJWK(public, algorithm=str(header['alg']))
        claims = jwt.decode(proof, key.key, algorithms=[str(header['alg'])],
                            options={'verify_aud': False, 'require': ['iat', 'jti']})
        bound = thumbprint(public)
    except (jwt.PyJWTError, ValueError):
        return None
    issued = claims.get('iat')
    if not isinstance(issued, int | float) or abs(time.time() - float(issued)) > DPOP_SKEW:
        return None
    if claims.get('htm') != method or claims.get('htu') != url.split('?', 1)[0].split('#', 1)[0]:
        return None
    if access_token is not None and claims.get('ath') != b64(hashlib.sha256(access_token.encode()).digest()):
        return None
    if not replay.first(f'{bound}:{claims.get("jti")}', float(issued) + 2 * DPOP_SKEW):
        return None
    return bound
