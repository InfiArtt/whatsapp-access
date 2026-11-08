# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Volumes changed from the keyboard: F6 chooses which one, F7 and F8 lower and raise it at once."""

import threading
from typing import TYPE_CHECKING

import addonHandler
import config
import ui
from logHandler import log

from . import sounds
from .configSpec import CONFIG_SECTION

if TYPE_CHECKING:
	from .whatsApp import WhatsAppSession

addonHandler.initTranslation()

KINDS = ("effectsVolume", "notificationVolume", "voiceVolume", "statusVolume", "callVolume")
STEP = 5

# The volume F7 and F8 change, kept while NVDA runs.
_kind = KINDS[0]


def kindName(kind: str) -> str:
	return {
		# Translators: A volume chosen with F6: the add-on's sounds such as sent and recording.
		"effectsVolume": _("Sound effects"),
		# Translators: A volume chosen with F6: new message sounds and the ring.
		"notificationVolume": _("Notifications"),
		# Translators: A volume chosen with F6: voice notes and videos in chats.
		"voiceVolume": _("Voice notes"),
		# Translators: A volume chosen with F6: voice and video statuses.
		"statusVolume": _("Statuses"),
		# Translators: A volume chosen with F6: the other person in a call.
		"callVolume": _("In call"),
	}[kind]


def nextKind() -> None:
	"""F6: the next volume, said with its value."""
	global _kind
	_kind = KINDS[(KINDS.index(_kind) + 1) % len(KINDS)]
	value = config.conf[CONFIG_SECTION][_kind]
	# Translators: Said after F6 chooses a volume, such as "Statuses volume, 80 percent".
	ui.message(_("{name} volume, {value} percent").format(name=kindName(_kind), value=value))


def change(step: int, session: "WhatsAppSession | None") -> None:
	"""F7 and F8: lower or raise the chosen volume by STEP percent; it applies at once."""
	settings = config.conf[CONFIG_SECTION]
	value = max(0, min(100, int(settings[_kind]) + step))
	settings[_kind] = value
	# Translators: Said after F7 or F8 changes a volume, such as "75 percent".
	ui.message(_("{value} percent").format(value=value))
	if _kind == "effectsVolume":
		sounds.play(sounds.TICK, sounds.EFFECTS)
	elif _kind == "notificationVolume":
		sounds.play(sounds.RECEIVED, sounds.NOTIFICATION)
	elif session is not None and session.connected:
		kind = _kind

		def apply() -> None:
			try:
				if kind == "callVolume":
					session.setCallVolume(value)
				else:
					session.setPlaybackVolume(value)
			except Exception as e:  # noqa: BLE001 - only the live change is lost; the setting is saved
				log.debugWarning(f"WhatsApp Access: volume: {e}")

		threading.Thread(target=apply, name="whatsAppAccess.volume", daemon=True).start()
	elif _kind == "callVolume" and session is not None:
		session.callVolume = value


def handleKey(keyCode: int, modifiers: int, session: "WhatsAppSession | None") -> bool:
	"""F6, F7 and F8 without modifiers. Returns whether the key was one of them."""
	import wx

	if modifiers != wx.MOD_NONE:
		return False
	if keyCode == wx.WXK_F6:
		nextKind()
	elif keyCode == wx.WXK_F7:
		change(-STEP, session)
	elif keyCode == wx.WXK_F8:
		change(STEP, session)
	else:
		return False
	return True
