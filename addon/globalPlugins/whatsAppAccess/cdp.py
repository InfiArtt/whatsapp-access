# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Finds a Chromium-based browser with remote debugging turned on and talks to it over the DevTools protocol.

The user turns remote debugging on at brave://inspect/#remote-debugging (chrome://, edge:// in other browsers).
The browser then writes its port to a DevToolsActivePort file and asks the user before it accepts each new
connection, so this module keeps one connection open for as long as it is needed.
It imports nothing from NVDA, so it can be tested on its own.
"""

import ctypes
import itertools
import json
import logging
import os
import socket
import sys
import threading
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .webSocket import HandshakeRefused, WebSocket, WebSocketError

__all__ = ["HandshakeRefused", "WebSocketError"]

# How long to wait for the user to answer the browser's "Allow remote debugging?" question.
APPROVAL_TIMEOUT_SECONDS = 180.0
COMMAND_TIMEOUT_SECONDS = 30.0
WHATSAPP_URL_PREFIX = "https://web.whatsapp.com"


@dataclass(frozen=True)
class Browser:
	name: str
	"""What to call the browser in messages, such as "Brave"."""
	userDataDir: Path
	executable: str
	"""The file name of the browser's program, to check who owns the debugging port."""
	inspectUrl: str


def knownBrowsers(localAppData: str | None = None) -> list[Browser]:
	base = Path(localAppData if localAppData is not None else os.environ.get("LOCALAPPDATA", ""))
	brave, chrome, edge = (
		"brave://inspect/#remote-debugging",
		"chrome://inspect/#remote-debugging",
		"edge://inspect/#remote-debugging",
	)
	return [
		Browser("Brave", base / r"BraveSoftware\Brave-Browser\User Data", "brave.exe", brave),
		Browser("Brave Beta", base / r"BraveSoftware\Brave-Browser-Beta\User Data", "brave.exe", brave),
		Browser("Brave Nightly", base / r"BraveSoftware\Brave-Browser-Nightly\User Data", "brave.exe", brave),
		Browser("Google Chrome", base / r"Google\Chrome\User Data", "chrome.exe", chrome),
		Browser("Google Chrome Beta", base / r"Google\Chrome Beta\User Data", "chrome.exe", chrome),
		Browser("Microsoft Edge", base / r"Microsoft\Edge\User Data", "msedge.exe", edge),
		Browser("Chromium", base / r"Chromium\User Data", "chrome.exe", chrome),
	]


def readActivePort(path: Path) -> tuple[int, str] | None:
	"""The port and browser WebSocket path in a DevToolsActivePort file, or None. The file can be stale."""
	try:
		lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
	except OSError:
		return None
	if len(lines) < 2:
		return None
	try:
		port = int(lines[0].strip())
	except ValueError:
		return None
	wsPath = lines[1].strip()
	if not 0 < port < 65536 or not wsPath.startswith("/devtools/browser/"):
		return None
	if not all(c.isalnum() or c in "/-_" for c in wsPath):
		return None
	return port, wsPath


# Who owns a port --------------------------------------------------------------------------------------------

_TCP_TABLE_OWNER_PID_LISTENER = 3
_ERROR_INSUFFICIENT_BUFFER = 122
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_LOOPBACK_OR_ANY = frozenset({"127.0.0.1", "0.0.0.0"})


class _TcpRowOwnerPid(ctypes.Structure):
	_fields_ = [
		("state", wintypes.DWORD),
		("localAddr", wintypes.DWORD),
		("localPort", wintypes.DWORD),
		("remoteAddr", wintypes.DWORD),
		("remotePort", wintypes.DWORD),
		("owningPid", wintypes.DWORD),
	]


def _listenerPids(port: int) -> list[int]:
	"""Processes listening on 127.0.0.1:port (or on every address), from Windows' TCP table."""
	if sys.platform != "win32":
		return []
	getTable = ctypes.WinDLL("iphlpapi").GetExtendedTcpTable
	getTable.argtypes = [
		ctypes.c_void_p,
		ctypes.POINTER(wintypes.DWORD),
		wintypes.BOOL,
		wintypes.ULONG,
		ctypes.c_int,
		wintypes.ULONG,
	]
	getTable.restype = wintypes.DWORD
	size = wintypes.DWORD(0)
	buffer = ctypes.create_string_buffer(4)
	for _ in range(8):
		result = getTable(buffer, ctypes.byref(size), False, socket.AF_INET, _TCP_TABLE_OWNER_PID_LISTENER, 0)
		if result == 0:
			break
		if result != _ERROR_INSUFFICIENT_BUFFER:
			return []
		buffer = ctypes.create_string_buffer(size.value + 1024)
	else:
		return []
	count = wintypes.DWORD.from_buffer(buffer).value
	offset = ctypes.sizeof(wintypes.DWORD)
	if offset + count * ctypes.sizeof(_TcpRowOwnerPid) > len(buffer):
		return []
	rows = (_TcpRowOwnerPid * count).from_buffer(buffer, offset)
	pids = []
	for row in rows:
		address = socket.inet_ntoa(int(row.localAddr).to_bytes(4, "little"))
		if socket.ntohs(row.localPort & 0xFFFF) == port and address in _LOOPBACK_OR_ANY:
			pids.append(int(row.owningPid))
	return pids


def _processImage(pid: int) -> str | None:
	if sys.platform != "win32":
		return None
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
	kernel32.OpenProcess.restype = wintypes.HANDLE
	kernel32.QueryFullProcessImageNameW.argtypes = [
		wintypes.HANDLE,
		wintypes.DWORD,
		wintypes.LPWSTR,
		ctypes.POINTER(wintypes.DWORD),
	]
	kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
	kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
	handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
	if not handle:
		return None
	try:
		size = wintypes.DWORD(32768)
		buffer = ctypes.create_unicode_buffer(size.value)
		if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
			return None
		return buffer.value
	finally:
		kernel32.CloseHandle(handle)


def portBelongsTo(port: int, executable: str) -> bool:
	"""Whether the program listening on the port is the browser, not some other program pretending to be it.

	Messages the user writes are sent over this connection, so it must not go anywhere else.
	"""
	pids = _listenerPids(port)
	if not pids:
		return False
	for pid in pids:
		image = _processImage(pid)
		if not image or os.path.basename(image).lower() != executable.lower():
			return False
	return True


@dataclass(frozen=True)
class DebuggableBrowser:
	browser: Browser
	port: int
	wsPath: str


def findDebuggableBrowsers(
	browsers: list[Browser] | None = None,
	ownerCheck: Callable[[int, str], bool] = portBelongsTo,
) -> list[DebuggableBrowser]:
	"""Browsers whose remote debugging is on and whose port really belongs to them, most recent first."""
	found = []
	for browser in browsers if browsers is not None else knownBrowsers():
		portFile = browser.userDataDir / "DevToolsActivePort"
		active = readActivePort(portFile)
		if active is None:
			continue
		port, wsPath = active
		if not ownerCheck(port, browser.executable):
			continue
		found.append((portFile.stat().st_mtime, DebuggableBrowser(browser, port, wsPath)))
	found.sort(key=lambda item: item[0], reverse=True)
	return [item[1] for item in found]


# The connection -----------------------------------------------------------------------------------------------


class CdpError(Exception):
	"""The browser answered a command with an error, or the connection is gone."""


class Disconnected(CdpError):
	pass


class CdpConnection:
	"""One DevTools connection to a browser. Commands can be sent from any thread except the reader thread.

	onEvent(method, params, sessionId) and onClose() run on the reader thread.
	"""

	def __init__(
		self,
		ws: WebSocket,
		onEvent: Callable[[str, dict, str | None], None] | None = None,
		onClose: Callable[[], None] | None = None,
	) -> None:
		self._ws = ws
		self._ids = itertools.count(1)
		self._pending: dict[int, dict] = {}
		self._lock = threading.Lock()
		self._onEvent = onEvent
		self._onClose = onClose
		self.closed = False
		self._reader = threading.Thread(target=self._read, name="whatsAppAccess.cdp", daemon=True)
		self._reader.start()

	@classmethod
	def open(cls, target: DebuggableBrowser, **kwargs) -> "CdpConnection":
		ws = WebSocket.connect("127.0.0.1", target.port, target.wsPath, APPROVAL_TIMEOUT_SECONDS)
		return cls(ws, **kwargs)

	def _read(self) -> None:
		try:
			while True:
				message = json.loads(self._ws.receive())
				messageId = message.get("id")
				if messageId is not None:
					with self._lock:
						slot = self._pending.get(messageId)
					if slot is not None:
						slot["answer"] = message
						slot["done"].set()
				elif self._onEvent is not None:
					try:
						self._onEvent(
							message.get("method", ""), message.get("params", {}), message.get("sessionId")
						)
					except Exception:  # A bad event handler must not end the connection.
						logging.getLogger(__name__).exception("WhatsApp Access: event handler failed")
		except (WebSocketError, ValueError, OSError):
			pass
		finally:
			self.closed = True
			self._ws.close()
			with self._lock:
				for slot in self._pending.values():
					slot["done"].set()
			if self._onClose is not None:
				self._onClose()

	def call(
		self,
		method: str,
		params: dict | None = None,
		sessionId: str | None = None,
		timeout: float = COMMAND_TIMEOUT_SECONDS,
	) -> dict:
		if self.closed:
			raise Disconnected("The browser connection is closed")
		messageId = next(self._ids)
		slot: dict[str, Any] = {"done": threading.Event()}
		with self._lock:
			self._pending[messageId] = slot
		message: dict[str, Any] = {"id": messageId, "method": method, "params": params or {}}
		if sessionId:
			message["sessionId"] = sessionId
		try:
			try:
				self._ws.send(json.dumps(message))
			except WebSocketError as e:
				raise Disconnected(str(e)) from e
			if not slot["done"].wait(timeout):
				raise CdpError(f"{method} did not answer within {timeout:g} seconds")
		finally:
			with self._lock:
				self._pending.pop(messageId, None)
		answer = slot.get("answer")
		if answer is None:
			raise Disconnected("The browser connection closed")
		if "error" in answer:
			raise CdpError(f"{method}: {answer['error'].get('message', answer['error'])}")
		return answer.get("result", {})

	def close(self) -> None:
		self._ws.close()
