"""`metaform node deploy`, `status`, `logs` and `update`: a plan of steps, each shown exactly as it runs.

A host is prepared once, by one idempotent script: as cloud-init user data on a VM the Node creates on Vultr, or
over SSH on a fresh Ubuntu host made any other way. Then the compose project is copied, built and started over SSH,
and the result is checked from outside: the certificate, the authorization server's metadata, and `/mcp` refusing a
request without a token. `--dry-run` prints every step, API calls and the cloud-init included, and runs none.
"""
from __future__ import annotations

import base64
import json
import os
import shlex
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from metaform.module import Stop

from .config import NodeSpec

REMOTE_DIR = '/opt/metaform-node'
USER = 'metaform'
SSH_OPTIONS = ('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=15')
SWAP_GB = 3  # a 1 GB host builds the image and runs four services; swap keeps a build from being killed


def install_script(user: str = USER, *, relay_port: int | None = None) -> str:
    """The host's base preparation, Ubuntu only, safe to run again: each step checks before it changes anything."""
    tunnel = f'ufw allow {relay_port}/tcp comment "frp relay control"\n' if relay_port else ''
    return f"""#!/usr/bin/env bash
# Metaform Node host preparation, written by metaform node. Idempotent: every step checks before it changes.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

. /etc/os-release
if [ "${{ID:-}}" != "ubuntu" ]; then
  echo "metaform node prepares Ubuntu hosts only; this is ${{PRETTY_NAME:-unknown}}." >&2
  exit 1
fi

# Swap, once, sized for a small host: the image build needs more than 1 GB.
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  if [ ! -f /swapfile ]; then
    fallocate -l {SWAP_GB}G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
fi
grep -qE '^/swapfile[[:space:]]' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab

# /dev/shm without exec or setuid.
if ! grep -qE '^tmpfs[[:space:]]+/dev/shm[[:space:]]' /etc/fstab; then
  echo 'tmpfs /dev/shm tmpfs defaults,noexec,nosuid,nodev 0 0' >> /etc/fstab
fi
mount -o remount,noexec,nosuid,nodev /dev/shm || true

apt-get update
apt-get install --yes ca-certificates curl ufw fail2ban unattended-upgrades bash-completion

# Docker from Docker's own apt repository.
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${{UBUNTU_CODENAME:-$VERSION_CODENAME}}
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update
  apt-get install --yes docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

# The working user: a home and a shell, in the docker group, sudo only for what the stack needs.
if ! id -u {user} >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash {user}
fi
usermod -aG docker {user}
install -d -m 0700 -o {user} -g {user} /home/{user}/.ssh
if [ -s /root/.ssh/authorized_keys ] && [ ! -s /home/{user}/.ssh/authorized_keys ]; then
  install -m 0600 -o {user} -g {user} /root/.ssh/authorized_keys /home/{user}/.ssh/authorized_keys
fi
cat > /etc/sudoers.d/90-{user} <<'EOF'
{user} ALL=(root) NOPASSWD: /usr/bin/systemctl restart docker, /usr/sbin/ufw status
EOF
chmod 0440 /etc/sudoers.d/90-{user}
visudo -cf /etc/sudoers.d/90-{user}
install -d -o {user} -g {user} {REMOTE_DIR}

# Bash completion for the working user.
grep -q bash_completion /home/{user}/.bashrc 2>/dev/null || \\
  echo '[ -f /usr/share/bash-completion/bash_completion ] && . /usr/share/bash-completion/bash_completion' \\
  >> /home/{user}/.bashrc

# Firewall: SSH, HTTP for the ACME challenge, HTTPS, and nothing else. Docker publishes only Caddy's 80 and 443.
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
{tunnel}ufw --force enable

# SSH: keys only, once a key is in place for the working user.
if [ -s /home/{user}/.ssh/authorized_keys ]; then
  cat > /etc/ssh/sshd_config.d/60-metaform.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
  sshd -t && systemctl reload ssh
fi

# Security updates by themselves; fail2ban watching SSH.
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
EOF
systemctl enable --now fail2ban unattended-upgrades
echo "metaform node: host ready"
"""


def cloud_init(user: str = USER, *, relay_port: int | None = None) -> str:
    """The same preparation as cloud-init user data: written once and run on first boot."""
    script = install_script(user, relay_port=relay_port)
    indented = ''.join(f'      {line}\n' if line else '\n' for line in script.splitlines())
    return ('#cloud-config\n'
            '# Metaform Node host preparation, run once on first boot; the same script node deploy runs over SSH.\n'
            'write_files:\n'
            '  - path: /usr/local/sbin/metaform-node-prepare\n'
            "    permissions: '0700'\n"
            '    content: |\n'
            f'{indented}'
            'runcmd:\n'
            '  - [/usr/local/sbin/metaform-node-prepare]\n')


# ---------------------------------------------------------------------------------------------------- steps

@dataclass
class Step:
    """One step of a plan: what it does, and exactly what it runs, shown the same way for --dry-run."""
    title: str
    shown: str
    run: Callable[[dict[str, Any]], Any] | None = None

    def line(self, number: int) -> str:
        return f'{number}. {self.title}\n' + ''.join(f'     {one}\n' for one in self.shown.splitlines())


@dataclass
class Target:
    """Where a plan runs: the host, the identity it is reached with, and the compose folder here."""
    host: str
    folder: Path
    identity: str = ''
    user: str = USER
    state: dict[str, Any] = field(default_factory=dict[str, Any])

    def ssh(self, user: str, command: str) -> list[str]:
        identity = ['-i', self.identity] if self.identity else []
        return ['ssh', *SSH_OPTIONS, *identity, f'{user}@{self.host}', command]


def _shown(argv: list[str], stdin: str | None = None) -> str:
    return shlex.join(argv) + (f' < {stdin}' if stdin else '')


def run_command(argv: list[str], *, stdin: bytes | None = None, quiet: bool = False) -> str:
    done = subprocess.run(argv, input=stdin, capture_output=True, check=False)
    if done.returncode != 0:
        said = (done.stderr or done.stdout).decode(errors='replace').strip().splitlines()
        raise Stop(f'{argv[0]} failed: {said[-1] if said else done.returncode}', 'metaform node deploy --dry-run')
    return '' if quiet else done.stdout.decode(errors='replace')


def ssh_step(target: Target, title: str, command: str, *, user: str | None = None, stdin_file: str | None = None,
             stdin: Callable[[], bytes] | None = None) -> Step:
    def run(_: dict[str, Any]) -> str:
        argv = target.ssh(user or target.user, command.format(**target.state))
        return run_command(argv, stdin=stdin() if stdin else None)
    return Step(title, _shown(target.ssh(user or target.user, command), stdin_file), run)


def build_step(target: Target) -> Step:
    """The wheel the image installs: every module this Metaform carries, built as `metaform build` builds."""
    argv = [sys.executable, '-m', 'metaform', 'build', 'kind=full']

    def run(_: dict[str, Any]) -> str:
        said = run_command(argv)
        wheel = next((line.split(':', 1)[1].strip() for line in said.splitlines() if line.startswith('Wheel:')), '')
        if not wheel:
            raise Stop('metaform build named no wheel.', 'metaform build kind=full')
        wheels = target.folder / 'wheels'
        wheels.mkdir(exist_ok=True)
        for old in wheels.glob('*.whl'):
            old.unlink()
        (wheels / Path(wheel).name).write_bytes(Path(wheel).read_bytes())
        (wheels / 'constraints.txt').write_text(constraints(), encoding='utf-8')
        return wheel
    return Step('Build the Metaform wheel the image installs', _shown(argv) + f'  # copied into {target.folder}/wheels/',
                run)


def constraints() -> str:
    """The versions this Metaform runs with here, as pip constraints, so the image installs what was tested."""
    from importlib import metadata
    found: dict[str, str] = {}
    for one in metadata.distributions():
        name = str(one.metadata['Name'] or '').strip()
        if name and name.lower() != 'metaform':
            found[name.lower()] = f'{name}=={one.version}'
    return ''.join(line + '\n' for _, line in sorted(found.items()))


def push_step(target: Target) -> Step:
    """The compose folder copied as a tar stream over SSH, so nothing but ssh and tar is needed on either side."""
    remote = f'mkdir -p {REMOTE_DIR} && tar -C {REMOTE_DIR} -xzf - && chmod 700 {REMOTE_DIR}'
    tar = ['tar', '-C', str(target.folder), '-czf', '-', '.']

    def run(_: dict[str, Any]) -> str:
        packed = subprocess.run(tar, capture_output=True, check=True).stdout
        return run_command(target.ssh(target.user, remote), stdin=packed)
    return Step(f'Copy the compose project to {REMOTE_DIR}', shlex.join(tar) + ' | ' +
                shlex.join(target.ssh(target.user, remote)), run)


def health_step(target: Target, seconds: float = 300) -> Step:
    command = f'cd {REMOTE_DIR} && docker compose ps --format json'

    def run(_: dict[str, Any]) -> list[dict[str, Any]]:
        deadline = time.monotonic() + seconds
        while True:
            services = parse_ps(run_command(target.ssh(target.user, command)))
            waiting = [one['Service'] for one in services if one.get('Health') not in ('healthy', '')
                       or one.get('State') != 'running']
            if services and not waiting:
                return services
            if time.monotonic() > deadline:
                raise Stop(f'Not healthy after {seconds:.0f} seconds: {", ".join(waiting) or "no services"}.',
                           'metaform node logs')
            time.sleep(5)
    return Step('Wait until every service is running and healthy', _shown(target.ssh(target.user, command)), run)


def parse_ps(text: str) -> list[dict[str, Any]]:
    """`docker compose ps --format json`: one JSON object per line in current Compose, a list in older ones."""
    text = text.strip()
    if not text:
        return []
    if text.startswith('['):
        return list(json.loads(text))
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def verify(domain: str, *, verify_tls: bool = True, opener: Callable[..., Any] | None = None) -> dict[str, Any]:
    """The Node as the internet sees it: a certificate a browser accepts, the authorization server's metadata naming
    this issuer, the MCP resource's metadata naming it, and `/mcp` refusing a request without a token with the
    pointer to that metadata, RFC 9728 section 5.1."""
    issuer = f'https://{domain}'
    found: dict[str, Any] = {}
    context = ssl.create_default_context()
    if not verify_tls:  # a stand-in with Caddy's local CA: the checks below still run, the chain is not trusted
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    if opener is None:
        with socket.create_connection((domain, 443), timeout=10) as raw, \
                context.wrap_socket(raw, server_hostname=domain) as wrapped:
            certificate: dict[str, Any] = dict(wrapped.getpeercert() or {})
        names = {str(pair[0][0]): str(pair[0][1]) for pair in certificate.get('issuer', ()) if pair}
        found['certificate'] = {'issuer': names.get('organizationName'), 'expires': certificate.get('notAfter')}

    def fetch(url: str) -> Any:
        if opener is not None:
            return opener(url)
        return urllib.request.urlopen(url, timeout=10, context=context)
    with fetch(issuer + '/.well-known/oauth-authorization-server') as answer:
        server = json.loads(answer.read())
    found['issuer'] = server.get('issuer') == issuer
    found['cimd'] = bool(server.get('client_id_metadata_document_supported'))
    with fetch(issuer + '/.well-known/oauth-protected-resource/mcp') as answer:
        resource = json.loads(answer.read())
    found['resource'] = resource.get('resource') == issuer + '/mcp' and issuer in resource.get('authorization_servers',
                                                                                                 [])
    try:
        fetch(issuer + '/mcp').close()
        found['mcp_refuses_anonymous'] = False
    except urllib.error.HTTPError as error:
        found['mcp_refuses_anonymous'] = error.code == 401 and 'resource_metadata=' in (
            error.headers.get('WWW-Authenticate') or '')
    return found


def verify_step(spec: NodeSpec) -> Step:
    def run(_: dict[str, Any]) -> dict[str, Any]:
        found = verify(spec.domain, verify_tls=spec.mode != 'internal')
        failed = [key for key in ('issuer', 'cimd', 'resource', 'mcp_refuses_anonymous') if not found.get(key)]
        if failed:
            raise Stop(f'The Node answers but fails: {", ".join(failed)}.', 'metaform node status')
        return found
    return Step('Check it from outside: TLS, the metadata, and /mcp refusing a request without a token',
                f'TLS handshake with {spec.domain}:443 (certificate checked against the system roots)\n'
                f'GET https://{spec.domain}/.well-known/oauth-authorization-server  -> issuer, CIMD supported\n'
                f'GET https://{spec.domain}/.well-known/oauth-protected-resource/mcp  -> resource, server\n'
                f'GET https://{spec.domain}/mcp  -> 401 with WWW-Authenticate resource_metadata', run)


def dns_step(spec: NodeSpec, target: Target, seconds: float = 1800) -> Step:
    """The certificate authority reaches the name, so the name must point here before Caddy asks for it; asking
    early only spends Let's Encrypt's rate limit."""
    def run(state: dict[str, Any]) -> str:
        wanted = state.get('main_ip') or target.host
        deadline = time.monotonic() + seconds
        while True:
            try:
                addresses: set[str] = {str(info[4][0]) for info in socket.getaddrinfo(spec.domain, 443)}
            except OSError:
                addresses = set()
            if wanted in addresses:
                return wanted
            if time.monotonic() > deadline:
                raise Stop(f'{spec.domain} does not resolve to {wanted} yet.',
                           f'Add an A record {spec.domain} -> {wanted} at your DNS provider, then deploy again.')
            time.sleep(15)
    return Step('Wait until the domain points at the host', f'resolve {spec.domain}; expect the host\'s address '
                '({main_ip} when the VM was made here)', run)


# ---------------------------------------------------------------------------------------------------- the plans

def deploy_plan(spec: NodeSpec, target: Target, *, provision: list[Step] | None = None,
                prepared_by_cloud_init: bool = False, relay_port: int | None = None) -> list[Step]:
    """`relay_port`: the host also runs the relay, so its firewall opens the tunnel's control port."""
    steps = list(provision or [])
    if prepared_by_cloud_init:
        steps.append(ssh_step(target, 'Wait for cloud-init to finish preparing the host', 'cloud-init status --wait',
                              user='root'))
    else:
        script = install_script(target.user, relay_port=relay_port)
        steps.append(ssh_step(target, 'Prepare the host: swap, Docker from its official repository, the working user, '
                              'ufw 22/80/443, SSH keys only, unattended upgrades, fail2ban', 'bash -s', user='root',
                              stdin_file='install.sh', stdin=lambda: script.encode()))
    if spec.mode in ('acme', 'dns') and not spec.wildcard:
        steps.append(dns_step(spec, target))
    steps += [build_step(target), push_step(target),
              ssh_step(target, 'Build the image and start the stack',
                       f'cd {REMOTE_DIR} && docker compose up -d --build --remove-orphans'),
              health_step(target), verify_step(spec)]
    return steps


def update_plan(spec: NodeSpec, target: Target) -> list[Step]:
    return [build_step(target), push_step(target),
            ssh_step(target, 'Rebuild and restart what changed',
                     f'cd {REMOTE_DIR} && docker compose up -d --build --remove-orphans && docker image prune -f'),
            health_step(target), verify_step(spec)]


def logs_command(service: str | None, lines: int) -> str:
    return f'cd {REMOTE_DIR} && docker compose logs --no-color --tail {int(lines)}' + (
        f' {shlex.quote(service)}' if service else '')


def show(steps: list[Step]) -> str:
    return ''.join(step.line(number) for number, step in enumerate(steps, 1))


def execute(steps: list[Step], state: dict[str, Any], say: Callable[[str], None]) -> dict[str, Any]:
    for number, step in enumerate(steps, 1):
        say(f'{number}/{len(steps)} {step.title}')
        if step.run is not None:
            result: Any = step.run(state)
            if isinstance(result, dict):
                state.update(cast(dict[str, Any], result))
    return state


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def environment_key(name: str) -> str:
    """A provider's API key, from the environment only: Metaform never stores it."""
    value = os.environ.get(name, '').strip()
    if not value:
        raise Stop(f'{name} is not set.', f'export {name}=<your API key> for this shell, then deploy again')
    return value
