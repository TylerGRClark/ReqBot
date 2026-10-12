"""Jobs: long-running ReqBot commands run in the background, one at a time (docs/WEB_UI_PARITY_PLAN.md, section 5, stage 3).

A job is a saved command line plus its state. The runner executes it as a child process of its own (the same Python, `cli/reqbot.py ingest ...`), so the pipeline, Docling's memory
and any crash stay out of the web server, and cancelling is ending a process. Nothing here imports the pipeline.

Where things live: `<processed_dir>/.jobs/<id>.json` (state), `<id>.log` (the command's own log, written by the child itself, so it survives a server crash) and `.lock`. That is
inside the folder the Docker example already mounts, and `rglob("*_requirements_normalized.jsonl")` does not see it.

The rules:
  - One job runs at a time, whichever runner started it. The queue is first in, first out and lives on disk.
  - A runner claims a job by writing a lease (runner, attempt, expiry) into the job file and renews it while the child runs. A runner that cannot renew stops its own child; an expired
    lease makes the job `interrupted`; the attempt number keeps a stale runner from writing over a newer one. The first runner is the local one (the server's thread, or `reqbot jobs worker`).
  - A child can outlive its server. Each job starts in its own process group; the job file records the group and the process start-time stamp (so a reused process number is never
    mistaken for it). Before the queue moves, a still-live group left by a dead runner is stopped (SIGTERM, then SIGKILL after a grace period) and waited for, and only then is the
    job marked `interrupted`. Reattaching to a live child is not done.
  - Before spawning, the runner checks that the model machine (and the model) and Qdrant answer, and fails the job at once, naming the one that does not.
  - Only allow-listed commands can be queued (`enqueue_ingest` builds the whole command line; nothing is run through a shell, and no caller supplies a command).
"""
import atexit
import fcntl
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core import config as _config

log = logging.getLogger(__name__)

CLI_SCRIPT = _ROOT / "cli" / "reqbot.py"
JOB_ID = re.compile(r"^JOB-\d{8}-\d{6}-[0-9a-f]{6}$")  # the only shape this module makes
STATES = ("queued", "running", "succeeded", "failed", "cancelled", "interrupted")
RETRYABLE = ("failed", "cancelled", "interrupted")
LEASE_SECONDS = 60.0
HEARTBEAT_SECONDS = 1.0
TERM_GRACE_SECONDS = 15.0
KILL_WAIT_SECONDS = 5.0
POLL_SECONDS = 2.0
LOG_TAIL_BYTES = 6000
JOB_ENV_ALLOWED = frozenset({"REQBOT_EMBEDDING_MODEL"})  # the only variables a job may set for its child


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Processes
# ---------------------------------------------------------------------------

def proc_start_stamp(pid: int) -> str | None:
    """A value that changes when a process number is reused: the process start time (/proc/<pid>/stat field 22, else `ps -o lstart=`); None when there is no such process."""
    try:
        data = Path(f"/proc/{pid}/stat").read_text()
        return data.rsplit(")", 1)[1].split()[19]  # fields after the command name start at field 3, so field 22 is index 19
    except (OSError, IndexError):
        pass
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
        return out or None
    except (OSError, subprocess.SubprocessError):
        return None


def pid_alive(pid: int | None, stamp: str | None = None) -> bool:
    """The process exists (and, when a stamp is given, is the same process that was recorded, not a reused number)."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    now = proc_start_stamp(pid)
    if now is None:
        return False  # a zombie, or gone between the two calls
    return stamp is None or now == stamp


def _live_members(pgid: int) -> int | None:
    """How many processes of the group are not zombies (a dead leader nobody has reaped yet is no reason to wait); None when /proc cannot be read."""
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    count = 0
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if fields and fields[0] != "Z" and len(fields) > 2 and fields[2] == str(pgid):  # state, ppid, pgrp
            count += 1
    return count


def _group_exists(pgid: int) -> bool:
    """Some process of the group is still running (zombies waiting to be reaped do not count)."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    members = _live_members(pgid)
    return True if members is None else members > 0


def _terminate_group(pgid: int, proc: subprocess.Popen | None = None, grace: float = TERM_GRACE_SECONDS) -> bool:
    """Stop a process group: SIGTERM, wait up to `grace`, then SIGKILL and wait a few seconds more. True when it is gone. `proc` is the leader when it is our own child, which has
    to be reaped (poll) before the group can look empty."""
    def gone() -> bool:
        if proc is not None:
            proc.poll()
        return not _group_exists(pgid)

    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        log.warning("Not allowed to signal process group %s", pgid)
        return False
    deadline = time.time() + grace
    while time.time() < deadline:
        if gone():
            return True
        time.sleep(0.1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    deadline = time.time() + KILL_WAIT_SECONDS
    while time.time() < deadline:
        if gone():
            return True
        time.sleep(0.1)
    return False


def _stop_recorded_child(job: dict, grace: float = TERM_GRACE_SECONDS) -> bool:
    """Stop the process group a dead runner left behind. A live process that has the recorded number but not the recorded start time is a reused number, not our child: left alone."""
    pgid = job.get("pgid")
    if not pgid:
        return True
    stamp = job.get("pid_stamp")
    if pid_alive(pgid) and stamp and not pid_alive(pgid, stamp):
        return True
    return _terminate_group(int(pgid), None, grace)


# ---------------------------------------------------------------------------
# Reachability checks, before any work is spawned
# ---------------------------------------------------------------------------

def _get_json(url: str, timeout: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (the URLs are the operator's configured service addresses)
        return json.loads(resp.read().decode("utf-8") or "{}")


def preflight(requires: dict | None, timeout: float = 5.0) -> str | None:
    """None when everything the job needs answers; otherwise one sentence naming what does not (the model machine, a missing model, or Qdrant)."""
    if not requires:
        return None
    ollama = (requires.get("ollama_url") or "").rstrip("/")
    if ollama:
        try:
            data = _get_json(f"{ollama}/api/tags", timeout)
        except (OSError, ValueError, urllib.error.URLError) as e:
            return f"The model machine (Ollama) did not answer at {ollama}: {e}"
        have = {str(m.get("name", "")) for m in (data.get("models") or []) if isinstance(m, dict)}
        have |= {n[: -len(":latest")] for n in have if n.endswith(":latest")}
        missing = [m for m in (requires.get("ollama_models") or []) if m and m not in have and f"{m}:latest" not in have]
        if missing:
            return f"The model machine at {ollama} does not have the model(s): {', '.join(missing)}."
    qdrant = (requires.get("qdrant_url") or "").rstrip("/")
    if qdrant:
        try:
            _get_json(f"{qdrant}/collections", timeout)
        except (OSError, ValueError, urllib.error.URLError) as e:
            return f"Qdrant (the search index) did not answer at {qdrant}: {e}"
    return None


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------

class JobAlreadyQueued(ValueError):
    """An exclusive enqueue found a queued or running job with the same key (for an ingest: the same document name)."""

    def __init__(self, job_id: str):
        super().__init__(f"already queued or running as {job_id}")
        self.job_id = job_id


class JobStore:
    """Jobs as small JSON files in one directory. Every read-modify-write happens under an advisory lock on `.lock`; a write goes to a temporary file and is renamed."""

    def __init__(self, directory: Path | str):
        self.dir = Path(directory)

    # -- files --
    def _path(self, job_id: str) -> Path:
        """The job file for an id. Only an id of the exact shape this module makes is accepted, and the normalized path must stay inside the jobs folder."""
        if not JOB_ID.match(job_id or ""):
            raise ValueError(f"not a job id: {job_id!r}")
        base = os.path.normpath(str(self.dir))
        full = os.path.normpath(os.path.join(base, f"{job_id}.json"))
        if not full.startswith(base + os.sep):
            raise ValueError(f"not a job id: {job_id!r}")
        return Path(full)

    def log_path(self, job_id: str) -> Path:
        return self._path(job_id).with_suffix(".log")

    @contextmanager
    def _locked(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / ".lock", "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _read(self, path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and data.get("id") else None

    def _write(self, job: dict) -> None:
        path = self._path(job["id"])
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(job, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)

    def _all(self) -> list[dict]:
        if not self.dir.exists():
            return []
        jobs = [j for j in (self._read(p) for p in self.dir.glob("JOB-*.json")) if j]
        return sorted(jobs, key=lambda j: (j.get("created_ts", 0), j["id"]))

    # -- reading --
    def get(self, job_id: str) -> dict | None:
        return self._read(self._path(job_id))

    def list_jobs(self, limit: int | None = None) -> list[dict]:
        """Newest first."""
        jobs = list(reversed(self._all()))
        return jobs[:limit] if limit else jobs

    def log_tail(self, job_id: str, nbytes: int = LOG_TAIL_BYTES) -> str:
        try:
            with open(self.log_path(job_id), "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - nbytes))
                return f.read().decode("utf-8", errors="replace")
        except OSError:
            return ""

    # -- queueing --
    def enqueue(self, kind: str, argv: list[str], *, title: str, run_dir: str = "", requires: dict | None = None,
                params: dict | None = None, requested_by: str = "", retry_of: str | None = None, env: dict | None = None,
                exclusive: tuple[str, str] | None = None) -> dict:
        if any(not isinstance(a, (str, Path)) for a in argv):
            raise ValueError("a job's command line may hold only strings and paths")  # str(None) would become the argument "None"
        job_id = f"JOB-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        job = {
            "id": job_id, "kind": kind, "title": title, "argv": [str(a) for a in argv], "run_dir": run_dir, "requires": requires or {}, "params": params or {},
            "env": {k: str(v) for k, v in (env or {}).items() if k in JOB_ENV_ALLOWED},
            "exclusive": list(exclusive) if exclusive else None,  # kept so a retry is held to the same rule as the original
            "requested_by": requested_by, "retry_of": retry_of, "state": "queued", "attempt": 0, "created_at": _now_iso(), "created_ts": time.time(),
            "started_at": None, "finished_at": None, "lease": None, "pid": None, "pgid": None, "pid_stamp": None, "progress": None,
            "cancel_requested": False, "exit_code": None, "error": "",
        }
        with self._locked():
            if exclusive:  # checked under the same lock that writes the job, so two requests at once cannot both pass
                key, value = exclusive
                for other in self._all():
                    if other["state"] in ("queued", "running") and (other.get("params") or {}).get(key) == value:
                        raise JobAlreadyQueued(other["id"])
            self._write(job)
        return job

    def cancel(self, job_id: str) -> dict | None:
        """A queued job is cancelled at once; a running one is asked to stop (its runner ends the child within about a second); anything else is returned unchanged."""
        with self._locked():
            job = self.get(job_id)
            if job is None:
                return None
            if job["state"] == "queued":
                job.update(state="cancelled", finished_at=_now_iso())
                self._write(job)
                if job.get("run_dir"):
                    try:
                        Path(job["run_dir"]).rmdir()  # only an empty folder: what was reserved and never used
                    except OSError:
                        pass
            elif job["state"] == "running" and not job.get("cancel_requested"):
                job["cancel_requested"] = True
                self._write(job)
            return job

    def retry(self, job_id: str) -> dict:
        """Queue a new job with the same command (and so the same run folder) as a failed, cancelled or interrupted one."""
        job = self.get(job_id)
        if job is None:
            raise ValueError(f"no such job: {job_id}")
        if job["state"] not in RETRYABLE:
            raise ValueError(f"job {job_id} is {job['state']}; only a failed, cancelled or interrupted job can be retried")
        excl = job.get("exclusive")
        return self.enqueue(job["kind"], job["argv"], title=job["title"], run_dir=job.get("run_dir", ""), requires=job.get("requires"),
                            params=job.get("params"), requested_by=job.get("requested_by", ""), retry_of=job["id"], env=job.get("env"),
                            exclusive=(excl[0], excl[1]) if excl else None)

    # -- running --
    def claim_next(self, runner: dict, lease_seconds: float = LEASE_SECONDS) -> dict | None:
        """Take the oldest queued job, unless any job is running (one at a time, whichever runner started it)."""
        if not self.dir.exists():
            return None  # nothing has ever been queued: do not create the folder just by looking
        with self._locked():
            jobs = self._all()
            if any(j["state"] == "running" for j in jobs):
                return None  # a live one is being worked on; an expired one is dealt with by reconcile() first
            queued = [j for j in jobs if j["state"] == "queued"]
            if not queued:
                return None
            job = queued[0]
            job.update(
                state="running", attempt=job.get("attempt", 0) + 1, started_at=_now_iso(), finished_at=None, cancel_requested=False,
                exit_code=None, error="", progress=None, pid=None, pgid=None, pid_stamp=None,
                lease={"runner": runner["id"], "host": runner["host"], "runner_pid": runner["pid"], "runner_stamp": runner["stamp"],
                       "expires_at": time.time() + lease_seconds},
            )
            self._write(job)
            return job

    def _mine(self, job: dict | None, attempt: int, runner_id: str) -> bool:
        return bool(job and job["state"] == "running" and job.get("attempt") == attempt and (job.get("lease") or {}).get("runner") == runner_id)

    def heartbeat(self, job_id: str, attempt: int, runner_id: str, lease_seconds: float = LEASE_SECONDS) -> str:
        """Renew the lease. "ok", "cancel" (someone asked to cancel) or "lost" (the job is no longer this runner's: stop the child and write nothing)."""
        with self._locked():
            job = self.get(job_id)
            if not self._mine(job, attempt, runner_id):
                return "lost"
            if job["lease"].get("expires_at", 0) - time.time() < lease_seconds / 2:
                job["lease"]["expires_at"] = time.time() + lease_seconds
                self._write(job)
            return "cancel" if job.get("cancel_requested") else "ok"

    def record_process(self, job_id: str, attempt: int, runner_id: str, pid: int, pgid: int, stamp: str | None) -> bool:
        with self._locked():
            job = self.get(job_id)
            if not self._mine(job, attempt, runner_id):
                return False
            job.update(pid=pid, pgid=pgid, pid_stamp=stamp)
            self._write(job)
            return True

    def record_progress(self, job_id: str, attempt: int, runner_id: str, progress: dict) -> None:
        with self._locked():
            job = self.get(job_id)
            if self._mine(job, attempt, runner_id):
                job["progress"] = progress
                self._write(job)

    def finish(self, job_id: str, attempt: int, runner_id: str, state: str, *, exit_code: int | None = None, error: str = "") -> bool:
        """End a job this runner still owns. False (and nothing written) when a newer attempt or another runner has it."""
        with self._locked():
            job = self.get(job_id)
            if not self._mine(job, attempt, runner_id):
                return False
            job.update(state=state, exit_code=exit_code, error=error, finished_at=_now_iso(), lease=None)
            self._write(job)
            return True

    def reconcile(self, runner: dict | None = None, grace: float = TERM_GRACE_SECONDS) -> list[str]:
        """Deal with jobs left `running` by a runner that is gone: stop any child group it left, then mark the job `interrupted` (`cancelled` if a cancel was asked for).

        A job is left alone when its lease is live and its runner is, as far as this host can tell, alive (another runner, or this one). Returns the ids it settled."""
        if not self.dir.exists():
            return []
        host = socket.gethostname()
        me = runner or {"id": f"reconciler:{host}:{os.getpid()}", "host": host, "pid": os.getpid(), "stamp": proc_start_stamp(os.getpid())}
        now = time.time()
        stale: list[dict] = []
        with self._locked():
            for job in self._all():
                if job["state"] != "running":
                    continue
                lease = job.get("lease") or {}
                if lease.get("runner") == me["id"]:
                    continue
                expired = float(lease.get("expires_at", 0)) <= now
                dead_here = lease.get("host") == host and not pid_alive(lease.get("runner_pid"), lease.get("runner_stamp"))
                if expired or dead_here or not lease:
                    # Fence it before the lock is released: a new attempt number and a lease of ours, so its former owner (perhaps only paused) can no longer renew,
                    # finish or write progress, and learns it has lost the job at its next heartbeat. If this process dies before settling it, the lease expires
                    # (or its runner pid is dead) and the next reconcile takes over.
                    job["attempt"] = job.get("attempt", 0) + 1
                    job["lease"] = {"runner": me["id"], "host": me["host"], "runner_pid": me["pid"], "runner_stamp": me["stamp"],
                                    "expires_at": now + grace + KILL_WAIT_SECONDS + 30}
                    self._write(job)
                    stale.append(job)
        settled = []
        for job in stale:  # the stops happen outside the lock: they can take seconds
            gone = _stop_recorded_child(job, grace)
            if not gone:
                log.error("Job %s: its process group could not be stopped; leaving it running", job["id"])
                continue
            with self._locked():
                current = self.get(job["id"])
                if not self._mine(current, job["attempt"], me["id"]):
                    continue
                cancelled = bool(current.get("cancel_requested"))
                current.update(state="cancelled" if cancelled else "interrupted", finished_at=_now_iso(), lease=None,
                               error="" if cancelled else "The runner stopped while this job was running; it can be retried.")
                self._write(current)
                settled.append(current["id"])
        return settled


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

def make_runner_identity() -> dict:
    pid = os.getpid()
    host = socket.gethostname()
    return {"id": f"{host}:{pid}:{uuid.uuid4().hex[:6]}", "host": host, "pid": pid, "stamp": proc_start_stamp(pid)}


class JobRunner:
    """Claims queued jobs and runs each as a child process, one at a time."""

    def __init__(self, store: JobStore, *, lease_seconds: float = LEASE_SECONDS, term_grace: float = TERM_GRACE_SECONDS, popen=subprocess.Popen):
        self.store = store
        self.identity = make_runner_identity()
        self.lease_seconds = lease_seconds
        self.term_grace = term_grace
        self._popen = popen
        self._shutdown = threading.Event()

    def shutdown(self) -> None:
        """Ask the runner to stop: a running job's child is ended and the job marked `interrupted` (it can be retried); nothing new is claimed."""
        self._shutdown.set()

    # -- one job --
    def run_pending_once(self) -> str | None:
        """Settle any job a dead runner left, then claim and run one job. Returns its id, or None when there was nothing to run."""
        self.store.reconcile(self.identity, self.term_grace)
        job = self.store.claim_next(self.identity, self.lease_seconds)
        if job is None:
            return None
        try:
            self._run(job)
        except Exception as e:  # a bug here must not leave the job running forever
            log.exception("Job %s: runner error", job["id"])
            self.store.finish(job["id"], job["attempt"], self.identity["id"], "failed", error=f"The runner failed: {e}")
        return job["id"]

    def _finish(self, job: dict, state: str, **kw) -> None:
        self.store.finish(job["id"], job["attempt"], self.identity["id"], state, **kw)

    def _run(self, job: dict) -> None:
        job_id, attempt, rid = job["id"], job["attempt"], self.identity["id"]
        problem = preflight(job.get("requires"))
        if problem:
            self._finish(job, "failed", error=problem)
            return
        log_path = self.store.log_path(job_id)
        logf = open(log_path, "ab", buffering=0)
        try:
            logf.write(f"\n=== attempt {attempt} started {_now_iso()} on {self.identity['host']} ===\n{' '.join(job['argv'])}\n".encode())
            env = dict(os.environ, PYTHONUNBUFFERED="1", **{k: v for k, v in (job.get("env") or {}).items() if k in JOB_ENV_ALLOWED})
            try:
                proc = self._popen(job["argv"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=logf, cwd=str(_ROOT), env=env,
                                   start_new_session=True, text=True, bufsize=1)
            except OSError as e:
                self._finish(job, "failed", error=f"The command could not be started: {e}")
                return
            if not self.store.record_process(job_id, attempt, rid, proc.pid, proc.pid, proc_start_stamp(proc.pid)):
                _terminate_group(proc.pid, proc, self.term_grace)  # the job is no longer ours
                return

            def read_stdout() -> None:
                last_step, last_write = None, 0.0
                for line in proc.stdout:
                    text = line.strip()
                    if text.startswith("{"):
                        try:
                            data = json.loads(text)
                        except ValueError:
                            data = None
                        if isinstance(data, dict) and "step" in data:
                            now = time.time()
                            if data.get("step") != last_step or now - last_write >= 1.0:
                                last_step, last_write = data.get("step"), now
                                self.store.record_progress(job_id, attempt, rid, {**data, "at": _now_iso()})
                            continue
                    if text:
                        logf.write((text + "\n").encode("utf-8", errors="replace"))

            reader = threading.Thread(target=read_stdout, daemon=True)
            reader.start()
            outcome = None  # None while running; "cancel", "lost" or "shutdown" when we stop it
            last_beat = 0.0
            try:
                while proc.poll() is None:
                    if self._shutdown.is_set():
                        outcome = "shutdown"
                        _terminate_group(proc.pid, proc, self.term_grace)
                        break
                    now = time.time()
                    if now - last_beat >= HEARTBEAT_SECONDS:
                        last_beat = now
                        status = self.store.heartbeat(job_id, attempt, rid, self.lease_seconds)
                        if status != "ok":
                            outcome = status
                            _terminate_group(proc.pid, proc, self.term_grace)
                            break
                    time.sleep(0.2)
            except BaseException:  # Ctrl+C or an exit while a job runs: do not leave its child behind
                _terminate_group(proc.pid, proc, self.term_grace)
                self._finish(job, "interrupted", error="The runner was stopped while this job was running; it can be retried.")
                raise
            rc = proc.wait()
            reader.join(timeout=5)
            if outcome == "lost":
                return  # another runner or attempt owns the job now; write nothing
            if outcome == "shutdown":
                self._finish(job, "interrupted", exit_code=rc, error="The runner was stopped while this job was running; it can be retried.")
            elif outcome == "cancel":
                self._finish(job, "cancelled", exit_code=rc)
            elif rc == 0:
                self._finish(job, "succeeded", exit_code=0)
            else:
                tail = [ln for ln in self.store.log_tail(job_id, 2000).splitlines() if ln.strip()]
                what = f"ended by signal {-rc}" if rc < 0 else f"exited with code {rc}"
                self._finish(job, "failed", exit_code=rc, error=f"The command {what}." + (f" Last line: {tail[-1][:300]}" if tail else ""))
        finally:
            logf.close()

    # -- a loop --
    def run_forever(self, stop: threading.Event, poll: float = POLL_SECONDS) -> None:
        while not stop.is_set() and not self._shutdown.is_set():
            try:
                ran = self.run_pending_once()
            except Exception:
                log.exception("Job runner loop error")
                ran = None
            if ran is None:
                stop.wait(poll)


def start_background_runner(store: JobStore | None = None) -> tuple[threading.Thread, threading.Event]:
    """Run the queue in a daemon thread of this process (what `reqbot serve` does). Returns the thread and the event that stops it."""
    runner = JobRunner(store or default_store())
    stop = threading.Event()
    thread = threading.Thread(target=runner.run_forever, args=(stop,), name="reqbot-job-runner", daemon=True)
    thread.start()

    def _stop_at_exit() -> None:  # a normal shutdown of the server must not leave a pipeline running behind it
        stop.set()
        runner.shutdown()
        thread.join(timeout=runner.term_grace + KILL_WAIT_SECONDS + 5)

    atexit.register(_stop_at_exit)
    return thread, stop


# ---------------------------------------------------------------------------
# Building jobs (the only commands that can be queued)
# ---------------------------------------------------------------------------

def default_store(processed_dir: Path | str | None = None) -> JobStore:
    base = Path(processed_dir) if processed_dir else _config.load().processed_dir_path()
    return JobStore(base / ".jobs")


def reserve_run_dir(base: Path, stem: str) -> Path:
    """Create and return `<base>/<stem>_<YYYYMMDD>_<HHMMSS>`, moving on a second at a time while that name is taken, so two jobs for PDFs with the same stem can never share a run
    folder (and so never reuse each other's chunks or cached answers). Creating the folder is the reservation (it is atomic); an explicit retry reuses its job's folder on purpose."""
    when = time.time()
    while True:
        candidate = base / f"{stem}_{time.strftime('%Y%m%d_%H%M%S', time.localtime(when))}"
        try:
            candidate.mkdir(parents=True)
            return candidate
        except FileExistsError:
            when += 1


def enqueue_ingest(pdf_path: str | Path, *, store: JobStore | None = None, cfg=None, no_index: bool = False, max_chunks: int | None = None,
                   requested_by: str = "", params_extra: dict | None = None, replace: bool = False) -> dict:
    """Queue `reqbot ingest` for one PDF. The job creates its run folder itself and passes it to the command, so a retry runs in the same folder and requirement finding reuses the
    answers it already has."""
    pdf = Path(pdf_path).expanduser().resolve()
    if pdf.suffix.lower() != ".pdf" or not pdf.is_file():
        raise ValueError(f"not a PDF file: {pdf_path}")
    if max_chunks is not None and max_chunks < 1:
        raise ValueError("max_chunks must be 1 or more")
    if replace and (no_index or max_chunks):
        raise ValueError("replace needs the whole document indexed: not with no_index or max_chunks")
    cfg = cfg or _config.load()
    store = store or default_store(cfg.processed_dir_path())
    run_dir = reserve_run_dir(cfg.processed_dir_path(), pdf.stem)
    # Every choice the command depends on is fixed now, so what is checked before the run is what runs, however long the job waits and whatever config does meanwhile.
    argv = [sys.executable, str(CLI_SCRIPT), "ingest", str(pdf), "--output-dir", str(run_dir)]
    for flag, value in (("--extraction-model", cfg.extraction_model), ("--enrichment-model", cfg.enrichment_model)):
        if value:  # an unset role is left to the command's own fallback; the string "None" must never reach it
            argv += [flag, str(value)]
    argv += ["--ollama-url", cfg.ollama_url, "--qdrant-url", cfg.qdrant_url, "--progress-json"]
    if no_index:
        argv.append("--no-index")
    if max_chunks:
        argv += ["--max-chunks", str(max_chunks)]
    if replace:
        argv.append("--replace")
    models = [cfg.extraction_model] + ([] if no_index else [cfg.embedding_model])
    requires = {"ollama_url": cfg.ollama_url, "ollama_models": [m for m in models if m], "qdrant_url": "" if no_index else cfg.qdrant_url}
    env = {} if no_index else {"REQBOT_EMBEDDING_MODEL": cfg.embedding_model}  # the ingest command has no flag for it; the environment overrides config
    try:
        return store.enqueue("ingest", argv, title=f"Ingest {pdf.name}", run_dir=str(run_dir), requires=requires, env=env,
                             params={"pdf": str(pdf), "stem": pdf.stem, "no_index": no_index, "max_chunks": max_chunks, "replace": replace, **(params_extra or {})},
                             requested_by=requested_by, exclusive=("stem", pdf.stem))
    except JobAlreadyQueued:
        try:
            run_dir.rmdir()  # the folder reserved a moment ago was never used
        except OSError:
            pass
        raise


QUESTIONS_MODEL = "qwen2.5:14b"  # the model `reqbot questions` writes with by default (services.audit_questions.MODEL); fixed in the job's command when it is queued
_DOC_KEY_BAD = re.compile(r"[\\/\x00-\x1f*?\[\]]")


def enqueue_questions(doc_key: str, *, store: JobStore | None = None, cfg=None, requested_by: str = "") -> dict:
    """Queue `reqbot questions --doc <doc_key>`: draft audit questions for one document's checklist rows. Only a document that is in the library can be named, and at most one
    such job per document is queued or running at a time. Rows whose input is unchanged are reused by the command, so running it again is cheap."""
    from core.artifact_resolver import resolve_requirement_file

    key = (doc_key or "").strip()
    if not key or _DOC_KEY_BAD.search(key) or key.startswith("."):
        raise ValueError(f"not a document key: {doc_key!r}")
    cfg = cfg or _config.load()
    store = store or default_store(cfg.processed_dir_path())
    try:
        resolve_requirement_file(cfg.processed_dir_path(), key)
    except (ValueError, FileNotFoundError, OSError):
        raise LookupError(f"No document {key!r} is in the library.") from None
    argv = [sys.executable, str(CLI_SCRIPT), "questions", "--doc", key, "--model", QUESTIONS_MODEL, "--ollama-url", cfg.ollama_url, "--progress-json"]
    requires = {"ollama_url": cfg.ollama_url, "ollama_models": [QUESTIONS_MODEL], "qdrant_url": ""}
    return store.enqueue("questions", argv, title=f"Draft questions for {key}", requires=requires, params={"doc_key": key, "model": QUESTIONS_MODEL},
                         requested_by=requested_by, exclusive=("doc_key", key))  # only questions jobs carry params.doc_key


def enqueue_reindex(*, store: JobStore | None = None, cfg=None, requirements_only: bool = False, requested_by: str = "") -> dict:
    """Queue `reqbot reindex`: rebuild the search library from the saved documents (no re-extraction). The live index is untouched until the new one is complete; the two
    halves (requirements, then context) are swapped one after the other, and the job's log says which one is done if the second fails. One rebuild at a time."""
    cfg = cfg or _config.load()
    store = store or default_store(cfg.processed_dir_path())
    argv = [sys.executable, str(CLI_SCRIPT), "reindex", "--ollama-url", cfg.ollama_url, "--qdrant-url", cfg.qdrant_url, "--progress-json"]
    if requirements_only:
        argv.append("--requirements-only")
    requires = {"ollama_url": cfg.ollama_url, "ollama_models": [cfg.embedding_model], "qdrant_url": cfg.qdrant_url}
    return store.enqueue("reindex", argv, title="Rebuild the search library" + (" (requirements only)" if requirements_only else ""), requires=requires,
                         env={"REQBOT_EMBEDDING_MODEL": cfg.embedding_model}, params={"requirements_only": requirements_only, "kind": "reindex"},
                         requested_by=requested_by, exclusive=("kind", "reindex"))


def summarize(job: dict) -> dict:
    """What a list or a screen shows: the job without its lease internals, and the command without the interpreter."""
    argv = job.get("argv") or []
    command = " ".join(["reqbot"] + [str(a) for a in argv[2:]]) if len(argv) > 2 else " ".join(argv)
    keys = ("id", "kind", "title", "state", "attempt", "created_at", "started_at", "finished_at", "progress", "error", "exit_code",
            "run_dir", "requested_by", "retry_of", "cancel_requested")
    params = {k: v for k, v in (job.get("params") or {}).items() if k in ("doc_key", "stem", "requirements_only", "replace")}  # what a screen matches a job to its document by
    return {**{k: job.get(k) for k in keys}, "command": command, "params": params}
