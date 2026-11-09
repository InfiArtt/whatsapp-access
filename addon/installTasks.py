# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Registers the add-on's configuration section, using the API added in NVDA 2026.3, and keeps the
WhatsApp login through updates; see dataFolder."""

import importlib.util
import os
import subprocess

_PACKAGE = os.path.join(os.path.dirname(__file__), "globalPlugins", "whatsAppAccess")


def _load(name: str):
	# Loaded by path so installing does not import the plugin package.
	spec = importlib.util.spec_from_file_location(
		f"whatsAppAccessInstall_{name}", os.path.join(_PACKAGE, f"{name}.py")
	)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def _configPath() -> str:
	import globalVars

	return globalVars.appArgs.configPath


def _stopRunning() -> None:
	"""Stop the WhatsApp Access that is running now, so its hidden browser lets go of the login."""
	import globalPluginHandler

	for plugin in list(globalPluginHandler.runningPlugins):
		if not type(plugin).__module__.startswith("globalPlugins.whatsAppAccess"):
			continue
		# Otherwise it would start the browser again when it sees it gone.
		plugin._stopping = True
		session, hidden = getattr(plugin, "session", None), getattr(plugin, "hidden", None)
		for stop in (getattr(session, "close", None), getattr(hidden, "stop", None)):
			if stop is None:
				continue
			try:
				stop()
			except Exception:  # noqa: BLE001 - forceClose follows if it is still running
				from logHandler import log

				log.debugWarning("WhatsApp Access: stopping it for the update", exc_info=True)


def _forceClose() -> None:
	"""Close any browser still using the add-on's profile, found by the profile in its command line."""
	profile = os.path.join(_configPath(), "whatsAppAccess", "browser").replace("'", "''")
	script = (
		"Get-CimInstance Win32_Process | Where-Object { $_.Name -ne 'powershell.exe' -and "
		f"$_.CommandLine -like '*--user-data-dir=*{profile}*' }} | "
		"ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
	)
	powershell = os.path.join(
		os.environ.get("SystemRoot", "C:\\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
	)
	subprocess.run(
		[powershell, "-NoProfile", "-NonInteractive", "-Command", script],
		stdin=subprocess.DEVNULL,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
		creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		timeout=30,
		check=False,
	)


def onInstall() -> None:
	from config.configSections import registerSection

	configSpec = _load("configSpec")
	registerSection(configSpec.CONFIG_SECTION, configSpec.CONFIG_SPEC)
	# The version being replaced may remove the data when NVDA restarts; move it aside until then.
	try:
		_load("dataFolder").keepThroughUpdate(_configPath(), _stopRunning, _forceClose)
	except Exception:  # noqa: BLE001 - installing must go on; at worst the phone is linked again
		from logHandler import log

		log.exception("WhatsApp Access: could not keep the WhatsApp data through the update")


def onUninstall() -> None:
	# This runs early in NVDA's startup; a failure here must not block removing the add-on.
	try:
		dataFolder = _load("dataFolder")
		addonPath = os.path.dirname(__file__)
		if dataFolder.updatePending(addonPath):
			# Replaced by a new version: the settings and the WhatsApp login stay.
			return
		if addonPath.endswith(dataFolder.PENDING_INSTALL_SUFFIX):
			# An update cancelled before NVDA restarted: the installed version keeps its data.
			dataFolder.restoreAfterUpdate(_configPath())
			return
	except Exception:  # noqa: BLE001 - see comment above
		from logHandler import log

		log.exception("WhatsApp Access: checking for an update")
		return
	try:
		from config.configSections import unregisterSection

		unregisterSection(_load("configSpec").CONFIG_SECTION)
	except Exception:  # noqa: BLE001 - see comment above
		from logHandler import log

		log.exception("Could not unregister the whatsAppAccess configuration section")
	# Removed for good: the hidden browser's profile holds the WhatsApp login and chats; it goes too,
	# from NVDA's configuration folder and, for an installed NVDA, from LocalAppData.
	try:
		dataFolder.removeAll(_configPath(), (dataFolder.addonDataPath(),))
	except Exception:  # noqa: BLE001 - see comment above
		from logHandler import log

		log.exception("Could not remove WhatsApp Access's data")
