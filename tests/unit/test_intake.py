"""Admin intake (docs/WEB_UI_PARITY_PLAN.md, stage 4a): uploads, the inbox, the same-file rules, and the routes that start, cancel and retry an ingest."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core import access
from services import intake_service as intake
from services import job_service as js
from services.intake_service import IntakeError, UploadWriter


def tiny_pdf(pages: int = 1, tag: str = "") -> bytes:
    """A small valid PDF; `tag` makes two files of the same page count differ in content."""
    kids = " ".join(f"{3 + i} 0 R" for i in range(pages))
    objs = ["1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n", f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {pages} >>\nendobj\n"]
    objs += [f"{3 + i} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>\nendobj\n" for i in range(pages)]
    body, offsets = f"%PDF-1.4\n%{tag}\n", []
    for o in objs:
        offsets.append(len(body.encode()))
        body += o
    xref = len(body.encode())
    body += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{off:010d} 00000 n \n" for off in offsets)
    body += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return body.encode()


@pytest.fixture
def env(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    monkeypatch.setenv("REQBOT_PROCESSED_DIR", str(processed))
    monkeypatch.delenv(intake.ENV_INBOX, raising=False)
    monkeypatch.delenv(intake.ENV_MAX_UPLOAD_MB, raising=False)
    monkeypatch.delenv(intake.ENV_MAX_PAGES, raising=False)
    monkeypatch.setattr(access, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.setattr(access, "FAILED_ATTEMPT_DELAY_SECONDS", 0)
    token, _ = access.create_admin_token()
    return SimpleEnv(processed, {"Authorization": f"Bearer {token}"})


class SimpleEnv:
    def __init__(self, processed: Path, headers: dict):
        self.processed, self.headers = processed, headers

    def client(self) -> TestClient:
        from api.app import app
        return TestClient(app)

    def library(self, stem: str, sha256: str) -> None:
        """Put a document in the library the way an ingest leaves it: a normalized file whose records carry the PDF's hash."""
        run = self.processed / f"{stem}_20261001_120000"
        run.mkdir()
        (run / f"{stem}_requirements_normalized.jsonl").write_text(
            json.dumps({"requirement_id": "REQ-1", "source_quote": "x", "document_hash_full": sha256, "source_pdf": f"{stem}.pdf"}) + "\n")


def upload(env: SimpleEnv, name: str, data: bytes, **kw):
    return env.client().post(f"/api/uploads?filename={name}", content=data, headers=env.headers, **kw)


# -- file names and the checks ----------------------------------------------------

@pytest.mark.parametrize("raw, clean", [
    ("afi17-203.pdf", "afi17-203.pdf"), ("My Doc (v2).PDF", "My Doc (v2).pdf"), ("../../etc/passwd.pdf", "passwd.pdf"),
    ("C:\\x\\y\\doc.pdf", "doc.pdf"), ("we!rd&name$.pdf", "we_rd_name_.pdf"),
])
def test_clean_filename_keeps_a_plain_name(raw, clean):
    assert intake.clean_filename(raw) == clean


@pytest.mark.parametrize("raw", ["notes.txt", "doc.pdf.exe", "", ".pdf", "...pdf", "/"])
def test_clean_filename_refuses_what_is_not_a_pdf_name(raw):
    with pytest.raises(IntakeError):
        intake.clean_filename(raw)


def test_a_chunked_upload_is_stored_hashed_and_counted(tmp_path):
    data = tiny_pdf(3)
    w = UploadWriter(tmp_path, "three.pdf")
    for i in range(0, len(data), 7):  # the %PDF- header is split across the first chunks
        w.write(data[i:i + 7])
    meta = w.finish()
    assert meta["pages"] == 3 and meta["size"] == len(data) and meta["stem"] == "three"
    assert Path(meta["path"]).read_bytes() == data and Path(meta["path"]).parent.parent == intake.uploads_dir(tmp_path)
    import hashlib
    assert meta["sha256"] == hashlib.sha256(data).hexdigest()


def test_the_size_cap_is_enforced_while_the_upload_streams(tmp_path):
    w = UploadWriter(tmp_path, "big.pdf", max_bytes=100)
    w.write(b"%PDF-1.4\n" + b"x" * 50)
    with pytest.raises(IntakeError) as e:
        w.write(b"x" * 60)
    assert e.value.code == "too_large" and e.value.status == 413
    w.abort()
    assert not w.dir.exists()


def test_a_file_that_is_not_a_pdf_is_refused_from_its_first_bytes(tmp_path):
    w = UploadWriter(tmp_path, "evil.pdf")
    with pytest.raises(IntakeError) as e:
        w.write(b"MZ\x90\x00 this is an executable")
    assert e.value.code == "not_pdf" and e.value.status == 415
    w.abort()


def test_a_file_that_starts_like_a_pdf_but_does_not_open_is_refused(tmp_path):
    w = UploadWriter(tmp_path, "broken.pdf")
    w.write(b"%PDF-1.4\nthis is not really a pdf")
    with pytest.raises(IntakeError) as e:
        w.finish()
    assert e.value.code == "unreadable"
    w.abort()


def test_the_page_cap_refuses_a_long_document(tmp_path, monkeypatch):
    monkeypatch.setenv(intake.ENV_MAX_PAGES, "2")
    w = UploadWriter(tmp_path, "long.pdf")
    w.write(tiny_pdf(3))
    with pytest.raises(IntakeError) as e:
        w.finish()
    assert e.value.code == "too_many_pages"
    w.abort()


def test_an_upload_id_cannot_be_used_to_reach_another_path(tmp_path):
    for bad in ("../x", "UP-1", "", "UP-20261012-010101-zzzzzz/../..", "/etc/passwd"):
        with pytest.raises(IntakeError):
            intake.read_upload(tmp_path, bad)


# -- the library rules --------------------------------------------------------------

def test_classify_tells_new_same_content_other_name_and_changed(env):
    env.library("afi99-1", "aaa")
    c = lambda stem, h, jobs=(): intake.classify(env.processed, stem, h, list(jobs))["status"]  # noqa: E731
    assert c("afi99-1", "aaa") == "same_content"
    assert c("afi99-1", "bbb") == "same_name_different_content"
    assert c("renamed-copy", "aaa") == "same_content_other_name"
    assert c("something-else", "ccc") == "new"
    queued = [{"kind": "ingest", "state": "queued", "id": "JOB-1", "params": {"stem": "brand-new"}}]
    assert c("brand-new", "ddd", queued) == "queued"


def test_free_stem_skips_names_in_the_library_and_the_queue(env):
    env.library("doc", "h1")
    env.library("doc_2", "h2")
    queued = [{"state": "queued", "params": {"stem": "doc_3"}}]
    assert intake.free_stem(env.processed, "doc", queued) == "doc_4"


# -- the routes: access ---------------------------------------------------------------

def test_every_intake_route_needs_the_admin_code(env):
    c = env.client()
    for method, path in (("post", "/api/uploads?filename=a.pdf"), ("get", "/api/inbox"), ("post", "/api/jobs/ingest"), ("post", "/api/jobs/inbox"),
                         ("post", "/api/jobs/JOB-1/cancel"), ("post", "/api/jobs/JOB-1/retry")):
        assert getattr(c, method)(path).status_code == 401, path
        assert getattr(c, method)(path, headers={"Authorization": "Bearer wrong"}).status_code == 401, path


# -- the routes: upload and start ---------------------------------------------------

def test_upload_then_start_queues_one_ingest_job(env):
    r = upload(env, "afi99-1.pdf", tiny_pdf(2))
    assert r.status_code == 201
    body = r.json()
    assert body["stem"] == "afi99-1" and body["pages"] == 2 and body["library"]["status"] == "new"
    assert re.fullmatch(r"UP-\d{8}-\d{6}-[0-9a-f]{6}", body["upload_id"]) and "path" not in body
    s = env.client().post("/api/jobs/ingest", json={"upload_id": body["upload_id"]}, headers=env.headers)
    assert s.status_code == 202 and s.json()["result"] == "queued"
    job = js.default_store().list_jobs()[0]
    assert job["state"] == "queued" and job["kind"] == "ingest" and job["params"]["stem"] == "afi99-1" and job["params"]["sha256"] == body["sha256"]
    assert job["requested_by"] and "--progress-json" in job["argv"]
    assert job["argv"][3].endswith(f"{body['upload_id']}/afi99-1.pdf")


def test_upload_refusals_have_a_code_and_leave_nothing_behind(env, monkeypatch):
    r = upload(env, "notes.txt", b"hello")
    assert r.status_code == 415 and r.json()["detail"]["code"] == "not_pdf"
    r = upload(env, "fake.pdf", b"MZ not a pdf")
    assert r.status_code == 415 and r.json()["detail"]["code"] == "not_pdf"
    monkeypatch.setenv(intake.ENV_MAX_UPLOAD_MB, "1")
    r = upload(env, "huge.pdf", b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10))
    assert r.status_code == 413 and r.json()["detail"]["code"] == "too_large"
    r = upload(env, "../../evil.pdf", tiny_pdf())
    assert r.status_code == 201 and r.json()["filename"] == "evil.pdf"  # the name is made plain, never followed
    leftovers = [p for p in (env.processed / ".uploads").iterdir()] if (env.processed / ".uploads").exists() else []
    assert len(leftovers) == 1  # only the one good upload remains


def test_the_same_content_again_is_skipped_not_queued(env):
    pdf = tiny_pdf(1, "same")
    import hashlib
    env.library("afi99-1", hashlib.sha256(pdf).hexdigest())
    up = upload(env, "afi99-1.pdf", pdf).json()
    assert up["library"]["status"] == "same_content"
    s = env.client().post("/api/jobs/ingest", json={"upload_id": up["upload_id"]}, headers=env.headers)
    assert s.status_code == 200 and s.json()["result"] == "skipped" and s.json()["reason"] == "same_content"
    assert js.default_store().list_jobs() == []


def test_same_name_different_content_asks_and_then_replaces_or_keeps_both(env):
    env.library("afi99-1", "old-content-hash")
    up = upload(env, "afi99-1.pdf", tiny_pdf(1, "new edition")).json()
    assert up["library"]["status"] == "same_name_different_content"
    c, h = env.client(), env.headers
    ask = c.post("/api/jobs/ingest", json={"upload_id": up["upload_id"]}, headers=h)
    assert ask.status_code == 409 and ask.json()["detail"]["options"] == ["replace", "keep_both"]
    assert js.default_store().list_jobs() == []  # never silent: nothing was queued
    both = c.post("/api/jobs/ingest", json={"upload_id": up["upload_id"], "if_exists": "keep_both"}, headers=h)
    assert both.status_code == 202 and both.json()["document"] == "afi99-1_2"
    assert js.default_store().list_jobs()[0]["params"]["stem"] == "afi99-1_2"
    rep = c.post("/api/jobs/ingest", json={"upload_id": up["upload_id"], "if_exists": "replace"}, headers=h)
    assert rep.status_code == 202 and rep.json()["document"] == "afi99-1"


def test_a_name_already_queued_is_not_queued_twice(env):
    a = upload(env, "afi99-2.pdf", tiny_pdf(1, "a")).json()
    b = upload(env, "afi99-2.pdf", tiny_pdf(1, "b")).json()
    c, h = env.client(), env.headers
    assert c.post("/api/jobs/ingest", json={"upload_id": a["upload_id"]}, headers=h).status_code == 202
    second = c.post("/api/jobs/ingest", json={"upload_id": b["upload_id"]}, headers=h)
    assert second.status_code == 200 and second.json()["reason"] == "queued"
    assert len(js.default_store().list_jobs()) == 1


def test_start_ingest_with_an_unknown_upload_is_a_404(env):
    for bad in ("UP-20261012-010101-abcdef", "../../etc/passwd", "x"):
        r = env.client().post("/api/jobs/ingest", json={"upload_id": bad}, headers=env.headers)
        assert r.status_code == 404 and r.json()["detail"]["code"] == "no_such_upload"


# -- the inbox ------------------------------------------------------------------------

def test_inbox_lists_pdfs_with_their_standing_and_imports_them(env):
    inbox = env.processed / ".inbox"
    inbox.mkdir()
    (inbox / "new-one.pdf").write_bytes(tiny_pdf(1, "n"))
    (inbox / "readme.txt").write_text("not a pdf name")
    (inbox / ".hidden.pdf").write_bytes(tiny_pdf())
    dup = tiny_pdf(1, "dup")
    (inbox / "have-it.pdf").write_bytes(dup)
    import hashlib
    env.library("have-it", hashlib.sha256(dup).hexdigest())
    (inbox / "changed.pdf").write_bytes(tiny_pdf(1, "changed"))
    env.library("changed", "an-older-hash")
    (inbox / "broken.pdf").write_bytes(b"%PDF-1.4\nnot really")

    listing = env.client().get("/api/inbox", headers=env.headers).json()
    assert listing["exists"] and {f["name"]: f["status"] for f in listing["files"]} == {
        "new-one.pdf": "new", "have-it.pdf": "same_content", "changed.pdf": "same_name_different_content", "broken.pdf": "new"}

    r = env.client().post("/api/jobs/inbox", json={}, headers=env.headers)
    assert r.status_code == 202
    by_file = {x["file"]: x for x in r.json()["results"]}
    assert by_file["new-one.pdf"]["result"] == "queued"
    assert by_file["have-it.pdf"]["result"] == "skipped" and by_file["have-it.pdf"]["reason"] == "same_content"
    assert by_file["changed.pdf"]["result"] == "needs_decision"
    assert by_file["broken.pdf"]["result"] == "refused" and by_file["broken.pdf"]["code"] == "unreadable"
    assert r.json()["queued"] == 1
    # the inbox file itself is what is ingested: never copied, never moved
    assert js.default_store().list_jobs()[0]["argv"][3] == str(inbox / "new-one.pdf")


def test_inbox_import_never_builds_a_path_from_the_request(env):
    (env.processed / ".inbox").mkdir()
    r = env.client().post("/api/jobs/inbox", json={"files": ["../../etc/passwd", "/etc/hosts", "sub/doc.pdf"]}, headers=env.headers)
    assert r.status_code == 202 and r.json()["queued"] == 0
    assert all(x["result"] == "refused" and x["code"] == "not_in_inbox" for x in r.json()["results"])


def test_a_missing_inbox_folder_is_a_clear_404_and_an_empty_listing(env):
    assert env.client().get("/api/inbox", headers=env.headers).json() == {"folder": str(env.processed / ".inbox"), "exists": False, "files": [], "truncated": False}
    r = env.client().post("/api/jobs/inbox", json={}, headers=env.headers)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "no_inbox"


# -- cancel and retry -----------------------------------------------------------------

def test_cancel_and_retry_a_job_over_the_api(env):
    up = upload(env, "afi99-3.pdf", tiny_pdf()).json()
    job = env.client().post("/api/jobs/ingest", json={"upload_id": up["upload_id"]}, headers=env.headers).json()["job"]
    c, h = env.client(), env.headers
    assert c.post(f"/api/jobs/{job['id']}/retry", headers=h).status_code == 409  # still queued
    cancelled = c.post(f"/api/jobs/{job['id']}/cancel", headers=h)
    assert cancelled.status_code == 200 and cancelled.json()["state"] == "cancelled"
    again = c.post(f"/api/jobs/{job['id']}/retry", headers=h)
    assert again.status_code == 202 and again.json()["state"] == "queued" and again.json()["retry_of"] == job["id"]
    assert c.post("/api/jobs/JOB-nope/cancel", headers=h).status_code == 404
    assert c.post("/api/jobs/.lock/cancel", headers=h).status_code == 404
