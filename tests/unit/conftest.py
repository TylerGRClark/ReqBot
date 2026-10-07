from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True, scope="session")
def block_live_services():
    """Guard: any test that forgets to mock QdrantClient fails fast instead of hitting live infra.

    Skips silently if qdrant_client is not installed so config/docs/normalize tests can
    still run in environments that only have test dependencies installed.
    """
    try:
        with patch("qdrant_client.QdrantClient", side_effect=RuntimeError("Live Qdrant called in tests")):
            yield
    except ModuleNotFoundError:
        yield


@pytest.fixture(scope="session")
def tree_at_commit(tmp_path_factory):
    """`tree_at_commit(commit, relative_paths)` -> a directory holding those files exactly as `commit` had them (via `git show`), for comparing a frozen manifest
    with the repository as of the run it describes rather than with the live tree. WP-45.7's frozen-code manifests pin every file a one-shot run imported,
    including shared production modules; comparing them with the live tree made any later, legitimate edit to such a module fail the manifest tests. Needs
    the commit in the clone (the CI test job fetches full history for this)."""
    import subprocess

    def make(commit, relative_paths):
        root = tmp_path_factory.mktemp(f"tree_{commit}")
        for rel in relative_paths:
            blob = subprocess.run(["git", "show", f"{commit}:{rel}"], capture_output=True)
            if blob.returncode:
                raise AssertionError(f"{rel} is not in commit {commit} ({blob.stderr.decode().strip()}); is the clone shallow?")
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob.stdout)
        return root

    return make
