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
	# How fast voice messages play: 1, 1.5 or 2 times, as in WhatsApp.
	"playbackSpeed": 'option("1", "1.5", "2", default="1")',
	# The sound of a new message in a personal chat and in a group, unless a chat has its own.
	"personalSound": 'option("received", "notifyBell", "notifyKalimba", "notifyFlute", "none", default="received")',
	"groupSound": 'option("received", "notifyBell", "notifyKalimba", "notifyFlute", "none", default="received")',
	# Read out what a new message says, or only who it is from.
	"readContent": "boolean(default=True)",
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
	# How loud the other person is in calls.
	"callVolume": "integer(min=0, max=100, default=100)",
	# Sound processing on the microphone during calls: WhatsApp's own, echo cancellation only, or none
	# (clearest, for headphones; with speakers the other person may hear an echo).
	"callProcessing": 'option("whatsapp", "echoOnly", "none", default="whatsapp")',
	# The microphone's name, for voice notes and calls, or empty for the browser's default.
	"microphone": 'string(default="")',
}
