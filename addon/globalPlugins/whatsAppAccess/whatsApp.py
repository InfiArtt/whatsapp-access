# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""The connection to WhatsApp Web: finds its tab, installs pageBridge.js there and calls it.

Calls block until WhatsApp answers, so run them on a background thread, never on NVDA's main thread.
It imports nothing from NVDA, so it can be tested on its own.
"""

import base64
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, BinaryIO

from . import cdp, fileSafety

EVENT_BINDING = "__waAccessEvent"
READY_TIMEOUT_SECONDS = 60.0
UPLOAD_CHUNK_BYTES = 512 * 1024
# Files go through the browser's memory; WhatsApp's own limit for documents is higher.
MAX_FILE_BYTES = 200 * 2**20
# How often the add-on tells the page it is still there. The page gives up after 60 seconds.
HEARTBEAT_SECONDS = 20.0
# WhatsApp Web keeps about 100 to 300 MB of JavaScript. Every few minutes the add-on looks, and above
# this it asks the browser to give memory back, as Chromium does by itself when the computer runs low.
# Nothing is reloaded, so calls, recordings and uploads go on undisturbed.
MEMORY_CHECK_SECONDS = 300.0
MEMORY_TRIM_BYTES = 500 * 1024 * 1024
BRIDGE_PATH = os.path.join(os.path.dirname(__file__), "pageBridge.js")
_BRIDGE_MISSING = 'typeof window.__waAccess === "undefined"'

_log = logging.getLogger(__name__)


class WhatsAppError(Exception):
	"""Something went wrong. code says what, for the add-on to explain to the user.

	Codes: noBrowser, refused, approvalTimedOut, noWhatsAppTab, notReady, disconnected, chatNotFound, emptyMessage, sendFailed,
	microphone, notRecording, noRecording, emptyRecording, mediaGone, noDownload, saveFailed, failed.
	"""

	def __init__(self, code: str, detail: str = "") -> None:
		super().__init__(f"{code}: {detail}" if detail else code)
		self.code = code
		self.detail = detail


def _codeFromPageError(description: str) -> WhatsAppError:
	"""pageBridge.js throws Error("code") or Error("code:detail"); the browser adds "Error: " and a stack."""
	firstLine = description.splitlines()[0] if description else ""
	firstLine = firstLine.removeprefix("Error: ")
	code, _, detail = firstLine.partition(":")
	known = {
		"chatNotFound",
		"emptyMessage",
		"sendFailed",
		"microphone",
		"notRecording",
		"noRecording",
		"emptyRecording",
		"mediaGone",
		"noMedia",
		"messageNotFound",
		"alreadyRecording",
		"recording",
		"sampleRate",
		"cannotRevoke",
		"notAPoll",
		"fileTooLarge",
		"noDownload",
		"notMine",
		"groupCall",
		"callNotStarted",
		"badNumber",
		"notOnWhatsApp",
		"noUpload",
		"oneOptionOnly",
	}
	if code in known:
		return WhatsAppError(code, detail)
	return WhatsAppError("failed", description[:500])


@dataclass(frozen=True)
class HiddenOptions:
	"""How to set up the add-on's own hidden browser when connecting to it."""

	userAgent: str
	userAgentMetadata: dict
	url: str


def _createFreeFile(folder: str, name: str) -> tuple[str, BinaryIO]:
	"""Create folder/name, or folder/name (2) and so on, without ever replacing a file that is there.

	:return: The path and the file, open for writing.
	"""
	stem, extension = os.path.splitext(name)
	number = 1
	while True:
		path = os.path.join(folder, name if number == 1 else f"{stem} ({number}){extension}")
		try:
			return path, open(path, "xb")
		except FileExistsError:
			number += 1


class WhatsAppSession:
	"""One connection to the WhatsApp Web tab. Listeners run on the connection's reader thread."""

	def __init__(
		self,
		onEvent: Callable[[dict], None] | None = None,
		onDisconnect: Callable[[], None] | None = None,
		findBrowsers: Callable[[], list[cdp.DebuggableBrowser]] = cdp.findDebuggableBrowsers,
		openConnection: Callable[..., cdp.CdpConnection] = cdp.CdpConnection.open,
	) -> None:
		self._onEvent = onEvent
		self._onDisconnect = onDisconnect
		self._findBrowsers = findBrowsers
		self._openConnection = openConnection
		self._connection: cdp.CdpConnection | None = None
		self._sessionId: str | None = None
		self._targetId: str | None = None
		self._lock = threading.Lock()
		self.browserName = ""
		self._closing = False
		self._bridgeSource: str | None = None
		self._bridgeHash = ""
		"""A hash of pageBridge.js, kept in the page, so a copy from an older version of the add-on is replaced."""
		self.missingFeatures: list[str] = []
		"""What the bridge could not hook because WhatsApp changed it, such as "reactions: ..."."""
		self.quietWhatsAppNotifications = False
		self.linked = False
		self.callAudio: tuple[str, str] = ("", "whatsapp")
		self.speaker = ""
		# How loud the other person is in calls, in percent; kept for the next connection.
		self.callVolume = 100
		self._heartbeat: threading.Thread | None = None
		self._memoryGuard: threading.Thread | None = None
		self._inCall = False

	@property
	def connected(self) -> bool:
		return self._connection is not None and not self._connection.closed and self._sessionId is not None

	def debuggableBrowsers(self) -> list[cdp.DebuggableBrowser]:
		return self._findBrowsers()

	def connect(
		self, target: cdp.DebuggableBrowser | cdp.PipeBrowser, hidden: HiddenOptions | None = None
	) -> str:
		"""Connect to the browser, which may ask the user first, then attach to WhatsApp Web.

		target is the user's own browser, reached through its debugging port, or the add-on's hidden
		browser, reached through its pipe.

		With hidden, the browser is the add-on's own: it may still be on a blank page, and it gets
		Chrome's user agent before WhatsApp opens. Returns "ready", or "needsLink" when WhatsApp waits
		to be linked to a phone.
		"""
		with self._lock:
			if self.connected:
				return "ready" if self.linked else "needsLink"
			self._closing = False
			try:
				connection = self._openConnection(
					target, onEvent=self._handleEvent, onClose=self._handleClose
				)
			except cdp.HandshakeRefused as e:
				raise WhatsAppError("refused", e.status) from e
			except TimeoutError as e:
				raise WhatsAppError("approvalTimedOut") from e
			except cdp.WebSocketError as e:
				# Brave closes the connection when the user chooses Cancel.
				raise WhatsAppError("refused", str(e)) from e
			except OSError as e:
				raise WhatsAppError("noBrowser", str(e)) from e
			self.browserName = target.browser.name
			try:
				targets = connection.call("Target.getTargets")["targetInfos"]
				pages = [
					t
					for t in targets
					if t.get("type") == "page" and t.get("url", "").startswith(cdp.WHATSAPP_URL_PREFIX)
				]
				if not pages and hidden is not None:
					pages = [t for t in targets if t.get("type") == "page"]
				if not pages:
					raise WhatsAppError("noWhatsAppTab")
				self._targetId = pages[0]["targetId"]
				attached = connection.call(
					"Target.attachToTarget", {"targetId": self._targetId, "flatten": True}
				)
				self._sessionId = attached["sessionId"]
				self._connection = connection
				self._call("Runtime.addBinding", {"name": EVENT_BINDING})
				self._call("Runtime.enable")
				if hidden is not None:
					# The hidden browser cannot ask the user; WhatsApp may use the microphone, nothing else may.
					connection.call(
						"Browser.grantPermissions",
						{"origin": hidden.url.rstrip("/"), "permissions": ["audioCapture", "notifications"]},
					)
					self._call("Network.enable")
					self._call(
						"Network.setUserAgentOverride",
						{"userAgent": hidden.userAgent, "userAgentMetadata": hidden.userAgentMetadata},
					)
					# The override applies from the next load, so WhatsApp always opens with it.
					self._call("Page.navigate", {"url": hidden.url})
			except WhatsAppError:
				self._sessionId = None
				self._connection = None
				connection.close()
				raise
			except cdp.CdpError as e:
				self._sessionId = None
				self._connection = None
				connection.close()
				raise WhatsAppError("failed", str(e)) from e
		if self._memoryGuard is None or not self._memoryGuard.is_alive():
			self._memoryGuard = threading.Thread(
				target=self._guardMemory, name="whatsAppAccess.memory", daemon=True
			)
			self._memoryGuard.start()
		try:
			return self.installBridge()
		except BaseException:
			# Otherwise the session would count as connected with no bridge: the next connect would answer
			# "needsLink" at once, and a retry that stops the browser would be reported as a lost connection.
			self.close()
			raise

	def installBridge(self) -> str:
		"""Install pageBridge.js and wait until WhatsApp has loaded its chats.

		Returns "ready", or "needsLink" when WhatsApp is waiting to be linked to a phone.
		"""
		if self._bridgeSource is None:
			with open(BRIDGE_PATH, encoding="utf-8") as file:
				self._bridgeSource = file.read()
			self._bridgeHash = hashlib.sha256(self._bridgeSource.encode("utf-8")).hexdigest()[:16]
		hashLiteral = json.dumps(self._bridgeHash)
		deadline = time.monotonic() + READY_TIMEOUT_SECONDS
		while True:
			# The page may still be loading, or loading again: install the bridge until it is there. A bridge
			# from another version of the add-on, left in a page that stayed open, is replaced: the new
			# copy unhooks the old one first.
			try:
				if not self._evaluate(
					f"!!(window.__waAccess && window.__waAccess.sourceHash === {hashLiteral})"
				):
					self._evaluate(self._bridgeSource)
					self._evaluate(f"window.__waAccess.sourceHash = {hashLiteral}")
				state = self._evaluate("window.__waAccess.authState()") or {}
			except WhatsAppError as e:
				if e.code == "disconnected":
					raise
				state = {}
			if state.get("needsLink"):
				self.linked = False
				return "needsLink"
			if state.get("ready") and self._evaluate("window.__waAccess.install()"):
				self.linked = True
				self.missingFeatures = list(self._evaluate("window.__waAccess.missingFeatures()") or [])
				if self.missingFeatures:
					_log.warning(
						f"WhatsApp Access: WhatsApp changed; turned off: {'; '.join(self.missingFeatures)}"
					)
				self.setQuietNotifications(self.quietWhatsAppNotifications)
				self._bridge(
					"setCallAudio",
					{
						"microphone": self.callAudio[0],
						"processing": self.callAudio[1],
						"speaker": self.speaker,
						"volume": self.callVolume / 100,
					},
				)
				return "ready"
			if time.monotonic() > deadline:
				raise WhatsAppError("notReady")
			time.sleep(0.5)

	def requestLinkCode(self, phone: str) -> str:
		"""The code to type on the phone to link this browser to WhatsApp. The phone shows a notification."""
		return self._bridge("requestLinkCode", phone, timeout=60)

	def waitUntilLinked(self, timeout: float) -> bool:
		"""After the code was typed on the phone: wait for WhatsApp to load the chats, then install."""
		deadline = time.monotonic() + timeout
		while time.monotonic() < deadline:
			try:
				state = self._evaluate("window.__waAccess ? window.__waAccess.authState() : null") or {}
			except WhatsAppError as e:
				if e.code == "disconnected":
					raise
				state = {}
			if not state:
				# The page reloads once linked; put the bridge back.
				try:
					self._evaluate(self._bridgeSource or "")
				except WhatsAppError:
					pass
			elif state.get("ready"):
				return self.installBridge() == "ready"
			time.sleep(1)
		return False

	def logout(self) -> None:
		"""Unlink this browser from the phone, as WhatsApp Web's Log out does."""
		self._bridge("logout", timeout=60)

	def setQuietNotifications(self, quiet: bool) -> None:
		"""Hold back WhatsApp's own banner and sound for new messages while the add-on reads them out.

		The page lets them through again if the add-on stops checking in, for example when NVDA exits.
		"""
		self.quietWhatsAppNotifications = quiet
		if not self.connected:
			return
		self._bridge("quietNotifications", quiet)
		if quiet and (self._heartbeat is None or not self._heartbeat.is_alive()):
			self._heartbeat = threading.Thread(
				target=self._beat, name="whatsAppAccess.heartbeat", daemon=True
			)
			self._heartbeat.start()

	def _beat(self) -> None:
		while self.connected and self.quietWhatsAppNotifications:
			try:
				self._bridge("heartbeat")
			except WhatsAppError:
				pass
			time.sleep(HEARTBEAT_SECONDS)

	def _guardMemory(self) -> None:
		"""Keep the hidden browser's memory down through long sessions, such as a call all night."""
		waited = 0.0
		while not self._closing:
			time.sleep(5)
			waited += 5
			if waited < MEMORY_CHECK_SECONDS or not self.connected:
				continue
			waited = 0.0
			try:
				if self.memoryInUse() > MEMORY_TRIM_BYTES:
					self.trimMemory()
			except WhatsAppError:
				pass

	def memoryInUse(self) -> int:
		"""The bytes of JavaScript WhatsApp Web uses now."""
		return int(self._call("Runtime.getHeapUsage").get("usedSize", 0))

	def trimMemory(self) -> None:
		"""Ask the browser to free what it can: caches, and memory nothing uses any more."""
		self._call("Memory.simulatePressureNotification", {"level": "critical"})
		self._call("HeapProfiler.collectGarbage")

	def _trimSoon(self) -> None:
		def trim() -> None:
			try:
				self.trimMemory()
			except WhatsAppError:
				pass

		threading.Thread(target=trim, name="whatsAppAccess.trim", daemon=True).start()

	def close(self) -> None:
		self._closing = True
		connection = self._connection
		self._connection = None
		self._sessionId = None
		if connection is not None:
			connection.close()

	# Events ---------------------------------------------------------------------------------------------

	def _handleEvent(self, method: str, params: dict, sessionId: str | None) -> None:
		if sessionId != self._sessionId:
			if method == "Target.detachedFromTarget" and params.get("sessionId") == self._sessionId:
				self._lost()
			return
		if method == "Runtime.bindingCalled" and params.get("name") == EVENT_BINDING:
			try:
				event = json.loads(params.get("payload", ""))
			except ValueError:
				return
			if event.get("type") == "call":
				inCall = bool(event.get("call"))
				if self._inCall and not inCall:
					# A call leaves much behind it, the longer it was the more; give it back at once.
					self._trimSoon()
				self._inCall = inCall
			if self._onEvent is not None:
				self._onEvent(event)
		elif method == "Runtime.executionContextCreated":
			context = params.get("context", {})
			if context.get("auxData", {}).get("isDefault") and context.get("origin", "").startswith(
				cdp.WHATSAPP_URL_PREFIX
			):
				# The page was loaded again: install the bridge again, off the reader thread.
				threading.Thread(target=self._reinstall, name="whatsAppAccess.reinstall", daemon=True).start()

	def _reinstall(self) -> None:
		try:
			self.installBridge()
			if self._onEvent is not None:
				self._onEvent({"type": "chatsChanged"})
		except (WhatsAppError, cdp.CdpError):
			pass

	def _handleClose(self) -> None:
		self._lost()

	def _lost(self) -> None:
		wasConnected = self._sessionId is not None
		self._sessionId = None
		connection, self._connection = self._connection, None
		if connection is not None and not connection.closed:
			# WhatsApp's page detached while the browser stayed: let go of the connection rather than leave
			# its reader thread behind. For the hidden browser this closes the pipe, and the next start
			# brings a fresh browser.
			connection.close()
		if wasConnected and not self._closing and self._onDisconnect is not None:
			self._onDisconnect()

	# Calls ----------------------------------------------------------------------------------------------

	def _call(
		self, method: str, params: dict | None = None, timeout: float = cdp.COMMAND_TIMEOUT_SECONDS
	) -> dict:
		connection, sessionId = self._connection, self._sessionId
		if connection is None or sessionId is None:
			raise WhatsAppError("disconnected")
		try:
			return connection.call(method, params, sessionId, timeout)
		except cdp.Disconnected as e:
			raise WhatsAppError("disconnected", str(e)) from e
		except cdp.CdpError as e:
			raise WhatsAppError("failed", str(e)) from e

	def _evaluate(self, expression: str, timeout: float = cdp.COMMAND_TIMEOUT_SECONDS) -> Any:
		result = self._call(
			"Runtime.evaluate",
			{"expression": expression, "awaitPromise": True, "returnByValue": True, "userGesture": True},
			timeout,
		)
		details = result.get("exceptionDetails")
		if details:
			description = details.get("exception", {}).get("description") or details.get("text", "")
			raise _codeFromPageError(description)
		return result.get("result", {}).get("value")

	def _bridge(self, function: str, *args: Any, timeout: float = cdp.COMMAND_TIMEOUT_SECONDS) -> Any:
		arguments = ", ".join(json.dumps(a) for a in args)
		expression = f"window.__waAccess.{function}({arguments})"
		try:
			return self._evaluate(expression, timeout)
		except WhatsAppError as e:
			# The page was reloaded and the bridge is not back yet. Only then is the call tried again: the
			# function never ran, so nothing can be sent twice.
			if e.code == "failed" and self._evaluate(_BRIDGE_MISSING):
				self.installBridge()
				return self._evaluate(expression, timeout)
			raise

	def chats(self, archived: bool = False) -> list[dict]:
		return self._bridge("chats", {"archived": archived})

	def messages(self, chatId: str, count: int = 50) -> list[dict]:
		return self._bridge("messages", chatId, count, timeout=60)

	def loadEarlier(self, chatId: str, beforeId: str) -> list[dict]:
		return self._bridge("loadEarlier", chatId, beforeId, timeout=60)

	def sendText(
		self, chatId: str, text: str, quotedId: str = "", mentions: list[dict] | None = None
	) -> None:
		"""Send text, as a reply to quotedId if given. mentions are {id, name} of people written as "@name"."""
		self._bridge("sendText", chatId, text, quotedId, mentions or [], timeout=60)

	def participants(self, chatId: str) -> list[dict]:
		"""The people in a group other than the user: id, name (as saved in contacts) and pushname."""
		return self._bridge("participants", chatId)

	def messageActions(self, messageId: str) -> dict:
		"""Which of WhatsApp's message menu items apply: star, starred, edit, deleteForEveryone, react, text."""
		return self._bridge("messageActions", messageId)

	def setTyping(self, chatId: str, state: str) -> None:
		"""Show the other person that the user is typing ("composing"), recording, or stopped ("paused")."""
		self._bridge("setTyping", chatId, state)

	def forward(self, messageIds: list[str], chatIds: list[str]) -> None:
		self._bridge("forward", messageIds, chatIds, timeout=120)

	def messageReceipts(self, messageId: str) -> dict:
		"""For one of the user's messages: who received, read and played it, and when."""
		return self._bridge("messageReceipts", messageId)

	def chatWithNumber(self, phone: str) -> dict:
		"""The chat with a phone number, made if needed. Fails with notOnWhatsApp."""
		return self._bridge("chatWithNumber", phone, timeout=60)

	def searchMessages(self, chatId: str, query: str, batches: int = 10) -> list[dict]:
		return self._bridge("searchMessages", chatId, query, batches, timeout=120)

	def allMessages(self, chatId: str) -> list[dict]:
		return self._bridge("allMessages", chatId)

	def reactions(self, messageId: str) -> list[dict]:
		"""Each emoji on a message, how many chose it, and whether the user did (mine)."""
		return self._bridge("reactions", messageId)

	def react(self, messageId: str, emoji: str) -> None:
		"""React with an emoji, or remove the user's reaction with an empty one."""
		self._bridge("react", messageId, emoji, timeout=60)

	def star(self, messageId: str, starred: bool) -> None:
		self._bridge("star", messageId, starred)

	def editText(self, messageId: str, text: str) -> None:
		self._bridge("editText", messageId, text, timeout=60)

	def deleteMessage(self, messageId: str, forEveryone: bool) -> None:
		self._bridge("deleteMessage", messageId, forEveryone)

	def messagesActions(self, messageIds: list[str]) -> dict:
		"""For several messages: deleteForEveryone (all may be), star (any may be), allStarred."""
		return self._bridge("messagesActions", messageIds)

	def deleteMessages(self, messageIds: list[str], forEveryone: bool) -> None:
		self._bridge("deleteMessages", messageIds, forEveryone, timeout=60)

	def starMessages(self, messageIds: list[str], starred: bool) -> None:
		self._bridge("starMessages", messageIds, starred)

	def chatsAction(self, chatIds: list[str], action: str, seconds: int = 0) -> dict:
		"""chatAction for several chats, and "delete". Returns done and skipped (groups still joined)."""
		return self._bridge("chatsAction", chatIds, action, seconds, timeout=120)

	# Starred messages, channels and communities

	def starredMessages(self) -> list[dict]:
		"""All starred messages, newest first, each with chatTitle."""
		return self._bridge("starredMessages", timeout=60)

	def channels(self) -> list[dict]:
		"""The channels the user follows, as chats with isChannel, canPost, followers and verified."""
		return self._bridge("channels")

	def searchChannels(self, text: str) -> list[dict]:
		return self._bridge("searchChannels", text, timeout=60)

	def followChannel(self, channelId: str, follow: bool) -> None:
		self._bridge("followChannel", channelId, follow, timeout=60)

	def communities(self) -> list[dict]:
		"""Communities with their groups: announcement, joined, needsApproval and requested for each."""
		return self._bridge("communities", timeout=90)

	def joinCommunityGroup(self, communityId: str, groupId: str) -> str:
		"""Returns "joined", or "requested" when the community's admins approve new members."""
		return self._bridge("joinCommunityGroup", communityId, groupId, timeout=60)

	# Groups and chats

	def chatAbilities(self, chatId: str) -> dict:
		"""What the user may do in a chat: admin, canAdd, favorite, ephemeral, blocked and so on."""
		return self._bridge("chatAbilities", chatId)

	def contactChoices(self) -> list[dict]:
		return self._bridge("contactChoices")

	def createGroup(self, title: str, contactIds: list[str]) -> dict:
		"""Returns chatId, and failed: how many people could not be added (WhatsApp offers to invite them)."""
		return self._bridge("createGroup", title, contactIds, timeout=90)

	def changeParticipants(self, chatId: str, action: str, ids: list[str]) -> int:
		"""add, remove, promote or demote; returns how many could not be done."""
		return int(self._bridge("changeParticipants", chatId, action, ids, timeout=60) or 0)

	def setGroupInfo(self, chatId: str, field: str, value: str) -> None:
		"""field is subject or description."""
		self._bridge("setGroupInfo", chatId, field, value, timeout=60)

	def setGroupSetting(self, chatId: str, setting: str, on: bool) -> None:
		"""announcement, restrict, membership_approval_mode or member_add_mode."""
		self._bridge("setGroupSetting", chatId, setting, on, timeout=60)

	def inviteLink(self, chatId: str, reset: bool = False) -> str:
		return self._bridge("inviteLink", chatId, reset, timeout=60)

	def exitGroup(self, chatId: str, andDelete: bool = False) -> None:
		self._bridge("exitGroup", chatId, andDelete, timeout=60)

	def deleteChat(self, chatId: str) -> None:
		self._bridge("deleteChat", chatId, timeout=60)

	def clearChat(self, chatId: str, keepStarred: bool) -> None:
		self._bridge("clearChat", chatId, keepStarred, timeout=60)

	def setBlocked(self, chatId: str, blocked: bool) -> None:
		self._bridge("setBlocked", chatId, blocked, timeout=60)

	def reportChat(self, chatId: str, alsoBlockOrExit: bool) -> None:
		self._bridge("reportChat", chatId, alsoBlockOrExit, timeout=60)

	def setDisappearing(self, chatId: str, seconds: int) -> None:
		"""0, 86400, 604800 or 7776000 seconds."""
		self._bridge("setDisappearing", chatId, seconds, timeout=60)

	def setFavorite(self, chatId: str, favorite: bool) -> None:
		self._bridge("setFavorite", chatId, favorite, timeout=60)

	# More for messages

	def sendPoll(self, chatId: str, question: str, options: list[str], single: bool) -> None:
		self._bridge("sendPoll", chatId, question, options, single, timeout=60)

	def pinMessage(self, messageId: str, duration: str | None) -> None:
		"""duration is day, week or month; None unpins."""
		self._bridge("pinMessage", messageId, duration, timeout=60)

	def pinnedMessages(self, chatId: str) -> list[dict]:
		return self._bridge("pinnedMessages", chatId)

	def replyPrivately(self, messageId: str, text: str) -> dict:
		"""Sends text to the group message's sender, quoting it; returns that chat."""
		return self._bridge("replyPrivately", messageId, text, timeout=60)

	def reactionDetails(self, messageId: str) -> list[dict]:
		"""Each emoji with its people: name, isMe, t."""
		return self._bridge("reactionDetails", messageId, timeout=30)

	def sendContacts(self, chatId: str, contactIds: list[str]) -> None:
		self._bridge("sendContacts", chatId, contactIds, timeout=60)

	def stickers(self) -> list[dict]:
		"""Favorite, then recent stickers: kind, index, label, pack, animated."""
		return self._bridge("stickers")

	def sendSticker(self, chatId: str, kind: str, index: int) -> None:
		self._bridge("sendSticker", chatId, kind, index, timeout=60)

	def searchAll(self, query: str, page: int = 1) -> dict:
		"""Messages in every chat containing query, each with chatTitle; done says there are no more."""
		return self._bridge("searchAll", query, page, timeout=60)

	def chatMedia(self, chatId: str, kind: str) -> list[dict]:
		"""kind is media, links or docs; newest first."""
		return self._bridge("chatMedia", chatId, kind, timeout=60)

	def unreadMentions(self, chatId: str) -> list[dict]:
		return self._bridge("unreadMentions", chatId, timeout=30)

	def eventInfo(self, messageId: str) -> dict:
		return self._bridge("eventInfo", messageId)

	def respondToEvent(self, messageId: str, answer: str) -> None:
		"""answer is going, maybe or notGoing."""
		self._bridge("respondToEvent", messageId, answer, timeout=60)

	def createEvent(self, chatId: str, options: dict) -> None:
		"""options: name, start (Unix seconds), and optionally end, description, location, callType."""
		self._bridge("createEvent", chatId, options, timeout=60)

	# Your status, profile and privacy

	def postTextStatus(self, text: str, colorIndex: int, font: int) -> None:
		self._bridge("postTextStatus", text, colorIndex, font, timeout=60)

	def myStatuses(self) -> list[dict]:
		"""The user's own statuses, newest first, each with viewers (name, t)."""
		return self._bridge("myStatuses", timeout=60)

	def deleteMyStatus(self, messageId: str) -> None:
		self._bridge("deleteMyStatus", messageId, timeout=60)

	def profile(self) -> dict:
		return self._bridge("profile", timeout=30)

	def setProfile(self, field: str, value: str) -> None:
		"""field is name or about."""
		self._bridge("setProfile", field, value, timeout=60)

	def setProfilePhoto(self, path: str | None) -> None:
		"""A picture file, cropped square as WhatsApp does; None removes the photo."""
		uploadId = self._upload(path) if path else None
		self._bridge("setProfilePhoto", uploadId, timeout=120)

	def privacy(self) -> dict:
		return self._bridge("privacy", timeout=30)

	def setPrivacy(self, key: str, value: str) -> None:
		self._bridge("setPrivacy", key, value, timeout=60)

	def blockedContacts(self) -> list[dict]:
		return self._bridge("blockedContacts")

	def unblock(self, contactId: str) -> None:
		self._bridge("unblock", contactId, timeout=60)

	# Group calls and the connection

	def startGroupCall(self, chatId: str) -> None:
		self._bridge("startGroupCall", chatId, timeout=60)

	def ongoingGroupCall(self, chatId: str) -> bool:
		return bool(self._bridge("ongoingGroupCall", chatId))

	def joinGroupCall(self, chatId: str) -> None:
		self._bridge("joinGroupCall", chatId, timeout=60)

	def setOnline(self, online: bool) -> None:
		"""Online while the add-on's window is open, as WhatsApp Web is while it is in front."""
		self._bridge("setOnline", online)

	def connectionState(self) -> dict:
		return self._bridge("connectionState")

	def chatAction(self, chatId: str, action: str, seconds: int = 0) -> None:
		"""archive, unarchive, pin, unpin, markUnread, markRead, mute (seconds, or -1 for always), unmute."""
		self._bridge("chatAction", chatId, action, seconds, timeout=60)

	def markSeen(self, chatId: str) -> bool:
		return bool(self._bridge("markSeen", chatId))

	def microphones(self) -> list[dict]:
		return self._bridge("microphones")

	def startRecording(self, stereo: bool, raw: bool, kbps: int, deviceId: str = "") -> dict:
		options = {"stereo": stereo, "raw": raw, "kbps": kbps, "deviceId": deviceId}
		return self._bridge("startRecording", options)

	def stopRecording(self) -> dict:
		return self._bridge("stopRecording")

	def pauseRecording(self) -> bool:
		"""Pause or resume recording. Returns whether it is now paused."""
		return bool(self._bridge("pauseRecording"))

	def sendFile(
		self, chatId: str, path: str, kind: str, mime: str, caption: str = "", quotedId: str = ""
	) -> None:
		"""Send a file as a photo, video, audio or document, as WhatsApp's attach menu does.

		The file goes to the page in pieces, since one DevTools message cannot carry a large file.
		"""
		if os.path.getsize(path) > MAX_FILE_BYTES:
			raise WhatsAppError("fileTooLarge", str(MAX_FILE_BYTES // 2**20))
		uploadId = uuid.uuid4().hex
		self._bridge("uploadStart", uploadId)
		try:
			with open(path, "rb") as file:
				while chunk := file.read(UPLOAD_CHUNK_BYTES):
					self._bridge("uploadChunk", uploadId, base64.b64encode(chunk).decode("ascii"))
			name = os.path.basename(path)
			self._bridge("sendFile", chatId, uploadId, name, mime, kind, caption, quotedId, timeout=300)
		except BaseException:
			try:
				self._bridge("uploadCancel", uploadId)
			except WhatsAppError:
				pass
			raise

	def _upload(self, path: str) -> str:
		"""Send a file to the page in pieces for a later bridge call; returns its upload id."""
		if os.path.getsize(path) > MAX_FILE_BYTES:
			raise WhatsAppError("fileTooLarge", str(MAX_FILE_BYTES // 2**20))
		uploadId = uuid.uuid4().hex
		self._bridge("uploadStart", uploadId)
		try:
			with open(path, "rb") as file:
				while chunk := file.read(UPLOAD_CHUNK_BYTES):
					self._bridge("uploadChunk", uploadId, base64.b64encode(chunk).decode("ascii"))
		except BaseException:
			try:
				self._bridge("uploadCancel", uploadId)
			except WhatsAppError:
				pass
			raise
		return uploadId

	def download(self, messageId: str, folder: str = "", path: str = "") -> str:
		"""Save a message's photo, video, audio or document.

		The file gets the mark Windows gives files from the internet, so SmartScreen and Office's Protected
		View check it before it runs or opens. A file that fails halfway is removed.

		:param messageId: The message with the file.
		:param folder: Save there, under a safe form of the sender's name for the file. A file that is
			already there is never replaced.
		:param path: Or save at this full path, which the user chose.
		:return: Where the file was saved.
		"""
		info = self._bridge("downloadStart", messageId, timeout=300)
		if not isinstance(info, dict) or not info.get("id"):
			raise WhatsAppError("noDownload")
		file: BinaryIO | None = None
		try:
			try:
				if path:
					file = open(path, "wb")
				else:
					name = fileSafety.safeFileName(str(info.get("name") or ""))
					path, file = _createFreeFile(folder, name)
				offset, size = 0, int(info.get("size") or 0)
				while offset < size:
					piece = self._bridge("downloadChunk", info["id"], offset, UPLOAD_CHUNK_BYTES)
					file.write(base64.b64decode(piece or ""))
					offset += UPLOAD_CHUNK_BYTES
				file.close()
			except BaseException:
				if file is not None:
					file.close()
					try:
						os.remove(path)
					except OSError:
						pass
				raise
		except OSError as e:
			raise WhatsAppError("saveFailed", str(e)) from e
		except (ValueError, TypeError) as e:
			# A piece that is not base64: the page sent something else.
			raise WhatsAppError("failed", f"download: {e}") from e
		finally:
			try:
				self._bridge("downloadEnd", info["id"])
			except WhatsAppError:
				pass
		fileSafety.markFromInternet(path)
		return path

	def suggestedFileName(self, messageId: str) -> str:
		"""A safe form of the name WhatsApp would give the file, without downloading it."""
		return fileSafety.safeFileName(str(self._bridge("suggestedFileName", messageId) or ""))

	def pollInfo(self, messageId: str) -> dict:
		"""A poll: question, whether several options may be chosen, how many people voted, and each
		option with who chose it and whether the user did."""
		return self._bridge("pollInfo", messageId)

	def vote(self, messageId: str, optionIds: list[int]) -> None:
		"""Vote in a poll. An empty list takes the user's vote back."""
		self._bridge("vote", messageId, optionIds, timeout=60)

	def openInWhatsApp(self, chatId: str) -> None:
		"""Open the chat in WhatsApp's own view too, so it loads poll votes and reactions."""
		self._bridge("openInWhatsApp", chatId, timeout=60)

	def contactInfo(self, chatId: str) -> dict:
		"""What WhatsApp's contact or group info shows: for a person, name, phone, about and groups in
		common; for a group, its description, who created it and when, and its people."""
		return self._bridge("contactInfo", chatId, timeout=60)

	def statuses(self) -> list[dict]:
		"""People who posted statuses, unseen first: id, name, unread, t, and items (messages, with viewed)."""
		return self._bridge("statuses")

	def statusSeen(self, messageId: str) -> None:
		self._bridge("statusSeen", messageId)

	def likeStatus(self, messageId: str, emoji: str = "") -> None:
		self._bridge("likeStatus", messageId, emoji)

	def replyStatus(self, messageId: str, text: str) -> None:
		self._bridge("replyStatus", messageId, text, timeout=60)

	def recentCalls(self, limit: int = 100) -> list[dict]:
		"""Newest first: name, chatId, outgoing, missed, video, group, duration (seconds), t."""
		return self._bridge("recentCalls", limit)

	def callState(self) -> dict | None:
		"""The call ringing or in progress: name, incoming, ringing, connected, ended, video, group."""
		return self._bridge("callState")

	def setCallAudio(self, microphone: str, processing: str, speaker: str | None = None) -> dict:
		"""The microphone and speaker (by name; empty for the default) and sound processing for calls:
		"whatsapp" leaves WhatsApp's own, "echoOnly" keeps only echo cancellation, "none" turns all off.

		They change at once, in a call too. Returns which of "microphone" and "speaker" changed now.
		"""
		self.callAudio = (microphone, processing)
		if speaker is not None:
			self.speaker = speaker
		if not self.connected:
			return {}
		options = {"microphone": microphone, "processing": processing, "speaker": self.speaker}
		return self._bridge("setCallAudio", options, timeout=30) or {}

	def emojiSuggestions(self, query: str, limit: int = 20) -> list[str]:
		"""Emoji whose English names start with what the user typed after ":", the best first."""
		return self._bridge("emojiSuggestions", query, limit) or []

	def audioDevices(self) -> dict:
		"""The names of the microphones and speakers: {"microphones": [...], "speakers": [...]}."""
		return self._bridge("audioDevices") or {}

	def setCallVolume(self, percent: int) -> None:
		"""How loud the other person is in calls, from 0 to 100, now and in later calls."""
		self.callVolume = max(0, min(100, int(percent)))
		if self.connected:
			self._bridge("setCallVolume", self.callVolume / 100)

	def answerCall(self) -> None:
		"""Answer with the microphone on and the camera off."""
		self._bridge("answerCall", timeout=60)

	def declineCall(self) -> None:
		self._bridge("declineCall")

	def endCall(self) -> None:
		self._bridge("endCall")

	def muteCall(self, muted: bool) -> bool:
		return bool(self._bridge("muteCall", muted))

	def raiseHand(self, raised: bool) -> None:
		self._bridge("raiseHand", raised, timeout=30)

	def callReaction(self, emoji: str) -> None:
		self._bridge("callReaction", emoji, timeout=30)

	def speakers(self) -> list[str]:
		"""Who was heard in the call in the last moments, the most recent first."""
		return self._bridge("speakers") or []

	def askToMute(self, participantId: str) -> None:
		self._bridge("askToMute", participantId, timeout=30)

	def startCall(self, chatId: str, video: bool = False) -> None:
		self._bridge("startCall", chatId, video, timeout=60)

	def presence(self, chatId: str) -> dict:
		"""For a person: state (online, typing, recording, offline, unknown) and lastSeen.
		For a group: the names of those typing and recording."""
		return self._bridge("presence", chatId)

	def watchPresence(self, chatId: str) -> dict | None:
		"""Report presence changes of this chat as "presence" events; an empty chatId stops watching."""
		return self._bridge("watchPresence", chatId)

	def cancelRecording(self) -> None:
		self._bridge("cancelRecording")

	def isRecording(self) -> bool:
		return bool(self._bridge("isRecording"))

	def sendRecording(self, chatId: str) -> None:
		self._bridge("sendRecording", chatId, timeout=120)

	def playRecording(self) -> None:
		self._bridge("playRecording")

	def playMessage(self, messageId: str) -> None:
		self._bridge("playMessage", messageId, timeout=60)

	def setPlaybackRate(self, rate: float) -> float:
		"""How fast voice messages and the user's recording play, now and from now on."""
		return float(self._bridge("setPlaybackRate", rate))

	def setPlaybackVolume(self, percent: int) -> float:
		"""How loud voice messages, videos and statuses play, now and from now on, from 0 to 100."""
		return float(self._bridge("setPlaybackVolume", max(0, min(100, int(percent))) / 100))

	def stopAudio(self) -> bool:
		return bool(self._bridge("stopAudio"))
