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


def test_an_interrupted_download_is_not_left_behind(tmp_path, monkeypatch):
    class Broken:
        def __init__(self):
            self.parts = [b"half of it"]

        def read(self, size):
            if self.parts:
                return self.parts.pop(0)
            raise OSError("connection reset")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(updates, "_open", lambda url, accept, timeout: Broken())
    path = tmp_path / "a.nvda-addon"
    with pytest.raises(updates.UpdateError, match="network"):
        updates.download(updates.parseRelease(release_data()), str(path))
    assert not path.exists()


def listed(version, body="", **changes):
    tag = "v" + version
    asset = f"whatsAppAccess-{version}.nvda-addon"
    url = f"https://github.com/InfiArtt/whatsapp-access/releases/download/{tag}/{asset}"
    return release_data(
        tag_name=tag,
        body=body,
        assets=[{"name": asset, "browser_download_url": url, "digest": "sha256:AB"}],
        **changes,
    )


def test_a_required_update_is_marked_in_its_notes():
    assert updates.isRequired("**Required update.** WhatsApp Web changed how chats load.")
    assert updates.isRequired("Fixed things.\n\nRequired update: WhatsApp Web changed.")
    assert not updates.isRequired("This is not a required update.")
    assert not updates.isRequired("")


def test_a_required_release_between_yours_and_the_newest_still_counts():
    releases = [
        listed("0.5.1", "Small fixes."),
        listed("0.5.0", "**Required update.** WhatsApp Web changed."),
        listed("0.4.1", "**Required update.** An older change."),
    ]
    newest = updates.newestRelease(releases, "0.4.1")
    assert (newest.version, newest.required) == ("0.5.1", True)
    # Already past the required one: the newest is an ordinary update.
    assert not updates.newestRelease(releases, "0.5.0").required


def test_drafts_and_prereleases_neither_count_nor_require():
    releases = [
        listed("0.6.0", "**Required update.**", prerelease=True),
        listed("0.5.0", "**Required update.**", draft=True),
        listed("0.4.2", "Fixes."),
    ]
    newest = updates.newestRelease(releases, "0.4.1")
    assert (newest.version, newest.required) == ("0.4.2", False)
    with pytest.raises(updates.UpdateError, match="noRelease"):
        updates.newestRelease([listed("0.6.0", prerelease=True)], "0.4.1")


def test_a_release_whose_file_is_not_uploaded_yet_does_not_hide_the_one_before():
    releases = [
        release_data(tag_name="v0.6.0", body="**Required update.**", assets=[]),
        listed("0.5.0", "Fixes."),
    ]
    newest = updates.newestRelease(releases, "0.4.1")
    # 0.5.0 is offered; 0.6.0 still counts as required, so its arrival is not missed.
    assert (newest.version, newest.required) == ("0.5.0", True)


def test_a_connection_dropped_during_the_download_is_a_network_error(tmp_path, monkeypatch):
    import http.client

    class Broken:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            raise http.client.IncompleteRead(b"partial", 100)

    monkeypatch.setattr(updates, "_open", lambda *args, **kwargs: Broken())
    path = tmp_path / "a.nvda-addon"
    with pytest.raises(updates.UpdateError, match="network"):
        updates.download(updates.parseRelease(release_data()), str(path))
    assert not path.exists()
