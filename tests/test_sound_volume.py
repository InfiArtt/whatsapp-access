"""The add-on's sounds are made quieter by scaling 16-bit samples."""

import array
import importlib.util
import sys
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
