"""installTasks run as NVDA runs them: an update keeps the WhatsApp login, removing the add-on does not."""

import importlib.util
import shutil
import sys
import types
from pathlib import Path

ADDON = Path(__file__).parent.parent / "addon"


def install_copy(addons: Path, name: str) -> types.ModuleType:
    """A copy of the add-on's install tasks and the modules they load, at addons/name."""
    target = addons / name
    package = target / "globalPlugins" / "whatsAppAccess"
    package.mkdir(parents=True)
    shutil.copy(ADDON / "installTasks.py", target / "installTasks.py")
    for module in ("dataFolder.py", "configSpec.py"):
        shutil.copy(ADDON / "globalPlugins" / "whatsAppAccess" / module, package / module)
    spec = importlib.util.spec_from_file_location(
        f"installTasks_{name.replace('.', '_')}", target / "installTasks.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def nvda(monkeypatch, config: Path, plugins=(), installed=False):
    calls = []
    stubs = {
        "globalVars": {"appArgs": types.SimpleNamespace(configPath=str(config))},
        "globalPluginHandler": {"runningPlugins": set(plugins)},
        "logHandler": {"log": types.SimpleNamespace(exception=print, debugWarning=print)},
        "config": {"isInstalledCopy": lambda: installed},
        "config.configSections": {
            "registerSection": lambda *a: calls.append("register"),
            "unregisterSection": lambda *a: calls.append("unregister"),
        },
    }
    for name, attributes in stubs.items():
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    return calls


def linked(config: Path) -> Path:
    login = config / "whatsAppAccess" / "browser" / "login"
    login.parent.mkdir(parents=True)
    login.write_text("linked")
    return login


def test_an_update_keeps_the_login(tmp_path, monkeypatch):
    config, addons = tmp_path / "config", tmp_path / "addons"
    login = linked(config)
    old = install_copy(addons, "whatsAppAccess")
    new = install_copy(addons, "whatsAppAccess.pendingInstall")
    calls = nvda(monkeypatch, config)
    new.onInstall()
    # NVDA restarts: the old version is removed first, with its uninstall task.
    old.onUninstall()
    assert "unregister" not in calls
    # Then the new version starts and puts the data back.
    sys.path.insert(0, str(ADDON / "globalPlugins"))
    from whatsAppAccess import dataFolder

    assert dataFolder.restoreAfterUpdate(str(config))
    assert login.read_text() == "linked"


def test_an_old_version_that_removes_the_data_finds_nothing(tmp_path, monkeypatch):
    config = tmp_path / "config"
    linked(config)
    new = install_copy(tmp_path / "addons", "whatsAppAccess.pendingInstall")
    nvda(monkeypatch, config)
    new.onInstall()
    # What 0.3.0's uninstall task did, whatever else was going on.
    shutil.rmtree(config / "whatsAppAccess", ignore_errors=True)
    assert (config / "whatsAppAccess.updating" / "browser" / "login").exists()


def test_the_running_add_on_is_stopped_before_its_data_moves(tmp_path, monkeypatch):
    config = tmp_path / "config"
    linked(config)
    stopped = []
    plugin_class = type("GlobalPlugin", (), {"__module__": "globalPlugins.whatsAppAccess"})
    plugin = plugin_class()
    plugin._stopping = False
    plugin.session = types.SimpleNamespace(close=lambda: stopped.append("session"))
    plugin.hidden = types.SimpleNamespace(stop=lambda: stopped.append("browser"))
    new = install_copy(tmp_path / "addons", "whatsAppAccess.pendingInstall")
    nvda(monkeypatch, config, plugins=[plugin])
    new.onInstall()
    assert stopped == ["session", "browser"]
    assert plugin._stopping


def test_removing_the_add_on_removes_the_login(tmp_path, monkeypatch):
    config = tmp_path / "config"
    login = linked(config)
    installed = install_copy(tmp_path / "addons", "whatsAppAccess")
    calls = nvda(monkeypatch, config)
    installed.onUninstall()
    assert "unregister" in calls
    assert not login.exists()


def test_a_cancelled_update_gives_the_data_back(tmp_path, monkeypatch):
    config, addons = tmp_path / "config", tmp_path / "addons"
    login = linked(config)
    install_copy(addons, "whatsAppAccess")
    new = install_copy(addons, "whatsAppAccess.pendingInstall")
    nvda(monkeypatch, config)
    new.onInstall()
    # The user removes the update before restarting NVDA: NVDA runs the new version's uninstall task.
    new.onUninstall()
    assert login.read_text() == "linked"


def test_removing_the_add_on_from_an_installed_nvda_removes_the_login_in_localappdata(tmp_path, monkeypatch):
    config, localAppData = tmp_path / "config", tmp_path / "local"
    login = localAppData / "NVDA WhatsApp Access" / "browser" / "login"
    login.parent.mkdir(parents=True)
    login.write_text("linked")
    monkeypatch.setenv("LOCALAPPDATA", str(localAppData))
    installed = install_copy(tmp_path / "addons", "whatsAppAccess")
    nvda(monkeypatch, config, installed=True)
    installed.onUninstall()
    assert not login.exists()
