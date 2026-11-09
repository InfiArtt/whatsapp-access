"""New versions come from the add-on's GitHub releases."""

import hashlib
import importlib.util
from pathlib import Path

import pytest

UPDATES = Path(__file__).parent.parent / "addon" / "globalPlugins" / "whatsAppAccess" / "updates.py"
spec = importlib.util.spec_from_file_location("updates", UPDATES)
updates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updates)

DOWNLOAD = "https://github.com/InfiArtt/whatsapp-access/releases/download/v0.2.0/"


def release_data(**changes):
    data = {
        "tag_name": "v0.2.0",
        "draft": False,
        "prerelease": False,
        "body": "Volumes and updates.",
        "assets": [
            {"name": "notes.txt", "browser_download_url": DOWNLOAD + "notes.txt"},
            {
                "name": "whatsAppAccess-0.2.0.nvda-addon",
                "browser_download_url": DOWNLOAD + "whatsAppAccess-0.2.0.nvda-addon",
                "digest": "sha256:ABCDEF",
            },
        ],
    }
    data.update(changes)
    return data


def test_versions_compare_by_number():
    assert updates.isNewer("v0.10.0", "0.9.9")
    assert updates.isNewer("1.0", "0.9.9")
    assert not updates.isNewer("1.0.0", "1.0")
    assert not updates.isNewer("v0.1.0", "0.2.0")
    assert updates.versionTuple("v1.2.3-beta") == (1, 2, 3)


def test_bad_version_is_refused():
    with pytest.raises(updates.UpdateError):
        updates.versionTuple("latest")


def test_release_takes_the_addon_file_and_its_checksum():
    release = updates.parseRelease(release_data())
    assert release.version == "0.2.0"
    assert release.fileName == "whatsAppAccess-0.2.0.nvda-addon"
    assert release.sha256 == "abcdef"
    assert release.notes == "Volumes and updates."


def test_files_from_elsewhere_and_prereleases_are_refused():
    elsewhere = release_data(
        assets=[{"name": "x.nvda-addon", "browser_download_url": "https://example.com/x.nvda-addon"}]
    )
    with pytest.raises(updates.UpdateError):
        updates.parseRelease(elsewhere)
    with pytest.raises(updates.UpdateError):
        updates.parseRelease(release_data(prerelease=True))


def test_a_release_without_a_checksum_is_not_installed():
    data = release_data()
    del data["assets"][1]["digest"]
    with pytest.raises(updates.UpdateError, match="noChecksum"):
        updates.parseRelease(data)


def test_download_checks_the_checksum(tmp_path, monkeypatch):
    content = b"add-on bytes"

    class Response:
        def __init__(self):
            self.parts = [content, b""]

        def read(self, size):
            return self.parts.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(updates, "_open", lambda url, accept, timeout: Response())
    good = updates.parseRelease(release_data())
    good.sha256 = hashlib.sha256(content).hexdigest()
    path = tmp_path / "a.nvda-addon"
    assert updates.download(good, str(path)) == str(path)
    assert path.read_bytes() == content
    good.sha256 = "0" * 64
    with pytest.raises(updates.UpdateError, match="badChecksum"):
        updates.download(good, str(path))
    # A damaged download is not left behind.
    assert not path.exists()
