"""Twilio, as its documentation defines it: the webhook signature, the TwiML answers, and the REST calls Metaform
makes: a call, a text, reading where the number sends its calls and texts, and, when the person asks, pointing them
at the bridge.

Credentials come only from the environment of the process that runs the phone bridge, read for each use, never stored,
logged, returned or shown to the page:

  TWILIO_ACCOUNT_SID   the account, in every REST URL
  TWILIO_AUTH_TOKEN    checks the signature Twilio puts on every webhook; Twilio signs with it alone
  TWILIO_API_KEY       with TWILIO_API_SECRET, an API key for the REST calls in place of the auth token,
  TWILIO_API_SECRET    so the token is never sent anywhere; the webhooks still need the auth token

The signature, https://www.twilio.com/docs/usage/webhooks/webhooks-security: HMAC-SHA1, keyed with the auth token, of
the full URL Twilio requested followed by each POST parameter's name and value, sorted by name, base64-encoded, in the
X-Twilio-Signature header. The URL is the public one Twilio used, never the loopback one the bridge sees behind its
proxy, so the bridge rebuilds it from twilio_public_url.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from xml.sax.saxutils import escape, quoteattr

SID = 'TWILIO_ACCOUNT_SID'
TOKEN = 'TWILIO_AUTH_TOKEN'
KEY = 'TWILIO_API_KEY'
SECRET = 'TWILIO_API_SECRET'
NAMES = (SID, TOKEN, KEY, SECRET)
API = 'https://api.twilio.com/2010-04-01'
TIMEOUT = 15
SMS_LIMIT = 1500  # characters in one text Metaform sends; Twilio takes 1600, and a long reply is cut at a sentence


def present() -> dict[str, bool]:
    """Which of the Twilio variables are in this process's environment, by name only; a value is never returned."""
    return {name: bool(os.environ.get(name, '').strip()) for name in NAMES}


def auth_token() -> str | None:
    return os.environ.get(TOKEN, '').strip() or None


# ---------------------------------------------------------------------------------------------- the signature

def signature(token: str, url: str, params: Iterable[tuple[str, str]] = ()) -> str:
    """Twilio's signature of a request: the URL, then each parameter's name and value sorted by name (and by value
    for a repeated name), as HMAC-SHA1 keyed with the auth token, base64-encoded."""
    data = url + ''.join(name + value for name, value in sorted(params))
    digest = hmac.new(token.encode('utf-8'), data.encode('utf-8'), hashlib.sha1).digest()
    return base64.b64encode(digest).decode('ascii')


def _ported(url: str) -> list[str]:
    """The URL as given, and with its default port written or left out: Twilio's own libraries accept either, since
    which one Twilio signs depends on how the webhook URL was entered."""
    parts = urllib.parse.urlsplit(url)
    default = {'https': 443, 'wss': 443, 'http': 80, 'ws': 80}.get(parts.scheme)
    found = [url]
    if parts.port is None and default:
        found.append(urllib.parse.urlunsplit(parts._replace(netloc=f'{parts.hostname}:{default}')))
    elif parts.port == default and parts.hostname:
        found.append(urllib.parse.urlunsplit(parts._replace(netloc=parts.hostname)))
    return found


def valid(token: str, url: str, params: Iterable[tuple[str, str]], given: str | None) -> bool:
    """Whether `given`, the X-Twilio-Signature header, is Twilio's signature of this request, compared in constant
    time. A request with no signature is never valid."""
    if not given or not token:
        return False
    listed = list(params)
    return any(hmac.compare_digest(signature(token, candidate, listed), given) for candidate in _ported(url))


# ---------------------------------------------------------------------------------------------------- TwiML

def _response(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'


def stream(url: str, parameters: Mapping[str, str]) -> str:
    """Connect the call to a bidirectional Media Stream at `url`, a wss URL with no query: Twilio passes custom
    parameters only as <Parameter>, which arrive in the stream's start message."""
    given = ''.join(f'<Parameter name={quoteattr(name)} value={quoteattr(value)}/>' for name, value in parameters.items())
    return _response(f'<Connect><Stream url={quoteattr(url)}>{given}</Stream></Connect>')


def gather(action: str, ask: str, otherwise: str) -> str:
    """Ask for digits on the keypad, ended by #, and post them, signed, to `action`; with none entered in time the
    call hears `otherwise` and is hung up. The PIN's length is not given, so the prompt does not tell it."""
    asked = f'<Say>{escape(ask)}</Say>' if ask else ''
    return _response(f'<Gather input="dtmf" action={quoteattr(action)} method="POST" finishOnKey="#" timeout="10">'
                     f'{asked}</Gather>' + (f'<Say>{escape(otherwise)}</Say>' if otherwise else '') + '<Hangup/>')


def refuse(said: str) -> str:
    """Say a short line and hang up."""
    return _response((f'<Say>{escape(said)}</Say>' if said else '') + '<Hangup/>')


def empty() -> str:
    """An answer that does nothing more, as to a text whose reply is sent later through the REST API."""
    return _response('')


# ---------------------------------------------------------------------------------------------------- the REST calls

Post = Callable[[str, dict[str, str], tuple[str, str]], dict[str, Any]]
Get = Callable[[str, tuple[str, str]], dict[str, Any]]


def _post(url: str, form: dict[str, str], auth: tuple[str, str]) -> dict[str, Any]:
    """One form POST to Twilio's REST API with HTTP Basic auth, its JSON answer back. Raises OSError with Twilio's own
    message, never a credential, when it refuses."""
    return _ask(url, auth, urllib.parse.urlencode(form).encode('utf-8'))


def _get(url: str, auth: tuple[str, str]) -> dict[str, Any]:
    """One GET of Twilio's REST API, which reads and changes nothing, its JSON answer back; refusals as `_post`."""
    return _ask(url, auth, None)


def _ask(url: str, auth: tuple[str, str], data: bytes | None) -> dict[str, Any]:
    basic = base64.b64encode(f'{auth[0]}:{auth[1]}'.encode()).decode('ascii')
    headers = {'Authorization': f'Basic {basic}', 'User-Agent': 'metaform-twilio', 'Accept': 'application/json'}
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    request = urllib.request.Request(url, data=data, method='GET' if data is None else 'POST', headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:
            found: Any = json.loads(answer.read() or b'{}')
    except urllib.error.HTTPError as error:
        said = error.read()[:400].decode('utf-8', 'replace')
        try:
            said = str(json.loads(said).get('message') or said)
        except ValueError:
            pass
        raise OSError(f'Twilio answered {error.code}: {said}') from None
    except urllib.error.URLError as error:
        raise OSError(f'Twilio could not be reached: {error.reason}') from None
    return found if isinstance(found, dict) else {}  # pyright: ignore[reportUnknownVariableType]


def credentials() -> tuple[str, tuple[str, str]]:
    """The account SID and the Basic auth pair for the REST API: the API key and secret when both are set, else the
    SID and the auth token. Raises OSError naming what is missing, by name."""
    sid = os.environ.get(SID, '').strip()
    key, secret = os.environ.get(KEY, '').strip(), os.environ.get(SECRET, '').strip()
    token = auth_token()
    if not sid:
        raise OSError(f'{SID} is not in the environment of the process that runs the phone bridge.')
    if key and secret:
        return sid, (key, secret)
    if token:
        return sid, (sid, token)
    raise OSError(f'Neither {TOKEN} nor {KEY} with {SECRET} is in the environment of the process that runs the phone '
                  'bridge.')


class Client:
    """Twilio's REST API for what Metaform does: place a call, send a text, read where the number sends its calls and
    texts, and point them at the bridge. `post` and `get` are the transport, replaced in tests so nothing reaches the
    network."""

    def __init__(self, post: Post | None = None, creds: Callable[[], tuple[str, tuple[str, str]]] = credentials,
                 get: Get | None = None) -> None:
        self.post = post or _post
        self.get = get or _get
        self.creds = creds

    def number(self, number: str) -> dict[str, Any] | None:
        """The account's incoming phone number `number`, as Twilio lists it: its `sid`, `voice_url`, `sms_url`, their
        methods, and `voice_application_sid` and `sms_application_sid`, which Twilio uses in place of the URLs when
        set. None when the account has no such number. Reads only."""
        sid, auth = self.creds()
        query = urllib.parse.urlencode({'PhoneNumber': number})
        found = self.get(f'{API}/Accounts/{urllib.parse.quote(sid)}/IncomingPhoneNumbers.json?{query}', auth)
        listed: Any = found.get('incoming_phone_numbers') or []
        return listed[0] if isinstance(listed, list) and listed and isinstance(listed[0], dict) else None  # pyright: ignore[reportUnknownVariableType]

    def point(self, number_sid: str, *, voice: str, sms: str, apps: bool = False) -> dict[str, Any]:
        """Set the number's voice and SMS webhooks to `voice` and `sms`, each by HTTP POST; with `apps`, also take off
        the TwiML Apps that would be used in their place. Only ever run when the person asks, `twilio check fix=true`."""
        sid, auth = self.creds()
        form = {'VoiceUrl': voice, 'VoiceMethod': 'POST', 'SmsUrl': sms, 'SmsMethod': 'POST'}
        if apps:
            form.update({'VoiceApplicationSid': '', 'SmsApplicationSid': ''})
        return self.post(f'{API}/Accounts/{urllib.parse.quote(sid)}/IncomingPhoneNumbers/{urllib.parse.quote(number_sid)}'
                         '.json', form, auth)

    def call(self, *, to: str, from_: str, url: str, timeout: int = 30) -> dict[str, Any]:
        """Place a call: Twilio rings `to` from `from_` and, when it is answered, fetches its TwiML from `url` with a
        signed POST. The answer's `sid` names the call."""
        sid, auth = self.creds()
        form = {'To': to, 'From': from_, 'Url': url, 'Method': 'POST', 'Timeout': str(timeout)}
        return self.post(f'{API}/Accounts/{urllib.parse.quote(sid)}/Calls.json', form, auth)

    def text(self, *, to: str, from_: str, body: str) -> dict[str, Any]:
        sid, auth = self.creds()
        form = {'To': to, 'From': from_, 'Body': cut(body)}
        return self.post(f'{API}/Accounts/{urllib.parse.quote(sid)}/Messages.json', form, auth)


def cut(text: str, limit: int = SMS_LIMIT) -> str:
    text = ' '.join(text.split())
    if len(text) <= limit:
        return text
    head = text[:limit]
    end = max(head.rfind('. '), head.rfind('? '), head.rfind('! '))
    return head[:end + 1] if end > limit // 2 else head[:limit - 1] + '…'
