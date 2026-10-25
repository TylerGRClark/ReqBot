"""Job engine (docs/WEB_UI_PARITY_PLAN.md, stage 3): queue, claim and lease, process-group reconcile, pre-flight, progress, cancel.

Every job here runs a tiny stub script, never the real pipeline. Real child processes are used on purpose: the rules being tested are about processes."""
import http.server
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services import job_service as js
from services.job_service import JobRunner, JobStore


def _script(tmp_path: Path, body: str, name: str = "stub.py") -> Path:
    path = tmp_path / name
    path.write_text(body)
    return path


def _store(tmp_path: Path) -> JobStore:
    return JobStore(tmp_path / "processed" / ".jobs")


def _queue(store: JobStore, script: Path, *args: str, **kw) -> dict:
    return store.enqueue("stub", [sys.executable, str(script), *args], title=kw.pop("title", "stub"), **kw)


def _runner(store: JobStore, **kw) -> JobRunner:
    return JobRunner(store, lease_seconds=kw.pop("lease_seconds", 30), term_grace=kw.pop("term_grace", 2), **kw)


def _wait(cond, timeout=15.0, step=0.05):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(step)
    return False


def _dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _sleeper(new_session: bool = True) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=new_session)


SUCCEED = '''
import json, sys
print(json.dumps({"step": "reading"}), flush=True)
print(json.dumps({"step": "finding", "done": 1, "total": 2}), flush=True)
sys.stderr.write("a log line on stderr\\n")
print("a plain line on stdout", flush=True)
print(json.dumps({"step": "done"}), flush=True)
'''


# -- queue and one-at-a-time -------------------------------------------------

def test_jobs_list_newest_first_and_ids_are_safe(tmp_path):
    store = _store(tmp_path)
    a = _queue(store, _script(tmp_path, "pass"), title="first")
    time.sleep(0.01)
    b = _queue(store, _script(tmp_path, "pass"), title="second")
    assert [j["id"] for j in store.list_jobs()] == [b["id"], a["id"]]
    assert [j["id"] for j in store.list_jobs(limit=1)] == [b["id"]]
    for bad in ("../x", "a/b", ".lock", ""):
        with pytest.raises(ValueError):
            store.get(bad)


def test_only_one_job_runs_at_a_time_and_oldest_first(tmp_path):
    store = _store(tmp_path)
    first = _queue(store, _script(tmp_path, "pass"), title="first")
    time.sleep(0.01)
    second = _queue(store, _script(tmp_path, "pass"), title="second")
    runner = {"id": "r1", "host": socket.gethostname(), "pid": os.getpid(), "stamp": js.proc_start_stamp(os.getpid())}
    claimed = store.claim_next(runner)
    assert claimed["id"] == first["id"] and claimed["state"] == "running" and claimed["attempt"] == 1
    assert store.claim_next(runner) is None  # one is running: nothing else starts
    assert store.finish(first["id"], 1, "r1", "succeeded", exit_code=0)
    assert store.claim_next(runner)["id"] == second["id"]


def test_two_runners_never_both_claim(tmp_path):
    store = _store(tmp_path)
    _queue(store, _script(tmp_path, "pass"))
    _queue(store, _script(tmp_path, "pass"))
    results = []

    def claim(n):
        results.append(store.claim_next({"id": f"r{n}", "host": socket.gethostname(), "pid": os.getpid(), "stamp": None}))

    threads = [threading.Thread(target=claim, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for r in results if r) == 1


# -- running -------------------------------------------------------------------

def test_a_job_runs_to_success_with_progress_and_a_log(tmp_path):
    store = _store(tmp_path)
    job = _queue(store, _script(tmp_path, SUCCEED))
    assert _runner(store).run_pending_once() == job["id"]
    done = store.get(job["id"])
    assert done["state"] == "succeeded" and done["exit_code"] == 0 and done["lease"] is None and done["finished_at"]
    assert done["progress"]["step"] == "done"
    log_text = store.log_tail(job["id"])
    assert "a log line on stderr" in log_text and "a plain line on stdout" in log_text
    assert '"step"' not in log_text  # progress lines are not log text


def test_a_failing_job_says_how_it_ended(tmp_path):
    store = _store(tmp_path)
    job = _queue(store, _script(tmp_path, "import sys; sys.stderr.write('boom: something broke\\n'); sys.exit(3)"))
    _runner(store).run_pending_once()
    failed = store.get(job["id"])
    assert failed["state"] == "failed" and failed["exit_code"] == 3
    assert "code 3" in failed["error"] and "boom: something broke" in failed["error"]


def test_a_command_that_cannot_start_fails_the_job_not_the_runner(tmp_path):
    store = _store(tmp_path)
    job = store.enqueue("stub", [str(tmp_path / "no-such-program")], title="x")
    _runner(store).run_pending_once()
    assert store.get(job["id"])["state"] == "failed" and "could not be started" in store.get(job["id"])["error"]


def test_nothing_queued_means_nothing_runs(tmp_path):
    assert _runner(_store(tmp_path)).run_pending_once() is None


# -- cancel --------------------------------------------------------------------

def test_cancel_a_queued_job(tmp_path):
    store = _store(tmp_path)
    job = _queue(store, _script(tmp_path, "pass"))
    assert store.cancel(job["id"])["state"] == "cancelled"
    assert _runner(store).run_pending_once() is None


def _run_in_thread(runner: JobRunner) -> threading.Thread:
    t = threading.Thread(target=runner.run_pending_once, daemon=True)
    t.start()
    return t


def test_cancel_a_running_job_ends_its_process_group_including_children(tmp_path):
    store = _store(tmp_path)
    marker = tmp_path / "grandchild.pid"
    job = _queue(store, _script(tmp_path, f'''
import subprocess, sys, time
g = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
open({str(marker)!r}, "w").write(str(g.pid))
time.sleep(120)
'''))
    thread = _run_in_thread(_runner(store))
    assert _wait(lambda: marker.exists() and (store.get(job["id"]) or {}).get("pid"))
    child_pid, grandchild_pid = store.get(job["id"])["pid"], int(marker.read_text())
    assert js.pid_alive(child_pid) and js.pid_alive(grandchild_pid)
    store.cancel(job["id"])
    thread.join(timeout=20)
    assert store.get(job["id"])["state"] == "cancelled"
    assert _wait(lambda: not js.pid_alive(child_pid) and not js.pid_alive(grandchild_pid), timeout=10)


def test_a_child_that_ignores_sigterm_is_killed_after_the_grace_period(tmp_path):
    store = _store(tmp_path)
    ready = tmp_path / "ready"
    job = _queue(store, _script(tmp_path, f'''
import signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
open({str(ready)!r}, "w").write("1")
time.sleep(120)
'''))
    thread = _run_in_thread(_runner(store, term_grace=1))
    assert _wait(lambda: ready.exists() and (store.get(job["id"]) or {}).get("pid"))
    pid = store.get(job["id"])["pid"]
    started = time.time()
    store.cancel(job["id"])
    thread.join(timeout=20)
    assert store.get(job["id"])["state"] == "cancelled"
    assert not js.pid_alive(pid)
    assert time.time() - started < 15


# -- a runner that dies --------------------------------------------------------

def _left_running(store: JobStore, child: subprocess.Popen, *, runner_pid: int, stamp: str | None = "same", expires_in: float = 300) -> dict:
    """A job file as a server that was killed mid-job leaves it: `running`, with the child's group recorded."""
    job = store.enqueue("stub", [sys.executable, "-c", "pass"], title="left running")
    with store._locked():
        j = store.get(job["id"])
        j.update(state="running", attempt=1, pid=child.pid, pgid=child.pid,
                 pid_stamp=js.proc_start_stamp(child.pid) if stamp == "same" else stamp,
                 lease={"runner": "old-runner", "host": socket.gethostname(), "runner_pid": runner_pid, "runner_stamp": "gone",
                        "expires_at": time.time() + expires_in})
        store._write(j)
    return store.get(job["id"])


def test_reconcile_stops_a_live_child_before_the_queue_moves(tmp_path):
    """Kill the server with a job running: the child outlives it. Nothing else may start until that child is gone."""
    store = _store(tmp_path)
    child = _sleeper()
    left = _left_running(store, child, runner_pid=_dead_pid())
    waiting = _queue(store, _script(tmp_path, "pass"), title="waiting")
    me = {"id": "new", "host": socket.gethostname(), "pid": os.getpid(), "stamp": js.proc_start_stamp(os.getpid())}
    assert store.claim_next(me) is None  # a job is still "running": the queue does not move
    settled = store.reconcile(me, grace=2)
    assert settled == [left["id"]]
    child.wait(timeout=10)  # reaped here only because the test is the parent; in life init does it
    assert not js.pid_alive(child.pid)
    after = store.get(left["id"])
    assert after["state"] == "interrupted" and after["lease"] is None and "retried" in after["error"]
    assert store.claim_next(me)["id"] == waiting["id"]


def test_the_runner_settles_a_dead_runners_job_before_claiming(tmp_path):
    store = _store(tmp_path)
    child = _sleeper()
    left = _left_running(store, child, runner_pid=_dead_pid())
    queued = _queue(store, _script(tmp_path, SUCCEED))
    assert _runner(store).run_pending_once() == queued["id"]
    child.wait(timeout=10)
    assert store.get(left["id"])["state"] == "interrupted" and store.get(queued["id"])["state"] == "succeeded"


def test_a_job_leased_by_a_live_runner_is_left_alone(tmp_path):
    store = _store(tmp_path)
    child = _sleeper()
    try:
        left = _left_running(store, child, runner_pid=os.getpid(), expires_in=300)
        with store._locked():  # the lease names a runner process that is alive here (this test process) with its real start stamp
            j = store.get(left["id"])
            j["lease"]["runner_stamp"] = js.proc_start_stamp(os.getpid())
            store._write(j)
        me = {"id": "other", "host": socket.gethostname(), "pid": os.getpid(), "stamp": None}
        assert store.reconcile(me, grace=1) == []
        assert store.get(left["id"])["state"] == "running" and js.pid_alive(child.pid)
        assert store.claim_next(me) is None
    finally:
        child.kill()
        child.wait()


def test_an_expired_lease_interrupts_the_job_even_with_nothing_to_stop(tmp_path):
    store = _store(tmp_path)
    job = store.enqueue("stub", [sys.executable, "-c", "pass"], title="x")
    with store._locked():
        j = store.get(job["id"])
        j.update(state="running", attempt=1, lease={"runner": "far-away", "host": "some-other-host", "runner_pid": 1, "runner_stamp": "x",
                                                     "expires_at": time.time() - 5})
        store._write(j)
    assert store.reconcile(None, grace=1) == [job["id"]]
    assert store.get(job["id"])["state"] == "interrupted"


def test_a_live_lease_on_another_host_is_not_touched(tmp_path):
    store = _store(tmp_path)
    job = store.enqueue("stub", [sys.executable, "-c", "pass"], title="x")
    with store._locked():
        j = store.get(job["id"])
        j.update(state="running", attempt=1, lease={"runner": "far-away", "host": "some-other-host", "runner_pid": 1, "runner_stamp": "x",
                                                     "expires_at": time.time() + 100})
        store._write(j)
    assert store.reconcile(None, grace=1) == []
    assert store.get(job["id"])["state"] == "running"


def test_a_reused_process_number_is_not_mistaken_for_the_child(tmp_path):
    store = _store(tmp_path)
    innocent = _sleeper()  # some other process that now has the number the job recorded
    try:
        left = _left_running(store, innocent, runner_pid=_dead_pid(), stamp="not-its-start-time")
        assert store.reconcile(None, grace=1) == [left["id"]]
        assert js.pid_alive(innocent.pid)  # not killed
        assert store.get(left["id"])["state"] == "interrupted"
    finally:
        innocent.kill()
        innocent.wait()


def test_a_stale_runner_cannot_write_over_a_newer_attempt(tmp_path):
    store = _store(tmp_path)
    job = _queue(store, _script(tmp_path, "pass"))
    old = {"id": "old", "host": socket.gethostname(), "pid": os.getpid(), "stamp": None}
    assert store.claim_next(old)["attempt"] == 1
    with store._locked():  # its lease expired and the job was settled and retried by someone else
        j = store.get(job["id"])
        j.update(state="interrupted", lease=None)
        store._write(j)
    assert store.finish(job["id"], 1, "old", "succeeded", exit_code=0) is False
    assert store.heartbeat(job["id"], 1, "old") == "lost"
    assert store.get(job["id"])["state"] == "interrupted"


def test_retry_queues_the_same_command_and_run_folder_but_only_from_an_ended_job(tmp_path):
    store = _store(tmp_path)
    job = _queue(store, _script(tmp_path, "import sys; sys.exit(1)"), run_dir=str(tmp_path / "run_1"), title="again")
    with pytest.raises(ValueError):
        store.retry(job["id"])  # still queued
    _runner(store).run_pending_once()
    new = store.retry(job["id"])
    assert new["argv"] == job["argv"] and new["run_dir"] == job["run_dir"] and new["retry_of"] == job["id"] and new["state"] == "queued"


# -- pre-flight ----------------------------------------------------------------

def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_preflight_names_the_model_machine_when_it_does_not_answer(tmp_path):
    problem = js.preflight({"ollama_url": f"http://127.0.0.1:{_closed_port()}"}, timeout=1)
    assert problem and "model machine" in problem


def test_preflight_names_qdrant_when_it_does_not_answer():
    problem = js.preflight({"qdrant_url": f"http://127.0.0.1:{_closed_port()}"}, timeout=1)
    assert problem and "Qdrant" in problem


class _Tags(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = json.dumps({"models": [{"name": "llama3.1:8b-instruct-q4_K_M"}, {"name": "nomic-embed-text:latest"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence
        pass


def test_preflight_checks_the_models_and_accepts_the_latest_tag():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Tags)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert js.preflight({"ollama_url": url, "ollama_models": ["llama3.1:8b-instruct-q4_K_M", "nomic-embed-text"]}) is None
        problem = js.preflight({"ollama_url": url, "ollama_models": ["qwen2.5:14b"]})
        assert problem and "qwen2.5:14b" in problem
        assert js.preflight(None) is None and js.preflight({}) is None
    finally:
        server.shutdown()


def test_a_failed_preflight_fails_the_job_at_once_without_starting_it(tmp_path):
    store = _store(tmp_path)
    marker = tmp_path / "started"
    job = _queue(store, _script(tmp_path, f"open({str(marker)!r}, 'w').write('x')"), requires={"ollama_url": f"http://127.0.0.1:{_closed_port()}"})
    _runner(store).run_pending_once()
    failed = store.get(job["id"])
    assert failed["state"] == "failed" and "model machine" in failed["error"]
    assert not marker.exists()


# -- building the ingest job ---------------------------------------------------

def _cfg(tmp_path: Path):
    return SimpleNamespace(
        ollama_url="http://ollama.test:11434", qdrant_url="http://qdrant.test:6333", extraction_model="llama3.1:8b",
        enrichment_model="llama3.1:8b", embedding_model="nomic-embed-text", processed_dir_path=lambda: tmp_path / "processed",
    )


def test_enqueue_ingest_builds_the_whole_command_itself(tmp_path):
    pdf = tmp_path / "afi99-1.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    job = js.enqueue_ingest(pdf, store=_store(tmp_path), cfg=_cfg(tmp_path), max_chunks=3, requested_by="cli")
    argv = job["argv"]
    assert argv[0] == sys.executable and argv[2] == "ingest" and argv[3] == str(pdf.resolve())
    assert argv[argv.index("--output-dir") + 1] == job["run_dir"] and Path(job["run_dir"]).parent == tmp_path / "processed"
    assert Path(job["run_dir"]).name.startswith("afi99-1_")
    assert "--progress-json" in argv and argv[argv.index("--max-chunks") + 1] == "3" and "--no-index" not in argv
    assert job["requires"]["ollama_models"] == ["llama3.1:8b", "nomic-embed-text"] and job["requires"]["qdrant_url"] == "http://qdrant.test:6333"
    assert job["title"] == "Ingest afi99-1.pdf" and job["requested_by"] == "cli"


def test_enqueue_ingest_without_indexing_does_not_need_qdrant_or_the_embedding_model(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    job = js.enqueue_ingest(pdf, store=_store(tmp_path), cfg=_cfg(tmp_path), no_index=True)
    assert "--no-index" in job["argv"] and job["requires"]["ollama_models"] == ["llama3.1:8b"] and job["requires"]["qdrant_url"] == ""


def test_enqueue_ingest_refuses_what_is_not_a_pdf_file(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    for bad in (tmp_path / "notes.txt", tmp_path / "missing.pdf", tmp_path):
        with pytest.raises(ValueError):
            js.enqueue_ingest(bad, store=_store(tmp_path), cfg=_cfg(tmp_path))
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError):
        js.enqueue_ingest(pdf, store=_store(tmp_path), cfg=_cfg(tmp_path), max_chunks=0)


def test_summarize_hides_the_interpreter_and_the_lease():
    job = {"id": "JOB-1", "kind": "ingest", "title": "t", "state": "running", "argv": ["/usr/bin/python3", "/x/cli/reqbot.py", "ingest", "a.pdf"],
           "lease": {"runner": "secret-ish"}, "progress": {"step": "finding"}}
    s = js.summarize(job)
    assert s["command"] == "reqbot ingest a.pdf" and "lease" not in s and s["progress"] == {"step": "finding"}


def test_process_stamps_tell_a_process_from_a_reused_number():
    me = os.getpid()
    stamp = js.proc_start_stamp(me)
    assert stamp and js.pid_alive(me, stamp) and not js.pid_alive(me, "0") and not js.pid_alive(None) and not js.pid_alive(_dead_pid())


def test_terminate_group_is_quiet_about_a_group_that_is_already_gone():
    assert js._terminate_group(_dead_pid(), None, grace=1) is True


def test_sigterm_constant_is_what_the_runner_sends():  # a guard on the one signal the cancel path relies on
    assert signal.SIGTERM.value == 15


# -- tightening ----------------------------------------------------------------

def test_looking_at_an_empty_store_creates_nothing(tmp_path):
    store = _store(tmp_path)
    runner = _runner(store)
    assert runner.run_pending_once() is None
    assert store.list_jobs() == [] and store.reconcile(None) == []
    assert not store.dir.exists()  # a server that merely starts must not make <processed_dir>/.jobs


def test_a_heartbeat_does_not_rewrite_the_job_until_the_lease_is_half_used(tmp_path):
    store = _store(tmp_path)
    job = _queue(store, _script(tmp_path, "pass"))
    runner = {"id": "r", "host": socket.gethostname(), "pid": os.getpid(), "stamp": None}
    store.claim_next(runner, lease_seconds=60)
    path = store._path(job["id"])
    before = path.stat().st_mtime_ns
    assert store.heartbeat(job["id"], 1, "r", 60) == "ok"
    assert path.stat().st_mtime_ns == before  # a fresh lease: nothing written
    with store._locked():
        j = store.get(job["id"])
        j["lease"]["expires_at"] = time.time() + 5
        store._write(j)
    assert store.heartbeat(job["id"], 1, "r", 60) == "ok"
    assert store.get(job["id"])["lease"]["expires_at"] > time.time() + 30  # renewed
    store.cancel(job["id"])
    assert store.heartbeat(job["id"], 1, "r", 60) == "cancel"


def test_stopping_the_runner_ends_the_running_child_and_marks_the_job_interrupted(tmp_path):
    store = _store(tmp_path)
    ready = tmp_path / "ready"
    job = _queue(store, _script(tmp_path, f"import time\nopen({str(ready)!r}, 'w').write('1')\ntime.sleep(120)"))
    runner = _runner(store)
    thread = _run_in_thread(runner)
    assert _wait(lambda: ready.exists() and (store.get(job["id"]) or {}).get("pid"))
    pid = store.get(job["id"])["pid"]
    runner.shutdown()
    thread.join(timeout=20)
    done = store.get(job["id"])
    assert done["state"] == "interrupted" and "retried" in done["error"]
    assert _wait(lambda: not js.pid_alive(pid), timeout=10)


def test_the_loop_stops_when_the_runner_is_shut_down(tmp_path):
    store = _store(tmp_path)
    runner = _runner(store)
    stop = threading.Event()
    t = threading.Thread(target=runner.run_forever, args=(stop, 0.05), daemon=True)
    t.start()
    runner.shutdown()
    t.join(timeout=5)
    assert not t.is_alive()


# -- the reviewer's findings on this change ---------------------------------------

def test_run_folders_reserved_in_the_same_second_are_all_different(tmp_path):
    base = tmp_path / "processed"
    base.mkdir()
    dirs = [js.reserve_run_dir(base, "afi99-1") for _ in range(4)]  # inside the same second
    assert len({d.name for d in dirs}) == 4 and all(d.is_dir() for d in dirs)
    assert all(re.fullmatch(r"afi99-1_\d{8}_\d{6}", d.name) for d in dirs)  # the name pattern the rest of ReqBot expects
    pdf = tmp_path / "afi99-1.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    job = js.enqueue_ingest(pdf, store=_store(tmp_path), cfg=_cfg(tmp_path))
    assert job["argv"][job["argv"].index("--output-dir") + 1] == job["run_dir"] and Path(job["run_dir"]).is_dir()


def test_the_same_name_cannot_be_queued_twice_even_by_requests_at_the_same_moment(tmp_path):
    pdf = tmp_path / "afi99-1.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    store, cfg = _store(tmp_path), _cfg(tmp_path)
    outcomes = []

    def go():
        try:
            outcomes.append(js.enqueue_ingest(pdf, store=store, cfg=cfg)["id"])
        except js.JobAlreadyQueued as e:
            outcomes.append(("refused", e.job_id))

    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    queued = [o for o in outcomes if isinstance(o, str)]
    assert len(queued) == 1 and len(store.list_jobs()) == 1
    assert all(o[1] == queued[0] for o in outcomes if isinstance(o, tuple))
    # the folders reserved by the refused attempts were released: only the winner's is left
    assert [d.name for d in (tmp_path / "processed").iterdir() if d.is_dir() and not d.name.startswith(".")] == [Path(store.list_jobs()[0]["run_dir"]).name]


def test_a_finished_job_no_longer_blocks_the_name(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    store, cfg = _store(tmp_path), _cfg(tmp_path)
    first = js.enqueue_ingest(pdf, store=store, cfg=cfg)
    with pytest.raises(js.JobAlreadyQueued):
        js.enqueue_ingest(pdf, store=store, cfg=cfg)
    store.cancel(first["id"])
    assert js.enqueue_ingest(pdf, store=store, cfg=cfg)["state"] == "queued"


def test_only_the_exact_job_id_shape_reaches_a_file(tmp_path):
    store = _store(tmp_path)
    for bad in ("JOB-1", "../JOB-20261012-010101-abcdef", "JOB-20261012-010101-ABCDEF", "JOB-20261012-010101-abcdef/../x", "JOB-20261012-010101-abcdef.json", "x" * 400):
        with pytest.raises(ValueError):
            store.get(bad)
    job = _queue(store, _script(tmp_path, "pass"))
    assert store.get(job["id"])["id"] == job["id"]


def test_a_retry_keeps_its_run_folder_and_a_cancelled_queued_job_releases_an_unused_one(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    store, cfg = _store(tmp_path), _cfg(tmp_path)
    job = js.enqueue_ingest(pdf, store=store, cfg=cfg)
    run_dir = Path(job["run_dir"])
    assert run_dir.is_dir()
    store.cancel(job["id"])
    assert not run_dir.exists()  # reserved and never used
    kept = js.enqueue_ingest(pdf, store=store, cfg=cfg)
    (Path(kept["run_dir"]) / "doc_chunks.jsonl").write_text("{}")  # work was done in it
    store.cancel(kept["id"])
    assert Path(kept["run_dir"]).is_dir()  # never removed when it holds anything
    assert store.retry(kept["id"])["run_dir"] == kept["run_dir"]


def test_reconcile_fences_the_job_so_a_paused_owner_cannot_renew_while_it_is_stopped(tmp_path):
    store = _store(tmp_path)
    job = _queue(store, _script(tmp_path, "pass"))
    old = {"id": "old-runner", "host": "some-other-host", "pid": 1, "stamp": "x"}
    assert store.claim_next(old, lease_seconds=60)["attempt"] == 1
    with store._locked():  # its lease ran out (the machine was paused)
        j = store.get(job["id"])
        j["lease"]["expires_at"] = time.time() - 1
        store._write(j)
    seen = {}
    original = js._stop_recorded_child

    def stop_while_the_owner_wakes_up(j, grace):
        # the owner comes back in the middle of the stop and tries everything it can
        seen["heartbeat"] = store.heartbeat(job["id"], 1, "old-runner", 60)
        seen["finish"] = store.finish(job["id"], 1, "old-runner", "succeeded", exit_code=0)
        seen["progress_job"] = store.get(job["id"])
        return original(j, grace)

    me = {"id": "new-runner", "host": socket.gethostname(), "pid": os.getpid(), "stamp": js.proc_start_stamp(os.getpid())}
    with patch.object(js, "_stop_recorded_child", stop_while_the_owner_wakes_up):
        assert store.reconcile(me, grace=1) == [job["id"]]
    assert seen["heartbeat"] == "lost" and seen["finish"] is False
    assert seen["progress_job"]["state"] == "running" and seen["progress_job"]["lease"]["runner"] == "new-runner"
    final = store.get(job["id"])
    assert final["state"] == "interrupted" and final["attempt"] == 2


def test_a_reconciler_that_died_midway_leaves_a_job_the_next_one_can_settle(tmp_path):
    store = _store(tmp_path)
    job = _queue(store, _script(tmp_path, "pass"))
    with store._locked():  # fenced by a reconciler whose process is gone
        j = store.get(job["id"])
        j.update(state="running", attempt=2, lease={"runner": "reconciler:x", "host": socket.gethostname(), "runner_pid": _dead_pid(),
                                                     "runner_stamp": "gone", "expires_at": time.time() + 300})
        store._write(j)
    assert store.reconcile(None, grace=1) == [job["id"]]
    assert store.get(job["id"])["state"] == "interrupted"


def test_the_models_are_fixed_when_the_job_is_queued(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    cfg = _cfg(tmp_path)
    store = _store(tmp_path)
    job = js.enqueue_ingest(pdf, store=store, cfg=cfg)
    argv = job["argv"]
    assert argv[argv.index("--extraction-model") + 1] == "llama3.1:8b" and "--enrichment-model" not in argv
    assert job["env"] == {"REQBOT_EMBEDDING_MODEL": "nomic-embed-text"}
    cfg.embedding_model = "a-different-model"  # config changes while the job waits
    cfg.extraction_model = "another-model"
    assert store.get(job["id"])["env"] == {"REQBOT_EMBEDDING_MODEL": "nomic-embed-text"}
    assert store.get(job["id"])["requires"]["ollama_models"] == ["llama3.1:8b", "nomic-embed-text"]
    store.cancel(job["id"])
    assert store.retry(job["id"])["env"] == job["env"]  # a retry keeps the same snapshot


def test_a_job_may_set_only_the_allow_listed_environment_and_its_child_gets_it(tmp_path):
    store = _store(tmp_path)
    out = tmp_path / "env.txt"
    job = store.enqueue("stub", [sys.executable, str(_script(tmp_path, f"import os\nopen({str(out)!r}, 'w').write(repr((os.environ.get('REQBOT_EMBEDDING_MODEL'), os.environ.get('LD_PRELOAD'))))")),],
                        title="env", env={"REQBOT_EMBEDDING_MODEL": "snap", "LD_PRELOAD": "/evil.so"})
    assert job["env"] == {"REQBOT_EMBEDDING_MODEL": "snap"}  # anything else is dropped at queue time
    _runner(store).run_pending_once()
    assert out.read_text() == repr(("snap", os.environ.get("LD_PRELOAD")))


def test_an_unset_model_role_leaves_its_flag_out_and_none_never_becomes_an_argument(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    cfg = _cfg(tmp_path)
    cfg.enrichment_model = None
    job = js.enqueue_ingest(pdf, store=_store(tmp_path), cfg=cfg, no_index=True)
    assert "--enrichment-model" not in job["argv"] and "None" not in job["argv"]
    assert "--extraction-model" in job["argv"]
    with pytest.raises(ValueError):
        _store(tmp_path).enqueue("stub", [sys.executable, None], title="x")
