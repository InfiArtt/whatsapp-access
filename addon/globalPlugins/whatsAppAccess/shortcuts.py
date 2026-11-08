# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""The keyboard shortcuts, as WhatsApp lists its own with Ctrl+/, named in WhatsApp's words.

It imports nothing from NVDA apart from _(), which addonHandler.initTranslation() installs.
"""


def sections() -> list[tuple[str, list[tuple[str, str]]]]:
	"""Each section's title and its shortcuts, as (keys, what they do)."""
	return [
		(
			# Translators: A section of the keyboard shortcuts list: keys that work in any program.
			_("From any program"),
			[
				# Translators: In the keyboard shortcuts list.
				("NVDA+Shift+W", _("Open WhatsApp")),
				# Translators: In the keyboard shortcuts list.
				("NVDA+Alt+A", _("Answer the call, or return to the call")),
				# Translators: In the keyboard shortcuts list.
				("NVDA+Alt+H", _("Decline or end the call")),
				# Translators: In the keyboard shortcuts list.
				("NVDA+Alt+M", _("Mute or unmute the microphone")),
			],
		),
		(
			# Translators: A section of the keyboard shortcuts list: keys anywhere in the WhatsApp window.
			_("General"),
			[
				(
					# Translators: In the keyboard shortcuts list: the keys that open the window's sections.
					_("Ctrl+1 to Ctrl+8"),
					# Translators: In the keyboard shortcuts list: the sections Ctrl+1 to Ctrl+8 open, in order.
					_("Chats, Status, Calls, Archived, Starred, Channels, Communities, Settings"),
				),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+N", _("New chat")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Shift+N", _("New group")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Shift+F", _("Search messages in all chats")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Tab", _("Next section; in a chat, next chat")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Shift+Tab", _("Previous section; in a chat, previous chat")),
				# Translators: In the keyboard shortcuts list.
				("F6", _("Choose a volume: sound effects, notifications, voice messages, status, call")),
				# Translators: In the keyboard shortcuts list.
				("F7, F8", _("Volume down, volume up")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+/", _("Keyboard shortcuts")),
				# Translators: In the keyboard shortcuts list.
				("Escape", _("Close chat, or close the window; WhatsApp keeps running")),
			],
		),
		(
			# Translators: A section of the keyboard shortcuts list.
			_("Chat list"),
			[
				# Translators: In the keyboard shortcuts list.
				("Alt+S", _("Search chats")),
				# Translators: In the keyboard shortcuts list: Alt+1 to Alt+4 and the chat filters they choose.
				(_("Alt+1 to Alt+4"), _("All, Unread, Groups, Favorites")),
				# Translators: In the keyboard shortcuts list.
				("Alt+U", _("Next unread chat")),
				# Translators: In the keyboard shortcuts list.
				("Enter", _("Open chat")),
				# Translators: In the keyboard shortcuts list.
				(_("Applications"), _("Archive, mute, pin, mark as unread, notifications")),
				# Translators: In the keyboard shortcuts list.
				("Delete", _("Delete chat")),
			],
		),
		(
			# Translators: A section of the keyboard shortcuts list: keys in an open chat.
			_("Chat"),
			[
				# Translators: In the keyboard shortcuts list.
				("Alt+M", _("Messages")),
				# Translators: In the keyboard shortcuts list.
				("Alt+E", _("Type a message")),
				# Translators: In the keyboard shortcuts list.
				("Alt+T", _("Online or last seen")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+F", _("Search in chat")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Shift+M", _("Unread mentions")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Shift+C", _("Voice call")),
				# Translators: In the keyboard shortcuts list.
				("Alt+A", _("Attach")),
			],
		),
		(
			# Translators: A section of the keyboard shortcuts list: keys in the message box.
			_("Typing a message"),
			[
				# Translators: In the keyboard shortcuts list.
				("Enter", _("Send")),
				# Translators: In the keyboard shortcuts list.
				("Shift+Enter", _("New line")),
				# Translators: In the keyboard shortcuts list: Up Arrow in the empty message box.
				(_("Up Arrow, in the empty box"), _("Edit last message")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+B", _("Bold")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+I", _("Italic")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Shift+X", _("Strikethrough")),
				# Translators: In the keyboard shortcuts list: typing @ in a group.
				("@", _("Mention someone: Up and Down Arrow choose, Enter adds")),
				# Translators: In the keyboard shortcuts list: typing : and part of an emoji's name.
				(_(":name"), _("Emoji: Left and Right Arrow choose, Enter adds")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+V", _("Paste; files copied in File Explorer are attached")),
				# Translators: In the keyboard shortcuts list.
				("Escape", _("Cancel reply or edit")),
			],
		),
		(
			# Translators: A section of the keyboard shortcuts list: keys on a message in the messages list.
			_("Messages"),
			[
				# Translators: In the keyboard shortcuts list.
				("Enter", _("Play or stop a voice message; open a photo, video or document")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+S", _("Voice message speed: 1x, 1.5x, 2x")),
				# Translators: In the keyboard shortcuts list.
				("Alt+R", _("Reply")),
				# Translators: In the keyboard shortcuts list.
				("Alt+Y", _("React")),
				# Translators: In the keyboard shortcuts list.
				("Alt+F", _("Forward")),
				# Translators: In the keyboard shortcuts list.
				("Alt+C", _("Read the message's text")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+C", _("Copy")),
				# Translators: In the keyboard shortcuts list.
				("Alt+D", _("Download")),
				# Translators: In the keyboard shortcuts list.
				("Alt+L", _("Open link")),
				# Translators: In the keyboard shortcuts list.
				("Alt+I", _("Message info")),
				# Translators: In the keyboard shortcuts list.
				("Alt+P", _("Describe photo")),
				# Translators: In the keyboard shortcuts list.
				("Delete", _("Delete message")),
				# Translators: In the keyboard shortcuts list.
				(_("Applications"), _("Star, edit, pin, reply privately, and more")),
				# Translators: In the keyboard shortcuts list: Up Arrow on the first message of a chat.
				(_("Up Arrow, on the first message"), _("Load older messages")),
			],
		),
		(
			# Translators: A section of the keyboard shortcuts list: selecting several messages or chats.
			_("Select"),
			[
				# Translators: In the keyboard shortcuts list.
				(_("Shift+Up Arrow, Shift+Down Arrow"), _("Select while moving")),
				# Translators: In the keyboard shortcuts list.
				(_("Space"), _("Select or unselect")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+A", _("Select all")),
				# Translators: In the keyboard shortcuts list.
				("Escape", _("Clear selection")),
			],
		),
		(
			# Translators: A section of the keyboard shortcuts list: recording voice messages.
			_("Voice messages"),
			[
				# Translators: In the keyboard shortcuts list.
				("Ctrl+R", _("Record; while recording, stop and listen")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Shift+R", _("Send voice message")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Shift+D", _("Pause or resume recording")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+D", _("Delete voice message")),
			],
		),
		(
			# Translators: A section of the keyboard shortcuts list.
			_("Calls"),
			[
				# Translators: In the keyboard shortcuts list.
				("Ctrl+M", _("Mute or unmute")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+H", _("Raise or lower hand")),
				# Translators: In the keyboard shortcuts list.
				("Ctrl+Shift+G", _("Who is speaking")),
				# Translators: In the keyboard shortcuts list.
				("Escape", _("Hide the call window; the call goes on")),
			],
		),
		(
			# Translators: A section of the keyboard shortcuts list: viewing someone's status.
			_("Status"),
			[
				# Translators: In the keyboard shortcuts list.
				(_("Left and Right Arrow"), _("Previous and next status")),
				# Translators: In the keyboard shortcuts list.
				(_("Ctrl+Left and Ctrl+Right Arrow"), _("Previous and next person")),
				# Translators: In the keyboard shortcuts list.
				("Enter", _("Play or stop; describe a photo")),
				# Translators: In the keyboard shortcuts list.
				("Alt+Y", _("Like")),
				# Translators: In the keyboard shortcuts list.
				("Alt+R", _("Reply")),
				# Translators: In the keyboard shortcuts list.
				("Alt+D", _("Download")),
			],
		),
	]


def shortcutsText() -> str:
	"""The list as text to read line by line: each section's title, then one shortcut per line."""
	blocks = []
	for title, items in sections():
		blocks.append("\n".join([title, *(f"{keys}: {action}" for keys, action in items)]))
	return "\n\n".join(blocks)
