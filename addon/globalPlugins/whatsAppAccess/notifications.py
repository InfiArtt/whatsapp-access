# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""What happens when a message arrives: whether it is read out, which sound plays, and how much is said.

Each chat may have its own rule; otherwise personal chats and groups follow their own settings.
It imports nothing from NVDA, so it can be tested on its own.
"""

import json
from dataclasses import dataclass

# The add-on's sounds that suit a new message; "custom" rules name a WAV file instead.
NOTIFICATION_SOUNDS = ("received", "notifyBell", "notifyKalimba", "notifyFlute")
# A message in the chat the user has open: a softer sound of its own, as WhatsApp's conversation tone.
OPEN_CHAT_SOUND = "openChatMessage"
ANNOUNCE_CHOICES = ("default", "always", "never")
CONTENT_CHOICES = ("default", "full", "nameOnly")


@dataclass(frozen=True)
class Rule:
	"""One chat's notification rule. "default" everywhere means: follow the general settings."""

	announce: str = "default"
	sound: str = "default"
	"""default, none, one of NOTIFICATION_SOUNDS, or the path of a WAV file."""
	content: str = "default"

	@property
	def isDefault(self) -> bool:
		return self == Rule()


@dataclass(frozen=True)
class Decision:
	announce: bool
	sound: str | None
	"""A sound name or WAV path to play, or None for silence."""
	withContent: bool


def loadRules(text: str) -> dict[str, Rule]:
	"""Rules by chat id, from the JSON kept in NVDA's configuration. Anything unreadable is ignored."""
	try:
		data = json.loads(text or "{}")
	except ValueError:
		return {}
	rules = {}
	if isinstance(data, dict):
		for chatId, value in data.items():
			if not isinstance(value, dict):
				continue
			announce = value.get("announce", "default")
			content = value.get("content", "default")
			rules[str(chatId)] = Rule(
				announce if announce in ANNOUNCE_CHOICES else "default",
				str(value.get("sound", "default")) or "default",
				content if content in CONTENT_CHOICES else "default",
			)
	return rules


def saveRules(rules: dict[str, Rule]) -> str:
	return json.dumps(
		{
			chatId: {"announce": r.announce, "sound": r.sound, "content": r.content}
			for chatId, r in rules.items()
			if not r.isDefault
		},
		ensure_ascii=False,
	)


def decide(
	rule: Rule | None,
	chat: dict,
	inOpenChat: bool,
	announceMode: str,
	personalSound: str,
	groupSound: str,
	readContent: bool,
) -> Decision:
	"""announceMode is the general setting: all, personal, openChat or off."""
	rule = rule or Rule()
	isGroup = bool(chat.get("isGroup"))
	if rule.announce == "never":
		return Decision(False, None, False)
	if rule.announce == "always":
		announce = True
	elif announceMode == "off":
		announce = False
	elif inOpenChat:
		announce = True
	elif chat.get("muted") or announceMode == "openChat":
		announce = False
	elif announceMode == "personal":
		announce = not isGroup
	else:
		announce = True
	if not announce:
		return Decision(False, None, False)
	if rule.sound == "none":
		sound = "none"
	elif inOpenChat:
		sound = OPEN_CHAT_SOUND
	elif rule.sound == "default":
		sound = groupSound if isGroup else personalSound
	else:
		sound = rule.sound
	withContent = readContent if rule.content == "default" else rule.content == "full"
	return Decision(True, None if sound in ("none", "") else sound, withContent)
