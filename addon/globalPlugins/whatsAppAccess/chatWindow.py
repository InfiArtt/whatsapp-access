# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""The add-on's WhatsApp window: a list of chats, and a conversation with a reply box and voice notes."""

import mimetypes
import os
import re
import threading
import time
import webbrowser
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import api
import config
import ui
import wx
from logHandler import log

from . import dataFolder, fileSafety, messageText, notifications, shortcuts, sounds, volumes
from . import translate as translator
from .configSpec import CONFIG_SECTION
from .moreDialogs import (
	CreateEventDialog,
	CreatePollDialog,
	ManageGroupDialog,
	PrivacyDialog,
	ProfileDialog,
	TextStatusDialog,
)
from .questions import askThreeWay, askYesNo
from .whatsApp import WhatsAppError, WhatsAppSession

MESSAGES_TO_LOAD = 50
MAX_MESSAGES_TO_REACH_UNREAD = 400
# How long after a message arrives in the open chat it is marked read; see _markSeenSoon.
MARK_SEEN_DELAY_MS = 1500
MENTION_SUGGESTIONS = 20
# The chat list's filters, as WhatsApp's tabs; Alt+1 to Alt+4 choose them.
FILTERS = ("all", "unread", "groups", "favorites")
# Telling the other person "typing…" again after this many seconds of writing, and stopping after a pause.
TYPING_REPEAT_SECONDS = 8
TYPING_PAUSE_MS = 5000
# "@" at the start or after a space, then what the user has typed of the name so far.
_MENTION_PATTERN = re.compile(r"(?:^|\s)@([^\s@]*)$")
# ":" and at least two letters of an emoji's name, at the start or after a space, as in WhatsApp; so
# times such as 10:30 and links do not offer emoji.
_EMOJI_PATTERN = re.compile(r"(?:^|\s):([a-zA-Z0-9_+\-]{2,})$")
EMOJI_SUGGESTIONS = 20
# Ctrl+B, Ctrl+I and Ctrl+Shift+X in the message box, as in WhatsApp: the mark and which formatting.
_FORMAT_KEYS = {
	(wx.MOD_CONTROL, ord("B")): ("*", "bold"),
	(wx.MOD_CONTROL, ord("I")): ("_", "italic"),
	(wx.MOD_CONTROL | wx.MOD_SHIFT, ord("X")): ("~", "strikethrough"),
}


def _formatName(kind: str) -> str:
	return {
		# Translators: Said when the user makes text bold in the message box (Ctrl+B).
		"bold": _("bold"),
		# Translators: Said when the user makes text italic in the message box (Ctrl+I).
		"italic": _("italic"),
		# Translators: Said when the user strikes text through in the message box (Ctrl+Shift+X).
		"strikethrough": _("strikethrough"),
	}[kind]


# Delivered, read and played are read out for messages sent this long ago at most.
ACK_ANNOUNCE_SECONDS = 15 * 60
# When someone opens the chat, every unread message the user sent turns read at once; they are said as one.
ACK_GROUP_MS = 700


PLAYBACK_SPEEDS = ("1", "1.5", "2")
# Messages whose file Enter opens and Alt+D saves.
FILE_TYPES = ("image", "video", "ptv", "document", "sticker", "audio", "ptt")
OPENED_TYPES = ("image", "video", "ptv", "document", "sticker")
# Played in the hidden browser, with no other program: voice notes, audio, and the sound of videos.
PLAYED_TYPES = ("ptt", "audio", "video", "ptv")
# Voice messages and audio have the position slider.
SEEKABLE_TYPES = ("ptt", "audio")
POSITION_STEP_SECONDS = 5
POSITION_PAGE_SECONDS = 30
POSITION_FOLLOW_MS = 1000
# The least width of the sections beside an open chat, and of the open chat, in pixels.
SIDE_MIN_WIDTH = 300
CONVERSATION_MIN_WIDTH = 450
# How long after the messages list moves to the next voice message its focus change may be kept quiet.
QUIET_FOCUS_SECONDS = 1.0
# The moment between one voice message of a run and the next, for the small sound between them.
VOICE_NEXT_DELAY_MS = 350
# Ctrl+T pressed again on the same message within this long shows the translation to read by line.
TRANSLATION_REPEAT_SECONDS = 1.5


def languageName(code: str) -> str:
	"""A language's name in NVDA's language, from its Google Translate code such as "id" or "zh-CN"."""
	import languageHandler

	return languageHandler.getLanguageDescription(code.replace("-", "_")) or code


def messagesLanguage() -> str:
	"""The language Ctrl+T translates messages into: the one chosen, or NVDA's own."""
	chosen = config.conf[CONFIG_SECTION]["translateMessagesTo"]
	if chosen:
		return chosen
	import languageHandler

	language = languageHandler.getLanguage()
	if language.startswith("zh"):
		return "zh-TW" if language in ("zh_TW", "zh_HK") else "zh-CN"
	return language.split("_")[0]


def withHint(message: str, hint: str) -> str:
	"""The message, followed by which keys to press when the user has hints turned on."""
	if config.conf[CONFIG_SECTION]["hints"] and hint:
		return f"{message}. {hint}"
	return message


def errorText(error: Exception, browserName: str = "") -> str:
	"""What to tell the user when something failed, and what to do next."""
	if not isinstance(error, WhatsAppError):
		# Translators: Reported when something unexpected failed. The details are in NVDA's log.
		return _("Something went wrong. Details are in NVDA's log.")
	code, detail = error.code, error.detail
	browser = browserName or "Brave"
	if code == "noBrowser":
		return _(
			# Translators: Reported when no browser lets the add-on connect.
			"Remote debugging is not turned on in your browser. In Brave, open a new tab, go to "
			"brave://inspect/#remote-debugging and check Allow remote debugging for this browser instance. "
			"Then press NVDA+Shift+W again."
		)
	if code == "refused":
		# Translators: Reported when the user chose Cancel in the browser's remote debugging question.
		return _(
			"{browser} did not allow the connection. Press NVDA+Shift+W to try again, and choose Allow."
		).format(browser=browser)
	if code == "approvalTimedOut":
		# Translators: Reported when nobody answered the browser's remote debugging question.
		return _("{browser}'s question was not answered. Press NVDA+Shift+W to try again.").format(
			browser=browser
		)
	if code == "noWhatsAppTab":
		# Translators: Reported when the browser has no WhatsApp Web tab.
		return _(
			"WhatsApp Web is not open in {browser}. Open web.whatsapp.com, log in, then try again."
		).format(browser=browser)
	if code == "pageNotLoaded":
		return _(
			# Translators: Reported when the hidden browser could not open WhatsApp Web. {detail} is what the
			# browser's page said, in English, such as "This site can't be reached".
			"WhatsApp Web did not open in {browser}. The page said: {detail} Check the internet connection, "
			"and whether a firewall or antivirus blocks {browser}."
		).format(browser=browser, detail=detail or "-")
	if code == "notReady":
		# Translators: Reported when WhatsApp Web has not finished loading.
		return _("WhatsApp Web is still loading. Try again in a moment.")
	if code == "disconnected":
		# Translators: Reported when the connection to the browser ended, for example because it was closed.
		return _("The connection to WhatsApp Web was lost. Press NVDA+Shift+W to connect again.")
	if code == "chatNotFound":
		# Translators: Reported when a chat no longer exists in WhatsApp.
		return _("This chat is no longer in WhatsApp.")
	if code == "microphone":
		# Translators: Reported when recording could not start. {reason} is the browser's reason, in English.
		return _(
			"The microphone could not be used ({reason}). Check that WhatsApp Web may use the microphone "
			"in {browser}, and that no other program is holding it."
		).format(reason=detail, browser=browser)
	if code == "emptyRecording":
		# Translators: Reported when a voice note had no sound in it.
		return _("Nothing was recorded.")
	if code in ("mediaGone", "noMedia"):
		# Translators: Reported when a voice message cannot be downloaded any more.
		return _("This voice message cannot be downloaded any more. Listen to it in WhatsApp on your phone.")
	if code == "noChromium":
		return _(
			# Translators: Reported when no browser can run WhatsApp hidden.
			"No browser on this computer can run WhatsApp hidden. Install Brave or Google Chrome, version 120 "
			"or newer, or choose WhatsApp Web in your own browser in NVDA's settings, WhatsApp Access."
		)
	if code == "loggedOut":
		# Translators: Reported when WhatsApp Web in the user's browser is not logged in.
		return _("WhatsApp Web is not logged in in {browser}. Log in there, then try again.").format(
			browser=browser
		)
	if code == "groupCall":
		# Translators: Reported when WhatsApp refuses a group call the add-on asked for.
		return _("Group calls are not supported yet")
	if code == "callNotStarted":
		# Translators: Reported when WhatsApp did not start a call, for example because it asks for consent first.
		return _(
			"WhatsApp did not start the call. Try calling once from WhatsApp on your phone or in a browser."
		)
	if code == "noMetaAi":
		# Translators: Reported when Alt+P cannot describe a photo because the user has no chat with Meta AI.
		return _(
			"Photos are described by Meta AI. Start a chat with Meta AI in WhatsApp on your phone first."
		)
	if code == "aiTimeout":
		# Translators: Reported when Meta AI did not describe a photo in time.
		return _("Meta AI did not answer in time. Its answer may still come in the chat with Meta AI.")
	if code == "inviteInvalid":
		# Translators: Reported when a group's invite link was reset by its admins or never existed.
		return _("This group link no longer works. Ask for a new one.")
	if code == "joinFailed":
		# Translators: Reported when joining a group from its link failed.
		return _("Could not join the group. Try again, or join from WhatsApp on your phone.")
	if code == "channelNotFound":
		# Translators: Reported when a channel link leads nowhere.
		return _("This channel could not be found.")
	if code == "notOnWhatsApp":
		# Translators: Reported when a phone number has no WhatsApp account.
		return _("This number is not on WhatsApp.")
	if code == "badNumber":
		# Translators: Reported when what the user typed is not a phone number.
		return _("Type a phone number with its country code, such as +62 812 3456 7890.")
	if code == "fileTooLarge":
		# Translators: Reported when a file is too large to send through the add-on.
		return _("This file is larger than {size} MB. Send it from WhatsApp on your phone.").format(
			size=detail
		)
	if code == "noDownload":
		# Translators: Reported when a file in a message cannot be downloaded.
		return _("This file cannot be downloaded any more. Open it in WhatsApp on your phone.")
	if code == "downloadTooLarge":
		# Translators: Reported when a file in a message is too large for the add-on to download.
		return _("This file is larger than {size} MB. Open it in WhatsApp on your phone.").format(size=detail)
	if code == "notMarked":
		# Translators: Reported when a file could not get the mark Windows gives files from the internet, so it
		# is not opened; the user can still save it.
		return _("The file could not be opened safely here. Save it with Alt+D instead.")
	if code == "saveFailed":
		# Translators: Reported when a downloaded file could not be written to disk. {reason} is Windows' reason.
		return _("The file could not be saved ({reason}).").format(reason=detail)
	if code == "sendFailed":
		# Translators: Reported when WhatsApp did not send a message. {reason} is WhatsApp's reason.
		return _("WhatsApp did not send it ({reason}).").format(reason=detail)
	log.error(f"WhatsApp Access: {error}")
	# Translators: Reported when something unexpected failed. The details are in NVDA's log.
	return _("Something went wrong. Details are in NVDA's log.")


class ChatWindow(wx.Dialog):
	"""Two views in one window: the chat list, and one conversation. Escape goes back, then closes."""

	def __init__(self, parent: wx.Window, session: WhatsAppSession, onClosed: Callable[[], None]) -> None:
		# Translators: The title of the add-on's window.
		super().__init__(parent, title=_("WhatsApp"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.session = session
		self._onClosed = onClosed
		self._chats: list[dict] = []
		self._shownChats: list[dict] = []
		self.chat: dict | None = None
		self._messages: list[dict] = []
		self._recording = False
		self._hasRecording = False
		self._recordingChatId: str | None = None
		"""The chat a voice note is recorded in. It can only be sent there."""
		self._recordingStarting = False
		self._recordingStopping = False
		self._recordingGeneration = 0
		"""Changes whenever a voice note starts or is thrown away, so late answers about an older one are
		ignored."""
		self._sendingIn: set[str] = set()
		# Messages written with Enter while one before them was still being sent, by chat.
		self._textQueue: dict[str, list[tuple[str, str, list[dict]]]] = {}
		"""Chats with a message, files or a voice note on the way, so a second key press sends nothing."""
		self._loadingEarlier = False
		self._playingId: str | None = None
		self._quietFocusUntil = 0.0
		self._voiceRun = False
		# The last message Ctrl+T translated: its id, when, and the translation, for Ctrl+T twice.
		self._lastTranslation: tuple[str, float, str] | None = None
		self._translatingId: str | None = None
		self._showWhenTranslated = False
		# What the user wrote before Ctrl+T translated it in the message box, and the translation.
		self._beforeTranslation: str | None = None
		self._translatedText = ""

		main = wx.BoxSizer(wx.VERTICAL)
		self._archivedChats: list[dict] = []
		self._statuses: list[dict] = []
		self._calls: list[dict] = []
		# The sections are pages without tabs: screen reader users found a tab control awkward. The
		# Sections list, reached with Tab, moves between them, like WhatsApp's sidebar.
		self.calls = None
		self.callPanel = wx.Panel(self)
		callSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.callText = wx.StaticText(self.callPanel, label="")
		callSizer.Add(self.callText, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
		# Translators: A button in the WhatsApp window during a call: shows the call's window again.
		self.returnToCallButton = wx.Button(self.callPanel, label=_("Return to call (NVDA+Alt+A)"))
		self.returnToCallButton.Bind(wx.EVT_BUTTON, lambda evt: self.calls and self.calls.answerOrShow())
		callSizer.Add(self.returnToCallButton, 0, wx.RIGHT, 6)
		self.callMuteButton = wx.Button(self.callPanel, label="")
		self.callMuteButton.Bind(wx.EVT_BUTTON, lambda evt: self.calls and self.calls.toggleMute())
		callSizer.Add(self.callMuteButton)
		self.callPanel.SetSizer(callSizer)
		self.callPanel.Hide()
		main.Add(self.callPanel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
		self.tabs = wx.Simplebook(self)
		self.chatsPanel = wx.Panel(self.tabs)
		self.statusPanel = wx.Panel(self.tabs)
		self.callsPanel = wx.Panel(self.tabs)
		self.archivedPanel = wx.Panel(self.tabs)
		self.starredPanel = wx.Panel(self.tabs)
		self.channelsPanel = wx.Panel(self.tabs)
		self.communitiesPanel = wx.Panel(self.tabs)
		self.settingsPanel = wx.Panel(self.tabs)
		self._starred: list[dict] = []
		self._goToMessageId: str | None = None
		self._channels: list[dict] = []
		self._communities: list[dict] = []
		self._buildChatsPanel(self.chatsPanel)
		self._buildStatusPanel(self.statusPanel)
		self._buildCallsPanel(self.callsPanel)
		self._buildArchivedPanel(self.archivedPanel)
		self._buildStarredPanel(self.starredPanel)
		self._buildChannelsPanel(self.channelsPanel)
		self._buildCommunitiesPanel(self.communitiesPanel)
		self._buildSettingsPanel(self.settingsPanel)
		pages = (
			self.chatsPanel,
			self.statusPanel,
			self.callsPanel,
			self.archivedPanel,
			self.starredPanel,
			self.channelsPanel,
			self.communitiesPanel,
			self.settingsPanel,
		)
		for page, label in zip(pages, tabNames(), strict=True):
			self.tabs.AddPage(page, label)
		self._selectedMessageIds: set[str] = set()
		self._selectedChatIds: set[str] = set()
		self.conversationPanel = wx.Panel(self)
		self._buildConversationPanel(self.conversationPanel)
		for listBox in (self.chatList, self.archivedList, self.messageList):
			listBox.Bind(wx.EVT_LISTBOX, self._onListMoved)
		# Made after the sections, so Tab from a section's last control reaches it.
		self.sectionsPanel = wx.Panel(self)
		sectionsSizer = wx.BoxSizer(wx.VERTICAL)
		sectionsLabel = (
			# Translators: The label of the list that moves between Chats, Status, Calls and Archived,
			# with a hint, when the user wants hints.
			_("Sections (Enter opens):")
			if config.conf[CONFIG_SECTION]["hints"]
			# Translators: The label of the list that moves between Chats, Status, Calls and Archived.
			else _("Sections:")
		)
		sectionsSizer.Add(wx.StaticText(self.sectionsPanel, label=sectionsLabel))
		self.sectionList = wx.ListBox(self.sectionsPanel, style=wx.LB_SINGLE)
		self.sectionList.Bind(wx.EVT_KEY_DOWN, self._onSectionKey)
		self.sectionList.Bind(
			wx.EVT_LISTBOX_DCLICK, lambda evt: self.showTab(self.sectionList.GetSelection())
		)
		sectionsSizer.Add(self.sectionList, 0, wx.EXPAND)
		self.sectionsPanel.SetSizer(sectionsSizer)
		self._updateSections()
		# As in WhatsApp's desktop app, the open chat is beside the sections, which stay: chats on the left,
		# the conversation on the right. Tab goes through the conversation, then on to the chat list.
		# A list asks to be as wide as its longest line, and chat lines with their last message are long:
		# the chat list took the whole width and left the open chat none, so it was not on the screen at
		# all (OCR said "content is not visible"). Set widths let the two share the window, 2 to 3.
		for part in (self.tabs, self.sectionsPanel):
			part.SetMinSize(wx.Size(SIDE_MIN_WIDTH, -1))
		self.conversationPanel.SetMinSize(wx.Size(CONVERSATION_MIN_WIDTH, -1))
		side = wx.BoxSizer(wx.VERTICAL)
		side.Add(self.tabs, 1, wx.EXPAND | wx.ALL, 6)
		side.Add(self.sectionsPanel, 0, wx.EXPAND | wx.ALL, 6)
		body = wx.BoxSizer(wx.HORIZONTAL)
		body.Add(side, 2, wx.EXPAND)
		body.Add(self.conversationPanel, 3, wx.EXPAND | wx.ALL, 6)
		main.Add(body, 1, wx.EXPAND)
		self.conversationPanel.MoveBeforeInTabOrder(self.tabs)
		self.conversationPanel.Hide()
		self.SetSizer(main)
		self.SetSize(wx.Size(1000, 650))
		self.CentreOnScreen()
		self.Bind(wx.EVT_CHAR_HOOK, self._onCharHook)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self.Bind(wx.EVT_ACTIVATE, self._onActivate)
		self._online = False

	# Building -------------------------------------------------------------------------------------------

	def _buildChatsPanel(self, panel: wx.Panel) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the box that filters the chat list by name.
		sizer.Add(wx.StaticText(panel, label=_("&Search chats:")))
		self.searchBox = wx.TextCtrl(panel)
		self.searchBox.Bind(wx.EVT_TEXT, lambda evt: self._showChats())
		sizer.Add(self.searchBox, 0, wx.EXPAND | wx.BOTTOM, 6)
		# Translators: The label of the choice of which chats to list, like WhatsApp's tabs.
		sizer.Add(wx.StaticText(panel, label=_("&Filter (Alt+1 to Alt+4):")))
		self.filterChoice = wx.Choice(panel, choices=filterNames())
		self.filterChoice.SetSelection(0)
		self.filterChoice.Bind(wx.EVT_CHOICE, lambda evt: self._showChats())
		sizer.Add(self.filterChoice, 0, wx.BOTTOM, 6)
		self._drafts: dict[str, str] = {}
		self._lastTyping = 0.0
		self._typingTimer: wx.CallLater | None = None
		# Translators: The label of the list of chats.
		sizer.Add(wx.StaticText(panel, label=_("&Chats:")))
		self.chatList = wx.ListBox(panel, style=wx.LB_SINGLE)
		self.chatList.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._openSelectedChat())
		self.chatList.Bind(wx.EVT_KEY_DOWN, self._onChatListKey)
		self.chatList.Bind(wx.EVT_CONTEXT_MENU, self._onChatMenu)
		sizer.Add(self.chatList, 1, wx.EXPAND | wx.BOTTOM, 6)
		# The list first, then the search and filter: Tab from an open chat's last button reaches the chats.
		self.chatList.MoveBeforeInTabOrder(self.searchBox)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button under the chat list with WhatsApp's menu there: opening a WhatsApp link and
		# marking all chats as read.
		self.optionsButton = wx.Button(panel, label=_("&Options"))
		self.optionsButton.Bind(wx.EVT_BUTTON, lambda evt: self._optionsMenu())
		buttons.Add(self.optionsButton, 0, wx.RIGHT, 6)
		# Translators: A button that closes the add-on's window. WhatsApp Web stays open.
		closeButton = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		buttons.Add(closeButton)
		sizer.Add(buttons)
		panel.SetSizer(sizer)

	def _buildStatusPanel(self, panel: wx.Panel) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the list of people who posted statuses. Enter views them.
		sizer.Add(wx.StaticText(panel, label=_("&Status updates:")))
		self.statusList = wx.ListBox(panel, style=wx.LB_SINGLE)
		self.statusList.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._viewStatus())
		sizer.Add(self.statusList, 1, wx.EXPAND | wx.BOTTOM, 6)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		for label, action in (
			# Translators: A button in the Status section: writes a text status.
			(_("&Write a status\u2026"), self._postTextStatus),
			# Translators: A button in the Status section: posts a photo or video as a status.
			(_("Post a &photo or video\u2026"), self._postMediaStatus),
			# Translators: A button in the Status section: the user's own statuses and who saw them.
			(_("&My status"), self._showMyStatus),
		):
			button = wx.Button(panel, label=label)
			button.Bind(wx.EVT_BUTTON, lambda evt, action=action: action())
			buttons.Add(button, 0, wx.RIGHT, 6)
		sizer.Add(buttons)
		panel.SetSizer(sizer)

	def _buildCallsPanel(self, panel: wx.Panel) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		label = (
			# Translators: The label of the list of recent calls, with a hint, when the user wants hints.
			_("&Recent calls (Enter calls back):")
			if config.conf[CONFIG_SECTION]["hints"]
			# Translators: The label of the list of recent calls.
			else _("&Recent calls:")
		)
		sizer.Add(wx.StaticText(panel, label=label))
		self.callsList = wx.ListBox(panel, style=wx.LB_SINGLE)
		self.callsList.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._callBack())
		self.callsList.Bind(wx.EVT_CONTEXT_MENU, self._onCallsMenu)
		sizer.Add(self.callsList, 1, wx.EXPAND)
		panel.SetSizer(sizer)

	def _buildArchivedPanel(self, panel: wx.Panel) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the list of archived chats.
		sizer.Add(wx.StaticText(panel, label=_("&Archived chats:")))
		self.archivedList = wx.ListBox(panel, style=wx.LB_SINGLE)
		self.archivedList.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._openSelectedChat())
		self.archivedList.Bind(wx.EVT_CONTEXT_MENU, self._onChatMenu)
		self.archivedList.Bind(wx.EVT_KEY_DOWN, self._onChatListKey)
		sizer.Add(self.archivedList, 1, wx.EXPAND)
		panel.SetSizer(sizer)

	def _buildStarredPanel(self, panel: wx.Panel) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the list of starred messages.
		sizer.Add(wx.StaticText(panel, label=_("Starred &messages:")))
		self.starredList = wx.ListBox(panel, style=wx.LB_SINGLE)
		self.starredList.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._openStarred())
		self.starredList.Bind(wx.EVT_CONTEXT_MENU, lambda evt: self._starredMenu())
		sizer.Add(self.starredList, 1, wx.EXPAND)
		panel.SetSizer(sizer)

	def _buildChannelsPanel(self, panel: wx.Panel) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the list of channels the user follows.
		sizer.Add(wx.StaticText(panel, label=_("C&hannels you follow:")))
		self.channelList = wx.ListBox(panel, style=wx.LB_SINGLE)
		self.channelList.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._openChannel())
		self.channelList.Bind(wx.EVT_CONTEXT_MENU, lambda evt: self._channelMenu())
		sizer.Add(self.channelList, 1, wx.EXPAND | wx.BOTTOM, 6)
		# Translators: A button that finds channels to follow.
		findButton = wx.Button(panel, label=_("&Find channels\u2026"))
		findButton.Bind(wx.EVT_BUTTON, lambda evt: self._findChannels())
		sizer.Add(findButton)
		panel.SetSizer(sizer)

	def _buildCommunitiesPanel(self, panel: wx.Panel) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the list of the user's communities. Enter shows a community's groups.
		sizer.Add(wx.StaticText(panel, label=_("Co&mmunities:")))
		self.communityList = wx.ListBox(panel, style=wx.LB_SINGLE)
		self.communityList.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._openCommunity())
		sizer.Add(self.communityList, 1, wx.EXPAND)
		panel.SetSizer(sizer)

	def _buildSettingsPanel(self, panel: wx.Panel) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the list of WhatsApp settings, such as profile and privacy.
		sizer.Add(wx.StaticText(panel, label=_("Se&ttings:")))
		self._settingsItems: list[tuple[str, Callable[[], None]]] = [
			# Translators: An item in the Settings section: the user's name, about and photo.
			(_("Profile: name, about and photo"), self._editProfile),
			# Translators: An item in the Settings section.
			(_("Privacy: last seen, read receipts, groups and more"), self._editPrivacy),
			# Translators: An item in the Settings section.
			(_("Blocked contacts"), self._showBlocked),
			# Translators: An item in the Settings section: the add-on's own settings in NVDA.
			(_("Add-on settings: sounds, volumes, microphone, notifications"), self._openAddonSettings),
		]
		self.settingsList = wx.ListBox(panel, choices=[label for label, action in self._settingsItems])
		self.settingsList.SetSelection(0)
		self.settingsList.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._openSetting())
		sizer.Add(self.settingsList, 1, wx.EXPAND)
		panel.SetSizer(sizer)

	# Starred messages ------------------------------------------------------------------------------------

	def _gotStarred(self, messages: list[dict]) -> None:
		selected = _selectedId(self.starredList, self._starred)
		self._starred = messages
		_fillList(
			self.starredList,
			[messageText.messageInChat(m) for m in messages]
			# Translators: Shown in the Starred section when no message is starred.
			or [_("No starred messages")],
			messages,
			selected,
		)

	def _selectedStarred(self) -> dict | None:
		index = self.starredList.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._starred):
			return None
		return self._starred[index]

	def _chatById(self, chatId: str, title: str = "") -> dict:
		for chat in (*self._chats, *self._archivedChats, *self._channels):
			if chat.get("id") == chatId:
				return chat
		return {"id": chatId, "title": title, "isGroup": chatId.endswith("@g.us")}

	def _openStarred(self) -> None:
		message = self._selectedStarred()
		if message is None:
			return
		self._goToMessageId = message["id"]
		self.openChat(self._chatById(message["chatId"], message.get("chatTitle", "")))

	def _starredMenu(self) -> None:
		message = self._selectedStarred()
		if message is None:
			return
		menu = wx.Menu()

		def add(label: str, handler: Callable[[], None]) -> None:
			item = menu.Append(wx.ID_ANY, label)
			menu.Bind(wx.EVT_MENU, lambda evt: handler(), item)

		# Translators: An item in a starred message's menu: opens its chat at the message.
		add(_("&Open in chat"), self._openStarred)
		# Translators: An item in a starred message's menu: copies its text.
		add(_("&Copy"), lambda: self._copy(message.get("text") or message.get("caption") or ""))

		def unstarred(result: Any) -> None:
			# Translators: Reported after a message was taken off the starred messages.
			ui.message(_("Unstarred"))
			self._loadTab(self.TAB_STARRED)

		add(
			# Translators: An item in a starred message's menu: takes it off the starred messages.
			_("Un&star"),
			lambda: self._run(lambda: self.session.starMessages([message["id"]], False), unstarred),
		)
		self.starredList.PopupMenu(menu)
		menu.Destroy()

	# Channels --------------------------------------------------------------------------------------------

	def _gotChannels(self, channels: list[dict]) -> None:
		selected = _selectedId(self.channelList, self._channels)
		self._channels = channels
		_fillList(
			self.channelList,
			[messageText.chatLine(c) for c in channels]
			# Translators: Shown in the Channels section when the user follows no channel.
			or [_("You follow no channels. Find channels with the button below.")],
			channels,
			selected,
		)

	def _selectedChannel(self) -> dict | None:
		index = self.channelList.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._channels):
			return None
		return self._channels[index]

	def _openChannel(self) -> None:
		channel = self._selectedChannel()
		if channel is not None:
			self.openChat(channel)

	def _channelMenu(self) -> None:
		channel = self._selectedChannel()
		if channel is None:
			return
		menu = wx.Menu()
		# Translators: An item in a channel's menu in the Channels section: opens the channel.
		item = menu.Append(wx.ID_ANY, _("&Open"))
		menu.Bind(wx.EVT_MENU, lambda evt: self.openChat(channel), item)
		# Translators: An item in a channel's menu: stops following it.
		item = menu.Append(wx.ID_ANY, _("&Unfollow"))
		menu.Bind(wx.EVT_MENU, lambda evt: self._followChannel(channel, False), item)
		self.channelList.PopupMenu(menu)
		menu.Destroy()

	def _followChannel(self, channel: dict, follow: bool) -> None:
		def done(result: Any) -> None:
			ui.message(
				# Translators: Reported after following or unfollowing a channel, with its name.
				(_("Following {name}") if follow else _("Unfollowed {name}")).format(name=channel["title"])
			)
			self._loadTab(self.TAB_CHANNELS)

		self._run(lambda: self.session.followChannel(channel["id"], follow), done)

	def _findChannels(self) -> None:
		dialog = wx.TextEntryDialog(
			self,
			# Translators: Asks what channels to look for.
			_("Find channels named:"),
			# Translators: The title of the dialog that finds channels.
			_("Find channels"),
		)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			query = dialog.GetValue().strip()
		finally:
			dialog.Destroy()
		if not query:
			return

		def show(found: list[dict]) -> None:
			if not found:
				# Translators: Reported when a channel search finds nothing.
				ui.message(_("No channels found"))
				return
			lines = []
			for c in found:
				# Translators: A channel found by a search: name, followers, and whether the user follows it.
				line = _("{name}, {count} followers").format(name=c["title"], count=c.get("followers", 0))
				if c.get("verified"):
					# Translators: Added to a channel that WhatsApp verified.
					line += ", " + _("verified")
				if c.get("following"):
					# Translators: Added to a channel the user already follows.
					line += ", " + _("following")
				if c.get("description"):
					line += ". " + c["description"][:150]
				lines.append(line)
			# Translators: The title of the list of channels found.
			picker = ListDialog(self, _("Channels found"), lines, okLabel=_("&Follow or open"))
			try:
				if picker.ShowModal() != wx.ID_OK:
					return
				chosen = found[picker.selection()]
			finally:
				picker.Destroy()
			if chosen.get("following"):
				self.openChat(chosen)
			else:
				self._followChannel(chosen, True)

		self._run(lambda: self.session.searchChannels(query), show)

	# Communities -----------------------------------------------------------------------------------------

	def _gotCommunities(self, communities: list[dict]) -> None:
		selected = _selectedId(self.communityList, self._communities)
		self._communities = communities
		lines = []
		for c in communities:
			# Translators: A community in its list: name and how many groups it has.
			line = _("{name}, {count} groups").format(name=c["title"], count=len(c.get("groups", [])))
			if c.get("unread"):
				# Translators: Added to a community in the list: how many unread messages it has.
				line += ", " + _("{count} unread").format(count=c["unread"])
			lines.append(line)
		# Translators: Shown in the Communities section when the user is in no community.
		_fillList(self.communityList, lines or [_("You are in no community")], communities, selected)

	def _openCommunity(self) -> None:
		index = self.communityList.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._communities):
			return
		community = self._communities[index]
		groups = community.get("groups", [])
		lines = []
		for g in groups:
			# Translators: The community's announcement group, in the list of its groups.
			line = _("Announcements: {name}").format(name=g["title"]) if g.get("announcement") else g["title"]
			if not g.get("joined"):
				if g.get("requested"):
					# Translators: A community group the user asked to join, waiting for its admins.
					line += ", " + _("request sent")
				elif g.get("needsApproval"):
					# Translators: A community group the user is not in; joining asks its admins.
					line += ", " + _("not joined, asks the admins")
				else:
					# Translators: A community group the user is not in.
					line += ", " + _("not joined")
			elif g.get("unread"):
				# Translators: Added to a community's group in the list: how many unread messages it has.
				line += ", " + _("{count} unread").format(count=g["unread"])
			lines.append(line)
		if not lines:
			return
		# Translators: The button that opens a community's group, or asks to join it.
		picker = ListDialog(self, community["title"], lines, okLabel=_("&Open or join"))
		try:
			if picker.ShowModal() != wx.ID_OK:
				return
			group = groups[picker.selection()]
		finally:
			picker.Destroy()
		if group.get("joined"):
			self.openChat(self._chatById(group["id"], group["title"]))
			return
		if group.get("requested"):
			# Translators: Reported when the user already asked to join a community group and waits for its admins.
			ui.message(_("request sent"))
			return
		if not askYesNo(
			self,
			# Translators: Asked before joining a community group, with its name.
			_("Join {name}?").format(name=group["title"]),
			community["title"],
			warning=False,
		):
			return

		def joined(result: str) -> None:
			if result == "requested":
				# Translators: Reported after asking to join a community group whose admins approve members.
				ui.message(_("Request sent to the admins"))
			else:
				# Translators: Reported after joining a community group.
				ui.message(_("Joined {name}").format(name=group["title"]))
			self._loadTab(self.TAB_COMMUNITIES)

		self._run(lambda: self.session.joinCommunityGroup(community["id"], group["id"]), joined)

	# Settings --------------------------------------------------------------------------------------------

	def _openSetting(self) -> None:
		index = self.settingsList.GetSelection()
		if 0 <= index < len(self._settingsItems):
			self._settingsItems[index][1]()

	def _openAddonSettings(self) -> None:
		import gui
		from gui.settingsDialogs import NVDASettingsDialog

		from . import WhatsAppSettingsPanel

		wx.CallAfter(gui.mainFrame.popupSettingsDialog, NVDASettingsDialog, WhatsAppSettingsPanel)

	# Tabs -----------------------------------------------------------------------------------------------

	(
		TAB_CHATS,
		TAB_STATUS,
		TAB_CALLS,
		TAB_ARCHIVED,
		TAB_STARRED,
		TAB_CHANNELS,
		TAB_COMMUNITIES,
		TAB_SETTINGS,
	) = range(8)

	def showTab(self, index: int) -> None:
		"""Ctrl+1 to Ctrl+8: Chats, Status, Calls, Archived, Starred, Channels, Communities or Settings. An
		open conversation stays open beside it."""
		self.tabs.ChangeSelection(index)
		self._updateSections()
		self._loadTab(index)
		self._focusTab(index)

	def _updateSections(self) -> None:
		"""The Sections list says which section is shown, and starts there."""
		current = self.tabs.GetSelection()
		lines = [
			# Translators: A section in the Sections list that is the one shown, such as "Chats (Ctrl+1), current".
			_("{section}, current").format(section=name) if index == current else name
			for index, name in enumerate(tabNames())
		]
		if self.sectionList.GetItems() != lines:
			self.sectionList.Set(lines)
		self.sectionList.SetSelection(current)

	def _onSectionKey(self, evt: wx.KeyEvent) -> None:
		if (
			evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_SPACE)
			and not evt.HasAnyModifiers()
		):
			self.showTab(self.sectionList.GetSelection())
			return
		evt.Skip()

	def _loadTab(self, index: int) -> None:
		if index == self.TAB_CHATS:
			self.refreshChats()
		elif index == self.TAB_STATUS:
			self._run(self.session.statuses, self._gotStatuses)
		elif index == self.TAB_CALLS:
			self._run(self.session.recentCalls, self._gotCalls)
		elif index == self.TAB_ARCHIVED:
			self._run(lambda: self.session.chats(True), self._gotArchived)
		elif index == self.TAB_STARRED:
			self._run(self.session.starredMessages, self._gotStarred)
		elif index == self.TAB_CHANNELS:
			self._run(self.session.channels, self._gotChannels)
		elif index == self.TAB_COMMUNITIES:
			self._run(self.session.communities, self._gotCommunities)

	def _focusTab(self, index: int) -> None:
		target = (
			self.chatList,
			self.statusList,
			self.callsList,
			self.archivedList,
			self.starredList,
			self.channelList,
			self.communityList,
			self.settingsList,
		)[index]
		target.SetFocus()

	def _gotStatuses(self, statuses: list[dict]) -> None:
		selected = _selectedId(self.statusList, self._statuses)
		self._statuses = statuses
		_fillList(self.statusList, [messageText.statusLine(s) for s in statuses], statuses, selected)

	def _gotCalls(self, calls: list[dict]) -> None:
		selected = _selectedId(self.callsList, self._calls)
		self._calls = calls
		_fillList(self.callsList, [messageText.callLogLine(c) for c in calls], calls, selected)

	def _gotArchived(self, chats: list[dict]) -> None:
		selected = _selectedId(self.archivedList, self._archivedChats)
		self._archivedChats = chats
		_fillList(self.archivedList, [self._chatLine(c) for c in chats], chats, selected)

	def _viewStatus(self) -> None:
		index = self.statusList.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._statuses):
			return
		viewer = StatusViewer(
			self, self.session, self._statuses, index, self._openFile, self._describeFile, self._saveFile
		)
		try:
			viewer.ShowModal()
		finally:
			viewer.Destroy()
			# However it closed (Escape, Close or Alt+F4), a status still playing stops with it.
			self._run(self.session.stopAudio, onError=lambda e: None)
		self._loadTab(self.TAB_STATUS)
		self.statusList.SetFocus()

	def _selectedCall(self) -> dict | None:
		index = self.callsList.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._calls):
			return None
		return self._calls[index]

	def _callBack(self) -> None:
		call = self._selectedCall()
		if call is None:
			return
		chatId = call["chatId"]
		if call.get("ongoing"):
			if call.get("joined") and self.calls:
				self.calls.answerOrShow()
				return
			# Translators: Reported while joining a group call.
			ui.message(_("Joining…"))
			self._run(lambda: self.session.joinGroupCall(chatId))
			return
		if call.get("group"):
			self._run(lambda: self.session.startGroupCall(chatId))
			return
		self._run(lambda: self.session.startCall(chatId))

	def _onCallsMenu(self, evt: wx.ContextMenuEvent) -> None:
		call = self._selectedCall()
		if call is None:
			return
		menu = wx.Menu()
		# Translators: An item in a recent call's menu: calls the person back.
		item = menu.Append(wx.ID_ANY, _("&Call back"))
		menu.Bind(wx.EVT_MENU, lambda e: self._callBack(), item)
		# Translators: An item in a recent call's menu: opens the chat with the person.
		item = menu.Append(wx.ID_ANY, _("&Open chat"))
		chat = next((c for c in self._chats + self._archivedChats if c["id"] == call["chatId"]), None)
		menu.Bind(wx.EVT_MENU, lambda e: self.openChat(chat) if chat else None, item)
		item.Enable(chat is not None)
		self.callsList.PopupMenu(menu)
		menu.Destroy()

	def _buildConversationPanel(self, panel: wx.Panel) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		# The chat's name and what WhatsApp shows under it (online, last seen, typing), as in WhatsApp's
		# header. Pressing it opens the contact or group info.
		header = wx.BoxSizer(wx.HORIZONTAL)
		self.chatButton = wx.Button(panel, label="")
		self.chatButton.Bind(wx.EVT_BUTTON, lambda evt: self._showContactInfo())
		header.Add(self.chatButton, 1, wx.RIGHT, 6)
		# Translators: A button beside the contact's name in a chat: calls the person (Ctrl+Shift+C).
		self.callButton = wx.Button(panel, label=_("Voice call (Ctrl+Shift+C)"))
		self.callButton.Bind(wx.EVT_BUTTON, lambda evt: self._startCall())
		header.Add(self.callButton, 0, wx.RIGHT, 6)
		# Translators: A button beside the contact's name in a chat: opens the chat's menu, as WhatsApp's.
		self.moreButton = wx.Button(panel, label=_("More options"))
		self.moreButton.Bind(wx.EVT_BUTTON, lambda evt: self._conversationMenu())
		header.Add(self.moreButton, 0)
		sizer.Add(header, 0, wx.EXPAND | wx.BOTTOM, 6)
		self._presence: dict | None = None
		self._presenceText = ""
		self._unreadAtOpen = 0
		self._firstUnreadId: str | None = None
		self._seenTimer: wx.CallLater | None = None
		self._ackTimer: wx.CallLater | None = None
		self._acksToSay: list[int] = []
		# Translators: The label of the list of messages in a conversation.
		sizer.Add(wx.StaticText(panel, label=_("&Messages:")))
		self.messageList = wx.ListBox(panel, style=wx.LB_SINGLE)
		self.messageList.Bind(wx.EVT_KEY_DOWN, self._onMessageListKey)
		self.messageList.Bind(wx.EVT_CONTEXT_MENU, self._onMessageMenu)
		self.messageList.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._activateMessage())
		sizer.Add(self.messageList, 1, wx.EXPAND | wx.BOTTOM, 6)
		# On a voice message, Tab from the messages reaches where it is playing, as WhatsApp's slider:
		# Left and Right go back and on 5 seconds, Page Up and Page Down 30.
		# Translators: The label of the slider for where a voice message plays; NVDA reads its value as the
		# time, such as "12 sec of 45 sec".
		self.positionLabel = wx.StaticText(panel, label=_("Voice message position:"))
		sizer.Add(self.positionLabel)
		self.positionSlider = wx.Slider(panel, value=0, minValue=0, maxValue=1)
		self.positionSlider.SetLineSize(POSITION_STEP_SECONDS)
		self.positionSlider.SetPageSize(POSITION_PAGE_SECONDS)
		self.positionSlider.Bind(wx.EVT_SLIDER, lambda evt: self._seek())
		sizer.Add(self.positionSlider, 0, wx.EXPAND | wx.BOTTOM, 6)
		self.positionLabel.Hide()
		self.positionSlider.Hide()
		self.messageList.Bind(wx.EVT_LISTBOX, self._onMessageMoved)
		# A wx.Timer owned by this window crashed NVDA when it fired after the window was destroyed, as on
		# reloading plugins during playback; a CallLater that checks the window is still there cannot.
		self._positionFollow: wx.CallLater | None = None
		# A position chosen on the slider before playing: (message id, seconds).
		self._startAt: tuple[str, float] | None = None
		self.replyingText = wx.StaticText(panel, label="")
		sizer.Add(self.replyingText, 0, wx.BOTTOM, 3)
		# Translators: The label of the box where the user writes a message. Enter sends it.
		self.composeLabel = wx.StaticText(panel, label=_("Typ&e a message:"))
		sizer.Add(self.composeLabel)
		# Several lines, as in WhatsApp: Enter sends, Shift+Enter starts a new line. Rich, so that positions
		# in the text are the same as in what GetValue returns, which the @ and : suggestions rely on.
		self.composeBox = wx.TextCtrl(
			panel, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER | wx.TE_RICH2, size=(-1, 54)
		)
		self.composeBox.Bind(wx.EVT_TEXT_ENTER, lambda evt: self._sendText())
		self.composeBox.Bind(wx.EVT_TEXT, self._onComposeText)
		self._participants: list[dict] = []
		self._mentionMatches: list[dict] = []
		self._emojiMatches: list[str] = []
		self._emojiIndex = -1
		self._mentionIndex = -1
		self._mentions: dict[str, str] = {}
		sizer.Add(self.composeBox, 0, wx.EXPAND | wx.BOTTOM, 6)
		# In place of the message box where the user cannot send, as WhatsApp's bar there says why. It comes
		# right after the box's label, so Alt+E reaches it as it would the box.
		self.cannotSendBox = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 54))
		self.cannotSendBox.Hide()
		sizer.Add(self.cannotSendBox, 0, wx.EXPAND | wx.BOTTOM, 6)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button that stops replying to a message; the message is then sent on its own.
		self.cancelReplyButton = wx.Button(panel, label=_("Cancel reply"))
		self.cancelReplyButton.Bind(
			wx.EVT_BUTTON, lambda evt: self._cancelEdit() if self._editing else self._cancelReply()
		)
		# Translators: A button that opens a file picker to send photos, videos, audio or documents.
		self.attachButton = wx.Button(panel, label=_("&Attach"))
		self.attachButton.Bind(wx.EVT_BUTTON, lambda evt: self._attachMenu())
		self._attachments: list[str] = []
		# Attached with Document: sent as files even when they are photos or videos, as in WhatsApp.
		self._asDocuments: set[str] = set()
		# Translators: A button that sends what the user wrote.
		self.sendButton = wx.Button(panel, label=_("&Send"))
		self.sendButton.Bind(wx.EVT_BUTTON, lambda evt: self._sendText())
		# Translators: A button that starts recording a voice note.
		self.recordButton = wx.Button(panel, label=_("Record voice note (Ctrl+R)"))
		self.recordButton.Bind(wx.EVT_BUTTON, lambda evt: self._toggleRecording())
		# Translators: A button that sends the voice note the user just recorded.
		self.sendVoiceButton = wx.Button(panel, label=_("Send voice note (Ctrl+Shift+R)"))
		self.sendVoiceButton.Bind(wx.EVT_BUTTON, lambda evt: self._sendVoiceNow())
		# Translators: A button that plays the voice note the user just recorded, before sending it.
		self.listenButton = wx.Button(panel, label=_("Listen (Ctrl+R)"))
		self.listenButton.Bind(wx.EVT_BUTTON, lambda evt: self._listenToRecording())
		# Translators: A button that throws away the voice note the user just recorded.
		self.discardButton = wx.Button(panel, label=_("Discard (Ctrl+D)"))
		self.discardButton.Bind(wx.EVT_BUTTON, lambda evt: self._discardRecording())
		self.pauseButton = wx.Button(panel, label="")
		self.pauseButton.Bind(wx.EVT_BUTTON, lambda evt: self._togglePause())
		self._paused = False
		for button in (
			self.cancelReplyButton,
			self.attachButton,
			self.sendButton,
			self.recordButton,
			self.pauseButton,
			self.sendVoiceButton,
			self.listenButton,
			self.discardButton,
		):
			buttons.Add(button, 0, wx.RIGHT, 6)
		sizer.Add(buttons)
		self.buttonSizer = buttons
		panel.SetSizer(sizer)
		self._replyTo: dict | None = None
		# The message being changed in the message box, its text then, and what the box held before.
		self._editing: dict | None = None
		self._editOriginal = ""
		self._draftBeforeEdit = ""
		self._updateButtons()

	# Background work ------------------------------------------------------------------------------------

	def _run(
		self,
		work: Callable[[], Any],
		onDone: Callable[[Any], None] | None = None,
		onError: Callable[[Exception], None] | None = None,
	) -> None:
		"""Run a call to WhatsApp off NVDA's main thread, then come back to it."""

		def target() -> None:
			try:
				result = work()
			except Exception as e:  # noqa: BLE001 - reported to the user
				if not isinstance(e, WhatsAppError):
					log.exception("WhatsApp Access")
				wx.CallAfter(self._failed, e, onError)
				return
			if onDone is not None:
				wx.CallAfter(self._done, onDone, result)

		threading.Thread(target=target, name="whatsAppAccess.call", daemon=True).start()

	def _done(self, onDone: Callable[[Any], None], result: Any) -> None:
		if self:
			onDone(result)

	def _failed(self, error: Exception, onError: Callable[[Exception], None] | None) -> None:
		if not self:
			# The window was closed meanwhile. Closing WhatsApp fully closes the window and the connection
			# together, so its last calls, such as going offline, find the connection gone: that is no news.
			if not (isinstance(error, WhatsAppError) and error.code == "disconnected"):
				ui.message(errorText(error))
			return
		if onError is not None:
			onError(error)
		ui.message(errorText(error, self.session.browserName))

	# Chats ----------------------------------------------------------------------------------------------

	def refreshChats(self, focus: bool = False) -> None:
		self._run(lambda: self.session.chats(False), lambda chats: self._gotChats(chats, focus))
		if self.tabs.GetSelection() == self.TAB_ARCHIVED:
			self._run(lambda: self.session.chats(True), self._gotArchived)

	def _gotChats(self, chats: list[dict], focus: bool) -> None:
		self._chats = chats
		self._showChats()
		if focus:
			self.chatList.SetFocus()

	def _showChats(self) -> None:
		query = self.searchBox.GetValue().strip().lower()
		chatFilter = FILTERS[max(0, self.filterChoice.GetSelection())]
		shown = [
			c
			for c in self._chats
			if (not query or query in c.get("title", "").lower()) and _passesFilter(c, chatFilter)
		]
		selected = self._selectedChat()
		selectedId = selected["id"] if selected else None
		lines = [self._chatLine(c) for c in shown]
		oldIds = [c["id"] for c in self._shownChats]
		self._shownChats = shown
		if oldIds == [c["id"] for c in shown] and self.chatList.GetCount() == len(lines):
			# Same chats in the same order: change only what changed, so NVDA does not read the list again.
			for index, line in enumerate(lines):
				if self.chatList.GetString(index) != line:
					self.chatList.SetString(index, line)
			return
		self.chatList.Set(lines)
		index = next((i for i, c in enumerate(shown) if c["id"] == selectedId), 0)
		if lines:
			self.chatList.SetSelection(index)

	def _chatLine(self, chat: dict) -> str:
		line = messageText.chatLine(chat)
		draft = self._drafts.get(chat["id"])
		if draft:
			# Translators: After a chat in the list, the message the user started writing there.
			line += ", " + _("draft: {text}").format(text=draft)
		return line

	def _setFilter(self, index: int) -> None:
		"""Alt+1 to Alt+4: show all chats, unread ones, groups or favorites, as WhatsApp's tabs."""
		if self.tabs.GetSelection() != self.TAB_CHATS:
			self.tabs.ChangeSelection(self.TAB_CHATS)
			self._updateSections()
		self.filterChoice.SetSelection(index)
		self._showChats()
		self.chatList.SetFocus()
		ui.message(
			# Translators: Read out after choosing a chat list filter: its name and how many chats it shows.
			_("{filter}, {count} chats").format(filter=filterNames()[index], count=len(self._shownChats))
		)

	def _nextUnread(self) -> None:
		"""Alt+U. In a chat: go to its first unread message, where WhatsApp shows "5 unread messages".
		In the chat list: select the next chat with unread messages, without opening it."""
		if self._focusInConversation():
			self._goToFirstUnread()
			return
		unread = [index for index, c in enumerate(self._shownChats) if messageText.isUnread(c)]
		if not unread:
			# Translators: Reported when no chat in the list has unread messages.
			ui.message(_("No unread chats"))
			return
		current = self.chatList.GetSelection()
		index = next((i for i in unread if i > current), unread[0])
		self.chatList.SetSelection(index)
		self.chatList.SetFocus()
		ui.message(self.chatList.GetString(index))

	def _goToFirstUnread(self, announce: bool = True) -> bool:
		"""Select the first message that was unread when the chat was opened. Returns whether there was one."""
		index = next((i for i, m in enumerate(self._messages) if m.get("id") == self._firstUnreadId), None)
		if index is None:
			if announce:
				# Translators: Reported when the open chat had no unread messages.
				ui.message(_("No unread messages"))
			return False
		self.messageList.SetSelection(index)
		self.messageList.SetFocus()
		if announce:
			ui.message(
				# Translators: Read out at the first unread message, as WhatsApp's divider says it.
				_("{count} unread messages").format(count=self._unreadAtOpen)
				+ ", "
				+ self.messageList.GetString(index)
			)
		return True

	def _newChat(self) -> None:
		"""Ctrl+N: a chat with a phone number, without saving the contact first."""
		dialog = wx.TextEntryDialog(
			self,
			# Translators: Asks for a phone number to start a chat, with an example.
			_("Phone number, with country code, such as +62 812 3456 7890:"),
			# Translators: The title of the dialog for starting a chat with a phone number.
			_("New chat"),
		)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			number = dialog.GetValue().strip()
		finally:
			dialog.Destroy()
		if number:
			self._run(lambda: self.session.chatWithNumber(number), self.openChat)

	def _optionsMenu(self) -> None:
		"""The Options button under the chat list, like WhatsApp's menu above its chats."""
		menu = wx.Menu()
		for label, action in (
			# Translators: An item in the Options menu: joins a group or opens a channel or chat from a link.
			(_("Open a WhatsApp &link\u2026"), self._askForLink),
			# Translators: An item in the Options menu, like WhatsApp's: marks every chat as read.
			(_("Mark all as &read"), self._markAllRead),
		):
			item = menu.Append(wx.ID_ANY, label)
			menu.Bind(wx.EVT_MENU, lambda evt, action=action: action(), item)
		self.optionsButton.PopupMenu(menu)
		menu.Destroy()

	def _askForLink(self) -> None:
		"""A WhatsApp link to open, such as a group's invite link; one copied already is filled in."""
		try:
			copied = (api.getClipData() or "").strip()
		except Exception:  # noqa: BLE001 - nothing usable on the clipboard
			copied = ""
		dialog = wx.TextEntryDialog(
			self,
			# Translators: Asks for a WhatsApp link: a group's invite link, a channel, or a wa.me link.
			_("WhatsApp link, such as a group's invite link, a channel or a wa.me link:"),
			# Translators: The title of the dialog that opens a WhatsApp link.
			_("Open a WhatsApp link"),
			value=copied if messageText.isWhatsAppLink(copied) else "",
		)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			link = dialog.GetValue().strip()
		finally:
			dialog.Destroy()
		if link:
			self.openWhatsAppLink(link)

	def openWhatsAppLink(self, link: str) -> None:
		"""Open a WhatsApp link as WhatsApp does: join a group, follow a channel or start a chat."""
		url = link if "://" in link else "https://" + link
		# Translators: Reported while the add-on asks WhatsApp what a link leads to.
		ui.message(_("Opening link"))
		self._run(lambda: self.session.linkInfo(url), self._gotLinkInfo)

	def _gotLinkInfo(self, info: dict) -> None:
		kind = info.get("kind")
		if kind == "group":
			self._offerGroup(info)
		elif kind == "channel":
			self._offerChannel(info)
		elif kind == "chat":
			phone, text = info["phone"], info.get("text") or ""

			def opened(chat: dict) -> None:
				if text and not self._drafts.get(chat["id"]):
					self._drafts[chat["id"]] = text
				self.openChat(chat)

			self._run(lambda: self.session.chatWithNumber(phone), opened)
		elif kind == "call":
			# Translators: Reported for a WhatsApp call link, which the add-on cannot join yet.
			ui.message(_("Call links cannot be joined from WhatsApp Access yet. Open it on your phone."))
		else:
			# Translators: Reported for a WhatsApp link the add-on does not know how to open.
			ui.message(_("WhatsApp Access cannot open this kind of link."))

	def _offerGroup(self, info: dict) -> None:
		if info.get("inGroup") and info.get("chat"):
			self.openChat(info["chat"])
			return
		if info.get("requested"):
			ui.message(
				# Translators: Reported for a group link when the user already asked to join and its admins have
				# not answered yet.
				_("You already asked to join {name}. Its admins have not answered yet.").format(
					name=info["name"]
				)
			)
			return
		lines = []
		if info.get("community"):
			# Translators: The community a group belongs to, in the question before joining it.
			lines.append(_("In the community {name}").format(name=info["community"]))
		if info.get("size"):
			# Translators: How many people a group has, in the question before joining it.
			lines.append(_("{count} members").format(count=info["size"]))
		if info.get("description"):
			lines.append(info["description"][:500])
		if info.get("needsApproval"):
			# Translators: Asked before asking to join a group whose admins approve new members.
			question = _("Ask to join {name}? Its admins approve new members.").format(name=info["name"])
		else:
			# Translators: Asked before joining a group from its invite link.
			question = _("Join {name}?").format(name=info["name"])
		# Translators: The title of the question before joining a group from its link.
		title = _("Join group")
		if not askYesNo(self, "\n\n".join([question, *lines]), title, warning=False):
			return

		def done(result: dict) -> None:
			if result.get("requested"):
				# Translators: Reported after asking to join a group whose admins approve new members.
				ui.message(_("Request sent. You join when an admin approves it."))
				return
			# Translators: Reported after joining a group from its link.
			ui.message(_("Joined {name}").format(name=info["name"]))
			self.refreshChats()
			if result.get("chat"):
				self.openChat(result["chat"])

		self._run(lambda: self.session.joinGroupLink(info["code"]), done)

	def _offerChannel(self, info: dict) -> None:
		chat = info["chat"]
		if info.get("following"):
			self.openChat(chat)
			return
		lines = []
		if info.get("followers"):
			# Translators: How many people follow a channel, in the question before following it.
			lines.append(_("{count} followers").format(count=info["followers"]))
		if info.get("description"):
			lines.append(info["description"][:500])
		# Translators: Asked when the user opens a channel's link, with its name.
		question = _("Follow the channel {name}?").format(name=info["name"])
		answer = askThreeWay(
			self,
			"\n\n".join([question, *lines]),
			# Translators: The title of the question when opening a channel's link.
			_("Channel"),
			# Translators: A button that follows a channel and opens it.
			_("&Follow"),
			# Translators: A button that opens a channel without following it.
			_("&Open without following"),
			# Translators: A button that closes the question.
			_("Cancel"),
		)
		if answer == wx.ID_CANCEL:
			return
		if answer == wx.ID_NO:
			self.openChat(chat)
			return

		def followed(result: Any) -> None:
			# Translators: Reported after following a channel, with its name.
			ui.message(_("Following {name}").format(name=info["name"]))
			self.openChat(chat)

		self._run(lambda: self.session.followChannel(chat["id"], True), followed)

	def _markAllRead(self) -> None:
		if not askYesNo(
			self,
			# Translators: Asked before marking every chat as read.
			_("Mark all chats as read? People who turned on read receipts see that you read their messages."),
			# Translators: The title of the question before marking every chat as read.
			_("Mark all as read"),
			warning=False,
		):
			return

		def done(count: int) -> None:
			if count:
				# Translators: Reported after marking every chat as read, with how many were unread.
				ui.message(_("{count} chats marked as read").format(count=count))
			else:
				# Translators: Reported when "mark all as read" found no unread chats.
				ui.message(_("No unread chats"))
			self.refreshChats()

		self._run(self.session.markAllRead, done)

	def _selectedChat(self) -> dict | None:
		if self.tabs.GetSelection() == self.TAB_ARCHIVED:
			index = self.archivedList.GetSelection()
			if index == wx.NOT_FOUND or index >= len(self._archivedChats):
				return None
			return self._archivedChats[index]
		index = self.chatList.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._shownChats):
			return None
		return self._shownChats[index]

	def _onChatListKey(self, evt: wx.KeyEvent) -> None:
		if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._openSelectedChat()
			return
		if evt.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not evt.HasAnyModifiers():
			self._deleteChats()
			return
		evt.Skip()

	def _switchChat(self, step: int) -> None:
		"""Ctrl+Tab and Ctrl+Shift+Tab in a chat: open the next or previous chat of the list it came from."""
		if not self.chat:
			return
		if self._recording or self._hasRecording:
			# Moving on would leave the voice note behind, or send it to the wrong chat.
			sounds.play(sounds.DISCARD)
			# Translators: Read out when Ctrl+Tab is pressed while a voice note is recorded or not sent yet.
			ui.message(_("Send the voice note with Ctrl+Shift+R or throw it away with Ctrl+D first"))
			return
		archived = self.tabs.GetSelection() == self.TAB_ARCHIVED
		chats, listBox = (
			(self._archivedChats, self.archivedList) if archived else (self._shownChats, self.chatList)
		)
		ids = [c["id"] for c in chats]
		if self.chat["id"] in ids:
			index = (ids.index(self.chat["id"]) + step) % len(ids)
		elif chats:
			index = 0 if step > 0 else len(chats) - 1
		else:
			index = -1
		if index < 0 or chats[index]["id"] == self.chat["id"]:
			# Translators: Read out when Ctrl+Tab finds no other chat to move to.
			ui.message(_("No other chat"))
			return
		listBox.SetSelection(index)
		self.openChat(chats[index])
		ui.message(chats[index].get("title", ""))

	def _openSelectedChat(self) -> None:
		chat = self._selectedChat()
		if chat is not None:
			self.openChat(chat)

	def _markSeenSoon(self) -> None:
		"""Mark the open chat read shortly after messages arrive in it.

		WhatsApp counts a new message as unread just after announcing it, so marking it read at once
		would come too early; several messages in a row are marked read together.
		"""
		if self._seenTimer is not None:
			self._seenTimer.Stop()
		self._seenTimer = wx.CallLater(MARK_SEEN_DELAY_MS, self._markSeenNow)

	def _markSeenNow(self) -> None:
		self._seenTimer = None
		if self.chat:
			chatId = self.chat["id"]
			self._run(lambda: self.session.markSeen(chatId), onError=lambda e: None)

	def _keepDraft(self) -> None:
		if not self.chat:
			return
		# An unfinished edit is dropped; what the box held before it is the draft.
		self._cancelEdit(announce=False)
		# Leaving the chat: whatever arrived while it was open has been read.
		if self._seenTimer is not None:
			self._seenTimer.Stop()
			self._seenTimer = None
		self._markSeenNow()
		text = self.composeBox.GetValue()
		if text.strip():
			self._drafts[self.chat["id"]] = text
		else:
			self._drafts.pop(self.chat["id"], None)
		self._stopTyping()

	def _focusInConversation(self) -> bool:
		"""Whether a chat is open and the focus is in it, not in the chat list or another section beside it."""
		if self.chat is None or not self.conversationPanel.IsShown():
			return False
		focus = wx.Window.FindFocus()
		while focus is not None:
			if focus is self.conversationPanel:
				return True
			focus = focus.GetParent()
		return False

	def showChats(self) -> None:
		"""Close the open chat (Escape or Ctrl+W); the section beside it, usually the chat list, gets the focus."""
		self._keepDraft()
		# A voice note belongs to the chat it was recorded in; one left behind could be sent to the next.
		if self._recording or self._hasRecording:
			self._discardRecording()
		self._stopPlayback()
		if self.chat is not None:
			sounds.play(sounds.CHAT_CLOSE)
			self._run(lambda: self.session.watchPresence(""))
		self.chat = None
		self._messages = []
		self.conversationPanel.Hide()
		# Translators: The title of the add-on's window.
		self.SetTitle(_("WhatsApp"))
		self.Layout()
		self._focusTab(self.tabs.GetSelection())
		self.refreshChats()

	# A conversation -------------------------------------------------------------------------------------

	def openChat(self, chat: dict) -> None:
		self._keepDraft()
		if self.chat is not None and self.chat["id"] != chat["id"]:
			self._stopPlayback()
		# A voice note belongs to the chat it was recorded in; never carry it to another one.
		if (self._recording or self._hasRecording) and self._recordingChatId != chat["id"]:
			self._discardRecording()
		self.chat = chat
		sounds.play(sounds.CHAT_OPEN)
		self.chatButton.SetLabel(self._headerLabel(chat, ""))
		# Channels have no calls, and only their admins post in them.
		isChannel = bool(chat.get("isChannel"))
		self.callButton.Show(not isChannel)
		self._canWrite = bool(chat.get("canPost")) if isChannel else chat.get("canSend", True) is not False
		self.composeBox.Show(self._canWrite)
		self.cannotSendBox.ChangeValue("" if self._canWrite else messageText.cannotSendText(chat))
		self.cannotSendBox.Show(not self._canWrite)
		self.messageList.Set([])
		self._messages = []
		self._selectedMessageIds = set()
		self.composeBox.Clear()
		self._cancelReply(announce=False)
		self._presence = None
		self._presenceText = ""
		self._participants = []
		self._mentions = {}
		self._attachments = []
		self._asDocuments = set()
		draft = self._drafts.get(chat["id"], "")
		if draft:
			self.composeBox.ChangeValue(draft)
			self.composeBox.SetInsertionPointEnd()
		self._closeMentions()
		self._closeEmoji()
		# Translators: The add-on's window title while a chat is open, such as "Budi - WhatsApp".
		self.SetTitle(_("{chat} - WhatsApp").format(chat=messageText.windowTitleName(chat.get("title", ""))))
		self.conversationPanel.Show()
		self.Layout()
		chatId = chat["id"]
		self._unreadAtOpen = int(chat.get("unread") or 0)
		self._firstUnreadId: str | None = None
		# Load enough to reach the first unread message, as WhatsApp opens a chat there.
		count = min(MAX_MESSAGES_TO_REACH_UNREAD, max(MESSAGES_TO_LOAD, self._unreadAtOpen + 10))

		def load() -> list[dict]:
			try:
				self.session.openInWhatsApp(chatId)
			except WhatsAppError as e:
				log.debugWarning(f"WhatsApp Access: could not open the chat in WhatsApp's view: {e}")
			messages = self.session.messages(chatId, count)
			try:
				self.session.markSeen(chatId)
			except WhatsAppError as e:
				log.debugWarning(f"WhatsApp Access: could not mark the chat as read: {e}")
			return messages

		def loadFailed(error: Exception) -> None:
			# Only if that chat is still open: the user may have moved on to another one meanwhile.
			if self.chat and self.chat["id"] == chatId:
				self.showChats()

		self._run(load, lambda messages: self._gotMessages(chatId, messages, opening=True), loadFailed)
		self._updateButtons()
		# Meta AI has no online or last seen, which would read as "no info".
		if isChannel or chat.get("isAi"):
			return
		self._run(
			lambda: self.session.watchPresence(chatId), lambda presence: self.onPresence(chatId, presence)
		)
		if chat.get("isGroup"):
			self._run(
				lambda: self.session.participants(chatId),
				lambda people: self._gotParticipants(chatId, people),
			)

	def _gotMessages(self, chatId: str, messages: list[dict], opening: bool = False) -> None:
		if not self.chat or self.chat["id"] != chatId:
			return
		self._messages = messages
		isGroup = self.chat.get("isGroup", False)
		self.messageList.Set([messageText.messageLine(m, isGroup) for m in messages])
		# Once the selection below is made, which sends no event: the slider follows the message chosen.
		wx.CallAfter(self._showPositionSlider)
		# Opened from a starred message or a search result: go to that message.
		goTo, self._goToMessageId = self._goToMessageId, None
		if opening and goTo:
			index = next((i for i, m in enumerate(messages) if m.get("id") == goTo), -1)
			if index >= 0:
				self.messageList.SetSelection(index)
				self.messageList.SetFocus()
				return
		if opening:
			self._firstUnreadId = messageText.firstUnreadId(messages, self._unreadAtOpen)
			if self._goToFirstUnread(announce=self._firstUnreadId is not None):
				return
		if messages:
			self.messageList.SetSelection(len(messages) - 1)
		self.messageList.SetFocus()

	def _selectedMessage(self) -> dict | None:
		index = self.messageList.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._messages):
			return None
		return self._messages[index]

	def _onMessageListKey(self, evt: wx.KeyEvent) -> None:
		key = evt.GetKeyCode()
		if key in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not evt.HasAnyModifiers():
			self._deleteChoice()
			return
		if key == ord("C") and evt.GetModifiers() == wx.MOD_CONTROL:
			self._copySelected()
			return
		if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._activateMessage()
			return
		if key in (wx.WXK_UP, wx.WXK_HOME, wx.WXK_PAGEUP) and self.messageList.GetSelection() == 0:
			self._loadEarlier()
			return
		evt.Skip()

	def _activateMessage(self) -> None:
		message = self._selectedMessage()
		if message is None:
			return
		if message.get("type") == "poll_creation":
			self._showPoll(message)
			return
		if message.get("type") == "event_creation":
			self._showEvent(message)
			return
		if message.get("type") in PLAYED_TYPES:
			if self._playingId == message["id"]:
				# Enter again pauses, and once more goes on from there, as WhatsApp's play button does.
				# Escape stops.
				self._togglePlaybackPause(message)
				return
			# Started by the user: a new run of voice messages, if more follow.
			self._voiceRun = False
			self._playVoice(message)
		elif message.get("type") in OPENED_TYPES:
			self._openFile(message)
		else:
			ui.message(messageText.messageLine(message, bool(self.chat and self.chat.get("isGroup"))))

	# Files in messages ----------------------------------------------------------------------------------

	def _openFile(self, message: dict) -> None:
		"""Enter on a photo, video or document: download it and open it with its usual Windows program.

		Only pictures, video, sound and documents without macros are opened. Anyone can send a program
		named like a document, such as "invoice.pdf.exe", so anything else is removed again and the
		user is told to save it with Alt+D instead.
		"""
		folder = dataFolder.tempMediaPath()
		os.makedirs(folder, exist_ok=True)

		def opened(path: str) -> None:
			name = os.path.basename(path)
			if not fileSafety.isSafeToOpen(path):
				try:
					os.remove(path)
				except OSError:
					pass
				ui.message(
					# Translators: Reported when Enter is pressed on a file that could be a program or a script,
					# such as invoice.pdf.exe. {name} is the file's name.
					_(
						"{name} was not opened: files of this kind can run programs. If you trust the sender, "
						"save it with Alt+D."
					).format(name=name)
				)
				return
			try:
				os.startfile(path)
			except OSError as e:
				log.debugWarning(f"WhatsApp Access: could not open {path}: {e}")
				# Translators: Reported when Windows has no program to open a downloaded file.
				ui.message(_("Windows has no program to open {name}").format(name=name))

		# Translators: Reported while a photo, video or document is downloaded before it opens.
		ui.message(_("Opening…"))
		# The mark from the internet is required: without it, Office opens macros and SmartScreen is silent.
		self._run(lambda: self.session.download(message["id"], folder=folder, requireMark=True), opened)

	def _saveFile(self, message: dict | None = None, parent: wx.Window | None = None) -> None:
		"""Alt+D: save the message's file where the user chooses, under WhatsApp's name for it."""
		message = message or self._selectedMessage()
		if message is None or message.get("type") not in FILE_TYPES:
			# Translators: Reported when the user asks to save a message that has no file.
			ui.message(_("This message has no file"))
			return

		def ask(name: str) -> None:
			# The status viewer that asked may have been closed while WhatsApp answered.
			owner = parent if parent else self
			dialog = wx.FileDialog(
				owner,
				# Translators: The title of the dialog for saving a file from a message.
				_("Save file"),
				defaultDir=os.path.join(os.path.expanduser("~"), "Downloads"),
				defaultFile=name,
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
			)
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				path = dialog.GetPath()
			finally:
				dialog.Destroy()
			# Translators: Reported while a file from a message is downloaded.
			ui.message(_("Saving…"))

			def saved(savedPath: str) -> None:
				sounds.play(sounds.SENT)
				ui.message(
					# Translators: Reported after a file was saved, with its name and folder.
					_("Saved {name} in {folder}").format(
						name=os.path.basename(savedPath), folder=os.path.dirname(savedPath)
					)
				)

			self._run(lambda: self.session.download(message["id"], path=path), saved)

		self._run(lambda: self.session.suggestedFileName(message["id"]), ask)

	# Links, search, forwarding, receipts and photos -----------------------------------------------------

	def _startCall(self) -> None:
		"""Ctrl+Shift+C: a voice call to the person in this chat, or to everyone in a group, as the More
		options menu and the Calls section already offer. The call window takes it from there."""
		if not self.chat:
			return
		chatId = self.chat["id"]
		if self.chat.get("isGroup"):
			self._run(lambda: self.session.startGroupCall(chatId))
			return
		self._run(lambda: self.session.startCall(chatId))

	def _openLinks(self) -> None:
		"""Alt+L: open a link in the message in the browser; with several, choose which."""
		message = self._selectedMessage()
		if message is None:
			return
		links = messageText.linksIn(message.get("text") or message.get("caption") or "")
		if not links:
			# Translators: Reported when the selected message has no web links.
			ui.message(_("No links in this message"))
			return
		if len(links) == 1:
			self._openLink(links[0])
			return
		menu = wx.Menu()
		for link in links:
			item = menu.Append(wx.ID_ANY, link)
			menu.Bind(wx.EVT_MENU, lambda evt, link=link: self._openLink(link), item)
		self.messageList.PopupMenu(menu)
		menu.Destroy()

	def _openLink(self, link: str) -> None:
		if messageText.isWhatsAppLink(link):
			# Groups, channels and wa.me chats open here, as in WhatsApp, not in the browser.
			self.openWhatsAppLink(link)
			return
		url = link if "://" in link else "https://" + link
		# Translators: Reported when a link from a message opens in the browser.
		ui.message(_("Opening {link}").format(link=link))
		webbrowser.open(url)

	def _searchMessages(self) -> None:
		"""Ctrl+F: messages in this chat containing some text, older ones included; Enter goes to one."""
		if not self.chat:
			return
		dialog = wx.TextEntryDialog(
			self,
			# Translators: Asks what to look for in a chat's messages.
			_("Find messages containing:"),
			# Translators: The title of the dialog for searching a chat's messages.
			_("Search messages"),
		)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			query = dialog.GetValue().strip()
		finally:
			dialog.Destroy()
		if not query:
			return
		chat = self.chat

		def search() -> tuple[list[dict], list[dict]]:
			found = self.session.searchMessages(chat["id"], query)
			return found, self.session.allMessages(chat["id"])

		def show(result: tuple[list[dict], list[dict]]) -> None:
			found, everything = result
			if self.chat is not chat:
				return
			if not found:
				# Translators: Reported when no message in the chat contains the searched text.
				ui.message(_("No messages contain {text}").format(text=query))
				return
			self._gotMessages(chat["id"], everything)
			isGroup = bool(chat.get("isGroup"))
			dialog = ListDialog(
				self,
				# Translators: The title of the list of messages found, with how many.
				_("{count} messages found").format(count=len(found)),
				[messageText.messageLine(m, isGroup) for m in reversed(found)],
			)
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				choice = list(reversed(found))[dialog.selection()]
			finally:
				dialog.Destroy()
			for index, message in enumerate(self._messages):
				if message.get("id") == choice.get("id"):
					self.messageList.SetSelection(index)
					break
			self.messageList.SetFocus()

		# Translators: Reported while older messages are searched.
		ui.message(_("Searching…"))
		self._run(search, show)

	def _forward(self) -> None:
		"""Alt+F: forward the message, or the selected ones, to one or more chats chosen from a list."""
		chosenMessages = self._chosenMessages()
		if not chosenMessages or not self._chats:
			return
		dialog = ChatPickerDialog(self, self._chats)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			chosen = dialog.chosen()
		finally:
			dialog.Destroy()
		self.messageList.SetFocus()
		if not chosen:
			return

		def done(result: Any) -> None:
			sounds.play(sounds.SENT)
			# Translators: Reported after a message was forwarded, with where to.
			ui.message(_("Forwarded to {chats}").format(chats=", ".join(c.get("title", "") for c in chosen)))

		ids = [m["id"] for m in chosenMessages]
		self._run(lambda: self.session.forward(ids, [c["id"] for c in chosen]), done)
		self._clearSelection(self.messageList, announce=False)

	def _showReceipts(self) -> None:
		"""Alt+I: for one of the user's messages, who received, read and played it, and when."""
		message = self._selectedMessage()
		if message is None:
			return
		if not message.get("fromMe"):
			# Translators: Reported when asking for message info on someone else's message.
			ui.message(_("Message info is only for your own messages"))
			return

		def show(receipts: dict) -> None:
			dialog = TextDialog(
				self,
				# Translators: The title of the message info window.
				_("Message info"),
				"\n".join(messageText.receiptLines(receipts, bool(self.chat and self.chat.get("isGroup")))),
			)
			try:
				dialog.ShowModal()
			finally:
				dialog.Destroy()
			self.messageList.SetFocus()

		self._run(lambda: self.session.messageReceipts(message["id"]), show)

	def _describePhoto(self) -> None:
		"""Alt+P: Meta AI describes the photo, and the description is read out."""
		self._describeFile(self._selectedMessage())

	def _describeFile(self, message: dict | None) -> None:
		"""Send a photo to the chat with Meta AI with a question, as the user could in WhatsApp, and read
		out its answer. The photo and the answer stay in the chat with Meta AI."""
		if message is None or message.get("type") not in ("image", "sticker"):
			# Translators: Reported when asking for a description of a message that is not a photo.
			ui.message(_("This message has no photo"))
			return
		question = messageText.describeQuestion(config.conf[CONFIG_SECTION]["describeQuestion"])

		# Translators: Reported while Meta AI describes a photo.
		ui.message(_("Asking Meta AI to describe the photo…"))
		self._run(lambda: self.session.describePhoto(message["id"], question), ui.message)

	# Reading, copying, reacting and deleting with keys -------------------------------------------------

	def _showShortcuts(self) -> None:
		"""Ctrl+/: every keyboard shortcut, as WhatsApp lists its own."""
		# Translators: The title of the window listing the keyboard shortcuts (Ctrl+/).
		dialog = TextDialog(self, "", shortcuts.shortcutsText(), title=_("Keyboard shortcuts"))
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()

	# Translating, only when the user presses Ctrl+T -------------------------------------------------------

	def _translateMessage(self) -> None:
		"""Ctrl+T on a message: read it in the user's language. Twice quickly: show it to read by line."""
		message = self._selectedMessage()
		if message is None:
			return
		text = message.get("text") or message.get("caption") or ""
		if not text.strip():
			# Translators: Reported when the selected message has no text to read, such as a sticker.
			ui.message(_("This message has no text"))
			return
		last = self._lastTranslation
		if last and last[0] == message["id"] and time.monotonic() - last[1] < TRANSLATION_REPEAT_SECONDS:
			self._showTranslation(message, last[2])
			return
		if self._translatingId == message["id"]:
			# Pressed again before Google answered: show the translation as soon as it comes.
			self._showWhenTranslated = True
			return
		target = messagesLanguage()
		self._translatingId, self._showWhenTranslated = message["id"], False

		def done(result: tuple[str, str]) -> None:
			translation, source = result
			self._lastTranslation = (message["id"], time.monotonic(), translation)
			if self._translatingId != message["id"]:
				# Another message was asked for meanwhile; its own answer speaks for it.
				return
			show = self._showWhenTranslated
			self._translatingId, self._showWhenTranslated = None, False
			if show:
				self._showTranslation(message, translation)
			elif source and source.split("-")[0] == target.split("-")[0]:
				# Translators: Said when Ctrl+T finds the message already in the user's language.
				ui.message(_("Already in {language}").format(language=languageName(target)))
			else:
				ui.message(
					# Translators: A message translated with Ctrl+T, with the language it was in.
					_("From {language}: {text}").format(language=languageName(source), text=translation)
				)

		self._translate(text, target, done)

	def _showTranslation(self, message: dict, translation: str) -> None:
		title = _(
			# Translators: The title of the window showing a message translated into the user's language.
			"Translation of a message from {sender}"
		).format(sender=messageText.sender(message))
		dialog = TextDialog(self, "", translation, title=title)
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()

	def _translateMyText(self) -> None:
		"""Ctrl+T in the message box: put what the user wrote into their chosen language, to check before
		sending. Ctrl+T again gives back what they wrote."""
		box = self.composeBox
		text = box.GetValue()
		if self._beforeTranslation is not None and text == self._translatedText:
			self._setComposeText(self._beforeTranslation)
			self._beforeTranslation = None
			# Translators: Said when Ctrl+T in the message box puts back what the user wrote before translating.
			ui.message(_("Your own words back: {text}").format(text=box.GetValue()))
			return
		if not text.strip():
			# Translators: Said when Ctrl+T is pressed in an empty message box.
			ui.message(_("Write the message first, then Ctrl+T translates it"))
			return
		target = config.conf[CONFIG_SECTION]["translateMyTextTo"] or "en"

		def done(result: tuple[str, str]) -> None:
			translation, source = result
			if box.GetValue() != text:
				return
			if source and source.split("-")[0] == target.split("-")[0]:
				# Translators: Reported when Ctrl+T is pressed on a message already in the language to translate into.
				ui.message(_("Already in {language}").format(language=languageName(target)))
				return
			self._beforeTranslation = text
			self._translatedText = translation
			self._setComposeText(translation)
			# Translators: Said after Ctrl+T translated the user's message; Enter sends it, Ctrl+T undoes it.
			ui.message(
				withHint(
					# Translators: What the user wrote, translated with Ctrl+T, with the language it is now in.
					_("In {language}: {text}").format(language=languageName(target), text=translation),
					# Translators: A hint after the user's message was translated.
					_("Enter sends it, Ctrl+T gives back your own words"),
				)
			)

		self._translate(text, target, done)

	def _setComposeText(self, text: str) -> None:
		self.composeBox.ChangeValue(text)
		self.composeBox.SetInsertionPointEnd()
		self._updateButtons()

	def _translate(self, text: str, target: str, done: Callable[[tuple[str, str]], None]) -> None:
		def failed(error: Exception) -> None:
			self._translatingId, self._showWhenTranslated = None, False
			log.debugWarning(f"WhatsApp Access: translating: {error}")
			# Translators: Said when Ctrl+T could not reach Google Translate.
			ui.message(_("Could not translate. Check the internet connection and try again"))

		def work() -> None:
			try:
				result = translator.translate(text, target)
			except translator.TranslationError as e:
				wx.CallAfter(failed, e)
				return
			wx.CallAfter(self._done, done, result)

		# Translators: Said while a message is being translated.
		ui.message(_("Translating"))
		threading.Thread(target=work, name="whatsAppAccess.translate", daemon=True).start()

	def _readText(self) -> None:
		"""Alt+C: the message's text alone, in a box to read by character, word or line."""
		message = self._selectedMessage()
		if message is None:
			return
		text = message.get("text") or message.get("caption") or ""
		if not text:
			# Translators: Reported when the selected message has no text to read, such as a sticker.
			ui.message(_("This message has no text"))
			return
		dialog = TextDialog(self, messageText.sender(message), text)
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()
		self.messageList.SetFocus()

	def _copySelected(self) -> None:
		chosen = self._chosenMessages()
		if len(chosen) > 1:
			self._copy(messageText.copiedText(chosen))
			return
		message = self._selectedMessage()
		if message is not None:
			text = message.get("text") or message.get("caption") or ""
			if text:
				self._copy(text)
			else:
				# Translators: Reported when copying a message that has no text, such as a voice message.
				ui.message(_("This message has no text"))

	def _reactMenu(self) -> None:
		"""Alt+Y: the emoji to react with, as WhatsApp's reaction bar."""
		message = self._selectedMessage()
		if message is None:
			return

		def show(reactions: list[dict]) -> None:
			if self._selectedMessage() is not message:
				return
			message["reactions"] = reactions
			self._refreshMessageLine(message)
			menu = self._buildReactMenu(message, reactions)
			self.messageList.PopupMenu(menu)
			menu.Destroy()

		self._run(lambda: self.session.reactions(message["id"]), show)

	def _buildReactMenu(self, message: dict, reactions: list[dict]) -> wx.Menu:
		"""The six emoji, with how many chose each and which is the user's; Remove only if there is one."""
		menu = wx.Menu()
		counts = {r["emoji"]: r for r in reactions}
		mine = next((r["emoji"] for r in reactions if r.get("mine")), "")
		emojis = list(self.REACTIONS) + [e for e in counts if e not in self.REACTIONS]
		for emoji in emojis:
			label = emoji
			if emoji in counts:
				label = f"{emoji} {counts[emoji]['count']}"
			if emoji == mine:
				# Translators: In the React menu, the emoji the user reacted with, such as "👍 2 (yours)".
				label = _("{reaction} (yours)").format(reaction=label)
			item = menu.Append(wx.ID_ANY, label)
			menu.Bind(wx.EVT_MENU, lambda evt, emoji=emoji: self._react(message, emoji), item)
		if mine:
			# Translators: In a message's React menu: takes away the user's reaction.
			item = menu.Append(wx.ID_ANY, _("Remove my reaction"))
			menu.Bind(wx.EVT_MENU, lambda evt: self._react(message, ""), item)
		return menu

	def _deleteChoice(self) -> None:
		"""Delete: ask whether to delete for the user only or for everyone, as WhatsApp does."""
		if self._selectedMessageIds:
			self._deleteSelectedMessages()
			return
		message = self._selectedMessage()
		if message is None:
			return
		chatId = self.chat["id"] if self.chat else None

		def ask(actions: dict) -> None:
			if not self.chat or self.chat["id"] != chatId:
				# The chat was left while WhatsApp answered: no question about a message no longer here.
				return
			dialog = DeleteDialog(self, self._replySummary(message), bool(actions.get("deleteForEveryone")))
			try:
				choice = dialog.ShowModal()
			finally:
				dialog.Destroy()
			if choice not in (DeleteDialog.FOR_ME, DeleteDialog.FOR_EVERYONE):
				return
			forEveryone = choice == DeleteDialog.FOR_EVERYONE

			def done(result: Any) -> None:
				if not forEveryone:
					self._removeMessage(message)
				sounds.play(sounds.DISCARD)
				# Translators: Reported after a message was deleted.
				ui.message(_("Deleted"))

			self._run(lambda: self.session.deleteMessage(message["id"], forEveryone), done)

		self._run(lambda: self.session.messageActions(message["id"]), ask)

	def _togglePlaybackPause(self, message: dict) -> None:
		def done(state: str) -> None:
			if state == "stopped":
				# It had ended meanwhile: play it again from the start.
				self._playVoice(message)
			elif state == "paused":
				sounds.play(sounds.PAUSE)

		self._run(self.session.togglePause, done)

	def _stopPlayback(self) -> None:
		self._voiceRun = False
		if self._playingId is not None:
			self._playingId = None
			self._run(self.session.stopAudio)

	def _playbackEnded(self) -> None:
		self._playingId = None

	def _loadEarlier(self) -> None:
		if self._loadingEarlier or not self._messages or not self.chat:
			return
		self._loadingEarlier = True
		chatId, firstId = self.chat["id"], self._messages[0]["id"]
		self._run(
			lambda: self.session.loadEarlier(chatId, firstId),
			lambda earlier: self._gotEarlier(chatId, earlier),
			lambda e: setattr(self, "_loadingEarlier", False),
		)

	def _gotEarlier(self, chatId: str, earlier: list[dict]) -> None:
		self._loadingEarlier = False
		if not self.chat or self.chat["id"] != chatId:
			return
		if not earlier:
			# Translators: Reported at the top of a conversation when there are no older messages.
			ui.message(_("No earlier messages"))
			return
		isGroup = self.chat.get("isGroup", False)
		self._messages = earlier + self._messages
		self.messageList.InsertItems([messageText.messageLine(m, isGroup) for m in earlier], 0)
		self.messageList.SetSelection(len(earlier) - 1)
		# Translators: Reported after older messages were added at the top of a conversation.
		ui.message(_("{count} earlier messages").format(count=len(earlier)))

	def _sendText(self) -> None:
		if self._mentionIndex >= 0:
			self._insertMention()
			return
		if self._emojiIndex >= 0:
			self._insertEmoji()
			return
		if self._editing is not None:
			self._saveEdit()
			return
		if self._attachments:
			self._sendAttachments()
			return
		text = self.composeBox.GetValue()
		if not text.strip() or not self.chat:
			return
		chatId = self.chat["id"]
		quotedId = self._replyTo["id"] if self._replyTo else ""
		mentions = [{"id": pid, "name": name} for name, pid in self._mentions.items() if f"@{name}" in text]
		# The box empties at once, as in WhatsApp, so the next message can be typed while this one goes.
		# Each message is sent once, after the ones before it; one that fails comes back to the box.
		self.composeBox.Clear()
		self._drafts.pop(chatId, None)
		self._mentions = {}
		if self._replyTo is not None:
			self._cancelReply(announce=False)
		self._textQueue.setdefault(chatId, []).append((text, quotedId, mentions))
		if chatId not in self._sendingIn:
			self._sendNextText(chatId)

	def _sendNextText(self, chatId: str) -> None:
		queue = self._textQueue.get(chatId)
		if not queue:
			self._textQueue.pop(chatId, None)
			self._sendingIn.discard(chatId)
			return
		text, quotedId, mentions = queue.pop(0)
		self._sendingIn.add(chatId)

		def sent(result: Any) -> None:
			sounds.play(sounds.SENT)
			# Translators: Reported after a message was sent.
			ui.message(_("Sent"))
			self._sendNextText(chatId)

		def failed(error: Exception) -> None:
			self._sendingIn.discard(chatId)
			# This one and those waiting after it go back to the box, in order, ahead of anything typed since.
			unsent = [text, *(waiting[0] for waiting in self._textQueue.pop(chatId, []))]
			if self.chat and self.chat["id"] == chatId:
				typed = self.composeBox.GetValue()
				self.composeBox.SetValue("\n".join([*unsent, typed] if typed else unsent))
				self.composeBox.SetInsertionPointEnd()
			else:
				typed = self._drafts.get(chatId, "")
				self._drafts[chatId] = "\n".join([*unsent, typed] if typed else unsent)

		self._run(lambda: self.session.sendText(chatId, text, quotedId, mentions), sent, failed)

	# Attaching files ------------------------------------------------------------------------------------

	def _attachMenu(self) -> None:
		"""The Attach button: everything that can be sent besides text and voice notes, as WhatsApp's
		attach menu lists it. Events are for groups, as in WhatsApp."""
		if not self.chat or self.chat.get("isChannel"):
			self._chooseFiles("all")
			return
		menu = wx.Menu()
		items = [
			# Translators: An item in the Attach menu: any file, sent as a document even if it is a photo.
			(_("&Document…"), lambda: self._chooseFiles("document")),
			# Translators: An item in the Attach menu: photos and videos, sent to be seen in the chat.
			(_("&Photos and videos…"), lambda: self._chooseFiles("media")),
			# Translators: An item in the Attach menu: sound files, sent to be played in the chat.
			(_("&Audio…"), lambda: self._chooseFiles("audio")),
			# Translators: An item in the Attach menu: sends a contact card.
			(_("&Contact…"), self._sendContact),
			# Translators: An item in the Attach menu: makes a poll.
			(_("P&oll…"), self._createPoll),
		]
		if self.chat.get("isGroup"):
			# Translators: An item in the Attach menu of a group: makes an event.
			items.append((_("&Event…"), self._createEvent))
		# Translators: An item in the Attach menu: sends one of the user's stickers.
		items.append((_("&Sticker…"), self._sendSticker))
		for label, handler in items:
			item = menu.Append(wx.ID_ANY, label)
			menu.Bind(wx.EVT_MENU, lambda evt, handler=handler: handler(), item)
		self.attachButton.PopupMenu(menu)
		menu.Destroy()

	def _chooseFiles(self, kind: str) -> None:
		"""kind: "document", "media", "audio", or "all" for a channel, where only files can be sent."""
		wildcards = {
			# Translators: The kind of files the file picker shows when attaching photos and videos.
			"media": _("Photos and videos")
			+ "|"
			+ ";".join(f"*{e}" for e in sorted(messageText.PHOTO_EXTENSIONS | messageText.VIDEO_EXTENSIONS)),
			# Translators: The kind of files the file picker shows when attaching audio.
			"audio": _("Audio") + "|" + ";".join(f"*{e}" for e in sorted(messageText.AUDIO_EXTENSIONS)),
		}
		dialog = wx.FileDialog(
			self,
			# Translators: The title of the file picker for sending files.
			_("Attach files"),
			wildcard=wildcards.get(kind, "*.*|*.*"),
			style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST,
		)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			paths = dialog.GetPaths()
		finally:
			dialog.Destroy()
		if kind == "document":
			self._asDocuments.update(paths)
		else:
			self._asDocuments.difference_update(paths)
		self._attach(paths)

	def _attachedKind(self, path: str) -> str:
		return "document" if path in self._asDocuments else messageText.fileKind(path)

	def _pasteFiles(self) -> bool:
		"""Ctrl+V in the message box: files copied in File Explorer are attached. Returns whether it did."""
		clipboard = wx.TheClipboard
		if not clipboard.Open():
			return False
		try:
			if not clipboard.IsSupported(wx.DataFormat(wx.DF_FILENAME)):
				return False
			data = wx.FileDataObject()
			if not clipboard.GetData(data):
				return False
			paths = [p for p in data.GetFilenames() if os.path.isfile(p)]
		finally:
			clipboard.Close()
		if not paths:
			return False
		self._attach(paths)
		return True

	def _attach(self, paths: list[str]) -> None:
		self._attachments.extend(p for p in paths if p not in self._attachments)
		self._updateButtons()
		self.composeBox.SetFocus()
		parts = [
			f"{os.path.basename(p)}, {messageText.fileKindName(self._attachedKind(p))}"
			for p in self._attachments
		]
		ui.message(
			withHint(
				# Translators: Read out after files were attached: how many, then each name and how it is sent.
				_("{count} attached: {files}").format(count=len(self._attachments), files="; ".join(parts)),
				# Translators: A hint after files were attached.
				_("Type a caption if you like. Enter sends, Escape removes the files"),
			)
		)

	def _clearAttachments(self) -> None:
		self._attachments = []
		self._asDocuments = set()
		self._updateButtons()
		sounds.play(sounds.DISCARD)
		# Translators: Read out when the user removes the attached files before sending.
		ui.message(_("Attachments removed"))

	def _sendAttachments(self) -> None:
		if not self.chat:
			return
		chatId = self.chat["id"]
		if chatId in self._sendingIn:
			return
		paths = list(self._attachments)
		caption = self.composeBox.GetValue().strip()
		rawCaption = self.composeBox.GetValue()
		quotedId = self._replyTo["id"] if self._replyTo else ""
		sentPaths: list[str] = []
		self._sendingIn.add(chatId)

		def send() -> int:
			for index, path in enumerate(paths):
				kind = self._attachedKind(path)
				mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
				# WhatsApp puts the caption on the first file and the reply on it too.
				first = index == 0
				self.session.sendFile(
					chatId, path, kind, mime, caption if first else "", quotedId if first else ""
				)
				sentPaths.append(path)
			return len(paths)

		def forgetSent() -> None:
			"""Take the files that went out off the list, with the caption and reply that went with them."""
			self._sendingIn.discard(chatId)
			if not sentPaths or not self.chat or self.chat["id"] != chatId:
				return
			self._attachments = [p for p in self._attachments if p not in sentPaths]
			self._asDocuments.difference_update(sentPaths)
			if self.composeBox.GetValue() == rawCaption:
				self.composeBox.Clear()
			if self._replyTo is not None and self._replyTo.get("id") == quotedId:
				self._cancelReply(announce=False)
			self._updateButtons()

		def sent(count: int) -> None:
			forgetSent()
			sounds.play(sounds.SENT)
			# Translators: Reported after files were sent, with how many.
			ui.message(_("{count} sent").format(count=count))

		def failed(error: Exception) -> None:
			forgetSent()
			if sentPaths:
				ui.message(
					# Translators: Reported when sending several files stopped partway. The files that were
					# sent are taken off the list, so Enter sends only the rest.
					_("{sent} of {count} sent; Enter sends the rest").format(
						sent=len(sentPaths), count=len(paths)
					)
				)

		# Translators: Reported while files are being sent; large ones take a while.
		ui.message(_("Sending {count}…").format(count=len(paths)))
		self._run(send, sent, failed)

	# Mentioning people in a group -----------------------------------------------------------------------

	def _gotParticipants(self, chatId: str, people: list[dict]) -> None:
		if self.chat and self.chat["id"] == chatId:
			self._participants = people

	def _onComposeText(self, evt: wx.CommandEvent) -> None:
		self._updateButtons()
		self._updateMentions()
		self._updateEmoji()
		self._typing()

	def _typing(self) -> None:
		"""Show the other person "typing…" while the user writes, as WhatsApp does, and stop after a pause."""
		if not self.chat:
			return
		if not self.composeBox.GetValue().strip():
			self._stopTyping()
			return
		chatId = self.chat["id"]
		if time.monotonic() - self._lastTyping > TYPING_REPEAT_SECONDS:
			self._lastTyping = time.monotonic()
			self._run(lambda: self.session.setTyping(chatId, "composing"), onError=lambda e: None)
		if self._typingTimer is not None:
			self._typingTimer.Stop()
		self._typingTimer = wx.CallLater(TYPING_PAUSE_MS, self._stopTyping)

	def _stopTyping(self) -> None:
		if self._typingTimer is not None:
			self._typingTimer.Stop()
			self._typingTimer = None
		if self._lastTyping and self.chat:
			self._lastTyping = 0.0
			chatId = self.chat["id"]
			self._run(lambda: self.session.setTyping(chatId, "paused"), onError=lambda e: None)

	def _updateMentions(self) -> None:
		"""After "@" and part of a name, offer the group's people whose names start that way."""
		if not self._participants:
			return
		before = self.composeBox.GetValue()[: self.composeBox.GetInsertionPoint()]
		match = _MENTION_PATTERN.search(before)
		if not match:
			self._closeMentions()
			return
		typed = match.group(1).lower()
		matches = [p for p in self._participants if _nameMatches(p, typed)][:MENTION_SUGGESTIONS]
		hadMatches = bool(self._mentionMatches)
		self._mentionMatches = matches
		self._mentionIndex = -1
		if matches and not hadMatches:
			ui.message(
				withHint(
					# Translators: Read out when the user types "@" in a group: how many people can be chosen.
					_("{count} people").format(count=len(matches)),
					# Translators: A hint after the number of people who can be mentioned.
					_("Up and Down Arrow to choose, Enter to add"),
				)
			)

	def _updateEmoji(self) -> None:
		"""After ":" and part of an emoji's name, such as ":grin", offer the emoji, as WhatsApp does."""
		before = self.composeBox.GetValue()[: self.composeBox.GetInsertionPoint()]
		match = _EMOJI_PATTERN.search(before)
		if not match or self._mentionMatches:
			self._closeEmoji()
			return
		typed = match.group(1).lower()

		def found(emoji: list[str]) -> None:
			# Only if the user has not typed on since.
			now = _EMOJI_PATTERN.search(self.composeBox.GetValue()[: self.composeBox.GetInsertionPoint()])
			if not now or now.group(1).lower() != typed:
				return
			hadMatches = bool(self._emojiMatches)
			self._emojiMatches = emoji
			self._emojiIndex = -1
			if emoji and not hadMatches:
				ui.message(
					withHint(
						# Translators: Read out when the user types ":" and part of an emoji's name.
						_("{count} emoji").format(count=len(emoji)),
						# Translators: A hint after the number of emoji offered for what the user typed.
						_("Left and Right Arrow to choose, Enter to add"),
					)
				)

		self._run(
			lambda: self.session.emojiSuggestions(typed.replace("_", " "), EMOJI_SUGGESTIONS),
			found,
			onError=lambda e: None,
		)

	def _closeEmoji(self) -> None:
		self._emojiMatches = []
		self._emojiIndex = -1

	def _moveEmoji(self, step: int) -> None:
		count = len(self._emojiMatches)
		self._emojiIndex = (
			(self._emojiIndex + step) % count if self._emojiIndex >= 0 else (0 if step > 0 else count - 1)
		)
		# NVDA says the emoji's name itself.
		ui.message(
			# Translators: One emoji offered for what the user typed, then its position, such as "😁, 2 of 8".
			_("{emoji}, {position} of {count}").format(
				emoji=self._emojiMatches[self._emojiIndex], position=self._emojiIndex + 1, count=count
			)
		)

	def _insertEmoji(self) -> None:
		emoji = self._emojiMatches[self._emojiIndex]
		text = self.composeBox.GetValue()
		position = self.composeBox.GetInsertionPoint()
		before, after = text[:position], text[position:]
		match = _EMOJI_PATTERN.search(before)
		start = match.end() - len(match.group(1)) - 1 if match else position
		self._closeEmoji()
		self.composeBox.ChangeValue(before[:start] + emoji + after)
		self.composeBox.SetInsertionPoint(start + len(emoji))
		self._updateButtons()
		ui.message(emoji)

	def _closeMentions(self) -> None:
		self._mentionMatches = []
		self._mentionIndex = -1

	def _moveMention(self, step: int) -> None:
		count = len(self._mentionMatches)
		self._mentionIndex = (
			(self._mentionIndex + step) % count if self._mentionIndex >= 0 else (0 if step > 0 else count - 1)
		)
		person = self._mentionMatches[self._mentionIndex]
		ui.message(
			# Translators: One person offered for an @mention: name, then position, such as "Rafli, 2 of 5".
			_("{name}, {position} of {count}").format(
				name=person["name"], position=self._mentionIndex + 1, count=count
			)
		)

	def _insertMention(self) -> None:
		person = self._mentionMatches[self._mentionIndex]
		text = self.composeBox.GetValue()
		position = self.composeBox.GetInsertionPoint()
		before, after = text[:position], text[position:]
		match = _MENTION_PATTERN.search(before)
		start = match.end() - len(match.group(1)) - 1 if match else position
		inserted = f"@{_mentionText(person)} "
		self._mentions[_mentionText(person)] = person["id"]
		self._closeMentions()
		self.composeBox.ChangeValue(before[:start] + inserted + after)
		self.composeBox.SetInsertionPoint(start + len(inserted))
		self._updateButtons()
		# Translators: Read out after the user chose a person to mention.
		ui.message(_("{name} mentioned").format(name=person["name"]))

	# Formatting, as in WhatsApp: *bold*, _italic_ and ~strikethrough~ ------------------------------------

	def _format(self, mark: str, kind: str) -> None:
		"""Ctrl+B, Ctrl+I and Ctrl+Shift+X: put the selected text between the marks, or take them away
		if it has them already. With nothing selected, the marks go in with the caret between them."""
		box = self.composeBox
		start, end = box.GetSelection()
		selected = box.GetValue()[start:end]
		name = _formatName(kind)
		if len(selected) > 2 and selected.startswith(mark) and selected.endswith(mark):
			inner = selected[1:-1]
			box.Replace(start, end, inner)
			box.SetSelection(start, start + len(inner))
			# Translators: Said when formatting such as bold is taken off the selected text.
			ui.message(_("{format} off").format(format=name))
			return
		core = selected.strip()
		if not core:
			box.WriteText(mark * 2)
			box.SetInsertionPoint(box.GetInsertionPoint() - 1)
			ui.message(name)
			return
		# WhatsApp formats only when the marks touch the text, so spaces around it stay outside.
		lead = len(selected) - len(selected.lstrip())
		formatted = mark + core + mark
		box.Replace(start, end, selected[:lead] + formatted + selected[lead + len(core) :])
		box.SetSelection(start + lead, start + lead + len(formatted))
		ui.message(name)

	def _pasteText(self) -> bool:
		"""Ctrl+V in the message box: plain text only, without the colours, fonts or pictures it may carry."""
		clipboard = wx.TheClipboard
		data = wx.TextDataObject()
		if clipboard.Open():
			try:
				has = clipboard.IsSupported(wx.DataFormat(wx.DF_UNICODETEXT)) and clipboard.GetData(data)
			finally:
				clipboard.Close()
			if has:
				self.composeBox.WriteText(data.GetText().replace("\r\n", "\n").replace("\r", "\n"))
		return True

	# Replying to one message ----------------------------------------------------------------------------

	def _showReplies(self, message: dict) -> None:
		"""A community announcement's replies, with a box to reply, as WhatsApp shows them."""
		dialog = RepliesDialog(self, message)
		try:
			dialog.ShowModal()
			count = len(dialog.replies) if dialog.loaded else None
		finally:
			dialog.Destroy()
		# The count after the announcement follows what the replies window found, own replies included.
		if count is not None and count != (message.get("replies") or 0) and message in self._messages:
			message["replies"] = count
			index = self._messages.index(message)
			self.messageList.SetString(
				index, messageText.messageLine(message, self.chat.get("isGroup", False))
			)

	def _startReply(self, message: dict | None = None) -> None:
		message = message or self._selectedMessage()
		if not self.chat:
			return
		if message is None:
			# Translators: Said when the user presses Alt+R but no message is selected in the chat.
			ui.message(_("Select the message to reply to in the messages list first"))
			return
		if self.chat.get("announcementGroup"):
			# In a community's announcements, replies go under the announcement, as in WhatsApp.
			self._showReplies(message)
			return
		if not self._canWrite and self.chat.get("isGroup"):
			if self.chat.get("left") or message.get("fromMe"):
				ui.message(messageText.cannotSendText(self.chat))
			else:
				# Only admins send here: a reply goes to its sender privately, as WhatsApp offers.
				self._replyPrivately(message)
			return
		self._cancelEdit(announce=False)
		self._replyTo = message
		summary = self._replySummary(message)
		# Translators: Shown above the message box while the user replies to one message.
		self.replyingText.SetLabel(_("Replying to {message}").format(message=summary))
		self._updateButtons()
		self.composeBox.SetFocus()
		ui.message(
			withHint(
				# Translators: Reported when the user starts replying to one message.
				_("Replying to {message}").format(message=summary),
				# Translators: A hint after the user starts replying to a message.
				_("Escape cancels the reply"),
			)
		)

	def _replySummary(self, message: dict) -> str:
		text = messageText.content(message)
		if len(text) > 80:
			text = text[:79].rstrip() + "…"
		return f"{messageText.sender(message)}: {text}"

	def _cancelReply(self, announce: bool = True) -> None:
		if self._replyTo is None:
			return
		self._replyTo = None
		self.replyingText.SetLabel("")
		self._updateButtons()
		if announce:
			sounds.play(sounds.DISCARD)
			# Translators: Reported when the user stops replying to a message.
			ui.message(_("Reply cancelled"))
			self.composeBox.SetFocus()

	# Buttons that change with what the user is doing ----------------------------------------------------

	def _updateButtons(self) -> None:
		"""As in WhatsApp: an empty message box offers a voice note, a written message offers Send."""
		hasText = bool(self.composeBox.GetValue().strip())
		if self._recording:
			# Translators: The record button's label while recording; pressing it stops and plays the recording.
			self.recordButton.SetLabel(_("Stop and listen (Ctrl+R)"))
		else:
			# Translators: The record button's label when nothing is being recorded.
			self.recordButton.SetLabel(_("Record voice note (Ctrl+R)"))
		self.pauseButton.SetLabel(
			# Translators: A button that continues a paused voice note recording.
			_("Resume (Ctrl+Shift+D)")
			if self._paused
			# Translators: A button that pauses recording a voice note.
			else _("Pause (Ctrl+Shift+D)")
		)
		shown = {
			self.pauseButton: self._recording,
			self.cancelReplyButton: self._replyTo is not None or self._editing is not None,
			self.sendButton: (hasText or bool(self._attachments))
			and not self._recording
			and not self._hasRecording,
			self.recordButton: (not hasText and not self._attachments and not self._hasRecording)
			or self._recording,
			self.attachButton: not self._recording and not self._hasRecording,
			self.sendVoiceButton: self._hasRecording or self._recording,
			self.listenButton: self._hasRecording,
			self.discardButton: self._hasRecording or self._recording,
		}
		if not getattr(self, "_canWrite", True):
			shown = dict.fromkeys(shown, False)
		changed = False
		for button, show in shown.items():
			if button.IsShown() != show:
				button.Show(show)
				changed = True
		self.cancelReplyButton.SetLabel(
			# Translators: A button that stops editing a message; it stays as it was.
			_("Cancel edit") if self._editing is not None else _("Cancel reply")
		)
		self.replyingText.Show(self._replyTo is not None or self._editing is not None)
		if changed:
			self.conversationPanel.Layout()

	# Voice notes ----------------------------------------------------------------------------------------

	def _toggleRecording(self) -> None:
		"""Ctrl+R: start recording; while recording, stop and listen; afterwards, listen again."""
		if self._recording:
			self._stopRecording(then="listen")
		elif self._hasRecording:
			self._listenToRecording()
		else:
			self._startRecording()

	def _togglePause(self) -> None:
		if not self._recording:
			return

		def done(paused: bool) -> None:
			self._paused = paused
			self._updateButtons()
			sounds.play(sounds.PAUSE if paused else sounds.RECORD_START)
			if paused:
				# Translators: Reported when recording a voice note is paused; a hint follows.
				ui.message(withHint(_("Paused"), _("Ctrl+Shift+D resumes")))
			else:
				# Translators: Reported when recording a voice note continues after a pause.
				ui.message(_("Recording"))

		self._run(self.session.pauseRecording, done)

	def _startRecording(self) -> None:
		if not self.chat or self._recordingStarting:
			# A second Ctrl+R while the microphone is still opening would only cancel the first.
			return
		settings = config.conf[CONFIG_SECTION]
		microphone = settings["microphone"]
		chatId = self.chat["id"]
		# A voice message playing now is left by recording; its end must not start the next one.
		self._playingId = None
		self._voiceRun = False
		self._recordingGeneration += 1
		generation = self._recordingGeneration
		self._recordingStarting = True

		def start() -> dict:
			deviceId = ""
			if microphone:
				deviceId = next((m["id"] for m in self.session.microphones() if m["label"] == microphone), "")
			return self.session.startRecording(
				settings["stereo"], settings["rawMicrophone"], settings["voiceKbps"], deviceId
			)

		def started(result: dict) -> None:
			self._recordingStarting = False
			if generation != self._recordingGeneration or not self.chat or self.chat["id"] != chatId:
				# The user left the chat, or threw the note away, before the microphone was ready.
				self._run(self.session.cancelRecording, onError=lambda e: None)
				return
			self._recording = True
			self._hasRecording = False
			self._recordingChatId = chatId
			self._paused = False
			self._updateButtons()
			self.recordButton.SetFocus()
			sounds.play(sounds.RECORD_START)
			self._run(lambda: self.session.setTyping(chatId, "recording"), onError=lambda e: None)
			ui.message(
				withHint(
					# Translators: Reported when recording a voice note starts; a hint follows.
					_("Recording"),
					# Translators: A hint after recording a voice note starts.
					_("Ctrl+R stops and plays it, Ctrl+Shift+R sends it, Ctrl+D throws it away"),
				)
			)

		def failed(error: Exception) -> None:
			self._recordingStarting = False

		self._run(start, started, failed)

	def _stopRecording(self, then: str = "") -> None:
		"""Stop recording; then "listen" plays it and "send" sends it. Otherwise it waits for the user."""
		if self._recordingStopping:
			# Pressed again before the first stop answered: that one carries on.
			return
		self._recordingStopping = True
		generation = self._recordingGeneration
		chatId = self._recordingChatId

		def stopped(result: dict) -> None:
			self._recordingStopping = False
			if generation != self._recordingGeneration or not self.chat or self.chat["id"] != chatId:
				# Thrown away, or the chat was left, while it stopped: the page must not keep it either.
				self._run(self.session.cancelRecording, onError=lambda e: None)
				return
			self._recording = False
			self._paused = False
			self._hasRecording = True
			self._updateButtons()
			self.sendVoiceButton.SetFocus()
			sounds.play(sounds.RECORD_STOP)
			self._run(lambda: self.session.setTyping(chatId, "paused"), onError=lambda e: None)
			if then == "send":
				self._sendRecording()
				return
			channels = (
				# Translators: Said for a voice note recorded in stereo.
				_("stereo")
				if result.get("channels") == 2
				# Translators: Said for a voice note recorded in mono.
				else _("mono")
			)
			ui.message(
				withHint(
					# Translators: Reported when recording stops. The voice note is not sent yet.
					_("Voice note, {duration}, {channels}").format(
						duration=messageText.duration(result.get("duration", 0)), channels=channels
					),
					# Translators: A hint after recording a voice note stops.
					_("Ctrl+Shift+R sends it, Ctrl+D throws it away"),
				)
			)
			if then == "listen":
				self._listenToRecording()

		def failed(error: Exception) -> None:
			self._recordingStopping = False
			if generation != self._recordingGeneration:
				return
			self._recording = False
			self._paused = False
			self._hasRecording = False
			self._recordingChatId = None
			self._updateButtons()

		self._run(self.session.stopRecording, stopped, failed)

	def onRecordingLimit(self) -> None:
		"""The page stopped a recording that reached its longest length: finish it as if the user had."""
		if not self._recording:
			return
		# Translators: Said when a voice note stops by itself because it reached the longest length.
		ui.message(_("Recording stopped after 30 minutes"))
		self._stopRecording()

	def _sendVoiceNow(self) -> None:
		"""Ctrl+Shift+R: send the voice note, stopping the recording first if needed."""
		if self._recording:
			self._stopRecording(then="send")
		elif self._hasRecording:
			self._sendRecording()

	def _listenToRecording(self) -> None:
		if self._hasRecording:
			# Playing the note leaves any voice message that was playing, without its end.
			self._playingId = None
			self._voiceRun = False
			settings = config.conf[CONFIG_SECTION]
			speed, volume = float(settings["playbackSpeed"]), int(settings["voiceVolume"])
			self._run(
				lambda: (
					self.session.setPlaybackRate(speed),
					self.session.setPlaybackVolume(volume),
					self.session.playRecording(),
				)
			)

	def _discardRecording(self) -> None:
		if self._recordingStarting and not self._recording:
			# Thrown away while the microphone is still opening: when it opens, started() sees the newer
			# generation and cancels it.
			self._recordingGeneration += 1
			sounds.play(sounds.DISCARD)
			# Translators: Said when the user throws away a voice note.
			ui.message(_("Voice note discarded"))
			return
		if not self._recording and not self._hasRecording:
			return
		self._paused = False
		self._recording = False
		self._hasRecording = False
		self._recordingChatId = None
		self._recordingGeneration += 1
		self._updateButtons()
		self._run(self.session.cancelRecording)
		self._run(self.session.stopAudio)
		sounds.play(sounds.DISCARD)
		# Translators: Reported when the user throws away a voice note.
		ui.message(_("Voice note discarded"))
		self.composeBox.SetFocus()

	def _sendRecording(self) -> None:
		if not self._hasRecording or not self.chat:
			return
		chatId = self._recordingChatId
		if chatId != self.chat["id"]:
			# Never happens while leaving a chat throws its voice note away; if it ever does, send nothing.
			log.error("WhatsApp Access: a voice note from another chat was about to be sent; discarding it")
			self._discardRecording()
			return
		if chatId in self._sendingIn:
			return
		generation = self._recordingGeneration
		self._sendingIn.add(chatId)

		def sent(result: Any) -> None:
			self._sendingIn.discard(chatId)
			if generation != self._recordingGeneration:
				return
			self._hasRecording = False
			self._recordingChatId = None
			self._recordingGeneration += 1
			self._updateButtons()
			self.composeBox.SetFocus()
			sounds.play(sounds.SENT)
			# Translators: Reported after a voice note was sent.
			ui.message(_("Voice note sent"))

		self._run(
			lambda: (self.session.stopAudio(), self.session.sendRecording(chatId)),
			sent,
			lambda error: self._sendingIn.discard(chatId),
		)

	# Menus, as in WhatsApp ------------------------------------------------------------------------------

	REACTIONS = ("👍", "❤️", "😂", "😮", "😢", "🙏")

	def _onMessageMenu(self, evt: wx.ContextMenuEvent) -> None:
		if self._selectedMessageIds:
			self._selectedMessagesMenu()
			return
		message = self._selectedMessage()
		if message is None:
			return
		self._run(
			lambda: self.session.messageActions(message["id"]),
			lambda actions: self._showMessageMenu(message, actions),
		)

	def _showMessageMenu(self, message: dict, actions: dict) -> None:
		if not self.conversationPanel.IsShown() or self._selectedMessage() is not message:
			return
		menu = wx.Menu()

		def add(target: wx.Menu, label: str, handler: Callable[[], None]) -> None:
			item = target.Append(wx.ID_ANY, label)
			target.Bind(wx.EVT_MENU, lambda evt: handler(), item)

		if message.get("type") in PLAYED_TYPES:
			# Translators: An item in a voice message's menu.
			add(menu, _("&Play"), self._activateMessage)
		if message.get("type") in OPENED_TYPES:
			# Translators: An item in the menu of a photo, video or document: opens it in Windows.
			add(menu, _("&Open"), lambda: self._openFile(message))
		if message.get("type") in FILE_TYPES:
			# Translators: An item in the menu of a message with a file: saves it.
			add(menu, _("&Download\tAlt+D"), lambda: self._saveFile(message))
		if message.get("type") == "poll_creation":
			# Translators: An item in a poll's menu, like WhatsApp's: shows the options and votes, to vote.
			add(menu, _("&View poll and vote"), lambda: self._showPoll(message))
		if self.chat and self.chat.get("announcementGroup"):
			# Translators: An item in the menu of a community announcement: its replies, and a box to reply.
			add(menu, _("&Replies\tAlt+R"), lambda: self._showReplies(message))
		else:
			# Translators: An item in a message's menu, like WhatsApp's.
			add(menu, _("&Reply\tAlt+R"), lambda: self._startReply(message))
		if actions.get("react"):
			reactMenu = self._buildReactMenu(message, actions.get("reactions") or [])
			# Translators: An item in a message's menu, like WhatsApp's: opens a list of emoji.
			menu.AppendSubMenu(reactMenu, _("R&eact\tAlt+Y"))
		if actions.get("text"):
			# Translators: An item in a message's menu, like WhatsApp's.
			add(menu, _("&Copy"), lambda: self._copy(actions["text"]))
		if actions.get("star"):
			if actions.get("starred"):
				# Translators: An item in a message's menu, like WhatsApp's.
				add(menu, _("Un&star"), lambda: self._star(message, False))
			else:
				# Translators: An item in a message's menu, like WhatsApp's.
				add(menu, _("&Star"), lambda: self._star(message, True))
		if actions.get("edit"):
			# Translators: An item in a message's menu, like WhatsApp's: changes a message the user sent.
			add(menu, _("E&dit"), lambda: self._edit(message, actions))
		if message.get("pinned"):
			# Translators: An item in a message's menu, like WhatsApp's.
			add(menu, _("Un&pin"), lambda: self._pin(message, None))
		elif not (self.chat and self.chat.get("isChannel")):
			pinMenu = wx.Menu()
			for label, duration in (
				# Translators: How long to pin a message, in its Pin menu.
				(_("For 24 hours"), "day"),
				# Translators: How long to pin a message, in its Pin menu.
				(_("For 7 days"), "week"),
				# Translators: How long to pin a message, in its Pin menu.
				(_("For 30 days"), "month"),
			):
				add(pinMenu, label, lambda duration=duration: self._pin(message, duration))
			# Translators: An item in a message's menu, like WhatsApp's: opens how long to pin it.
			menu.AppendSubMenu(pinMenu, _("Pi&n"))
		if self.chat and self.chat.get("isGroup") and not message.get("fromMe"):
			# Translators: An item in a group message's menu, like WhatsApp's: replies in a personal chat.
			add(menu, _("Reply &privately\u2026"), lambda: self._replyPrivately(message))
		if message.get("reactions"):
			# Translators: An item in a message's menu: who reacted with which emoji.
			add(menu, _("&Who reacted"), lambda: self._whoReacted(message))
		if message.get("type") == "event_creation":
			# Translators: An item in an event's menu: its time, place and who is going.
			add(menu, _("Event &details"), lambda: self._showEvent(message))
			eventMenu = wx.Menu()
			for label, answer in (
				# Translators: An answer to an event, like WhatsApp's.
				(_("Going"), "going"),
				# Translators: An answer to an event, like WhatsApp's.
				(_("Maybe"), "maybe"),
				# Translators: An answer to an event, like WhatsApp's.
				(_("Not going"), "notGoing"),
			):
				add(
					eventMenu,
					label,
					lambda answer=answer, label=label: self._respondToEvent(message, answer, label),
				)
			# Translators: An item in an event's menu: answers whether the user is going.
			menu.AppendSubMenu(eventMenu, _("Res&pond"))
		menu.AppendSeparator()
		# Translators: An item in a message's menu, like WhatsApp's: removes it from this computer and phone only.
		add(menu, _("Delete for &me"), lambda: self._delete(message, False))
		if actions.get("deleteForEveryone"):
			# Translators: An item in a message's menu, like WhatsApp's: removes it for everyone in the chat.
			add(menu, _("Delete for &everyone"), lambda: self._delete(message, True))
		self.messageList.PopupMenu(menu)
		menu.Destroy()

	def _react(self, message: dict, emoji: str) -> None:
		def done(result: Any) -> None:
			if emoji:
				# Translators: Reported after the user reacted to a message, with the emoji.
				ui.message(_("Reacted {emoji}").format(emoji=emoji))
			else:
				# Translators: Reported after the user removed their reaction.
				ui.message(_("Reaction removed"))

		def react() -> None:
			self.session.react(message["id"], emoji)
			try:
				reactions = self.session.reactions(message["id"])
			except Exception:  # noqa: BLE001 - the line is only a little out of date then
				return
			wx.CallAfter(self.onReactions, message["id"], reactions)

		self._run(react, done)

	def _copy(self, text: str) -> None:
		if api.copyToClip(text):
			# Translators: Reported after a message's text was copied.
			ui.message(_("Copied"))

	def _star(self, message: dict, starred: bool) -> None:
		def done(result: Any) -> None:
			message["starred"] = starred
			self._refreshMessageLine(message)
			# Translators: Reported after the user starred or unstarred a message.
			ui.message(_("Starred") if starred else _("Unstarred"))

		self._run(lambda: self.session.star(message["id"], starred), done)

	# Editing a message the user sent, in the message box as in WhatsApp ---------------------------------

	def _editLastMessage(self) -> None:
		"""Up arrow in the empty message box: edit the user's last message, as in WhatsApp."""
		mine = [m for m in self._messages if m.get("fromMe") and m.get("type") not in ("revoked", "call_log")]
		if not mine:
			# Translators: Said when Up arrow in the empty message box finds no message of the user's.
			ui.message(_("No message of yours to edit here"))
			return
		message = mine[-1]
		chatId = self.chat["id"] if self.chat else None

		def gotActions(actions: dict) -> None:
			# Only in the chat it was asked in: Ctrl+Tab meanwhile must not edit the last chat's message.
			if self.chat and self.chat["id"] == chatId:
				self._edit(message, actions)

		self._run(lambda: self.session.messageActions(message["id"]), gotActions)

	def _edit(self, message: dict, actions: dict) -> None:
		if not actions.get("edit"):
			reason = actions.get("editBlocked")
			if reason == "notMine":
				# Translators: Said when the user tries to edit someone else's message.
				text = _("Only your own messages can be edited")
			elif reason == "notText":
				# Translators: Said when the user tries to edit a photo, voice message or other non-text message.
				text = _("Only text messages can be edited")
			else:
				# Translators: Said when the user tries to edit a message sent too long ago.
				text = _(
					"This message can't be edited any more: WhatsApp allows edits for 15 minutes after sending"
				)
			ui.message(text)
			return
		if self._recording or self._hasRecording:
			# Translators: Reported when the user tries to edit a message while a voice note is recorded or not sent.
			ui.message(_("Send the voice note with Ctrl+Shift+R or throw it away with Ctrl+D first"))
			return
		self._cancelReply(announce=False)
		if self._editing is None:
			self._draftBeforeEdit = self.composeBox.GetValue()
		self._editing = message
		self._editOriginal = actions.get("text", "")
		self.composeBox.ChangeValue(self._editOriginal)
		self.composeBox.SetInsertionPointEnd()
		# Translators: Shown above the message box while the user changes a message they sent.
		self.replyingText.SetLabel(_("Editing your message"))
		self._updateButtons()
		self.composeBox.SetFocus()
		ui.message(
			withHint(
				# Translators: Said when the user starts changing a message they sent, with its text.
				_("Editing: {text}").format(text=self._editOriginal),
				# Translators: A hint after the user starts editing a message.
				_("Enter saves, Escape cancels"),
			)
		)

	def _saveEdit(self) -> None:
		message, text = self._editing, self.composeBox.GetValue()
		if message is None:
			return
		if not text.strip():
			# Translators: Said when the user tries to save an edited message with no text.
			ui.message(_("Write the new text, or press Escape to leave the message as it is"))
			return
		if text == self._editOriginal:
			self._cancelEdit(announce=False)
			# Translators: Said when the user saves an edit without changing the text.
			ui.message(_("Not changed"))
			return

		def done(result: Any) -> None:
			message["text"] = text
			message["edited"] = True
			self._refreshMessageLine(message)
			if self._editing is message:
				self._cancelEdit(announce=False)
			sounds.play(sounds.SENT)
			# Translators: Reported after a message was changed.
			ui.message(_("Edited"))

		self._run(lambda: self.session.editText(message["id"], text), done)

	def _cancelEdit(self, announce: bool = True) -> None:
		"""Stop editing; the message box gets back what it held before."""
		if self._editing is None:
			return
		self._editing = None
		self.composeBox.ChangeValue(self._draftBeforeEdit)
		self.composeBox.SetInsertionPointEnd()
		self._draftBeforeEdit = ""
		self._editOriginal = ""
		self.replyingText.SetLabel("")
		self._updateButtons()
		if announce:
			sounds.play(sounds.DISCARD)
			# Translators: Reported when the user stops editing a message; it stays as it was.
			ui.message(_("Editing cancelled"))
			self.composeBox.SetFocus()

	def onEdited(self, info: dict) -> None:
		"""A message was edited or deleted for everyone, here, on the phone or by its sender: show it now.

		A message deleted for everyone comes back under a new id, with replacesId naming the one it
		replaced, so its line is found by either.
		"""
		ids = {info.get("id"), info.get("replacesId")} - {None, ""}
		for message in self._messages:
			if message.get("id") in ids:
				oldId = message.get("id")
				message.update(info)
				message.pop("replacesId", None)
				self._refreshMessageLine(message, oldId)
				return

	def _delete(self, message: dict, forEveryone: bool) -> None:
		question = (
			# Translators: Asked before deleting a message for everyone in the chat.
			_("Delete this message for everyone?\n\n{message}")
			if forEveryone
			# Translators: Asked before deleting a message on this computer and phone only.
			else _("Delete this message for you?\n\n{message}")
		).format(message=self._replySummary(message))
		# Translators: The title of the question before deleting a message.
		if not askYesNo(self, question, _("Delete message")):
			return

		def done(result: Any) -> None:
			if not forEveryone:
				self._removeMessage(message)
			elif isinstance(result, dict):
				# The message stays, as "This message was deleted": show that at once.
				self.onEdited(result)
			# Translators: Reported after a message was deleted.
			ui.message(_("Deleted"))

		self._run(lambda: self.session.deleteMessage(message["id"], forEveryone), done)

	def _refreshMessageLine(self, message: dict, oldId: str | None = None) -> None:
		for index, m in enumerate(self._messages):
			if m is message or m["id"] in (message["id"], oldId):
				line = messageText.messageLine(m, bool(self.chat and self.chat.get("isGroup")))
				if self.messageList.GetString(index) != line:
					self.messageList.SetString(index, line)
				return

	def _removeMessage(self, message: dict) -> None:
		for index, m in enumerate(self._messages):
			if m["id"] == message["id"]:
				del self._messages[index]
				self.messageList.Delete(index)
				if self._messages:
					self.messageList.SetSelection(min(index, len(self._messages) - 1))
				return

	def _onChatMenu(self, evt: wx.ContextMenuEvent) -> None:
		if self._selectedChatIds:
			self._selectedChatsMenu()
			return
		chat = self._selectedChat()
		if chat is None:
			return
		menu = wx.Menu()

		def add(target: wx.Menu, label: str, handler: Callable[[], None]) -> None:
			item = target.Append(wx.ID_ANY, label)
			target.Bind(wx.EVT_MENU, lambda evt: handler(), item)

		# Translators: An item in a chat's menu: opens the conversation.
		add(menu, _("&Open"), lambda: self.openChat(chat))
		# Translators: An item in a chat's menu: how new messages from this chat are announced.
		self._addChatItems(menu, chat, add)
		if _isJoinedGroup(chat):
			# Translators: An item in a chat's menu, like WhatsApp's: leaves the group.
			add(menu, _("E&xit group…"), lambda: self._exitGroup(chat))
		else:
			# Translators: An item in a chat's menu, like WhatsApp's.
			add(menu, _("Delete chat…"), lambda: self._deleteChat(chat))
		source = self.archivedList if self.tabs.GetSelection() == self.TAB_ARCHIVED else self.chatList
		source.PopupMenu(menu)
		menu.Destroy()

	def _addChatItems(
		self, menu: wx.Menu, chat: dict, add: Callable[[wx.Menu, str, Callable[[], None]], None]
	) -> None:
		"""What both the chat list's menu and a chat's More options offer."""
		# Translators: An item in a chat's menu: opens the notification settings of this chat.
		add(menu, _("&Notifications for this chat\u2026"), lambda: self._chatNotifications(chat))
		if chat.get("archived"):
			# Translators: An item in a chat's menu, like WhatsApp's.
			add(menu, _("Un&archive chat"), lambda: self._chatAction(chat, "unarchive", _("Unarchived")))
		else:
			# Translators: An item in a chat's menu, like WhatsApp's.
			add(menu, _("&Archive chat"), lambda: self._chatAction(chat, "archive", _("Archived")))
		if chat.get("muted"):
			# Translators: An item in a chat's menu, like WhatsApp's.
			add(menu, _("Unmute n&otifications"), lambda: self._chatAction(chat, "unmute", _("Unmuted")))
		else:
			muteMenu = wx.Menu()
			for label, seconds in (
				# Translators: How long to mute a chat, in its Mute menu.
				(_("8 hours"), 8 * 3600),
				# Translators: How long to mute a chat, in its Mute menu.
				(_("1 week"), 7 * 86400),
				# Translators: How long to mute a chat, in its Mute menu.
				(_("Always"), -1),
			):
				add(
					muteMenu,
					label,
					# Translators: Reported after a chat was muted.
					lambda seconds=seconds: self._chatAction(chat, "mute", _("Muted"), seconds),
				)
			# Translators: An item in a chat's menu, like WhatsApp's: opens how long to mute it.
			menu.AppendSubMenu(muteMenu, _("Mute n&otifications"))
		if chat.get("pinned"):
			# Translators: An item in a chat's menu, like WhatsApp's.
			add(menu, _("Unpin &chat"), lambda: self._chatAction(chat, "unpin", _("Unpinned")))
		else:
			# Translators: An item in a chat's menu, like WhatsApp's.
			add(menu, _("Pin &chat"), lambda: self._chatAction(chat, "pin", _("Pinned")))
		if messageText.isUnread(chat):
			# Translators: An item in a chat's menu, like WhatsApp's.
			add(menu, _("Mark as &read"), lambda: self._chatAction(chat, "markRead", _("Marked as read")))
		else:
			# Translators: An item in a chat's menu, like WhatsApp's.
			add(
				menu,
				# Translators: An item in a chat's menu, like WhatsApp's.
				_("Ma&rk as unread"),
				# Translators: Reported after a chat was marked as unread.
				lambda: self._chatAction(chat, "markUnread", _("Marked as unread")),
			)

	def _conversationMenu(self) -> None:
		"""More options in a chat's header, like WhatsApp's menu there."""
		if not self.chat:
			return
		# The lists are refreshed after muting, pinning or archiving; the open chat's copy is not.
		chatId = self.chat["id"]
		chat = next((c for c in (*self._chats, *self._archivedChats) if c.get("id") == chatId), self.chat)
		menu = wx.Menu()

		def add(target: wx.Menu, label: str, handler: Callable[[], None]) -> None:
			item = target.Append(wx.ID_ANY, label)
			target.Bind(wx.EVT_MENU, lambda evt: handler(), item)

		add(
			menu,
			# Translators: An item in a chat's More options menu: the group's details.
			_("Group &info")
			if chat.get("isGroup")
			# Translators: An item in a chat's More options menu: the contact's details.
			else _("Contact &info"),
			self._showContactInfo,
		)
		# Translators: An item in a chat's More options menu: finds messages in this chat.
		add(menu, _("&Search in chat\tCtrl+F"), self._searchMessages)
		# Translators: An item in a chat's More options menu: explains how to select messages.
		add(menu, _("Select &messages"), self._startSelecting)

		def show(found: tuple[dict, bool]) -> None:
			if not self.chat or self.chat["id"] != chatId or not self.conversationPanel.IsShown():
				# The user moved on while WhatsApp answered; its Delete, Exit group and Block would act on
				# the chat that was left.
				menu.Destroy()
				return
			abilities, ongoingCall = found
			self._moreOptions(menu, add, chat, abilities, ongoingCall)
			self.moreButton.PopupMenu(menu)
			menu.Destroy()

		if chat.get("isChannel"):
			# Translators: An item in a channel's More options menu: stops following it.
			add(menu, _("&Unfollow channel"), lambda: self._followChannel(chat, False))
			# Translators: An item in a channel's More options menu: goes back to the chat list.
			add(menu, _("Close chat"), self.showChats)
			self.moreButton.PopupMenu(menu)
			menu.Destroy()
			return
		self._run(
			lambda: (
				self.session.chatAbilities(chatId),
				bool(chat.get("isGroup")) and self.session.ongoingGroupCall(chatId),
			),
			show,
		)

	def _moreOptions(
		self,
		menu: wx.Menu,
		add: Callable[[wx.Menu, str, Callable[[], None]], None],
		chat: dict,
		abilities: dict,
		ongoingCall: bool,
	) -> None:
		chatId = chat["id"]
		isGroup = bool(chat.get("isGroup"))
		# Translators: An item in a chat's More options menu: pinned messages of this chat.
		add(menu, _("&Pinned messages"), self._showPinned)
		mediaMenu = wx.Menu()
		for label, kind in (
			# Translators: An item in the Media, links and docs menu.
			(_("&Photos, videos and audio"), "media"),
			# Translators: An item in the Media, links and docs menu.
			(_("&Links"), "links"),
			# Translators: An item in the Media, links and docs menu.
			(_("&Documents"), "docs"),
		):
			add(mediaMenu, label, lambda kind=kind: self._showMedia(kind))
		# Translators: An item in a chat's More options menu, like WhatsApp's chat info.
		menu.AppendSubMenu(mediaMenu, _("Media, &links and docs"))
		if isGroup:
			# Translators: An item in a group's More options menu: messages that mention the user, not read yet.
			add(menu, _("&Unread mentions\tCtrl+Shift+M"), self._showMentions)
		if isGroup and ongoingCall:
			# Translators: An item in a group's More options menu: joins the call going on in the group.
			add(
				menu,
				# Translators: An item in a group's More options menu: joins the call going on in the group.
				_("Join &the group call"),
				lambda: self._run(lambda: self.session.joinGroupCall(chatId)),
			)
		elif isGroup and abilities.get("member", True):
			# Translators: An item in a group's More options menu: calls everyone in the group.
			add(
				menu,
				# Translators: An item in a group's More options menu: calls everyone in the group.
				_("S&tart a group voice call"),
				lambda: self._run(lambda: self.session.startGroupCall(chatId)),
			)
		menu.AppendSeparator()
		self._addChatItems(menu, chat, add)
		if abilities.get("favoritesEnabled"):
			if abilities.get("favorite"):
				# Translators: An item in a chat's More options menu, like WhatsApp's.
				add(
					menu,
					# Translators: An item in a chat's More options menu, like WhatsApp's.
					_("Remove &from favorites"),
					lambda: self._chatSet(
						lambda: self.session.setFavorite(chatId, False),
						# Translators: Reported after a chat was removed from favorites.
						_("Removed from favorites"),
					),
				)
			else:
				# Translators: An item in a chat's More options menu, like WhatsApp's.
				add(
					menu,
					# Translators: An item in a chat's More options menu, like WhatsApp's.
					_("Add to &favorites"),
					lambda: self._chatSet(
						lambda: self.session.setFavorite(chatId, True),
						# Translators: Reported after a chat was added to favorites.
						_("Added to favorites"),
					),
				)
		if abilities.get("canSetEphemeral"):
			current = int(abilities.get("ephemeral") or 0)
			ephemeralMenu = wx.Menu()
			for label, seconds in (
				# Translators: A choice for disappearing messages, like WhatsApp's.
				(_("Off"), 0),
				# Translators: A choice for disappearing messages, like WhatsApp's.
				(_("24 hours"), 86400),
				# Translators: A choice for disappearing messages, like WhatsApp's.
				(_("7 days"), 604800),
				# Translators: A choice for disappearing messages, like WhatsApp's.
				(_("90 days"), 7776000),
			):
				item = ephemeralMenu.AppendRadioItem(wx.ID_ANY, label)
				item.Check(seconds == current)
				ephemeralMenu.Bind(
					wx.EVT_MENU,
					lambda evt, seconds=seconds, label=label: self._chatSet(
						lambda: (
							self.session.setDisappearing(chatId, seconds),
							self._setDisappearing(chatId, seconds),
						),
						# Translators: Reported after setting disappearing messages, such as "Disappearing messages: 7 days".
						_("Disappearing messages: {choice}").format(choice=label),
					),
					item,
				)
			# Translators: An item in a chat's More options menu, like WhatsApp's.
			menu.AppendSubMenu(ephemeralMenu, _("&Disappearing messages"))
		if isGroup and abilities.get("admin"):
			# Translators: An item in a group's More options menu, for its admins: name, settings, members, link.
			add(menu, _("Manage &group\u2026"), lambda: self._manageGroup(chat, abilities))
		elif isGroup and abilities.get("canAdd"):
			# Translators: An item in a group's More options menu: adds people to it.
			add(menu, _("Add mem&bers\u2026"), lambda: self._addMembers(chat))
		menu.AppendSeparator()
		if not isGroup:
			if abilities.get("blocked"):
				# Translators: An item in a chat's More options menu, like WhatsApp's.
				add(menu, _("Unbloc&k"), lambda: self._block(chat, False))
			else:
				# Translators: An item in a chat's More options menu, like WhatsApp's.
				add(menu, _("Bloc&k\u2026"), lambda: self._block(chat, True))
		# Translators: An item in a chat's More options menu, like WhatsApp's.
		add(menu, _("Report\u2026"), lambda: self._report(chat))
		# Translators: An item in a chat's More options menu, like WhatsApp's: deletes its messages.
		add(menu, _("Clear c&hat\u2026"), lambda: self._clearChat(chat))
		if isGroup and abilities.get("member") and not abilities.get("readOnly"):
			# Translators: An item in a group's More options menu, like WhatsApp's.
			add(menu, _("E&xit group\u2026"), lambda: self._exitGroup(chat))
		else:
			# Translators: An item in a chat's More options menu, like WhatsApp's.
			add(menu, _("Delete chat\u2026"), lambda: self._deleteChat(chat))
		# Translators: An item in a chat's More options menu: goes back to the list of chats.
		add(menu, _("Close chat"), self.showChats)

	def _setDisappearing(self, chatId: str, seconds: int) -> None:
		def update() -> None:
			if self.chat and self.chat["id"] == chatId:
				self.chat["disappearing"] = seconds
				self.chatButton.SetLabel(self._headerLabel(self.chat, self._presenceText))

		wx.CallAfter(update)

	def _chatSet(self, work: Callable[[], Any], doneText: str) -> None:
		def done(result: Any) -> None:
			ui.message(doneText)
			self.refreshChats()

		self._run(work, done)

	def _confirm(self, question: str, title: str) -> bool:
		return askYesNo(self, question, title)

	def _askText(self, prompt: str, title: str, value: str = "", multiline: bool = False) -> str | None:
		style = wx.TextEntryDialogStyle | (wx.TE_MULTILINE if multiline else 0)
		dialog = wx.TextEntryDialog(self, prompt, title, value, style=style)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return None
			return dialog.GetValue().strip()
		finally:
			dialog.Destroy()

	# Pins, reactions, private replies and events ---------------------------------------------------------

	def _pin(self, message: dict, duration: str | None) -> None:
		def done(result: Any) -> None:
			message["pinned"] = duration is not None
			# Translators: Reported after pinning or unpinning a message.
			ui.message(_("Pinned") if duration else _("Unpinned"))

		self._run(lambda: self.session.pinMessage(message["id"], duration), done)

	def _showPinned(self) -> None:
		if not self.chat:
			return
		# Translators: Reported when a chat has no pinned messages.
		self._run(
			lambda: self.session.pinnedMessages(self.chat["id"]),
			# Translators: The title of the list of a chat's pinned messages, and what it says when there are none.
			lambda found: self._pickMessage(found, _("Pinned messages"), _("No pinned messages")),
		)

	def _pickMessage(self, messages: list[dict], title: str, emptyText: str, withChat: bool = False) -> None:
		# A list of messages; Enter goes to the chosen one in the conversation, or opens its chat.
		if not messages:
			ui.message(emptyText)
			return
		isGroup = bool(self.chat and self.chat.get("isGroup"))
		lines = [
			messageText.messageInChat(m) if withChat else messageText.messageLine(m, isGroup)
			for m in messages
		]
		picker = ListDialog(self, title, lines)
		try:
			if picker.ShowModal() != wx.ID_OK:
				return
			chosen = messages[picker.selection()]
		finally:
			picker.Destroy()
		if self.chat and chosen.get("chatId") == self.chat["id"]:
			index = next((i for i, m in enumerate(self._messages) if m.get("id") == chosen["id"]), -1)
			if index >= 0:
				self.messageList.SetSelection(index)
				self.messageList.SetFocus()
				ui.message(self.messageList.GetString(index))
				return
			if chosen.get("type") in FILE_TYPES:
				self._openFile(chosen)
				return
			ui.message(messageText.messageLine(chosen, isGroup))
			return
		self._goToMessageId = chosen["id"]
		self.openChat(self._chatById(chosen.get("chatId", ""), chosen.get("chatTitle", "")))

	def _showMedia(self, kind: str) -> None:
		if not self.chat:
			return
		titles = {
			# Translators: The title of the list of a chat's photos, videos and audio.
			"media": _("Photos, videos and audio"),
			# Translators: The title of the list of links sent in a chat.
			"links": _("Links"),
			# Translators: The title of the list of documents sent in a chat.
			"docs": _("Documents"),
		}
		chatId = self.chat["id"]
		# Translators: Reported when a chat has no media, links or documents of the kind asked for.
		self._run(
			lambda: self.session.chatMedia(chatId, kind),
			# Translators: Shown in the list of a chat's media, links or documents when there are none.
			lambda found: self._pickMessage(found, titles[kind], _("Nothing here yet")),
		)

	def _showMentions(self) -> None:
		if not self.chat or not self.chat.get("isGroup"):
			return
		chatId = self.chat["id"]
		self._run(
			lambda: self.session.unreadMentions(chatId),
			# Translators: The title of the list of unread messages that mention the user.
			lambda found: self._pickMessage(found, _("Unread mentions"), _("No unread mentions")),
		)

	def _replyPrivately(self, message: dict) -> None:
		sender = message.get("sender") or ""
		text = self._askText(
			# Translators: Asks for a private reply to a group message, with its sender.
			_("Reply privately to {name}:").format(name=sender),
			# Translators: The title of the dialog for a private reply.
			_("Reply privately"),
		)
		if not text:
			return

		def done(chat: dict) -> None:
			sounds.play(sounds.SENT)
			# Translators: Reported after a private reply was sent, with who it went to.
			ui.message(_("Sent to {name}").format(name=chat.get("title", sender)))

		self._run(lambda: self.session.replyPrivately(message["id"], text), done)

	def _whoReacted(self, message: dict) -> None:
		def show(details: list[dict]) -> None:
			lines = []
			for reaction in details:
				for person in reaction.get("people", []):
					# Translators: Who reacted, in the list of reactions; for the user it says You.
					name = _("You") if person.get("isMe") else person.get("name", "")
					lines.append(f"{reaction.get('emoji', '')} {name}")
			if not lines:
				# Translators: Reported for a channel post, whose reactions show counts only.
				ui.message(_("Only the number of reactions is known"))
				return
			# Translators: The title of the list of who reacted to a message.
			picker = ListDialog(self, _("Reactions"), lines, okLabel=_("Close"))
			try:
				picker.ShowModal()
			finally:
				picker.Destroy()

		self._run(lambda: self.session.reactionDetails(message["id"]), show)

	def _showEvent(self, message: dict) -> None:
		def show(event: dict) -> None:
			dialog = TextDialog(self, event.get("name", ""), messageText.eventText(event))
			try:
				dialog.ShowModal()
			finally:
				dialog.Destroy()

		self._run(lambda: self.session.eventInfo(message["id"]), show)

	def _respondToEvent(self, message: dict, answer: str, label: str) -> None:
		# Translators: Reported after answering an event, such as "Answered: Going".
		self._run(
			lambda: self.session.respondToEvent(message["id"], answer),
			# Translators: Reported after answering an event's invitation, with the answer chosen.
			lambda r: ui.message(_("Answered: {answer}").format(answer=label)),
		)

	# Sending polls, contacts, stickers and events --------------------------------------------------------

	def _createPoll(self) -> None:
		if not self.chat:
			return
		dialog = CreatePollDialog(self)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			question, options, single = dialog.values()
		finally:
			dialog.Destroy()
		problem = messageText.pollProblem(question, options)
		if problem:
			ui.message(problem)
			return
		chatId = self.chat["id"]

		def done(result: Any) -> None:
			sounds.play(sounds.SENT)
			# Translators: Reported after a poll was sent.
			ui.message(_("Poll sent"))

		self._run(lambda: self.session.sendPoll(chatId, question, options, single), done)

	def _sendContact(self) -> None:
		if not self.chat:
			return
		chatId = self.chat["id"]

		def pick(contacts: list[dict]) -> None:
			# Translators: The title and button of the list of contacts to send as cards.
			dialog = ChatPickerDialog(self, contacts, title=_("Send contacts"), okLabel=_("&Send"))
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				chosen = [c["id"] for c in dialog.chosen()]
			finally:
				dialog.Destroy()
			if chosen:
				self._run(
					lambda: self.session.sendContacts(chatId, chosen),
					# Translators: Reported after contacts were sent.
					lambda r: (sounds.play(sounds.SENT), ui.message(_("Sent"))),
				)

		self._run(self.session.contactChoices, pick)

	def _sendSticker(self) -> None:
		if not self.chat:
			return
		chatId = self.chat["id"]

		def pick(stickers: list[dict]) -> None:
			if not stickers:
				# Translators: Reported when the user has no recent or favorite stickers.
				ui.message(_("No stickers yet. Stickers you send or favorite on your phone appear here."))
				return
			lines = []
			for number, s in enumerate(stickers, 1):
				# Translators: A sticker in the list: its number, and whether it is a favorite or recent.
				kind = _("favorite") if s["kind"] == "favorite" else _("recent")
				# Translators: A sticker in the list: its number, and whether it is a favorite or recent.
				line = _("Sticker {number}, {kind}").format(number=number, kind=kind)
				for extra in (s.get("label"), s.get("pack")):
					if extra:
						line += ", " + extra
				if s.get("animated"):
					# Translators: Added to an animated sticker.
					line += ", " + _("animated")
				lines.append(line)
			# Translators: The title of the list of stickers to send.
			picker = ListDialog(self, _("Stickers"), lines, okLabel=_("&Send"))
			try:
				if picker.ShowModal() != wx.ID_OK:
					return
				chosen = stickers[picker.selection()]
			finally:
				picker.Destroy()
			self._run(
				lambda: self.session.sendSticker(
					chatId, chosen["kind"], chosen["index"], chosen.get("key", "")
				),
				# Translators: Reported after a sticker was sent.
				lambda r: (sounds.play(sounds.SENT), ui.message(_("Sent"))),
			)

		self._run(self.session.stickers, pick)

	def _createEvent(self) -> None:
		if not self.chat:
			return
		dialog = CreateEventDialog(self)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			options = dialog.values()
		finally:
			dialog.Destroy()
		if options is None:
			return
		chatId = self.chat["id"]

		def done(result: Any) -> None:
			sounds.play(sounds.SENT)
			# Translators: Reported after an event was sent to a group.
			ui.message(_("Event sent"))

		self._run(lambda: self.session.createEvent(chatId, options), done)

	# Managing chats and groups -------------------------------------------------------------------------

	def _block(self, chat: dict, blocked: bool) -> None:
		if blocked and not self._confirm(
			# Translators: Asked before blocking someone, with their name.
			_("Block {name}? Blocked contacts can't call you or send you messages.").format(
				name=chat["title"]
			),
			# Translators: The title of the question before blocking a contact.
			_("Block"),
		):
			return
		self._chatSet(
			lambda: self.session.setBlocked(chat["id"], blocked),
			# Translators: Reported after blocking or unblocking someone.
			_("Blocked") if blocked else _("Unblocked"),
		)

	def _report(self, chat: dict) -> None:
		isGroup = bool(chat.get("isGroup"))
		answer = askThreeWay(
			self,
			# Translators: Asked before reporting a chat to WhatsApp, with its name.
			_("Report {name} to WhatsApp? The last messages in this chat are sent to WhatsApp.").format(
				name=chat["title"]
			),
			# Translators: The title of the question before reporting a chat.
			_("Report"),
			# Translators: A button that reports a group and leaves it, or reports a person and blocks them.
			_("Report and &exit group") if isGroup else _("Report and &block"),
			# Translators: A button that only reports a chat.
			_("&Report only"),
			# Translators: A button that closes the question without reporting.
			_("Cancel"),
		)
		if answer == wx.ID_CANCEL:
			return
		# Translators: Reported after a chat was reported to WhatsApp.
		self._chatSet(lambda: self.session.reportChat(chat["id"], answer == wx.ID_YES), _("Reported"))

	def _clearChat(self, chat: dict) -> None:
		answer = askThreeWay(
			self,
			# Translators: Asked before clearing a chat's messages, with its name.
			_("Clear all messages in {name}? The chat stays in your list.").format(name=chat["title"]),
			# Translators: The title of the question before clearing a chat.
			_("Clear chat"),
			# Translators: A button that clears a chat but keeps its starred messages.
			_("Clear, &keep starred"),
			# Translators: A button that clears a chat with its starred messages.
			_("Clear &all"),
			# Translators: A button that closes the question without clearing the chat.
			_("Cancel"),
		)
		if answer == wx.ID_CANCEL:
			return

		def done(result: Any) -> None:
			sounds.play(sounds.DISCARD)
			# Translators: Reported after a chat was cleared.
			ui.message(_("Chat cleared"))
			if self.chat and self.chat["id"] == chat["id"]:
				self.openChat(chat)

		self._run(lambda: self.session.clearChat(chat["id"], answer == wx.ID_YES), done)

	def _deleteChat(self, chat: dict) -> None:
		if not self._confirm(
			# Translators: Asked before deleting one chat, with its name.
			_("Delete the chat with {name}? Its messages are removed from this device.").format(
				name=chat["title"]
			),
			# Translators: The title of the question before deleting chats.
			_("Delete chats"),
		):
			return

		def done(result: Any) -> None:
			sounds.play(sounds.DISCARD)
			# Translators: Reported after a chat was deleted.
			ui.message(_("Deleted"))
			self.showChats()

		self._run(lambda: self.session.deleteChat(chat["id"]), done)

	def _exitGroup(self, chat: dict) -> None:
		answer = askThreeWay(
			self,
			# Translators: Asked before leaving a group, with its name.
			_("Exit {name}? Only the group's admins are told.").format(name=chat["title"]),
			# Translators: The title of the question before leaving a group.
			_("Exit group"),
			# Translators: Buttons when leaving a group: leave and also delete the chat, or only leave.
			_("Exit and &delete"),
			# Translators: A button that leaves a group but keeps the chat.
			_("&Exit"),
			# Translators: A button that closes the question without leaving the group.
			_("Cancel"),
		)
		if answer == wx.ID_CANCEL:
			return

		def done(result: Any) -> None:
			# Translators: Reported after leaving a group.
			ui.message(_("You left {name}").format(name=chat["title"]))
			if answer == wx.ID_YES and self.chat and self.chat["id"] == chat["id"]:
				self.showChats()
			self.refreshChats()

		self._run(lambda: self.session.exitGroup(chat["id"], answer == wx.ID_YES), done)

	def _addMembers(self, chat: dict) -> None:
		def pick(contacts: list[dict]) -> None:
			# Translators: The title and button of the list of people to add to a group.
			dialog = ChatPickerDialog(self, contacts, title=_("Add members"), okLabel=_("&Add"))
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				chosen = [c["id"] for c in dialog.chosen()]
			finally:
				dialog.Destroy()
			if not chosen:
				return

			def done(failed: int) -> None:
				if failed:
					ui.message(
						# Translators: Reported when some people could not be added, usually for their privacy.
						_("{count} could not be added. WhatsApp offers to send them an invite.").format(
							count=failed
						)
					)
				else:
					# Translators: Reported after people were added to a group.
					ui.message(_("Added"))

			self._run(lambda: self.session.changeParticipants(chat["id"], "add", chosen), done)

		self._run(self.session.contactChoices, pick)

	def _manageGroup(self, chat: dict, abilities: dict) -> None:
		dialog = ManageGroupDialog(self, chat, abilities)
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()

	def _newGroup(self) -> None:
		name = self._askText(
			# Translators: Asks for the name of a new group.
			_("Group name:"),
			# Translators: The title of the dialogs that make a new group.
			_("New group"),
		)
		if not name:
			return

		def pick(contacts: list[dict]) -> None:
			# Translators: The title and button of the list of people to put in a new group.
			dialog = ChatPickerDialog(self, contacts, title=_("New group"), okLabel=_("&Create"))
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				chosen = [c["id"] for c in dialog.chosen()]
			finally:
				dialog.Destroy()
			if not chosen:
				return

			def done(result: dict) -> None:
				# Translators: Reported after a group was made, with its name.
				message = _("Group {name} created").format(name=name)
				if result.get("failed"):
					# Translators: Added after a new group was created: some people could not be added, usually for their privacy.
					message += ". " + _(
						"{count} could not be added. WhatsApp offers to send them an invite."
					).format(count=result["failed"])
				ui.message(message)
				self.refreshChats()
				self.openChat({"id": result["chatId"], "title": name, "isGroup": True})

			self._run(lambda: self.session.createGroup(name, chosen), done)

		self._run(self.session.contactChoices, pick)

	def _searchAll(self) -> None:
		query = self._askText(
			# Translators: Asks what to look for in every chat's messages.
			_("Find messages in all chats containing:"),
			# Translators: The title of the dialog that searches every chat.
			_("Search all chats"),
		)
		if not query:
			return
		# Translators: The title of the list of messages found in all chats.
		self._run(
			lambda: self.session.searchAll(query),
			lambda found: self._pickMessage(
				found["messages"],
				# Translators: The title of the messages found in every chat, and what it says when nothing was found.
				_("Messages found"),
				# Translators: What the list of messages found says when nothing was found.
				_("No messages found"),
				withChat=True,
			),
		)

	# Your status --------------------------------------------------------------------------------------

	def _postTextStatus(self) -> None:
		dialog = TextStatusDialog(self)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			text, colorIndex, font = dialog.values()
		finally:
			dialog.Destroy()
		if not text:
			return

		def done(result: Any) -> None:
			sounds.play(sounds.SENT)
			# Translators: Reported after the user posted a status.
			ui.message(_("Status posted"))

		self._run(lambda: self.session.postTextStatus(text, colorIndex, font), done)

	def _postMediaStatus(self) -> None:
		dialog = wx.FileDialog(
			self,
			# Translators: The title of the dialog for choosing a photo or video to post as a status.
			_("Choose a photo or video for your status"),
			# Translators: The file type in the dialog for choosing a photo or video for a status.
			wildcard=_("Photos and videos") + "|*.jpg;*.jpeg;*.png;*.webp;*.mp4;*.3gp;*.mov",
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			path = dialog.GetPath()
		finally:
			dialog.Destroy()
		# Translators: Asks for a caption for a photo or video status; it may stay empty.
		caption = self._askText(_("Caption (may be empty):"), _("Your status"))
		if caption is None:
			return
		mime = mimetypes.guess_type(path)[0] or "image/jpeg"
		kind = "video" if mime.startswith("video/") else "image"

		def done(result: Any) -> None:
			sounds.play(sounds.SENT)
			# Translators: Reported after the user's status was posted.
			ui.message(_("Status posted"))

		# Translators: Reported while a status photo or video is sent.
		ui.message(_("Posting…"))
		self._run(lambda: self.session.sendFile("status@broadcast", path, kind, mime, caption), done)

	def _showMyStatus(self) -> None:
		def show(statuses: list[dict]) -> None:
			if not statuses:
				# Translators: Reported when the user has no status in the last 24 hours.
				ui.message(_("You have no status now"))
				return
			lines = []
			for s in statuses:
				names = ", ".join(v["name"] for v in s.get("viewers", []))
				lines.append(
					# Translators: One of the user's statuses: what it is, then who saw it.
					_("{status}. Seen by {count}: {names}").format(
						status=messageText.content(s) if not s.get("text") else s["text"],
						count=len(s.get("viewers", [])),
						names=names,
					)
					if names
					# Translators: One of the user's statuses that nobody has seen yet.
					else _("{status}. Not seen yet").format(
						status=messageText.content(s) if not s.get("text") else s["text"]
					)
				)
			# Translators: The title of the list of the user's own statuses; its button deletes one.
			picker = ListDialog(self, _("My status"), lines, okLabel=_("&Delete this status"))
			try:
				if picker.ShowModal() != wx.ID_OK:
					return
				chosen = statuses[picker.selection()]
			finally:
				picker.Destroy()
			# Translators: Asked before deleting one of the user's statuses.
			if self._confirm(_("Delete this status for everyone?"), _("My status")):
				self._run(
					lambda: self.session.deleteMyStatus(chosen["id"]),
					# Translators: Reported after one of the user's statuses was deleted.
					lambda r: (sounds.play(sounds.DISCARD), ui.message(_("Deleted"))),
				)

		self._run(self.session.myStatuses, show)

	# Settings: profile, privacy, blocked contacts ---------------------------------------------------------

	def _editProfile(self) -> None:
		def show(profile: dict) -> None:
			dialog = ProfileDialog(self, profile)
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				name, about, photo = dialog.values()
			finally:
				dialog.Destroy()

			def work() -> None:
				if name and name != profile.get("name"):
					self.session.setProfile("name", name)
				if about and about != profile.get("about"):
					self.session.setProfile("about", about)
				if photo == "":
					self.session.setProfilePhoto(None)
				elif photo:
					self.session.setProfilePhoto(photo)

			def saved(result: Any) -> None:
				if not about and profile.get("about"):
					# WhatsApp keeps an About; saying "saved" for an emptied one would not be true.
					# Translators: Reported after saving the profile when the user emptied the About text.
					ui.message(_("Profile saved. About was not emptied: WhatsApp needs some text there."))
					return
				# Translators: Reported after the user's profile was saved.
				ui.message(_("Profile saved"))

			self._run(work, saved)

		self._run(self.session.profile, show)

	def _editPrivacy(self) -> None:
		def show(current: dict) -> None:
			dialog = PrivacyDialog(self, current)
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				changed = dialog.changes()
			finally:
				dialog.Destroy()
			if not changed:
				return

			def work() -> None:
				for key, value in changed.items():
					self.session.setPrivacy(key, value)

			# Translators: Reported after privacy settings were saved.
			self._run(work, lambda r: ui.message(_("Privacy saved")))

		self._run(self.session.privacy, show)

	def _showBlocked(self) -> None:
		def show(blocked: list[dict]) -> None:
			if not blocked:
				# Translators: Reported when the user blocked nobody.
				ui.message(_("You blocked nobody"))
				return
			picker = ListDialog(
				self,
				# Translators: The title of the list of blocked contacts; its button unblocks one.
				_("Blocked contacts"),
				[b["name"] for b in blocked],
				# Translators: The button of the list of blocked contacts: unblocks the chosen one.
				okLabel=_("&Unblock"),
			)
			try:
				if picker.ShowModal() != wx.ID_OK:
					return
				chosen = blocked[picker.selection()]
			finally:
				picker.Destroy()
			# Translators: Reported after a contact was unblocked.
			self._run(lambda: self.session.unblock(chosen["id"]), lambda r: ui.message(_("Unblocked")))

		self._run(self.session.blockedContacts, show)

	def _startSelecting(self) -> None:
		self.messageList.SetFocus()
		ui.message(
			# Translators: Read out after choosing Select messages in a chat's More options menu.
			_("Space selects a message, Shift+arrows select as you move, Escape clears the selection")
		)

	def _chatNotifications(self, chat: dict) -> None:
		settings = config.conf[CONFIG_SECTION]
		rules = notifications.loadRules(settings["chatRules"])
		dialog = NotificationDialog(self, chat.get("title", ""), rules.get(chat["id"], notifications.Rule()))
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			rules[chat["id"]] = dialog.rule()
		finally:
			dialog.Destroy()
			sounds.stopRing()
		settings["chatRules"] = notifications.saveRules(rules)
		# Translators: Reported after a chat's notification settings were saved.
		ui.message(_("Saved"))

	def _chatAction(self, chat: dict, action: str, doneText: str, seconds: int = 0) -> None:
		def done(result: Any) -> None:
			ui.message(doneText)
			self.refreshChats()

		self._run(lambda: self.session.chatAction(chat["id"], action, seconds), done)

	# Events from WhatsApp -------------------------------------------------------------------------------

	def onMessage(self, message: dict, chat: dict) -> bool:
		"""Add a new message to the open conversation. Returns whether it belongs to it."""
		if not self.chat or chat.get("id") != self.chat["id"]:
			return False
		messageId = message.get("id")
		if messageId and any(m.get("id") == messageId for m in self._messages):
			return True
		self._messages.append(message)
		self.messageList.Append(messageText.messageLine(message, self.chat.get("isGroup", False)))
		if not message.get("fromMe"):
			self._markSeenSoon()
		return True

	def onAck(self, messageId: str, ack: int) -> None:
		"""A message the user sent was delivered, read or played. Say so for recent ones, as WhatsApp's ticks."""
		for message in self._messages:
			if message.get("id") == messageId:
				before = message.get("ack") or 0
				message["ack"] = ack
				self._refreshMessageLine(message)
				recent = time.time() - (message.get("t") or 0) < ACK_ANNOUNCE_SECONDS
				if ack > before and recent and messageText.ackText(ack):
					self._sayAckSoon(ack)
				return

	def _sayAckSoon(self, ack: int) -> None:
		"""Say a message's new state, once for all those that change together, such as five messages read."""
		self._acksToSay.append(ack)
		if self._ackTimer is not None:
			self._ackTimer.Stop()
		self._ackTimer = wx.CallLater(ACK_GROUP_MS, self._sayAcks)

	def _sayAcks(self) -> None:
		self._ackTimer = None
		acks, self._acksToSay = self._acksToSay, []
		text = messageText.acksText(acks)
		if text:
			ui.message(text)

	def _nextSpeed(self) -> None:
		"""Ctrl+S: voice messages play at 1, 1.5 or 2 times, as in WhatsApp. Kept for next time."""
		settings = config.conf[CONFIG_SECTION]
		current = settings["playbackSpeed"]
		speed = PLAYBACK_SPEEDS[(PLAYBACK_SPEEDS.index(current) + 1) % len(PLAYBACK_SPEEDS)]
		settings["playbackSpeed"] = speed
		# Translators: Reported when the user changes how fast voice messages play, such as "1.5x".
		ui.message(_("{speed}x").format(speed=speed))
		self._run(lambda: self.session.setPlaybackRate(float(speed)))

	@staticmethod
	def _headerLabel(chat: dict, presenceText: str) -> str:
		"""The chat's name, then what WhatsApp shows under it: disappearing messages, online or last seen."""
		parts = [chat.get("title", "")]
		if chat.get("disappearing"):
			parts.append(messageText.disappearingText(chat["disappearing"]))
		if presenceText:
			parts.append(presenceText)
		return ", ".join(parts)

	def onPresence(self, chatId: str, presence: dict | None) -> None:
		"""Show what WhatsApp shows under the chat's name, and read out typing and recording as they start."""
		if not self.chat or self.chat["id"] != chatId or presence is None:
			return
		before = self._presence
		self._presence = presence
		text = messageText.presenceText(presence)
		if text != self._presenceText:
			self._presenceText = text
			self.chatButton.SetLabel(self._headerLabel(self.chat, text))
		if messageText.isActivity(presence) and messageText.presenceText(before) != text:
			ui.message(text)

	def _showPoll(self, message: dict) -> None:
		chat = self.chat

		def show(poll: dict) -> None:
			if self.chat is not chat:
				return
			dialog = PollDialog(self, poll)
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				chosen = dialog.chosen()
			finally:
				dialog.Destroy()
			self.messageList.SetFocus()

			def voted(result: Any) -> None:
				message.setdefault("poll", {})
				sounds.play(sounds.SENT)
				ui.message(
					# Translators: Reported after the user voted in a poll.
					_("Voted")
					if chosen
					# Translators: Reported after the user took back their vote in a poll.
					else _("Vote removed")
				)

			self._run(lambda: self.session.vote(poll["id"], chosen), voted)

		self._run(lambda: self.session.pollInfo(message["id"]), show)

	def _showContactInfo(self) -> None:
		if not self.chat:
			return
		chatId = self.chat["id"]

		def show(info: dict) -> None:
			if not self.chat or self.chat["id"] != chatId:
				return
			dialog = ContactInfoDialog(self, info, self._presenceText)
			try:
				dialog.ShowModal()
			finally:
				dialog.Destroy()
			self.messageList.SetFocus()

		self._run(lambda: self.session.contactInfo(chatId), show)

	def _reportPresence(self) -> None:
		"""Alt+T: say whether the other person is online, or when they were last seen."""
		if not self.chat:
			return
		chat = self.chat

		def report(presence: dict) -> None:
			self.onPresence(chat["id"], presence)
			# Only who and their state, to be quick; the chat's name button also says disappearing messages.
			text = messageText.presenceText(presence)
			title = chat.get("title", "")
			ui.message(f"{title}, {text}" if text else title)

		self._run(lambda: self.session.presence(chat["id"]), report)

	def onReactions(self, messageId: str, reactions: list[dict]) -> None:
		"""Someone reacted, or took a reaction back: update that message's line."""
		for message in self._messages:
			if message.get("id") == messageId:
				message["reactions"] = reactions
				self._refreshMessageLine(message)
				return

	def _playVoice(self, message: dict) -> None:
		self._playingId = message["id"]
		settings = config.conf[CONFIG_SECTION]
		speed, volume = float(settings["playbackSpeed"]), int(settings["voiceVolume"])
		startAt = self._startAt[1] if self._startAt and self._startAt[0] == message["id"] else 0
		self._startAt = None
		self._run(
			lambda: (
				self.session.setPlaybackRate(speed),
				self.session.setPlaybackVolume(volume),
				self.session.playMessage(message["id"], startAt),
			),
			onError=lambda e: self._playbackEnded(),
		)
		self._followPositionSoon()

	# The position slider -----------------------------------------------------------------------------------

	def _onMessageMoved(self, evt: wx.CommandEvent) -> None:
		self._showPositionSlider()
		evt.Skip()

	def _showPositionSlider(self) -> None:
		"""The slider is there only on a voice message or audio, its range that message's length."""
		message = self._selectedMessage()
		show = bool(message and message.get("type") in SEEKABLE_TYPES and message.get("duration"))
		if show:
			self.positionSlider.SetRange(0, max(1, int(message["duration"])))
			if message["id"] != self._playingId:
				start = self._startAt[1] if self._startAt and self._startAt[0] == message["id"] else 0
				self.positionSlider.SetValue(int(start))
		if self.positionSlider.IsShown() != show:
			self.positionLabel.Show(show)
			self.positionSlider.Show(show)
			self.conversationPanel.Layout()

	def positionText(self) -> str:
		"""What NVDA says for the position slider: where it is and how long the message is."""
		# Translators: The position slider of a voice message, such as "12 sec of 45 sec".
		return _("{position} of {length}").format(
			position=messageText.duration(self.positionSlider.GetValue()),
			length=messageText.duration(self.positionSlider.GetMax()),
		)

	def _seek(self) -> None:
		message = self._selectedMessage()
		if not message or message.get("type") not in SEEKABLE_TYPES:
			return
		seconds = self.positionSlider.GetValue()
		if message["id"] == self._playingId:

			def done(moved: bool) -> None:
				if not moved and self._playingId == message["id"]:
					# It had ended meanwhile: play it from there.
					self._startAt = (message["id"], seconds)
					self._playVoice(message)

			self._run(lambda: self.session.seekAudio(seconds), done)
		else:
			# Not playing: Enter plays it from here.
			self._startAt = (message["id"], seconds)

	def _followPositionSoon(self) -> None:
		if self._positionFollow is None or not self._positionFollow.IsRunning():
			self._positionFollow = wx.CallLater(POSITION_FOLLOW_MS, self._followPosition)

	def _followPosition(self) -> None:
		"""While a voice message plays, the slider follows it, unless the user is on it."""
		if not self or self._playingId is None:
			return
		self._followPositionSoon()
		message = self._selectedMessage()
		if not message or message["id"] != self._playingId or not self.positionSlider.IsShown():
			return
		if wx.Window.FindFocus() is self.positionSlider:
			return

		def show(position: dict) -> None:
			if self and position.get("loaded") and self._playingId == message["id"]:
				self.positionSlider.SetValue(int(position.get("time") or 0))

		self._run(self.session.audioPosition, show, onError=lambda e: None)

	def onPlaybackEnded(self, messageId: str | None = None) -> None:
		"""A voice message ended: as in WhatsApp, the voice message right after it plays next."""
		# Only the end of the one playing now counts: not the user's own recording (no id), nor a
		# message that was playing before.
		if not messageId or messageId != self._playingId:
			return
		finished, self._playingId = self._playingId, None
		index = next((i for i, m in enumerate(self._messages) if m.get("id") == finished), -1)
		following = self._messages[index + 1] if 0 <= index < len(self._messages) - 1 else None
		# Only a voice message straight after: a text, a document or anything else ends the run.
		if following is None or self._messages[index].get("type") != "ptt" or following.get("type") != "ptt":
			if self._voiceRun:
				self._voiceRun = False
				sounds.play(sounds.VOICE_END)
			return
		self._voiceRun = True
		sounds.play(sounds.VOICE_NEXT)
		if wx.Window.FindFocus() is self.messageList and self.messageList.GetSelection() == index:
			# The cursor follows, as long as the user is still on the one that ended. NVDA reads the new
			# message itself, unless the user asked for quiet.
			if not config.conf[CONFIG_SECTION]["sayNextVoiceMessage"]:
				self._quietFocusUntil = time.monotonic() + QUIET_FOCUS_SECONDS
			self.messageList.SetSelection(index + 1)
			self._showPositionSlider()
		# After the small sound, as WhatsApp leaves a moment between them. Enter meanwhile stops the run.
		self._playingId = following["id"]

		def start() -> None:
			if self._playingId == following["id"]:
				self._playVoice(following)

		wx.CallLater(VOICE_NEXT_DELAY_MS, start)

	def isQuietFocus(self, windowHandle: int) -> bool:
		"""Whether NVDA should not read this focus change: the messages list following voice messages."""
		if windowHandle != self.messageList.GetHandle() or time.monotonic() > self._quietFocusUntil:
			return False
		self._quietFocusUntil = 0.0
		return True

	# Selecting several messages or chats, as WhatsApp's "Select" -------------------------------------------

	def _selectionOf(self, listBox: wx.ListBox) -> tuple[set[str], list[dict]]:
		"""The selected ids and the items shown in a list."""
		if listBox is self.messageList:
			return self._selectedMessageIds, self._messages
		if listBox is self.archivedList:
			return self._selectedChatIds, self._archivedChats
		return self._selectedChatIds, self._shownChats

	def _onListMoved(self, evt: wx.CommandEvent) -> None:
		"""A soft tick on reaching a selected item, so the user knows without hearing it said."""
		listBox = evt.GetEventObject()
		selected, items = self._selectionOf(listBox)
		index = listBox.GetSelection()
		if selected and 0 <= index < len(items) and items[index].get("id") in selected:
			sounds.play(sounds.TICK)
		evt.Skip()

	def _setSelected(self, listBox: wx.ListBox, index: int, selected: bool | None = None) -> bool:
		chosen, items = self._selectionOf(listBox)
		if not 0 <= index < len(items):
			return False
		itemId = items[index]["id"]
		selected = itemId not in chosen if selected is None else selected
		if selected:
			chosen.add(itemId)
		else:
			chosen.discard(itemId)
		return selected

	def _sayCount(self, listBox: wx.ListBox, selected: bool) -> None:
		count = len(self._selectionOf(listBox)[0])
		if selected:
			sounds.play(sounds.TICK)
		ui.message(
			# Translators: Read out after selecting an item, with how many are selected.
			_("Selected, {count} selected").format(count=count)
			if selected
			# Translators: Read out after unselecting an item, with how many stay selected.
			else _("Not selected, {count} selected").format(count=count)
		)

	def _handleSelectionKey(self, listBox: wx.ListBox, evt: wx.KeyEvent) -> bool:
		key, modifiers = evt.GetKeyCode(), evt.GetModifiers()
		index = listBox.GetSelection()
		if key == wx.WXK_SPACE and modifiers == wx.MOD_NONE:
			self._sayCount(listBox, self._setSelected(listBox, index))
			return True
		if key in (wx.WXK_DOWN, wx.WXK_UP) and modifiers == wx.MOD_SHIFT:
			# As in WhatsApp: the item left and the one reached are both selected.
			self._setSelected(listBox, index, True)
			target = index + (1 if key == wx.WXK_DOWN else -1)
			if 0 <= target < listBox.GetCount():
				listBox.SetSelection(target)
				self._setSelected(listBox, target, True)
				ui.message(listBox.GetString(target))
			self._sayCount(listBox, True)
			return True
		if key == ord("A") and modifiers == wx.MOD_CONTROL:
			chosen, items = self._selectionOf(listBox)
			chosen.update(item["id"] for item in items)
			self._sayCount(listBox, True)
			return True
		return False

	def _clearSelection(self, listBox: wx.ListBox, announce: bool = True) -> None:
		self._selectionOf(listBox)[0].clear()
		if announce:
			# Translators: Read out when the user cancels the selection of messages or chats.
			ui.message(_("Selection cleared"))

	def _chosenMessages(self) -> list[dict]:
		"""The selected messages in their order, or the focused message when none is selected."""
		if self._selectedMessageIds:
			return [m for m in self._messages if m.get("id") in self._selectedMessageIds]
		message = self._selectedMessage()
		return [message] if message else []

	def _chosenChats(self) -> list[dict]:
		listBox = self.archivedList if self.tabs.GetSelection() == self.TAB_ARCHIVED else self.chatList
		chosen, items = self._selectionOf(listBox)
		if chosen:
			return [c for c in items if c.get("id") in chosen]
		chat = self._selectedChat()
		return [chat] if chat else []

	def _deleteSelectedMessages(self) -> None:
		ids = [m["id"] for m in self._chosenMessages()]

		def ask(actions: dict) -> None:
			# Translators: The summary in the delete question for several selected messages.
			summary = _("{count} selected messages").format(count=len(ids))
			dialog = DeleteDialog(self, summary, bool(actions.get("deleteForEveryone")))
			try:
				choice = dialog.ShowModal()
			finally:
				dialog.Destroy()
			if choice not in (DeleteDialog.FOR_ME, DeleteDialog.FOR_EVERYONE):
				return
			forEveryone = choice == DeleteDialog.FOR_EVERYONE

			def done(result: Any) -> None:
				if not forEveryone:
					for message in [m for m in self._messages if m.get("id") in ids]:
						self._removeMessage(message)
				self._clearSelection(self.messageList, announce=False)
				sounds.play(sounds.DISCARD)
				# Translators: Reported after several messages were deleted, with how many.
				ui.message(_("{count} deleted").format(count=len(ids)))

			self._run(lambda: self.session.deleteMessages(ids, forEveryone), done)

		self._run(lambda: self.session.messagesActions(ids), ask)

	def _selectedMessagesMenu(self) -> None:
		ids = [m["id"] for m in self._chosenMessages()]

		def show(actions: dict) -> None:
			menu = wx.Menu()

			def add(label: str, handler: Callable[[], None]) -> None:
				item = menu.Append(wx.ID_ANY, label)
				menu.Bind(wx.EVT_MENU, lambda evt: handler(), item)

			# Translators: The first, disabled item of the menu for several selected messages.
			menu.Append(wx.ID_ANY, _("{count} messages selected").format(count=len(ids))).Enable(False)
			# Translators: An item in the menu for several selected messages: copies their text.
			add(_("&Copy"), self._copySelected)
			# Translators: An item in the menu for several selected messages.
			add(_("&Forward\tAlt+F"), self._forward)
			if actions.get("star"):
				starred = not actions.get("allStarred")
				add(
					# Translators: An item in the menu for several selected messages: stars or unstars them.
					_("&Star") if starred else _("Un&star"),
					lambda: self._run(
						lambda: self.session.starMessages(ids, starred),
						# Translators: Reported after the selected messages were starred or unstarred.
						lambda r: ui.message(_("Starred") if starred else _("Unstarred")),
					),
				)
			# Translators: An item in the menu for several selected messages.
			add(_("&Delete\tDelete"), self._deleteSelectedMessages)
			# Translators: An item in the menu of selected messages or chats: unselects them all.
			add(_("C&lear selection\tEscape"), lambda: self._clearSelection(self.messageList))
			self.messageList.PopupMenu(menu)
			menu.Destroy()

		self._run(lambda: self.session.messagesActions(ids), show)

	def _selectedChatsMenu(self) -> None:
		chats = self._chosenChats()
		ids = [c["id"] for c in chats]
		archived = self.tabs.GetSelection() == self.TAB_ARCHIVED
		listBox = self.archivedList if archived else self.chatList
		menu = wx.Menu()

		def add(target: wx.Menu, label: str, action: str, doneText: str, seconds: int = 0) -> None:
			item = target.Append(wx.ID_ANY, label)
			target.Bind(wx.EVT_MENU, lambda evt: self._chatsAction(ids, action, doneText, seconds), item)

		# Translators: The first, disabled item of the menu for several selected chats.
		menu.Append(wx.ID_ANY, _("{count} chats selected").format(count=len(ids))).Enable(False)
		if archived:
			# Translators: An item in the menu for selected chats, and what is said after it was done.
			add(menu, _("Un&archive chat"), "unarchive", _("Unarchived"))
		else:
			# Translators: An item in the menu for selected chats, and what is said after it was done.
			add(menu, _("&Archive chat"), "archive", _("Archived"))
		muteMenu = wx.Menu()
		# Translators: How long to mute the selected chats, in a submenu.
		for label, seconds in ((_("8 hours"), 8 * 3600), (_("1 week"), 7 * 86400), (_("Always"), -1)):
			# Translators: Reported after the selected chats were muted.
			add(muteMenu, label, "mute", _("Muted"), seconds)
		# Translators: A submenu in the menu for selected chats: how long to mute them.
		menu.AppendSubMenu(muteMenu, _("Mute n&otifications"))
		# Translators: An item in the menu for selected chats, and what is said after it was done.
		add(menu, _("Unmute n&otifications"), "unmute", _("Unmuted"))
		# Translators: An item in the menu for selected chats, and what is said after it was done.
		add(menu, _("Pin &chat"), "pin", _("Pinned"))
		# Translators: An item in the menu for selected chats, and what is said after it was done.
		add(menu, _("Unpin &chat"), "unpin", _("Unpinned"))
		# Translators: An item in the menu for selected chats, and what is said after it was done.
		add(menu, _("Mark as &read"), "markRead", _("Marked as read"))
		# Translators: An item in the menu for selected chats, and what is said after it was done.
		add(menu, _("Ma&rk as unread"), "markUnread", _("Marked as unread"))
		# Translators: An item in the menu for selected chats: deletes them.
		item = menu.Append(wx.ID_ANY, _("&Delete chats\tDelete"))
		menu.Bind(wx.EVT_MENU, lambda evt: self._deleteChats(), item)
		# Translators: An item in the menu for selected chats: unselects them all.
		item = menu.Append(wx.ID_ANY, _("C&lear selection\tEscape"))
		menu.Bind(wx.EVT_MENU, lambda evt: self._clearSelection(listBox), item)
		listBox.PopupMenu(menu)
		menu.Destroy()

	def _chatsAction(self, ids: list[str], action: str, doneText: str, seconds: int = 0) -> None:
		def done(result: dict) -> None:
			self._selectedChatIds.clear()
			ui.message(doneText)
			self.refreshChats()

		self._run(lambda: self.session.chatsAction(ids, action, seconds), done)

	def _deleteChats(self) -> None:
		chats = self._chosenChats()
		if not chats:
			return
		if len(chats) == 1 and _isJoinedGroup(chats[0]):
			# WhatsApp deletes a group only after the user exits it: Delete offers that, Exit and delete
			# first, rather than doing nothing.
			self._exitGroup(chats[0])
			return
		names = ", ".join(c.get("title", "") for c in chats[:5]) + ("…" if len(chats) > 5 else "")
		if not askYesNo(
			self,
			# Translators: Asked before deleting chats, with how many and their names.
			_("Delete {count} chats? Their messages are removed from this device.\n\n{names}").format(
				count=len(chats), names=names
			),
			# Translators: The title of the question before deleting chats.
			_("Delete chats"),
		):
			return

		def done(result: dict) -> None:
			self._selectedChatIds.clear()
			sounds.play(sounds.DISCARD)
			# Translators: Reported after selected chats were deleted, with how many.
			message = _("{count} deleted").format(count=result.get("done", 0))
			if result.get("skipped"):
				# Translators: Added when some selected groups were not deleted because the user is still in them.
				message += ". " + _("{count} groups were kept: exit a group before deleting it").format(
					count=result["skipped"]
				)
			ui.message(message)
			self.refreshChats()

		self._run(lambda: self.session.chatsAction([c["id"] for c in chats], "delete"), done)

	# Keys and closing -----------------------------------------------------------------------------------

	def _onActivate(self, evt: wx.ActivateEvent) -> None:
		"""Online while this window is in front, as WhatsApp Web is; offline once the user goes to another
		program. The add-on's own dialogs over this window keep it online."""
		evt.Skip()
		if evt.GetActive():
			self._setOnline(True)
		else:
			wx.CallLater(400, self._checkStillInFront)

	def _checkStillInFront(self) -> None:
		import ctypes

		user32 = ctypes.windll.user32
		pid = ctypes.c_ulong()
		user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
		if pid.value != os.getpid():
			self._setOnline(False)

	def _setOnline(self, online: bool) -> None:
		if self and online != self._online:
			self._online = online
			self._run(lambda: self.session.setOnline(online))

	def onCallChanged(self) -> None:
		"""During a call, a bar at the top says who it is with and offers Return to call and Mute."""
		calls = self.calls
		inCall = bool(calls and calls.inCall)
		if inCall:
			# Translators: The bar at the top of the WhatsApp window during a call, with who it is with.
			self.callText.SetLabel(_("In a call with {name}").format(name=calls.call.get("name", "")))
			self.callMuteButton.SetLabel(
				# Translators: A button in the WhatsApp window during a call: turns the microphone back on.
				_("Unmute microphone (Ctrl+M)")
				if calls.muted
				# Translators: A button in the WhatsApp window during a call: turns the microphone off.
				else _("Mute microphone (Ctrl+M)")
			)
		if self.callPanel.IsShown() != inCall:
			self.callPanel.Show(inCall)
			self.Layout()

	def _onCharHook(self, evt: wx.KeyEvent) -> None:
		key = evt.GetKeyCode()
		if volumes.handleKey(key, evt.GetModifiers(), self.session):
			return
		# A chat's own keys work where its controls are; the chat list beside it keeps its own.
		inConversation = self._focusInConversation()
		chatOpen = self.chat is not None and self.conversationPanel.IsShown()
		focus = wx.Window.FindFocus()
		if key == ord("W") and evt.GetModifiers() == wx.MOD_CONTROL:
			if chatOpen and (self._recording or self._hasRecording):
				# Closing the chat would throw the voice note away; it says what to do instead, as Escape does.
				sounds.play(sounds.DISCARD)
				# Translators: Said when the user tries to close a chat that still has a voice note recorded.
				ui.message(_("Send the voice note with Ctrl+Shift+R or throw it away with Ctrl+D first"))
			elif chatOpen:
				self.showChats()
			else:
				# Translators: Said when the user presses Ctrl+W, which closes a chat, while none is open.
				ui.message(_("No chat open"))
			return
		if focus in (self.chatList, self.archivedList, self.messageList) and self._handleSelectionKey(
			focus, evt
		):
			return
		if key == wx.WXK_ESCAPE and not evt.HasAnyModifiers():
			if focus in (self.chatList, self.archivedList, self.messageList) and self._selectionOf(focus)[0]:
				self._clearSelection(focus)
			elif inConversation and self._attachments:
				self._clearAttachments()
			elif self._mentionMatches or self._emojiMatches:
				self._closeMentions()
				self._closeEmoji()
				# Translators: Read out when the user closes the list of people to mention.
				ui.message(_("Suggestions closed"))
			elif self._playingId is not None:
				self._stopPlayback()
			elif self._recording:
				self._discardRecording()
			elif chatOpen and self._hasRecording:
				# A recorded note is not thrown away by Escape, as leaving the chat would: it says what to do.
				self._run(self.session.stopAudio, onError=lambda e: None)
				sounds.play(sounds.DISCARD)
				# Translators: Said when the user tries to close a chat that still has a voice note recorded.
				ui.message(_("Send the voice note with Ctrl+Shift+R or throw it away with Ctrl+D first"))
			elif inConversation and self._editing is not None:
				self._cancelEdit()
			elif inConversation and self._replyTo is not None:
				self._cancelReply()
			elif chatOpen:
				# From the chat or from the list beside it: the chat closes first, the window only after.
				self.showChats()
			else:
				self.Close()
			return
		if (
			key in (wx.WXK_UP, wx.WXK_DOWN)
			and not evt.HasAnyModifiers()
			and self._mentionMatches
			and wx.Window.FindFocus() is self.composeBox
		):
			self._moveMention(-1 if key == wx.WXK_UP else 1)
			return
		if (
			key in (wx.WXK_LEFT, wx.WXK_RIGHT)
			and not evt.HasAnyModifiers()
			and self._emojiMatches
			and focus is self.composeBox
		):
			self._moveEmoji(-1 if key == wx.WXK_LEFT else 1)
			return
		if (
			key == wx.WXK_UP
			and not evt.HasAnyModifiers()
			and inConversation
			and focus is self.composeBox
			and not self.composeBox.GetValue()
			and self._editing is None
			and not self._attachments
			and not self._recording
			and not self._hasRecording
		):
			self._editLastMessage()
			return
		if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and focus is self.composeBox:
			if evt.GetModifiers() == wx.MOD_SHIFT:
				self.composeBox.WriteText("\n")
				return
			if not evt.HasAnyModifiers():
				self._sendText()
				return
		if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not evt.HasAnyModifiers():
			# The dialog would take Enter for its default button before the lists see it.
			focus = wx.Window.FindFocus()
			if focus in (self.chatList, self.archivedList):
				self._openSelectedChat()
				return
			if focus is self.statusList:
				self._viewStatus()
				return
			if focus is self.callsList:
				self._callBack()
				return
			if focus is self.messageList:
				self._activateMessage()
				return
			if focus is self.sectionList:
				self.showTab(self.sectionList.GetSelection())
				return
			if focus is self.starredList:
				self._openStarred()
				return
			if focus is self.channelList:
				self._openChannel()
				return
			if focus is self.communityList:
				self._openCommunity()
				return
			if focus is self.settingsList:
				self._openSetting()
				return
		modifiers = evt.GetModifiers()
		if inConversation and focus is self.composeBox and (modifiers, key) in _FORMAT_KEYS:
			self._format(*_FORMAT_KEYS[(modifiers, key)])
			return
		if inConversation and modifiers == wx.MOD_CONTROL and key == ord("T"):
			if focus is self.composeBox:
				self._translateMyText()
				return
			if focus is self.messageList:
				self._translateMessage()
				return
		if modifiers == wx.MOD_CONTROL and key in (ord("/"), wx.WXK_NUMPAD_DIVIDE, wx.WXK_DIVIDE):
			self._showShortcuts()
			return
		if modifiers == wx.MOD_CONTROL and ord("1") <= key <= ord("8"):
			self.showTab(key - ord("1"))
			return
		if (
			not inConversation
			and key == wx.WXK_TAB
			and modifiers in (wx.MOD_CONTROL, wx.MOD_CONTROL | wx.MOD_SHIFT)
		):
			# Ctrl+Tab and Ctrl+Shift+Tab: the next or previous section, as they moved between tabs before.
			step = -1 if modifiers & wx.MOD_SHIFT else 1
			self.showTab((self.tabs.GetSelection() + step) % self.tabs.GetPageCount())
			return
		if (
			inConversation
			and key == wx.WXK_TAB
			and modifiers in (wx.MOD_CONTROL, wx.MOD_CONTROL | wx.MOD_SHIFT)
		):
			self._switchChat(-1 if modifiers & wx.MOD_SHIFT else 1)
			return
		if modifiers == wx.MOD_ALT and ord("1") <= key <= ord("4"):
			self._setFilter(key - ord("1"))
			return
		if modifiers == wx.MOD_ALT and key == ord("U"):
			self._nextUnread()
			return
		if modifiers == wx.MOD_CONTROL and key == ord("M") and self.calls and self.calls.inCall:
			self.calls.toggleMute()
			return
		if (
			modifiers == wx.MOD_CONTROL | wx.MOD_SHIFT
			and key == ord("G")
			and self.calls
			and self.calls.inCall
		):
			self.calls.saySpeakers()
			return
		if modifiers == wx.MOD_CONTROL | wx.MOD_SHIFT and key in (ord("N"), ord("F"), ord("M")):
			if key == ord("N"):
				self._newGroup()
			elif key == ord("F"):
				self._searchAll()
			elif inConversation:
				self._showMentions()
			return
		if modifiers == wx.MOD_CONTROL and key == ord("N"):
			self._newChat()
			return
		if inConversation and modifiers == wx.MOD_CONTROL | wx.MOD_SHIFT and key == ord("C"):
			self._startCall()
			return
		if inConversation and modifiers == wx.MOD_CONTROL and key == ord("F"):
			self._searchMessages()
			return
		if inConversation and modifiers == wx.MOD_ALT and key in (ord("L"), ord("F"), ord("I"), ord("P")):
			{
				ord("L"): self._openLinks,
				ord("F"): self._forward,
				ord("I"): self._showReceipts,
				ord("P"): self._describePhoto,
			}[key]()
			return
		if (
			inConversation
			and key == ord("V")
			and evt.GetModifiers() == wx.MOD_CONTROL
			and wx.Window.FindFocus() is self.composeBox
			and (self._pasteFiles() or self._pasteText())
		):
			return
		if inConversation and evt.GetModifiers() == wx.MOD_ALT and key in (ord("C"), ord("Y")):
			if key == ord("C"):
				self._readText()
			else:
				self._reactMenu()
			return
		# A voice note under way can be stopped, sent or thrown away from the chat list beside it too.
		hasVoiceNote = chatOpen and (self._recording or self._hasRecording)
		if (inConversation or hasVoiceNote) and key in (ord("R"), ord("D"), ord("T"), ord("S")):
			if not inConversation and modifiers not in (wx.MOD_CONTROL, wx.MOD_CONTROL | wx.MOD_SHIFT):
				evt.Skip()
				return
			if not inConversation and modifiers == wx.MOD_CONTROL and key in (ord("T"), ord("S")):
				evt.Skip()
				return
			if modifiers == wx.MOD_ALT and key == ord("R"):
				self._startReply()
				return
			if modifiers == wx.MOD_ALT and key == ord("T"):
				self._reportPresence()
				return
			if modifiers == wx.MOD_ALT and key == ord("D"):
				self._saveFile()
				return
			if modifiers == wx.MOD_CONTROL and key == ord("R"):
				self._toggleRecording()
				return
			if modifiers == wx.MOD_CONTROL | wx.MOD_SHIFT and key == ord("R"):
				self._sendVoiceNow()
				return
			if modifiers == wx.MOD_CONTROL and key == ord("S"):
				self._nextSpeed()
				return
			if modifiers == wx.MOD_CONTROL and key == ord("D"):
				self._discardRecording()
				return
			if modifiers == wx.MOD_CONTROL | wx.MOD_SHIFT and key == ord("D"):
				self._togglePause()
				return
		evt.Skip()

	def _onClose(self, evt: wx.CloseEvent) -> None:
		self._keepDraft()
		if self._recording or self._hasRecording:
			self._run(self.session.cancelRecording)
		self._stopPlayback()
		if self._ackTimer is not None:
			self._ackTimer.Stop()
			self._ackTimer = None
		if self._positionFollow is not None:
			self._positionFollow.Stop()
			self._positionFollow = None
		# Offline again, as WhatsApp Web is when it is no longer in front.
		if self._online:
			self._online = False
			self._run(lambda: self.session.setOnline(False))
		self._onClosed()
		self.Destroy()


def _nameMatches(person: dict, typed: str) -> bool:
	"""Whether any word of the person's contact name or WhatsApp name starts with what was typed."""
	if not typed:
		return True
	# The name as a mention writes it, without the words saying someone is not a contact.
	name = _mentionText(person)
	words = f"{name} {person.get('pushname', '')}".lower().split()
	return any(word.startswith(typed) for word in words) or name.lower().startswith(typed)


def _mentionText(person: dict) -> str:
	"""The name an @mention of this person writes in the message box."""
	return person.get("mention") or person.get("name", "")


class ContactInfoDialog(wx.Dialog):
	"""Contact or group info, as WhatsApp shows it: details to read line by line, then a list of groups
	in common or of the group's people."""

	def __init__(self, parent: wx.Window, info: dict, presence: str) -> None:
		isGroup = info.get("kind") == "group"
		title = (
			# Translators: The title of the dialog with a group's info.
			_("Group info")
			if isGroup
			# Translators: The title of the dialog with a contact's info.
			else _("Contact info")
		)
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the box with a contact's or group's details.
		sizer.Add(wx.StaticText(self, label=_("&Details:")))
		details = wx.TextCtrl(
			self,
			value="\n".join(infoLines(info, presence)),
			style=wx.TE_MULTILINE | wx.TE_READONLY,
			size=(500, 200),
		)
		sizer.Add(details, 1, wx.EXPAND | wx.BOTTOM, 6)
		if isGroup:
			people = info.get("participants") or []
			items = []
			for person in people:
				name = messageText.sender({"fromMe": True}) if person.get("isMe") else person["name"]
				# Translators: A group member who is an admin, in the group info's list.
				items.append(_("{name}, admin").format(name=name) if person.get("admin") else name)
			# Translators: The label of the list of a group's members, with how many there are.
			label = _("&Participants ({count}):").format(count=len(people))
		else:
			items = info.get("commonGroups") or []
			# Translators: The label of the list of groups the user shares with a contact.
			label = _("&Groups in common ({count}):").format(count=len(items))
		sizer.Add(wx.StaticText(self, label=label))
		sizer.Add(wx.ListBox(self, choices=items, size=(500, 160)), 1, wx.EXPAND | wx.BOTTOM, 6)
		# Translators: The button that closes a list of information.
		closeButton = wx.Button(self, wx.ID_CANCEL, label=_("Close"))
		sizer.Add(closeButton, 0, wx.ALIGN_RIGHT)
		outer = wx.BoxSizer(wx.VERTICAL)
		outer.Add(sizer, 1, wx.EXPAND | wx.ALL, 10)
		self.SetSizerAndFit(outer)
		self.CentreOnParent()
		details.SetFocus()


def infoLines(info: dict, presence: str) -> list[str]:
	"""The details in the info dialog, one per line."""
	lines = [info.get("title", "")]
	if info.get("kind") == "group":
		if info.get("description"):
			# Translators: A group's description in the group info.
			lines.append(_("Description: {text}").format(text=info["description"]))
		if info.get("created"):
			created = time.strftime("%d/%m/%Y", time.localtime(info["created"]))
			if info.get("creator"):
				# Translators: Who created a group and when, in the group info.
				lines.append(_("Created by {name} on {date}").format(name=info["creator"], date=created))
			else:
				# Translators: When a group was created, in the group info.
				lines.append(_("Created on {date}").format(date=created))
		return lines
	if presence:
		lines.append(presence)
	if info.get("phone"):
		# Translators: A contact's phone number in the contact info.
		lines.append(_("Phone: {number}").format(number=info["phone"]))
	if info.get("pushname") and info.get("pushname") != info.get("title"):
		# Translators: The name a contact gave themselves in WhatsApp, in the contact info.
		lines.append(_("WhatsApp name: {name}").format(name=info["pushname"]))
	# Translators: A contact's About text in the contact info, or a dash when they share none.
	lines.append(_("About: {text}").format(text=info.get("about") or "-"))
	if info.get("business"):
		# Translators: Said in the contact info of a WhatsApp Business account.
		lines.append(_("Business account"))
	if info.get("blocked"):
		# Translators: Said in the contact info of someone the user blocked.
		lines.append(_("Blocked"))
	return lines


class PollDialog(wx.Dialog):
	"""A poll: check the options to vote for, as in WhatsApp, and hear who chose each one."""

	def __init__(self, parent: wx.Window, poll: dict) -> None:
		# Translators: The title of the dialog that shows a poll.
		super().__init__(parent, title=_("Poll"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.poll = poll
		self.options = poll.get("options") or []
		sizer = wx.BoxSizer(wx.VERTICAL)
		howMany = (
			# Translators: Under a poll's question, when several options may be chosen.
			_("Select one or more")
			if poll.get("multiple")
			# Translators: Under a poll's question, when only one option may be chosen.
			else _("Select one")
		)
		# Translators: A poll's question, how many may be chosen, and how many people voted.
		heading = _("{question}. {howMany}. {count} voted.").format(
			question=poll.get("question", ""), howMany=howMany, count=poll.get("voters", 0)
		)
		sizer.Add(wx.StaticText(self, label=heading), 0, wx.BOTTOM, 6)
		# Translators: The label of a poll's options. Space checks one.
		sizer.Add(wx.StaticText(self, label=_("&Options:")))
		self.optionList = wx.CheckListBox(
			self, choices=[self._line(o) for o in self.options], size=(500, 180)
		)
		for index, option in enumerate(self.options):
			self.optionList.Check(index, bool(option.get("mine")))
		self.optionList.Bind(wx.EVT_CHECKLISTBOX, self._onCheck)
		self.optionList.Bind(wx.EVT_LISTBOX, lambda evt: self._showVoters())
		sizer.Add(self.optionList, 1, wx.EXPAND | wx.BOTTOM, 6)
		# Translators: The label of the box listing who chose the selected poll option.
		sizer.Add(wx.StaticText(self, label=_("Voted &by:")))
		self.votersBox = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(500, 80))
		sizer.Add(self.votersBox, 0, wx.EXPAND | wx.BOTTOM, 6)
		buttons = wx.StdDialogButtonSizer()
		# Translators: The button that sends the user's choice in a poll.
		buttons.AddButton(wx.Button(self, wx.ID_OK, label=_("&Vote")))
		# Translators: The button that closes a poll without voting.
		buttons.AddButton(wx.Button(self, wx.ID_CANCEL, label=_("Close")))
		buttons.Realize()
		sizer.Add(buttons, 0, wx.ALIGN_RIGHT)
		outer = wx.BoxSizer(wx.VERTICAL)
		outer.Add(sizer, 1, wx.EXPAND | wx.ALL, 10)
		self.SetSizerAndFit(outer)
		self.CentreOnParent()
		if self.options:
			self.optionList.SetSelection(0)
			self._showVoters()
		self.optionList.SetFocus()

	def _line(self, option: dict) -> str:
		count = len(option.get("voters") or []) + (1 if option.get("mine") else 0)
		# Translators: One poll option and how many people chose it, such as "SAB, 15.00 WIB, 5 votes".
		return _("{option}, {count} votes").format(option=option.get("name", ""), count=count)

	def _onCheck(self, evt: wx.CommandEvent) -> None:
		index = evt.GetInt()
		if not self.poll.get("multiple") and self.optionList.IsChecked(index):
			# Only one may be chosen: checking one clears the others, like radio buttons.
			for other in range(len(self.options)):
				if other != index:
					self.optionList.Check(other, False)

	def _showVoters(self) -> None:
		index = self.optionList.GetSelection()
		if index == wx.NOT_FOUND:
			return
		option = self.options[index]
		names = list(option.get("voters") or [])
		if option.get("mine"):
			names.insert(0, messageText.sender({"fromMe": True}))
		# Translators: Shown for a poll option nobody chose.
		self.votersBox.SetValue(", ".join(names) if names else _("Nobody yet"))

	def chosen(self) -> list[int]:
		return [self.options[i]["id"] for i in range(len(self.options)) if self.optionList.IsChecked(i)]


class TextDialog(wx.Dialog):
	"""A message's text alone, read-only, to read by character, word or line. Escape closes it."""

	def __init__(self, parent: wx.Window, sender: str, text: str, title: str = "") -> None:
		super().__init__(
			parent,
			# Translators: The title of the window that shows one message's text, with who sent it.
			title=title or _("Message from {sender}").format(sender=sender),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		sizer = wx.BoxSizer(wx.VERTICAL)
		box = wx.TextCtrl(
			self, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(560, 300)
		)
		sizer.Add(box, 1, wx.EXPAND | wx.ALL, 10)
		sizer.Add(
			# Translators: The button that closes a message's details.
			wx.Button(self, wx.ID_CANCEL, label=_("Close")),
			0,
			wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM,
			10,
		)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		box.SetFocus()
		box.SetInsertionPoint(0)


class DeleteDialog(wx.Dialog):
	"""Delete for me, delete for everyone (when WhatsApp allows it), or cancel."""

	FOR_ME = wx.ID_HIGHEST + 1
	FOR_EVERYONE = wx.ID_HIGHEST + 2

	def __init__(self, parent: wx.Window, summary: str, canDeleteForEveryone: bool) -> None:
		# Translators: The title of the question before deleting a message.
		super().__init__(parent, title=_("Delete message"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(
			# Translators: Asked before deleting a message, with the message.
			wx.StaticText(self, label=_("Delete this message?\n\n{message}").format(message=summary)),
			0,
			wx.ALL,
			10,
		)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button that deletes a message on this computer and the user's phone only.
		choices = [(self.FOR_ME, _("Delete for &me"))]
		if canDeleteForEveryone:
			# Translators: A button that deletes a message for everyone in the chat.
			choices.append((self.FOR_EVERYONE, _("Delete for &everyone")))
		for choiceId, label in choices:
			button = wx.Button(self, choiceId, label=label)
			button.Bind(wx.EVT_BUTTON, lambda evt, choiceId=choiceId: self.EndModal(choiceId))
			buttons.Add(button, 0, wx.RIGHT, 6)
		# Translators: A button that closes the question without deleting.
		buttons.Add(wx.Button(self, wx.ID_CANCEL, label=_("Cancel")))
		sizer.Add(buttons, 0, wx.ALL, 10)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.FindWindowById(wx.ID_CANCEL, self).SetFocus()


def filterNames() -> list[str]:
	return [
		# Translators: A chat list filter, like WhatsApp's tabs.
		_("All"),
		# Translators: A chat list filter, like WhatsApp's tabs.
		_("Unread"),
		# Translators: A chat list filter, like WhatsApp's tabs.
		_("Groups"),
		# Translators: A chat list filter, like WhatsApp's tabs.
		_("Favorites"),
	]


def _passesFilter(chat: dict, chatFilter: str) -> bool:
	if chatFilter == "unread":
		return messageText.isUnread(chat)
	if chatFilter == "groups":
		return bool(chat.get("isGroup"))
	if chatFilter == "favorites":
		return bool(chat.get("favorite"))
	return True


def _isJoinedGroup(chat: dict) -> bool:
	"""A group the user is still in, other than a community's announcements, which one leaves with the
	community: WhatsApp has the user exit it before the chat can be deleted."""
	return bool(chat.get("isGroup") and not chat.get("left") and not chat.get("announcementGroup"))


class RepliesDialog(wx.Dialog):
	"""The replies to a community announcement, oldest first, and a box to reply to it."""

	def __init__(self, window: "ChatWindow", message: dict) -> None:
		super().__init__(
			window,
			# Translators: The title of the window with the replies to a community announcement.
			title=_("Replies"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self.window = window
		self.message = message
		self.replies: list[dict] = []
		self.loaded = False
		sizer = wx.BoxSizer(wx.VERTICAL)
		announcement = messageText.messageLine(message, True)
		sizer.Add(wx.StaticText(self, label=announcement[:300]), 0, wx.ALL, 10)
		# Translators: The label of the list of replies to a community announcement.
		sizer.Add(wx.StaticText(self, label=_("&Replies:")), 0, wx.LEFT | wx.RIGHT, 10)
		# Translators: Shown in the list of replies while they load.
		self.list = wx.ListBox(self, choices=[_("Loading\u2026")], size=(600, 300))
		sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 10)
		# Translators: The label of the box for replying to a community announcement.
		sizer.Add(wx.StaticText(self, label=_("&Your reply:")), 0, wx.LEFT | wx.RIGHT, 10)
		self.box = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.box.Bind(wx.EVT_TEXT_ENTER, lambda evt: self._send())
		sizer.Add(self.box, 0, wx.EXPAND | wx.ALL, 10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: The button that sends a reply to a community announcement.
		send = wx.Button(self, label=_("&Send"))
		send.Bind(wx.EVT_BUTTON, lambda evt: self._send())
		buttons.Add(send, 0, wx.RIGHT, 6)
		# Translators: The button that closes the replies window.
		buttons.Add(wx.Button(self, wx.ID_CANCEL, label=_("Close")))
		sizer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.list.SetFocus()
		self._load()

	def _load(self, focusLast: bool = False) -> None:
		self.window._run(
			lambda: self.window.session.replies(self.message["id"]), lambda r: self._show(r, focusLast)
		)

	def _show(self, replies: list[dict], focusLast: bool) -> None:
		if not self:
			return
		self.replies = replies
		self.loaded = True
		lines = [
			messageText.messageLine(
				{
					"type": "revoked" if r.get("revoked") else "chat",
					"fromMe": r.get("fromMe"),
					"sender": r.get("sender"),
					"text": r.get("text") or "",
					"t": r.get("t", 0),
					"ack": None,
				},
				True,
			)
			for r in replies
		]
		# Translators: Shown in the list of replies when an announcement has none yet.
		self.list.Set(lines or [_("No replies yet")])
		self.list.SetSelection(len(lines) - 1 if focusLast and lines else 0)
		if focusLast and lines:
			ui.message(lines[-1])

	def _send(self) -> None:
		text = self.box.GetValue().strip()
		if not text:
			self.box.SetFocus()
			return

		def sent(result: object) -> None:
			if not self:
				return
			self.box.ChangeValue("")
			sounds.play(sounds.SENT)
			# Translators: Reported after replying to a community announcement.
			ui.message(_("Reply sent"))
			self._load(focusLast=True)

		self.window._run(lambda: self.window.session.sendReply(self.message["id"], text), sent)


class ListDialog(wx.Dialog):
	"""A list to choose one item from with Enter."""

	def __init__(self, parent: wx.Window, title: str, items: list[str], okLabel: str | None = None) -> None:
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		sizer = wx.BoxSizer(wx.VERTICAL)
		# The list is named after the dialog, so NVDA says what it lists when it gets the focus.
		sizer.Add(wx.StaticText(self, label=title), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
		self.list = wx.ListBox(self, choices=items, size=(600, 300))
		self.list.SetSelection(0)
		self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self.EndModal(wx.ID_OK))
		self.list.Bind(wx.EVT_CHAR_HOOK, self._onKey)
		sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 10)
		buttons = wx.StdDialogButtonSizer()
		# Translators: The button that goes to the chosen message.
		buttons.AddButton(wx.Button(self, wx.ID_OK, label=okLabel or _("&Go to message")))
		# Translators: The button that closes a list of messages.
		buttons.AddButton(wx.Button(self, wx.ID_CANCEL, label=_("Close")))
		buttons.Realize()
		sizer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.list.SetFocus()

	def _onKey(self, evt: wx.KeyEvent) -> None:
		if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self.EndModal(wx.ID_OK)
			return
		evt.Skip()

	def selection(self) -> int:
		return max(0, self.list.GetSelection())


class ChatPickerDialog(wx.Dialog):
	"""Choose chats to forward to: type to narrow the list, Space to check, Enter to forward."""

	def __init__(
		self, parent: wx.Window, chats: list[dict], title: str | None = None, okLabel: str | None = None
	) -> None:
		super().__init__(
			parent,
			# Translators: The title of the dialog for choosing the chats to forward a message to.
			title=title or _("Forward to"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self.chats = chats
		self.shown: list[dict] = []
		self.checked: set[str] = set()
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the box that narrows the list of chats to forward to.
		sizer.Add(wx.StaticText(self, label=_("&Search chats:")), 0, wx.LEFT | wx.TOP, 10)
		self.searchBox = wx.TextCtrl(self)
		self.searchBox.Bind(wx.EVT_TEXT, lambda evt: self._fill())
		sizer.Add(self.searchBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		# Translators: The label of the list of chats to forward to. Space checks one.
		sizer.Add(wx.StaticText(self, label=_("&Chats (Space checks):")), 0, wx.LEFT | wx.TOP, 10)
		self.list = wx.CheckListBox(self, size=(500, 300))
		self.list.Bind(wx.EVT_CHECKLISTBOX, self._onCheck)
		sizer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		buttons = wx.StdDialogButtonSizer()
		# Translators: The button that forwards the message to the checked chats.
		buttons.AddButton(wx.Button(self, wx.ID_OK, label=okLabel or _("&Forward")))
		# Translators: A button that closes the dialog without forwarding.
		buttons.AddButton(wx.Button(self, wx.ID_CANCEL, label=_("Cancel")))
		buttons.Realize()
		sizer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self._fill()
		self.searchBox.SetFocus()

	def _fill(self) -> None:
		query = self.searchBox.GetValue().strip().lower()
		self.shown = [c for c in self.chats if not query or query in c.get("title", "").lower()][:200]
		self.list.Set([c.get("title", "") for c in self.shown])
		for index, chat in enumerate(self.shown):
			self.list.Check(index, chat["id"] in self.checked)
		if self.shown:
			self.list.SetSelection(0)

	def _onCheck(self, evt: wx.CommandEvent) -> None:
		chat = self.shown[evt.GetInt()]
		if self.list.IsChecked(evt.GetInt()):
			self.checked.add(chat["id"])
		else:
			self.checked.discard(chat["id"])

	def chosen(self) -> list[dict]:
		if not self.checked:
			# Nothing checked: forward to the selected chat, as a quick choice.
			index = self.list.GetSelection()
			return [self.shown[index]] if index != wx.NOT_FOUND and self.shown else []
		return [c for c in self.chats if c["id"] in self.checked]


def tabNames() -> list[str]:
	return [
		# Translators: A tab of the add-on's window, like WhatsApp's: the chats.
		_("Chats (Ctrl+1)"),
		# Translators: A tab of the add-on's window, like WhatsApp's: status updates.
		_("Status (Ctrl+2)"),
		# Translators: A tab of the add-on's window, like WhatsApp's: recent calls.
		_("Calls (Ctrl+3)"),
		# Translators: A tab of the add-on's window: archived chats.
		_("Archived (Ctrl+4)"),
		# Translators: A section of the add-on's window, like WhatsApp's: starred messages.
		_("Starred (Ctrl+5)"),
		# Translators: A section of the add-on's window, like WhatsApp's: the channels the user follows.
		_("Channels (Ctrl+6)"),
		# Translators: A section of the add-on's window, like WhatsApp's: the user's communities.
		_("Communities (Ctrl+7)"),
		# Translators: A section of the add-on's window, like WhatsApp's: profile, privacy and more.
		_("Settings (Ctrl+8)"),
	]


def _selectedId(listBox: wx.ListBox, items: list[dict]) -> str | None:
	"""The id of the item selected in a list that shows items, or None."""
	index = listBox.GetSelection()
	if index == wx.NOT_FOUND or index >= len(items):
		return None
	return items[index].get("id")


def _fillList(
	listBox: wx.ListBox,
	lines: list[str],
	items: list[dict] | None = None,
	selectedId: str | None = None,
) -> None:
	"""Put lines in a list, changing nothing when nothing changed.

	The list is refreshed in the background, for example when a message arrives, and items move. So the
	selection stays on the same item, found by its id, rather than on the same position: Enter, Delete or
	the menu must act on the item the user last heard, never on one that moved into its place.

	:param listBox: The list.
	:param lines: What it shows, one line per item.
	:param items: The items the lines are for, each with an "id". Without them the position is kept.
	:param selectedId: The id of the item selected before the items changed, from _selectedId.
	"""
	if listBox.GetItems() == lines:
		return
	selection = listBox.GetSelection()
	listBox.Set(lines)
	if not lines:
		return
	if items is not None and selectedId is not None:
		index = next((i for i, item in enumerate(items) if item.get("id") == selectedId), -1)
		if index >= 0:
			listBox.SetSelection(index)
			return
	listBox.SetSelection(min(max(selection, 0), len(lines) - 1))


class StatusViewer(wx.Dialog):
	"""Status updates one by one, as in WhatsApp: arrows go through them, the next person follows."""

	def __init__(
		self,
		parent: wx.Window,
		session: WhatsAppSession,
		people: list[dict],
		personIndex: int,
		openFile: Callable[[dict], None],
		describe: Callable[[dict], None],
		save: Callable[[dict, wx.Window], None],
	) -> None:
		# Translators: The title of the window that shows status updates.
		super().__init__(parent, title=_("Status"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.session = session
		self.people = people
		self.person = personIndex
		self.openFile = openFile
		self.describe = describe
		self.saveFile = save
		self._playingId: str | None = None
		self._liked: set[str] = set()
		"""Statuses liked in this viewer: each like is a message, so a second press sends nothing."""
		# Stopping and playing go to the browser one after another, in the order asked: from two threads,
		# the stop for the status left could arrive after the play for the next one, and cut it off.
		self._audio = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whatsAppAccess.statusAudio")
		self.Bind(wx.EVT_WINDOW_DESTROY, self._onDestroy)
		items = people[personIndex].get("items") or []
		# Start at the first status not seen yet, as WhatsApp does.
		self.item = next((i for i, item in enumerate(items) if not item.get("viewed")), 0)
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.textBox = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(520, 140))
		sizer.Add(self.textBox, 1, wx.EXPAND | wx.ALL, 8)
		help = wx.StaticText(
			self,
			label=_(
				# Translators: The keys of the status window.
				"Arrows: next and previous. Ctrl+arrows: next and previous person. Voice and video statuses "
				"play by themselves; Enter stops or plays again, and describes a photo. "
				"Alt+Y: like. Alt+R: reply. Alt+D: download. Escape: close."
			),
		)
		sizer.Add(help, 0, wx.LEFT | wx.RIGHT, 8)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		for label, action in (
			# Translators: A button in the status window.
			(_("&Like"), self.like),
			# Translators: A button in the status window.
			(_("&Reply"), self.reply),
			# Translators: A button in the status window: plays or stops a voice or video status, or
			# describes a photo.
			(_("&Play, stop or describe"), self.open),
			# Translators: A button in the status window: saves the photo, video or voice status as a file.
			(_("&Download"), self.download),
		):
			button = wx.Button(self, label=label)
			button.Bind(wx.EVT_BUTTON, lambda evt, action=action: action())
			buttons.Add(button, 0, wx.RIGHT, 6)
		# Translators: The button that closes the status viewer.
		buttons.Add(wx.Button(self, wx.ID_CANCEL, label=_("Close")))
		sizer.Add(buttons, 0, wx.ALL, 8)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.Bind(wx.EVT_CHAR_HOOK, self._onKey)
		self.textBox.SetFocus()
		self.show()

	@property
	def current(self) -> dict:
		return (self.people[self.person].get("items") or [])[self.item]

	def show(self) -> None:
		person = self.people[self.person]
		text = messageText.statusItemText(person, self.item)
		self.textBox.SetValue(text)
		ui.message(text)
		item = self.current
		# Voice and video statuses play by themselves, as in WhatsApp.
		if item.get("type") in PLAYED_TYPES:
			self.play(item, toggle=False)
		if not item.get("viewed"):
			item["viewed"] = True
			person["unread"] = max(0, int(person.get("unread") or 0) - 1)
			threading.Thread(
				target=self._quietly,
				args=(self.session.statusSeen, item["id"]),
				name="whatsAppAccess.status",
				daemon=True,
			).start()

	@staticmethod
	def _quietly(work: Callable[..., Any], *args: Any) -> None:
		try:
			work(*args)
		except WhatsAppError as e:
			log.debugWarning(f"WhatsApp Access: status: {e}")

	def _onDestroy(self, evt: wx.WindowDestroyEvent) -> None:
		if evt.GetEventObject() is self:
			self._audio.shutdown(wait=False)
		evt.Skip()

	def move(self, step: int, byPerson: bool = False) -> None:
		self._audio.submit(self._quietly, self.session.stopAudio)
		person, item = self.person, self.item
		if byPerson:
			person += step
			item = 0
		else:
			item += step
			count = len(self.people[person].get("items") or [])
			if item >= count:
				person, item = person + 1, 0
			elif item < 0:
				person -= 1
				item = (
					len(self.people[person].get("items") or []) - 1 if 0 <= person < len(self.people) else 0
				)
		if not 0 <= person < len(self.people):
			# Translators: Reported at the first or last status update.
			ui.message(_("No more status updates"))
			return
		self.person, self.item = person, item
		self.show()

	def open(self) -> None:
		"""Enter: play or stop a voice or video status here, describe a photo, or open a document."""
		item = self.current
		kind = item.get("type")
		if kind in PLAYED_TYPES:
			self.play(item)
		elif kind in ("image", "sticker"):
			self.describe(item)
		elif kind in OPENED_TYPES:
			self.openFile(item)
		else:
			ui.message(messageText.content(item))

	def download(self) -> None:
		"""Alt+D: save the status's photo, video or voice where the user chooses."""
		item = self.current
		if item.get("type") not in FILE_TYPES:
			# Translators: Reported when the user asks to download a status that is only text.
			ui.message(_("This status is only text"))
			return
		self.saveFile(item, self)

	def play(self, item: dict, toggle: bool = True) -> None:
		"""Plays the status's sound in the hidden browser, as voice notes are; a second Enter stops it."""
		itemId = item["id"]
		wasThis = self._playingId == itemId
		self._playingId = itemId

		volume = int(config.conf[CONFIG_SECTION]["statusVolume"])

		def work() -> None:
			if toggle and wasThis and self.session.stopAudio():
				self._playingId = None
				return
			self.session.setPlaybackVolume(volume)
			self.session.playMessage(itemId)

		self._audio.submit(self._quietly, work)

	def like(self) -> None:
		item = self.current
		name = self.people[self.person].get("name", "")
		if item["id"] in self._liked:
			# Each like is a message in the poster's chat, so pressing again must not send another.
			# Translators: Said when the user likes a status they already liked.
			ui.message(_("Already liked"))
			return
		self._liked.add(item["id"])

		def work() -> None:
			try:
				self.session.likeStatus(item["id"])
			except WhatsAppError as e:
				self._liked.discard(item["id"])
				wx.CallAfter(ui.message, errorText(e))
				return
			sounds.play(sounds.SENT)
			wx.CallAfter(
				ui.message,
				# Translators: Reported after the user liked a status. WhatsApp Web cannot react to a status,
				# so the heart goes to the poster's chat as a reply to the status. {name} is the poster.
				_("Liked: a heart was sent to {name} as a reply to the status").format(name=name),
			)

		threading.Thread(target=work, name="whatsAppAccess.like", daemon=True).start()

	def reply(self) -> None:
		item = self.current
		name = self.people[self.person].get("name", "")
		dialog = wx.TextEntryDialog(
			self,
			# Translators: Asks for a reply to someone's status; it goes to their chat.
			_("Reply to {name}'s status:").format(name=name),
			# Translators: The title of the dialog for replying to a status.
			_("Reply to status"),
		)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			text = dialog.GetValue().strip()
		finally:
			dialog.Destroy()
		if not text:
			return

		def work() -> None:
			try:
				self.session.replyStatus(item["id"], text)
			except WhatsAppError as e:
				wx.CallAfter(ui.message, errorText(e))
				return
			sounds.play(sounds.SENT)
			# Translators: Reported after a reply to a status was sent.
			wx.CallAfter(ui.message, _("Sent"))

		threading.Thread(target=work, name="whatsAppAccess.statusReply", daemon=True).start()

	def _onKey(self, evt: wx.KeyEvent) -> None:
		key, modifiers = evt.GetKeyCode(), evt.GetModifiers()
		if volumes.handleKey(key, modifiers, self.session):
			return
		if key in (wx.WXK_RIGHT, wx.WXK_DOWN, wx.WXK_LEFT, wx.WXK_UP) and modifiers in (
			wx.MOD_NONE,
			wx.MOD_CONTROL,
		):
			step = 1 if key in (wx.WXK_RIGHT, wx.WXK_DOWN) else -1
			self.move(step, byPerson=modifiers == wx.MOD_CONTROL)
			return
		if (
			key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
			and modifiers == wx.MOD_NONE
			and wx.Window.FindFocus() is self.textBox
		):
			self.open()
			return
		if modifiers == wx.MOD_ALT and key in (ord("Y"), ord("R"), ord("P"), ord("D")):
			{
				ord("Y"): self.like,
				ord("R"): self.reply,
				# As the button "Play, stop or describe" says: describe a photo, play or stop the rest.
				ord("P"): lambda: self.open(),
				ord("D"): self.download,
			}[key]()
			return
		if key == wx.WXK_ESCAPE:
			self._audio.submit(self._quietly, self.session.stopAudio)
		evt.Skip()


class NotificationDialog(wx.Dialog):
	"""How new messages from one chat are announced: always, never, or as usual; which sound; how much is said."""

	def __init__(self, parent: wx.Window, title: str, rule: "notifications.Rule") -> None:
		# Translators: The title of the dialog with one chat's notification settings, with the chat's name.
		super().__init__(parent, title=_("Notifications for {chat}").format(chat=title))
		self.customPath = rule.sound if os.path.isabs(rule.sound) else ""
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = wx.FlexGridSizer(cols=2, vgap=6, hgap=6)

		def labeled(label: str, make: Callable[[], wx.Window]) -> Any:
			# Screen readers name a control by the text made just before it: the label comes first.
			text = wx.StaticText(self, label=label)
			control = make()
			helper.Add(text, 0, wx.ALIGN_CENTER_VERTICAL)
			helper.Add(control, 1, wx.EXPAND)
			return control

		self.announceChoice = labeled(
			# Translators: The label of the choice of whether this chat's new messages are read out.
			_("Read out new &messages:"),
			lambda: wx.Choice(
				self,
				choices=[
					# Translators: A choice for one chat's notifications.
					_("As in the general settings"),
					# Translators: A choice for one chat's notifications.
					_("Always, even when the chat is muted"),
					# Translators: A choice for one chat's notifications.
					_("Never"),
				],
			),
		)
		self.announceChoice.SetSelection(notifications.ANNOUNCE_CHOICES.index(rule.announce))
		self.soundKeys = ["default", *notifications.NOTIFICATION_SOUNDS, "none", "custom"]
		self.soundChoice = labeled(
			# Translators: The label of the choice of sound for this chat's new messages.
			_("&Sound:"),
			lambda: wx.Choice(
				self,
				choices=[
					# Translators: A choice of sound for one chat: the sound of personal chats or groups.
					_("As in the general settings"),
					# Translators: A sound for new messages in one chat's settings.
					_("Classic"),
					# Translators: A sound for new messages in one chat's settings.
					_("Bell"),
					# Translators: A sound for new messages in one chat's settings.
					_("Kalimba"),
					# Translators: A sound for new messages in one chat's settings.
					_("Flute"),
					# Translators: No sound for new messages in one chat's settings.
					_("None"),
					# Translators: A choice of sound for one chat: a WAV file the user picks.
					_("A WAV file of your own"),
				],
			),
		)
		key = "custom" if self.customPath else rule.sound
		self.soundChoice.SetSelection(self.soundKeys.index(key) if key in self.soundKeys else 0)
		self.contentChoice = labeled(
			# Translators: The label of the choice of how much is said for this chat's new messages.
			_("&What to say:"),
			lambda: wx.Choice(
				self,
				choices=[
					# Translators: A choice for one chat's notifications.
					_("As in the general settings"),
					# Translators: A choice for one chat's notifications.
					_("Who it is from and what it says"),
					# Translators: A choice for one chat's notifications.
					_("Only who it is from"),
				],
			),
		)
		self.contentChoice.SetSelection(notifications.CONTENT_CHOICES.index(rule.content))
		sizer.Add(helper, 0, wx.ALL, 10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button that picks a WAV file as this chat's sound.
		chooseButton = wx.Button(self, label=_("&Choose WAV file\u2026"))
		chooseButton.Bind(wx.EVT_BUTTON, lambda evt: self._chooseFile())
		# Translators: A button that plays the chosen sound.
		playButton = wx.Button(self, label=_("&Play sound"))
		playButton.Bind(wx.EVT_BUTTON, lambda evt: self._play())
		buttons.Add(chooseButton, 0, wx.RIGHT, 6)
		buttons.Add(playButton)
		sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT, 10)
		sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.announceChoice.SetFocus()

	def _chooseFile(self) -> None:
		dialog = wx.FileDialog(
			self,
			# Translators: The title of the file picker for a chat's own sound.
			_("Choose a WAV file"),
			wildcard="WAV (*.wav)|*.wav",
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		try:
			if dialog.ShowModal() == wx.ID_OK:
				self.customPath = dialog.GetPath()
				self.soundChoice.SetSelection(self.soundKeys.index("custom"))
				ui.message(os.path.basename(self.customPath))
		finally:
			dialog.Destroy()

	def _sound(self) -> str:
		key = self.soundKeys[self.soundChoice.GetSelection()]
		if key == "custom":
			return self.customPath or "default"
		return key

	def _play(self) -> None:
		sound = self._sound()
		if sound == "default":
			sound = sounds.RECEIVED
		if sound != "none":
			# A preview, which the next one or closing the dialog stops, however long the file.
			sounds.preview(sound)

	def rule(self) -> "notifications.Rule":
		return notifications.Rule(
			notifications.ANNOUNCE_CHOICES[self.announceChoice.GetSelection()],
			self._sound(),
			notifications.CONTENT_CHOICES[self.contentChoice.GetSelection()],
		)
