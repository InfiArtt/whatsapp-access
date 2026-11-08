"""The add-on's sounds are made quieter by scaling 16-bit samples."""

import array
import importlib.util
import sys
import threading
import time
import types
from pathlib import Path

SOUNDS = Path(__file__).parent.parent / "addon" / "globalPlugins" / "whatsAppAccess" / "sounds.py"


def load_sounds():
    for name in ("config", "nvwave", "logHandler"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["logHandler"].log = None
    package = types.ModuleType("soundsPackage")
    package.__path__ = [str(SOUNDS.parent)]
    sys.modules["soundsPackage"] = package
    config_spec = importlib.util.spec_from_file_location(
        "soundsPackage.configSpec", SOUNDS.parent / "configSpec.py"
    )
    sys.modules["soundsPackage.configSpec"] = importlib.util.module_from_spec(config_spec)
    config_spec.loader.exec_module(sys.modules["soundsPackage.configSpec"])
    spec = importlib.util.spec_from_file_location("soundsPackage.sounds", SOUNDS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_half_volume_halves_samples():
    sounds = load_sounds()
    frames = array.array("h", [1000, -1000, 32767, -32768]).tobytes()
    result = array.array("h")
    result.frombytes(sounds.scaled(frames, 2, 0.5))
    assert list(result) == [500, -500, 16383, -16384]


def test_full_volume_and_other_widths_are_unchanged():
    sounds = load_sounds()
    frames = bytes(range(8))
    assert sounds.scaled(frames, 2, 1.0) == frames
    assert sounds.scaled(frames, 1, 0.5) == frames


class FakePlayer:
    """Stands in for NVDA's WavePlayer: a sound "plays" for 0.3 seconds unless stopped."""

    played = 0

    def __init__(self, **kwargs):
        self.stopped = threading.Event()

    def feed(self, frames):
        FakePlayer.played += 1

    def idle(self):
        self.stopped.wait(0.3)

    def stop(self):
        self.stopped.set()


def test_the_ring_repeats_until_stopped():
    sounds = load_sounds()
    sounds.config.conf = {
        "whatsAppAccess": {"sounds": True, "notificationVolume": 100},
        "audio": {"outputDevice": ""},
    }
    sounds.nvwave.WavePlayer = FakePlayer
    sounds.nvwave.AudioPurpose = types.SimpleNamespace(SOUNDS=None)
    sounds.log = types.SimpleNamespace(debugWarning=lambda *a, **k: None)
    sounds.RING_GAP_SECONDS = 0.05
    FakePlayer.played = 0
    sounds.startRing("ring")
    deadline = time.monotonic() + 5
    while FakePlayer.played < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert FakePlayer.played >= 2
    sounds.stopRing()
    time.sleep(0.2)
    stoppedAt = FakePlayer.played
    time.sleep(0.6)
    assert FakePlayer.played == stoppedAt


def test_no_ring_when_none_is_chosen():
    sounds = load_sounds()
    sounds.config.conf = {
        "whatsAppAccess": {"sounds": True, "notificationVolume": 100},
        "audio": {"outputDevice": ""},
    }
    sounds.nvwave.WavePlayer = FakePlayer
    FakePlayer.played = 0
    sounds.startRing("none")
    time.sleep(0.3)
    assert FakePlayer.played == 0


def test_windows_ringtones_are_found(tmp_path, monkeypatch):
    sounds = load_sounds()
    media = tmp_path / "Media"
    media.mkdir()
    for name in ("Ring01.wav", "Ring10.wav", "Windows Ringin.wav", "Alarm01.wav", "Ringout.wav", "notes.txt"):
        (media / name).write_bytes(b"")
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    assert [name for path, name in sounds.windowsRingtones()] == ["Ring 01", "Ring 10", "Windows Ringin"]


def test_a_preview_can_be_stopped():
    sounds = load_sounds()
    sounds.config.conf = {
        "whatsAppAccess": {"sounds": True, "notificationVolume": 100},
        "audio": {"outputDevice": ""},
    }
    sounds.nvwave.WavePlayer = FakePlayer
    sounds.nvwave.AudioPurpose = types.SimpleNamespace(SOUNDS=None)
    sounds.preview("ring")
    deadline = time.monotonic() + 5
    while not sounds.previewPlaying() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert sounds.previewPlaying()
    sounds.stopRing()
    time.sleep(0.1)
    assert not sounds.previewPlaying()
