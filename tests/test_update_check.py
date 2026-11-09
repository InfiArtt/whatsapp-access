"""Checking for and installing a new version: one at a time, each download in a folder of its own."""

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest
from whatsAppAccess import updates

PACKAGE_DIR = Path(__file__).parent.parent / "addon" / "globalPlugins" / "whatsAppAccess"
ID_OK, ID_CANCEL = 5100, 5101
RELEASE = updates.Release("2.0.0", "", "https://example.invalid/x", "whatsAppAccess-2.0.0.nvda-addon", "0")


class Nvda:
    """Just enough of NVDA and wx for updateCheck. Threads wait in pending until runThreads()."""

    def __init__(self, monkeypatch):
        self.messages = []
        self.installed = []
        self.answer = ID_CANCEL
        self.offers = 0
        self.pending = []
        nvda = self

        class Dialog:
            def __init__(self, *args, **kwargs):
                pass

        stubs = {
            "addonHandler": {
                "initTranslation": lambda: None,
                "getCodeAddon": lambda: types.SimpleNamespace(version="1.0.0"),
            },
            "config": {"conf": {"whatsAppAccess": {}}},
            "gui": {"mainFrame": types.SimpleNamespace(prePopup=lambda: None, postPopup=lambda: None)},
            "gui.addonGui": {"installAddon": self._install, "promptUserForRestart": lambda: None},
            "ui": {"message": self.messages.append},
            "wx": {
                "CallAfter": lambda function, *args: function(*args),
                "CallLater": Dialog,
                "Dialog": Dialog,
                "Window": Dialog,
                "ID_OK": ID_OK,
                "ID_CANCEL": ID_CANCEL,
            },
            "logHandler": {"log": types.SimpleNamespace(info=lambda *args: None)},
        }
        for name, attributes in stubs.items():
            module = types.ModuleType(name)
            module.__dict__.update(attributes)
            monkeypatch.setitem(sys.modules, name, module)
        sys.modules["gui"].addonGui = sys.modules["gui.addonGui"]
        spec = importlib.util.spec_from_file_location(
            "whatsAppAccess.updateCheck", PACKAGE_DIR / "updateCheck.py"
        )
        self.module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, "whatsAppAccess.updateCheck", self.module)
        spec.loader.exec_module(self.module)

        class Thread:
            def __init__(self, target, **kwargs):
                self.target = target

            def start(self):
                nvda.pending.append(self.target)

        class UpdateDialog:
            def __init__(self, parent, release):
                nvda.offers += 1

            def ShowModal(self):
                return nvda.answer

            def Destroy(self):
                pass

        monkeypatch.setattr(self.module, "threading", types.SimpleNamespace(Thread=Thread))
        monkeypatch.setattr(self.module, "UpdateDialog", UpdateDialog)

    def _install(self, parent, path):
        self.installed.append((path, Path(path).read_bytes()))
        return True

    def runThreads(self):
        for _ in range(20):
            if not self.pending:
                return
            self.pending.pop(0)()
        pytest.fail("checks kept starting one another")


def test_a_second_check_waits_until_the_offer_is_answered(monkeypatch):
    nvda = Nvda(monkeypatch)
    asked = []

    def latestRelease():
        asked.append(1)
        return RELEASE

    def offer(release, original=nvda.module._offer):
        # While the window is open, the user checks from the menu too: no second window opens.
        nvda.module.check(True)
        original(release)

    monkeypatch.setattr(nvda.module.updates, "latestRelease", latestRelease)
    monkeypatch.setattr(nvda.module, "_offer", offer)
    nvda.module.check(False)
    # The automatic check and the user's own, at the same moment.
    nvda.module.check(True)
    assert len(nvda.pending) == 1
    nvda.runThreads()
    assert len(asked) == 1
    assert nvda.offers == 1
    # Declined: the next check may ask again.
    nvda.module.check(True)
    nvda.runThreads()
    assert len(asked) == 2


def test_a_download_goes_to_a_folder_of_its_own_that_is_removed(monkeypatch):
    nvda = Nvda(monkeypatch)
    nvda.answer = ID_OK
    monkeypatch.setattr(nvda.module.updates, "latestRelease", lambda: RELEASE)
    folders = []

    def download(release, path):
        folders.append(os.path.dirname(path))
        Path(path).write_bytes(b"add-on")
        return path

    monkeypatch.setattr(nvda.module.updates, "download", download)
    nvda.module.check(True)
    nvda.runThreads()
    [(path, content)] = nvda.installed
    assert content == b"add-on"
    assert os.path.basename(path) == RELEASE.fileName
    assert os.path.dirname(path) == folders[0]
    # Not the temporary folder itself, where another download could use the same name.
    assert Path(folders[0]).name.startswith("whatsAppAccess-update-")
    # Installed: the downloaded file is gone, and a new check may start.
    assert not os.path.exists(folders[0])
    assert not nvda.module._busy


@pytest.mark.parametrize("error", [updates.UpdateError("badChecksum"), OSError("disk full")])
def test_a_failed_download_leaves_nothing_behind(monkeypatch, error):
    nvda = Nvda(monkeypatch)
    nvda.answer = ID_OK
    monkeypatch.setattr(nvda.module.updates, "latestRelease", lambda: RELEASE)
    folders = []

    def download(release, path):
        folders.append(os.path.dirname(path))
        Path(path).write_bytes(b"part")
        raise error

    monkeypatch.setattr(nvda.module.updates, "download", download)
    nvda.module.check(True)
    nvda.runThreads()
    assert nvda.installed == []
    assert not os.path.exists(folders[0])
    assert not nvda.module._busy
    assert "The new version could not be downloaded. Try again later." in nvda.messages
