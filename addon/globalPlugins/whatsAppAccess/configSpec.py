# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""The add-on's settings in NVDA's configuration."""

CONFIG_SECTION = "whatsAppAccess"

ANNOUNCE_CHOICES = ("all", "personal", "openChat", "off")

CONFIG_SPEC = {
	# How the add-on reaches WhatsApp: its own hidden browser, or the WhatsApp Web tab in the user's browser.
	"connection": 'option("hidden", "ownBrowser", default="hidden")',
	# Start the hidden browser when NVDA starts, so new messages are read out without opening the window.
	"startWithNVDA": "boolean(default=True)",
	# Which installed Chromium browser runs hidden; "auto" prefers Brave, then Chrome, and Edge last.
	"hiddenBrowser": 'option("auto", "brave", "chrome", "chromium", "vivaldi", "opera", "edge", default="auto")',
	# Whether the first-time setup was done.
	"setupDone": "boolean(default=False)",
	# Which incoming messages NVDA reads out. Muted chats are never read out, except the open one.
	"announce": 'option("all", "personal", "openChat", "off", default="all")',
	# Record voice notes in stereo when the microphone has two channels.
	"stereo": "boolean(default=True)",
	# Turn off the browser's echo cancellation, noise suppression and automatic gain for voice notes.
	"rawMicrophone": "boolean(default=True)",
	# Opus bit rate of voice notes. WhatsApp's own recorder uses much less.
	"voiceKbps": "integer(min=16, max=256, default=128)",
	# Hold back WhatsApp's own notification banner and sound for new messages; the add-on reads them out.
	"replaceNotifications": "boolean(default=True)",
	# Add which keys to press to messages, such as "Ctrl+Shift+R sends it" after recording.
	"hints": "boolean(default=True)",
	# When voice messages play one after another, the messages list moves to the next; NVDA reads it too.
	"sayNextVoiceMessage": "boolean(default=True)",
	# Ctrl+T translates a message into this language (Google Translate's code), or NVDA's when empty,
	# and what the user writes into the other one.
	"translateMessagesTo": 'string(default="")',
	"translateMyTextTo": 'string(default="en")',
	# How fast voice messages play: 1, 1.5 or 2 times, as in WhatsApp.
	"playbackSpeed": 'option("1", "1.5", "2", default="1")',
	# The sound of a new message in a personal chat and in a group, unless a chat has its own.
	"personalSound": 'string(default="received")',
	# Different from personal chats at first, so a group's message can be told apart by its sound.
	"groupSound": 'string(default="notifyKalimba")',
	# The ring for incoming calls: "ring" (the add-on's), "none", or a WAV file's full path.
	"ringSound": 'string(default="ring")',
	# Read out what a new message says, or only who it is from.
	"readContent": "boolean(default=True)",
	# Name people outside the contacts with their phone number too, such as "+62812… ~Budi", not just "~Budi".
	"showNumbers": "boolean(default=False)",
	# Each chat's own notification rule, as JSON; see notifications.py.
	"chatRules": 'string(default="{}")',
	# Play the add-on's sounds: sent, new message, recording and so on.
	"sounds": "boolean(default=True)",
	# Volumes in percent: new-message sounds and the ring; the other sounds; voice notes, audio and the
	# sound of videos in chats; voice and video statuses.
	"notificationVolume": "integer(min=0, max=100, default=100)",
	"effectsVolume": "integer(min=0, max=100, default=100)",
	"voiceVolume": "integer(min=0, max=100, default=100)",
	"statusVolume": "integer(min=0, max=100, default=100)",
	# Look for new versions on the add-on's GitHub page once a day, and when the last look was.
	"checkUpdates": "boolean(default=True)",
	"lastUpdateCheck": "integer(default=0)",
	# A required update that is not installed yet: WhatsApp cannot be used until it is. See updates.py.
	"requiredVersion": 'string(default="")',
	# How loud the other person is in calls.
	"callVolume": "integer(min=0, max=100, default=100)",
	# Sound processing on the microphone during calls: WhatsApp's own, echo cancellation only, or none
	# (clearest, for headphones; with speakers the other person may hear an echo).
	"callProcessing": 'option("whatsapp", "echoOnly", "none", default="whatsapp")',
	# The microphone's name, for voice notes and calls, or empty for the browser's default.
	"microphone": 'string(default="")',
	# The speaker's name, for calls, voice notes and statuses, or empty for Windows' default.
	"speaker": 'string(default="")',
}
