# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Registers the add-on's configuration section, using the API added in NVDA 2026.3."""

import importlib.util
import os


def _loadConfigSpec():
	# Loaded by path so installing does not import the plugin package.
	path = os.path.join(os.path.dirname(__file__), "globalPlugins", "whatsAppAccess", "configSpec.py")
	spec = importlib.util.spec_from_file_location("whatsAppAccessConfigSpec", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def onInstall() -> None:
	from config.configSections import registerSection

	configSpec = _loadConfigSpec()
	registerSection(configSpec.CONFIG_SECTION, configSpec.CONFIG_SPEC)


def onUninstall() -> None:
	# This runs early in NVDA's startup; a failure here must not block removing the add-on.
	try:
		from config.configSections import unregisterSection

		unregisterSection(_loadConfigSpec().CONFIG_SECTION)
	except Exception:  # noqa: BLE001 - see comment above
		from logHandler import log

		log.exception("Could not unregister the whatsAppAccess configuration section")
	# The hidden browser's profile holds the WhatsApp login and chats; it goes with the add-on.
	try:
		import shutil

		import globalVars

		shutil.rmtree(os.path.join(globalVars.appArgs.configPath, "whatsAppAccess"), ignore_errors=True)
	except Exception:  # noqa: BLE001 - see comment above
		from logHandler import log

		log.exception("Could not remove WhatsApp Access's data")
