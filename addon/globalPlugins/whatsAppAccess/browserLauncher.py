# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Runs WhatsApp Web in a hidden Chromium-based browser of the add-on's own.

The browser runs headless, with its own profile, so the user's own browser and its profile are never
touched. The add-on talks to it over a pair of anonymous pipes (--remote-debugging-pipe), not a debugging
port: a port on 127.0.0.1 can be reached by every program on the computer, and through it, read the chats
and send messages. Only the add-on holds the pipes, and the browser exits by itself when they close, even
if NVDA does not exit cleanly.
It imports nothing from NVDA, so it can be tested on its own.
"""

import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from . import cdp

# Headless "new" mode (a whole browser with no window), --remote-debugging-io-pipes on Windows (Chromium
# 117) and everything else the add-on uses arrived before this.
MINIMUM_MAJOR_VERSION = 120
START_TIMEOUT_SECONDS = 45.0
WHATSAPP_URL = "https://web.whatsapp.com/"
# GetSystemMetrics: whether Windows is shutting down, restarting or signing the user out.
SM_SHUTTINGDOWN = 0x2000


def windowsShuttingDown(getSystemMetrics: Callable[[int], int] | None = None) -> bool:
	"""Whether Windows is shutting down, restarting or signing out. It then closes the hidden browser
	before NVDA, which is no reason to say WhatsApp stopped or to start it again."""
	if getSystemMetrics is None:
		getSystemMetrics = ctypes.windll.user32.GetSystemMetrics
	try:
		return bool(getSystemMetrics(SM_SHUTTINGDOWN))
	except OSError:
		return False


@dataclass(frozen=True)
class InstalledBrowser:
	key: str
	"""brave, chrome, chromium, vivaldi, opera or edge."""
	name: str
	path: str
	version: tuple[int, ...]

	@property
	def major(self) -> int:
		return self.version[0] if self.version else 0


# The order of preference for "automatic": Brave first, Edge last.
# (key, name, executable, folders under Program Files and the user's LocalAppData)
KNOWN_BROWSERS = (
	("brave", "Brave", "brave.exe", (r"BraveSoftware\Brave-Browser\Application",)),
	("chrome", "Google Chrome", "chrome.exe", (r"Google\Chrome\Application",)),
	("chromium", "Chromium", "chrome.exe", (r"Chromium\Application",)),
	("vivaldi", "Vivaldi", "vivaldi.exe", (r"Vivaldi\Application",)),
	("opera", "Opera", "opera.exe", (r"Programs\Opera", "Opera")),
	("edge", "Microsoft Edge", "msedge.exe", (r"Microsoft\Edge\Application",)),
)
BROWSER_KEYS = tuple(k for k, _, _, _ in KNOWN_BROWSERS)

_VERSION_FOLDER = re.compile(r"^\d+(\.\d+){1,3}$")


def parseVersion(text: str) -> tuple[int, ...]:
	"""'157.0.8103.39' -> (157, 0, 8103, 39); () when it is not a version."""
	text = text.strip()
	if not _VERSION_FOLDER.match(text):
		return ()
	return tuple(int(part) for part in text.split("."))


def _versionFromFolders(executable: Path) -> tuple[int, ...]:
	"""Chromium browsers keep their files in a folder named after the version, next to the program."""
	try:
		versions = [parseVersion(entry.name) for entry in executable.parent.iterdir() if entry.is_dir()]
	except OSError:
		return ()
	versions = [v for v in versions if v]
	return max(versions) if versions else ()


def _fileVersion(path: str) -> tuple[int, ...]:
	"""The version in a program file's version resource, from Windows."""
	if sys.platform != "win32":
		return ()
	version = ctypes.WinDLL("version")
	size = version.GetFileVersionInfoSizeW(path, None)
	if not size:
		return ()
	buffer = ctypes.create_string_buffer(size)
	if not version.GetFileVersionInfoW(path, 0, size, buffer):
		return ()
	info = ctypes.c_void_p()
	length = wintypes.UINT()
	if not version.VerQueryValueW(buffer, "\\", ctypes.byref(info), ctypes.byref(length)):
		return ()

	class FixedFileInfo(ctypes.Structure):
		_fields_ = [
			("signature", wintypes.DWORD),
			("strucVersion", wintypes.DWORD),
			("ms", wintypes.DWORD),
			("ls", wintypes.DWORD),
		]

	fixed = ctypes.cast(info, ctypes.POINTER(FixedFileInfo)).contents
	return (fixed.ms >> 16, fixed.ms & 0xFFFF, fixed.ls >> 16, fixed.ls & 0xFFFF)


def _registryPath(executable: str) -> str | None:
	"""Where Windows' App Paths say a program is, for browsers installed somewhere unusual."""
	if sys.platform != "win32":
		return None
	import winreg

	key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
	# NVDA before 2026.1 is a 32-bit program: Windows would show it only the 32-bit programs' part of
	# HKEY_LOCAL_MACHINE, where 64-bit browsers are not listed. The 64-bit view comes first.
	views = (winreg.KEY_WOW64_64KEY, 0)
	for root, view in [(winreg.HKEY_CURRENT_USER, 0)] + [(winreg.HKEY_LOCAL_MACHINE, v) for v in views]:
		try:
			with winreg.OpenKey(root, key, 0, winreg.KEY_READ | view) as handle:
				value, _ = winreg.QueryValueEx(handle, "")
				if value and os.path.isfile(value):
					return value
		except OSError:
			continue
	return None


def findBrowsers(
	roots: list[str] | None = None,
	registry: Callable[[str], str | None] = _registryPath,
	fileVersion: Callable[[str], tuple[int, ...]] = _fileVersion,
) -> list[InstalledBrowser]:
	"""The Chromium-based browsers installed, in order of preference, each with its version."""
	if roots is None:
		roots = [
			# In a 32-bit program, such as NVDA before 2026.1, ProgramFiles is the "(x86)" folder;
			# ProgramW6432 is always the real Program Files, where 64-bit browsers are.
			os.environ.get("ProgramW6432", ""),
			os.environ.get("ProgramFiles", r"C:\Program Files"),
			os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
			os.environ.get("LOCALAPPDATA", ""),
		]
	found = []
	for key, name, executable, folders in KNOWN_BROWSERS:
		candidates = [Path(root) / folder / executable for root in roots if root for folder in folders]
		path = next((str(c) for c in candidates if c.is_file()), None)
		if path is None and key != "chromium":
			# Chromium's chrome.exe would be found as Google Chrome's, so only look it up in folders.
			path = registry(executable)
		if path is None:
			continue
		version = _versionFromFolders(Path(path)) or fileVersion(path)
		found.append(InstalledBrowser(key, name, path, version))
	return found


def chooseBrowser(browsers: list[InstalledBrowser], preference: str = "auto") -> InstalledBrowser | None:
	"""The browser to use: the one the user chose if it is new enough, else the first new enough one."""
	usable = [b for b in browsers if b.major >= MINIMUM_MAJOR_VERSION]
	if preference != "auto":
		chosen = next((b for b in usable if b.key == preference), None)
		if chosen is not None:
			return chosen
	return usable[0] if usable else None


def chromeUserAgent(major: int) -> str:
	"""The user agent of Google Chrome of this version, in place of headless mode's "HeadlessChrome"."""
	return (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
		f"Chrome/{major}.0.0.0 Safari/537.36"
	)


def chromeUserAgentMetadata(version: tuple[int, ...]) -> dict:
	"""The client hints Google Chrome sends, so the browser's brands do not give headless mode away."""
	major = str(version[0]) if version else "0"
	# Chrome's own reduced form; Brave's and others' own version numbers would give them away.
	full = f"{major}.0.0.0"
	return {
		"brands": [
			{"brand": "Chromium", "version": major},
			{"brand": "Google Chrome", "version": major},
			{"brand": "Not=A?Brand", "version": "24"},
		],
		"fullVersionList": [
			{"brand": "Chromium", "version": full},
			{"brand": "Google Chrome", "version": full},
			{"brand": "Not=A?Brand", "version": "24.0.0.0"},
		],
		"platform": "Windows",
		"platformVersion": "10.0.0",
		"architecture": "x86",
		"model": "",
		"mobile": False,
		"bitness": "64",
	}


def launchArguments(browser: InstalledBrowser, profileDir: str, pipeHandles: tuple[int, int]) -> list[str]:
	"""The hidden browser's command line.

	:param pipeHandles: The Windows handles the browser reads DevTools commands from and writes answers to.
	"""
	return [
		browser.path,
		"--headless=new",
		f"--user-data-dir={profileDir}",
		# DevTools over the two pipes only; no port is opened.
		"--remote-debugging-pipe",
		f"--remote-debugging-io-pipes={pipeHandles[0]},{pipeHandles[1]}",
		"--no-first-run",
		"--no-default-browser-check",
		"--disable-gpu",
		"--disable-extensions",
		"--disable-sync",
		# WhatsApp must keep running at full speed although nobody looks at it.
		"--disable-background-timer-throttling",
		"--disable-renderer-backgrounding",
		"--disable-backgrounding-occluded-windows",
		"--autoplay-policy=no-user-gesture-required",
		# Less memory: drawing needs no GPU process, and browser services nobody uses here are left off.
		# Site isolation stays on: WhatsApp shows media and link previews from anyone, and a separate,
		# sandboxed renderer per site keeps a flaw in one from reaching the WhatsApp page.
		(
			"--disable-features=Translate,OptimizationHints,MediaRouter,"
			"BackForwardCache,AutofillServerCommunication,CalculateNativeWinOcclusion"
		),
		"--in-process-gpu",
		"--disable-background-networking",
		"--disable-component-update",
		"--disable-default-apps",
		"--disable-domain-reliability",
		"--no-pings",
		# A small page: fewer chats and pictures are laid out at once.
		"--window-size=800,600",
		"--force-device-scale-factor=1",
		f"--user-agent={chromeUserAgent(browser.major)}",
		"about:blank",
	]


def profileInUse(profileDir: str) -> bool:
	"""Whether a browser still runs with this profile: Chromium keeps its lockfile open while it does."""
	lock = Path(profileDir) / "lockfile"
	if not lock.exists():
		return False
	try:
		lock.unlink()
	except PermissionError:
		return True
	except OSError:
		pass
	return False


# The process id of the hidden browser, kept in its profile, so one left running can be closed later.
PID_FILE = "whatsAppAccess.pid"


def _quiet(arguments: list[str], timeout: float, env: dict[str, str] | None = None) -> int:
	"""Run a program with no window and wait for it. Returns its exit code."""
	return subprocess.run(
		arguments,
		# All three: NVDA has no console, and handles it would pass on can be invalid.
		stdin=subprocess.DEVNULL,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
		creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		timeout=timeout,
		check=False,
		env=env,
	).returncode


def _waitUntilFree(profileDir: str, seconds: float) -> bool:
	deadline = time.monotonic() + seconds
	while profileInUse(profileDir):
		if time.monotonic() > deadline:
			return False
		time.sleep(0.2)
	return True


# Whether a Win32_Process $p is the hidden browser with this profile. The profile and the program's name come
# in environment variables, never inside the script, so no character in them (' " [ ] * ?) can change what
# it does or matches. The profile's argument must end there, at a space or a closing quote, so a profile
# named ...\profile does not match ...\profile2.
_IS_HIDDEN_BROWSER = (
	"function IsHiddenBrowser($p) { "
	"$line = [string]$p.CommandLine + ' '; "
	"$argument = '--user-data-dir=' + $env:WA_PROFILE; "
	"return ($p.Name -eq $env:WA_EXE) -and "
	"($line.Contains($argument + ' ') -or $line.Contains($argument + [char]34)) "
	"}; "
)


def _powerShell(script: str, profileDir: str, executable: str, timeout: float, **variables: str) -> int:
	powershell = os.path.join(
		os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
	)
	env = dict(os.environ, WA_PROFILE=profileDir, WA_EXE=executable, **variables)
	return _quiet(
		[powershell, "-NoProfile", "-NonInteractive", "-Command", _IS_HIDDEN_BROWSER + script], timeout, env
	)


def isHiddenBrowser(pid: int, profileDir: str, executable: str) -> bool:
	"""Whether the process with this id is the hidden browser with this profile.

	Windows reuses process ids: the id in the pid file may now belong to the user's own browser, which
	must never be closed.
	"""
	script = (
		"$p = Get-CimInstance Win32_Process -Filter ('ProcessId=' + [int]$env:WA_PID); "
		"if ($p -and (IsHiddenBrowser $p)) { exit 0 } else { exit 1 }"
	)
	try:
		return _powerShell(script, profileDir, executable, 30, WA_PID=str(int(pid))) == 0
	except (OSError, subprocess.SubprocessError):
		return False


def stopHiddenBrowsers(profileDir: str, executable: str) -> None:
	"""Stop every process of the program whose command line has this profile, whatever its id."""
	script = (
		"Get-CimInstance Win32_Process | Where-Object { IsHiddenBrowser $_ } | "
		"ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
	)
	_powerShell(script, profileDir, executable, 30)


def closeLeftovers(profileDir: str, executable: str) -> str:
	"""Close a hidden browser left running with this profile, for example when NVDA could not close it.

	Otherwise a new one hands over to it and closes at once (exit code 21), and WhatsApp never starts.
	Returns why it could not be closed, or "" when the profile is free.
	"""
	if sys.platform != "win32" or not profileInUse(profileDir):
		return ""
	problems = []
	try:
		pid = int((Path(profileDir) / PID_FILE).read_text(encoding="ascii").strip())
	except (OSError, ValueError):
		pid = 0
	if pid and isHiddenBrowser(pid, profileDir, executable):
		taskkill = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
		try:
			_quiet(
				[taskkill, "/F", "/T", "/FI", f"PID eq {pid}", "/FI", f"IMAGENAME eq {executable}"],
				timeout=15,
			)
		except (OSError, subprocess.SubprocessError) as e:
			problems.append(f"taskkill: {e}")
		if _waitUntilFree(profileDir, 5):
			return ""
	# Started by an older version, or its id was lost or reused: find it by its profile in its command line.
	try:
		stopHiddenBrowsers(profileDir, executable)
	except (OSError, subprocess.SubprocessError) as e:
		problems.append(f"PowerShell: {e}")
	if _waitUntilFree(profileDir, 5):
		return ""
	return "; ".join(problems) or "it is still running"


class HiddenBrowser:
	"""One hidden browser process with the add-on's profile. start() waits until it answers on its pipe."""

	def __init__(self, browser: InstalledBrowser, profileDir: str) -> None:
		self.browser = browser
		self.profileDir = profileDir
		self.process: subprocess.Popen | None = None
		self._transport: cdp.PipeTransport | None = None
		self._lock = threading.Lock()

	@property
	def running(self) -> bool:
		return self.process is not None and self.process.poll() is None

	def start(self) -> cdp.PipeBrowser:
		"""Start the browser, or give the one already running, and wait until it answers.

		A pipe serves one connection for the browser's whole life. When the last connection closed it, the
		browser is on its way out, so a new one is started.
		"""
		with self._lock:
			target = cdp.Browser(
				self.browser.name, Path(self.profileDir), os.path.basename(self.browser.path), ""
			)
			if self.running and self._transport is not None and not self._transport.closed:
				return cdp.PipeBrowser(target, self._transport)
			if self.running:
				self._stopLocked()
			os.makedirs(self.profileDir, exist_ok=True)
			leftover = closeLeftovers(self.profileDir, os.path.basename(self.browser.path))
			# Left by versions that used a debugging port; it names a port nothing listens on any more.
			try:
				(Path(self.profileDir) / "DevToolsActivePort").unlink()
			except OSError:
				pass
			transport, handles = cdp.PipeTransport.forChild()
			info = subprocess.STARTUPINFO()
			# Only the two pipe ends (and the standard handles subprocess adds) reach the browser.
			info.lpAttributeList = {"handle_list": list(handles)}
			try:
				self.process = subprocess.Popen(
					launchArguments(self.browser, self.profileDir, handles),
					stdin=subprocess.DEVNULL,
					stdout=subprocess.DEVNULL,
					stderr=subprocess.DEVNULL,
					startupinfo=info,
					close_fds=True,
					creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
				)
			except BaseException:
				transport.close()
				transport.closeReader()
				raise
			finally:
				transport.childStarted()
			self._transport = transport
			try:
				self._waitForAnswer(transport, leftover)
			except BaseException:
				self._stopLocked()
				raise
			# Only now: a browser that never answered left nothing to close later.
			try:
				(Path(self.profileDir) / PID_FILE).write_text(str(self.process.pid), encoding="ascii")
			except OSError:
				pass
			return cdp.PipeBrowser(target, transport)

	def _waitForAnswer(self, transport: cdp.PipeTransport, leftover: str) -> None:
		"""Ask the browser its version over the pipe, and wait for the answer before anything else is sent."""
		transport.send(json.dumps({"id": 0, "method": "Browser.getVersion"}))
		outcome: dict[str, BaseException | str] = {}

		def read() -> None:
			try:
				outcome["answer"] = transport.receive()
			except BaseException as e:  # noqa: BLE001 - handed to the waiting thread
				outcome["error"] = e

		reader = threading.Thread(target=read, name="whatsAppAccess.browserStart", daemon=True)
		reader.start()
		deadline = time.monotonic() + START_TIMEOUT_SECONDS
		while reader.is_alive() and time.monotonic() < deadline:
			reader.join(0.2)
		process = self.process
		if "answer" in outcome:
			return
		if process is not None and process.poll() is not None:
			reason = f"{self.browser.name} closed while starting (exit code {process.returncode})"
			if leftover:
				reason += f"; the last hidden browser could not be closed: {leftover}"
			raise OSError(reason)
		if "error" in outcome:
			raise OSError(f"{self.browser.name} did not answer on its pipe: {outcome['error']}")
		raise TimeoutError(f"{self.browser.name} did not start within {START_TIMEOUT_SECONDS:g} seconds")

	def stop(self) -> None:
		"""Close the browser and the processes it started."""
		with self._lock:
			self._stopLocked()

	def _stopLocked(self) -> None:
		process, self.process = self.process, None
		transport, self._transport = self._transport, None
		if process is not None:
			# Its id is free for Windows to give to another program now.
			try:
				(Path(self.profileDir) / PID_FILE).unlink()
			except OSError:
				pass
		if transport is not None:
			# The browser exits by itself once its pipe closes; taskkill below makes sure.
			transport.close()
		if process is None or process.poll() is not None:
			return
		if sys.platform == "win32":
			flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
			taskkill = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
			try:
				subprocess.run(
					[taskkill, "/PID", str(process.pid), "/T", "/F"],
					# All three: NVDA has no console, and while it closes, handles it would pass on are invalid.
					stdin=subprocess.DEVNULL,
					stdout=subprocess.DEVNULL,
					stderr=subprocess.DEVNULL,
					creationflags=flags,
					check=False,
				)
			except OSError:
				process.kill()
		else:
			process.terminate()
		try:
			process.wait(timeout=5)
		except subprocess.TimeoutExpired:
			process.kill()
