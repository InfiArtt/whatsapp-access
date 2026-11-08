"""F7 and F8 keep the changed volume: NVDA's configuration is saved shortly after."""

import importlib.util
import sys
import types
from pathlib import Path

CODE = Path(__file__).parent.parent / "addon" / "globalPlugins" / "whatsAppAccess"


class Conf(dict):
    def __init__(self, saveOnExit):
        super().__init__(
            {
                "general": {"saveConfigurationOnExit": saveOnExit},
                "whatsAppAccess": {"effectsVolume": 100},
            }
        )
        self.saved = 0

    def save(self):
        self.saved += 1


def load_volumes(conf, monkeypatch):
    stubs = {
        "addonHandler": {"initTranslation": lambda: None},
        "config": {"conf": conf},
        "ui": {"message": lambda text: None},
        "logHandler": {"log": types.SimpleNamespace(debugWarning=lambda text: None)},
        "wx": {
            "CallLater": lambda delay, function: (function(), types.SimpleNamespace(Stop=lambda: None))[1],
            "MOD_NONE": 0,
            "WXK_F6": 6,
            "WXK_F7": 7,
            "WXK_F8": 8,
        },
    }
    for name, attributes in stubs.items():
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    package = types.ModuleType("volumesPackage")
    package.__path__ = [str(CODE)]
    monkeypatch.setitem(sys.modules, "volumesPackage", package)
    sounds = types.ModuleType("volumesPackage.sounds")
    sounds.__dict__.update(play=lambda *a: None, TICK="", RECEIVED="", EFFECTS="", NOTIFICATION="")
    monkeypatch.setitem(sys.modules, "volumesPackage.sounds", sounds)
    configSpec = types.ModuleType("volumesPackage.configSpec")
    configSpec.CONFIG_SECTION = "whatsAppAccess"
    monkeypatch.setitem(sys.modules, "volumesPackage.configSpec", configSpec)
    spec = importlib.util.spec_from_file_location("volumesPackage.volumes", CODE / "volumes.py")
    module = importlib.util.module_from_spec(spec)
    module._ = lambda text: text
    import builtins

    monkeypatch.setattr(builtins, "_", lambda text: text, raising=False)
    spec.loader.exec_module(module)
    return module


def test_a_changed_volume_is_saved_at_once(monkeypatch):
    conf = Conf(saveOnExit=True)
    volumes = load_volumes(conf, monkeypatch)
    assert volumes.handleKey(7, 0, None)
    assert conf["whatsAppAccess"]["effectsVolume"] == 95
    assert conf.saved == 1


def test_nothing_is_saved_when_nvda_does_not_save_on_exit(monkeypatch):
    conf = Conf(saveOnExit=False)
    volumes = load_volumes(conf, monkeypatch)
    volumes.handleKey(8, 0, None)
    assert conf["whatsAppAccess"]["effectsVolume"] == 100
    assert conf.saved == 0
