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
		# Until NVDA restarts, the login waits aside; starting WhatsApp again would make a new, empty one.
		plugin._updateInstalled = True
		session, hidden = getattr(plugin, "session", None), getattr(plugin, "hidden", None)
		for stop in (getattr(session, "close", None), getattr(hidden, "stop", None)):
			if stop is None:
				continue
			try:
				stop()
			except Exception:  # noqa: BLE001 - forceClose follows if it is still running
				from logHandler import log

				log.debugWarning("WhatsApp Access: stopping it for the update", exc_info=True)


# Only these programs can be the hidden browser; anything else using the profile path is left alone.
_BROWSERS = ("brave.exe", "chrome.exe", "msedge.exe", "chromium.exe", "vivaldi.exe", "opera.exe")


def _forceClose() -> None:
	"""Close any browser still using the add-on's profile, found by the profile in its command line.

	The profile goes to PowerShell in an environment variable and is matched as plain text, so quotes,
	"$" or the square brackets of a folder such as "Tools [portable]" are never read as code or wildcards.
	"""
	profile = os.path.join(_configPath(), "whatsAppAccess", "browser")
	script = (
		"$names = $env:WA_BROWSERS -split ','; "
		"Get-CimInstance Win32_Process | Where-Object { $names -contains $_.Name.ToLower() -and "
		"$_.CommandLine -and $_.CommandLine.Contains($env:WA_PROFILE) } | "
		"ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
	)
	powershell = os.path.join(
		os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
	)
	environment = dict(os.environ, WA_PROFILE=profile, WA_BROWSERS=",".join(_BROWSERS))
	subprocess.run(
		[powershell, "-NoProfile", "-NonInteractive", "-Command", script],
		stdin=subprocess.DEVNULL,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
		creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		env=environment,
		# Short: NVDA is waiting, silent, while an update installs.
		timeout=10,
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
		dataFolder.removeAll(_configPath(), (dataFolder.addonDataPath(), dataFolder.tempMediaPath()))
	except Exception:  # noqa: BLE001 - see comment above
		from logHandler import log

		log.exception("Could not remove WhatsApp Access's data")
