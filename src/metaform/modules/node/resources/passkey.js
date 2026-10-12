// Passkey ceremonies for the Metaform Node: the server makes the options and checks the answer (py_webauthn);
// this file only carries them between the server and the browser's WebAuthn API.
(function () {
  'use strict';
  const said = (text) => { const node = document.getElementById('said'); if (node) node.textContent = text; };
  const toBytes = (text) => {
    const padded = text.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((text.length + 3) % 4);
    return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0)).buffer;
  };
  const toText = (buffer) => btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const descriptors = (list) => (list || []).map((one) => ({ ...one, id: toBytes(one.id) }));
  const creation = (options) => PublicKeyCredential.parseCreationOptionsFromJSON
    ? PublicKeyCredential.parseCreationOptionsFromJSON(options)
    : { ...options, challenge: toBytes(options.challenge), user: { ...options.user, id: toBytes(options.user.id) },
        excludeCredentials: descriptors(options.excludeCredentials) };
  const request = (options) => PublicKeyCredential.parseRequestOptionsFromJSON
    ? PublicKeyCredential.parseRequestOptionsFromJSON(options)
    : { ...options, challenge: toBytes(options.challenge), allowCredentials: descriptors(options.allowCredentials) };
  const json = (credential) => {
    if (typeof credential.toJSON === 'function') return credential.toJSON();
    const response = credential.response;
    const out = { id: credential.id, rawId: toText(credential.rawId), type: credential.type,
                  clientExtensionResults: credential.getClientExtensionResults(),
                  authenticatorAttachment: credential.authenticatorAttachment, response: {
                    clientDataJSON: toText(response.clientDataJSON) } };
    if (response.attestationObject) {
      out.response.attestationObject = toText(response.attestationObject);
      out.response.transports = response.getTransports ? response.getTransports() : [];
    } else {
      out.response.authenticatorData = toText(response.authenticatorData);
      out.response.signature = toText(response.signature);
      if (response.userHandle) out.response.userHandle = toText(response.userHandle);
    }
    return out;
  };
  const post = async (path, body) => {
    const answer = await fetch(path, { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await answer.json().catch(() => ({}));
    if (!answer.ok) throw new Error(data.error || 'The server refused.');
    return data;
  };
  async function signIn(next) {
    try {
      said('Waiting for your passkey…');
      const started = await post('/node/passkey/login/options', {});
      const credential = await navigator.credentials.get({ publicKey: request(started.options) });
      const done = await post('/node/passkey/login/verify', { ceremony: started.ceremony, credential: json(credential), next });
      location.assign(done.next || '/');
    } catch (error) { said(error.message || String(error)); }
  }
  async function enrol(invite) {
    try {
      said('Waiting for your device…');
      const started = await post('/node/passkey/register/options', { invite });
      const credential = await navigator.credentials.create({ publicKey: creation(started.options) });
      const done = await post('/node/passkey/register/verify', { ceremony: started.ceremony, credential: json(credential), invite });
      said('Your passkey is enrolled.');
      location.assign(done.next || '/');
    } catch (error) { said(error.message || String(error)); }
  }
  window.metaformPasskey = { signIn, enrol };
})();
