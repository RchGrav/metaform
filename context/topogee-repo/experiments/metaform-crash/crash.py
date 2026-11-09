"""Storage risk 3: kill the Metaform server in the middle of writes, many times, under load.

Not product code. It drives the real `metaform` binary through `metaform call`, as an agent's
harness would, and checks two things after every round of SIGKILLs:

1. Every write that was acknowledged (exit 0) is present.
2. No write is half visible. Each write adds a receiver whose want creates its provider, so
   the receiver, the provider and the want edge must all exist or none of them.

Usage: python3 crash.py <metaform binary> <scratch dir> [rounds] [writers]
"""
import json, os, random, signal, subprocess, sys, threading, time

binary, scratch = sys.argv[1], sys.argv[2]
rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 20
writers = int(sys.argv[4]) if len(sys.argv) > 4 else 6
home = os.path.join(scratch, "home")
env = dict(os.environ, METAFORM_LAUNCHER="")
WANT = {"why": "Receive the part.", "how": "Supplies the part.", "intent": "receive"}


def call(command, timeout=20):
    try:
        done = subprocess.run([binary, "call", "--home", home, "--map", "crash", json.dumps(command)],
                              capture_output=True, text=True, env=env, timeout=timeout)
        return done.returncode, done.stdout
    except subprocess.TimeoutExpired:
        return 99, ""


def server_pids():
    out = subprocess.run(["pgrep", "-f", f"metaform serve --home {home}"], capture_output=True, text=True)
    return [int(p) for p in out.stdout.split()]


acked, attempted = set(), set()
codes = {}
lock = threading.Lock()


def writer(r, t, stop):
    i = 0
    while not stop.is_set():
        name = f"r{r}t{t}x{i}"
        command = {"add": {f"code.recv.{name}": {"name": name, "wants": {f"code.prov.{name}": WANT}}}}
        with lock:
            attempted.add(name)
        started = time.time()
        code, _ = call(command)
        with lock:
            key = (code, "slow" if time.time() - started > 2 else "fast")
            codes[key] = codes.get(key, 0) + 1
        if code == 0:
            with lock:
                acked.add(name)
        i += 1


def check(round_no):
    code, out = call({".": {}}, timeout=60)
    assert code == 0, f"round {round_no}: root read failed with exit {code}: {out}"
    root = json.loads(out)
    addresses = set(root["addresses"])
    edges = {tuple(e) for e in root["edges"]}
    missing = [n for n in acked if f"code.recv.{n}" not in addresses]
    assert not missing, f"round {round_no}: acknowledged writes lost: {missing[:5]}"
    for n in attempted:
        parts = (f"code.recv.{n}" in addresses, f"code.prov.{n}" in addresses,
                 (f"code.recv.{n}", f"code.prov.{n}") in edges)
        assert all(parts) or not parts[0], f"round {round_no}: write {n} half visible: {parts}"
    return len(addresses)


random.seed(7)
kills = 0
for r in range(rounds):
    stop = threading.Event()
    threads = [threading.Thread(target=writer, args=(r, t, stop)) for t in range(writers)]
    for th in threads:
        th.start()
    time.sleep(random.uniform(0.3, 1.5))
    for pid in server_pids():
        os.kill(pid, signal.SIGKILL)
        kills += 1
    stop.set()
    for th in threads:
        th.join()
    size = check(r)
    with lock:
        seen = dict(codes)
        codes.clear()
    print(f"round {r + 1}: exits {seen}; {len(acked)} acknowledged of {len(attempted)} attempted; map holds {size} addresses; all acknowledged present; none half visible", flush=True)

for pid in server_pids():
    os.kill(pid, signal.SIGTERM)
print(f"PASS: {rounds} rounds, {kills} SIGKILLs, {len(acked)} acknowledged writes all present, no write half visible")
