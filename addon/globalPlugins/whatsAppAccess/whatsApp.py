# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""The connection to WhatsApp Web: finds its tab, installs pageBridge.js there and calls it.

Calls block until WhatsApp answers, so run them on a background thread, never on NVDA's main thread.
It imports nothing from NVDA, so it can be tested on its own.
"""

import base64
import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import cdp

EVENT_BINDING = "__waAccessEvent"
READY_TIMEOUT_SECONDS = 60.0
UPLOAD_CHUNK_BYTES = 512 * 1024
# Files go through the browser's memory; WhatsApp's own limit for documents is higher.
MAX_FILE_BYTES = 200 * 2**20
# How often the add-on tells the page it is still there. The page gives up after 60 seconds.
HEARTBEAT_SECONDS = 20.0
BRIDGE_PATH = os.path.join(os.path.dirname(__file__), "pageBridge.js")


class WhatsAppError(Exception):
	"""Something went wrong. code says what, for the add-on to explain to the user.

	Codes: noBrowser, refused, approvalTimedOut, noWhatsAppTab, notReady, disconnected, chatNotFound, emptyMessage, sendFailed,
	microphone, notRecording, noRecording, emptyRecording, mediaGone, failed.
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


def _safeFileName(name: str) -> str:
	"""A name Windows accepts: no path, no reserved characters."""
	name = os.path.basename(name.replace("\\", "/"))
	cleaned = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in name).strip(" .")
	return cleaned or "WhatsApp file"


def _freePath(folder: str, name: str) -> str:
	"""folder/name, or folder/name (2) and so on when that file already exists."""
	stem, extension = os.path.splitext(name)
	path = os.path.join(folder, name)
	number = 2
	while os.path.exists(path):
		path = os.path.join(folder, f"{stem} ({number}){extension}")
		number += 1
	return path


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
		self.quietWhatsAppNotifications = False
		self.linked = False
		self.callAudio: tuple[str, str] = ("", "whatsapp")
		# How loud the other person is in calls, in percent; kept for the next connection.
		self.callVolume = 100
		self._heartbeat: threading.Thread | None = None

	@property
	def connected(self) -> bool:
		return self._connection is not None and not self._connection.closed and self._sessionId is not None

	def debuggableBrowsers(self) -> list[cdp.DebuggableBrowser]:
		return self._findBrowsers()

	def connect(self, target: cdp.DebuggableBrowser, hidden: "HiddenOptions | None" = None) -> str:
		"""Connect to the browser, which may ask the user first, then attach to WhatsApp Web.

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
		return self.installBridge()

	def installBridge(self) -> str:
		"""Install pageBridge.js and wait until WhatsApp has loaded its chats.

		Returns "ready", or "needsLink" when WhatsApp is waiting to be linked to a phone.
		"""
		if self._bridgeSource is None:
			with open(BRIDGE_PATH, encoding="utf-8") as file:
				self._bridgeSource = file.read()
		deadline = time.monotonic() + READY_TIMEOUT_SECONDS
		while True:
			# The page may still be loading, or loading again: install the bridge until it is there.
			try:
				if not self._evaluate("!!(window.__waAccess && window.__waAccess.authState)"):
					self._evaluate(self._bridgeSource)
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
				self.setQuietNotifications(self.quietWhatsAppNotifications)
				self._bridge(
					"setCallAudio",
					{
						"microphone": self.callAudio[0],
						"processing": self.callAudio[1],
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
		self._connection = None
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
			if e.code == "failed" and "__waAccess" in e.detail:
				# The page was reloaded and the bridge is not back yet.
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

	def download(self, messageId: str, folder: str = "", path: str = "") -> str:
		"""Save a message's photo, video, audio or document. Give a folder to use WhatsApp's name for the
		file there, or a full path. Returns where it was saved."""
		info = self._bridge("downloadStart", messageId, timeout=300)
		try:
			if not path:
				path = _freePath(folder, _safeFileName(info.get("name") or "WhatsApp file"))
			with open(path, "wb") as file:
				offset, size = 0, int(info.get("size") or 0)
				while offset < size:
					piece = self._bridge("downloadChunk", info["id"], offset, UPLOAD_CHUNK_BYTES)
					file.write(base64.b64decode(piece))
					offset += UPLOAD_CHUNK_BYTES
		finally:
			try:
				self._bridge("downloadEnd", info["id"])
			except WhatsAppError:
				pass
		return path

	def suggestedFileName(self, messageId: str) -> str:
		"""The name WhatsApp would give the file, without downloading it."""
		return self._bridge("suggestedFileName", messageId)

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

	def setCallAudio(self, microphone: str, processing: str) -> None:
		"""The microphone (by name; empty for the browser's) and sound processing WhatsApp gets for calls:
		"whatsapp" leaves WhatsApp's own, "echoOnly" keeps only echo cancellation, "none" turns all off."""
		self.callAudio = (microphone, processing)
		if self.connected:
			self._bridge("setCallAudio", {"microphone": microphone, "processing": processing})

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
