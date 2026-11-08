# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Runs WhatsApp Web in a hidden Chromium-based browser of the add-on's own.

The browser runs headless, with its own profile in NVDA's configuration folder, so the user's own browser
and its profile are never touched, and no "Allow remote debugging?" question is asked: browsers ask that
only for their default profile. The DevTools port is chosen by the browser at random and read from the
DevToolsActivePort file in the profile.
It imports nothing from NVDA, so it can be tested on its own.
"""

import ctypes
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

# Headless "new" mode (a whole browser with no window) and everything the add-on uses arrived before this.
MINIMUM_MAJOR_VERSION = 120
START_TIMEOUT_SECONDS = 45.0
WHATSAPP_URL = "https://web.whatsapp.com/"


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
	for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
		try:
			with winreg.OpenKey(root, key) as handle:
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


def launchArguments(browser: InstalledBrowser, profileDir: str) -> list[str]:
	return [
		browser.path,
		"--headless=new",
		f"--user-data-dir={profileDir}",
		# 0: the browser picks a free port and writes it to DevToolsActivePort in the profile.
		"--remote-debugging-port=0",
		"--remote-debugging-address=127.0.0.1",
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
		f"--user-agent={chromeUserAgent(browser.major)}",
		"about:blank",
	]


class HiddenBrowser:
	"""One hidden browser process with the add-on's profile. start() waits until DevTools is reachable."""

	def __init__(self, browser: InstalledBrowser, profileDir: str) -> None:
		self.browser = browser
		self.profileDir = profileDir
		self.process: subprocess.Popen | None = None
		self._lock = threading.Lock()

	@property
	def running(self) -> bool:
		return self.process is not None and self.process.poll() is None

	def start(self) -> cdp.DebuggableBrowser:
		with self._lock:
			os.makedirs(self.profileDir, exist_ok=True)
			portFile = Path(self.profileDir) / "DevToolsActivePort"
			if not self.running:
				try:
					portFile.unlink()
				except OSError:
					pass
				flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
				self.process = subprocess.Popen(
					launchArguments(self.browser, self.profileDir),
					stdin=subprocess.DEVNULL,
					stdout=subprocess.DEVNULL,
					stderr=subprocess.DEVNULL,
					creationflags=flags,
				)
			deadline = time.monotonic() + START_TIMEOUT_SECONDS
			while time.monotonic() < deadline:
				if self.process.poll() is not None:
					raise OSError(
						f"{self.browser.name} closed while starting (exit code {self.process.returncode})"
					)
				active = cdp.readActivePort(portFile)
				executable = os.path.basename(self.browser.path)
				if active is not None and cdp.portBelongsTo(active[0], executable):
					port, wsPath = active
					target = cdp.Browser(self.browser.name, Path(self.profileDir), executable, "")
					return cdp.DebuggableBrowser(target, port, wsPath)
				time.sleep(0.2)
			raise TimeoutError(f"{self.browser.name} did not start within {START_TIMEOUT_SECONDS:g} seconds")

	def stop(self) -> None:
		"""Close the browser and the processes it started."""
		with self._lock:
			process, self.process = self.process, None
		if process is None or process.poll() is not None:
			return
		if sys.platform == "win32":
			flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
			subprocess.run(
				["taskkill", "/PID", str(process.pid), "/T", "/F"],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
				creationflags=flags,
				check=False,
			)
		else:
			process.terminate()
		try:
			process.wait(timeout=5)
		except subprocess.TimeoutExpired:
			process.kill()
