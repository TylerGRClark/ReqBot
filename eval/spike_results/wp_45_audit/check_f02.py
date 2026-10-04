"""F02 repro: a failed Ollama request becomes a permanent cache hit on resume."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import json
import tempfile

from unittest import mock
import requests
from pipeline import llm_extract_requirements as L

chunk = {"chunk_id": 0, "text": "Users shall change passwords every 90 days.", "raw_text": "x"}
with tempfile.TemporaryDirectory() as tmp:
    chunks = Path(tmp) / "doc_chunks.jsonl"
    chunks.write_text(json.dumps(chunk) + "\n")
    tags = mock.Mock()
    tags.raise_for_status = lambda: None
    tags.json = lambda: {"models": [{"name": "m"}]}
    good = json.dumps(
        {
            "requirements": [
                {"source_quote": "Users shall change passwords every 90 days.", "source_ref": ""}
            ]
        }
    )
    # run 1: transport error
    with (
        mock.patch.object(L.requests, "get", return_value=tags),
        mock.patch.object(L, "call_ollama", side_effect=requests.RequestException("boom")) as c1,
    ):
        L.run(str(chunks), tmp, model="m", ollama_url="http://x")
        print("run1 generation calls:", c1.call_count)
    # run 2 (resume, same dir): transport now works
    with (
        mock.patch.object(L.requests, "get", return_value=tags),
        mock.patch.object(L, "call_ollama", return_value=good) as c2,
    ):
        L.run(str(chunks), tmp, model="m", ollama_url="http://x")
        print("run2 (resume) generation calls:", c2.call_count)
    reqs = (Path(tmp) / "doc_extracted_requirements.jsonl").read_text()
    print("requirements after resume:", repr(reqs))
    print(
        "RESULT:",
        "REPRODUCED (failed chunk skipped, requirement lost)"
        if c2.call_count == 0 and not reqs
        else "NOT reproduced",
    )
