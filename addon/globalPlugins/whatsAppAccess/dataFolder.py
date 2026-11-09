# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Keeps the add-on's data (the WhatsApp login and the user's own sounds) through updates.

NVDA updates an add-on by installing the new version beside the old one and, at the next start,
removing the old one with its uninstall task. Up to 0.3.0 that task removed the data folder, so every
update meant linking the phone again. The new version therefore moves the data aside while it is
installed, and puts it back when it first runs.

An installed NVDA keeps the data in the Windows account's LocalAppData folder, not in NVDA's configuration
folder. NVDA's "Use currently saved settings during sign-in and on secure screens" copies that whole folder
to Program Files, where every account on the computer can read it, and on many networks the roaming
AppData folder travels to a server. A portable NVDA keeps the data with its own configuration.
It imports nothing from NVDA at load time, so installTasks can load it by path and the tests can run it.
"""

import os
import shutil
import tempfile
import time
from collections.abc import Callable

DATA_NAME = "whatsAppAccess"
# The folder in LocalAppData, for an installed NVDA.
LOCAL_DATA_NAME = "NVDA WhatsApp Access"
UPDATING_NAME = "whatsAppAccess.updating"
PENDING_INSTALL_SUFFIX = ".pendingInstall"


def dataPath(configPath: str) -> str:
	return os.path.join(configPath, DATA_NAME)


def localDataPath(localAppData: str) -> str:
	return os.path.join(localAppData, LOCAL_DATA_NAME)


def addonDataPath() -> str:
	"""Where the running add-on keeps its data: LocalAppData for an installed NVDA, else the configuration.

	:return: The folder, or "" outside NVDA, as in the tests.
	"""
	try:
		import config
		import globalVars
	except ImportError:
		return ""
	localAppData = os.environ.get("LOCALAPPDATA", "")
	isInstalledCopy = getattr(config, "isInstalledCopy", None)
	if localAppData and isInstalledCopy is not None and isInstalledCopy():
		return localDataPath(localAppData)
	return dataPath(globalVars.appArgs.configPath)


def moveData(oldPath: str, newPath: str) -> bool:
	"""Move the data from where older versions kept it, then remove the old folder.

	Moving within one drive is a rename. Across drives, such as a roaming AppData folder on a server, it
	is copied first and the old folder removed only when the copy is whole. When newPath already exists,
	what is in it wins, such as a newer login, and only what it lacks, such as the user's own sounds,
	comes over.

	:return: Whether anything was moved.
	"""
	if os.path.normcase(os.path.abspath(oldPath)) == os.path.normcase(os.path.abspath(newPath)):
		return False
	if not os.path.isdir(oldPath):
		return False
	if not os.path.isdir(newPath):
		os.makedirs(os.path.dirname(newPath), exist_ok=True)
		_move(oldPath, newPath)
		return True
	moved = False
	for name in os.listdir(oldPath):
		if not os.path.exists(os.path.join(newPath, name)):
			_move(os.path.join(oldPath, name), os.path.join(newPath, name))
			moved = True
	# What is left is an older copy of the login, which must not stay where others can read it.
	shutil.rmtree(oldPath, ignore_errors=True)
	return moved


def _move(source: str, target: str) -> None:
	try:
		os.replace(source, target)
	except OSError:
		partial = target + ".moving"
		shutil.rmtree(partial, ignore_errors=True)
		if os.path.isdir(source):
			shutil.copytree(source, partial)
		else:
			shutil.copy2(source, partial)
		os.replace(partial, target)
		shutil.rmtree(source, ignore_errors=True)


# Photos, videos and documents opened with Enter are downloaded here, outside the login's folder.
TEMP_MEDIA_NAME = "WhatsApp Access"


def tempMediaPath() -> str:
	return os.path.join(tempfile.gettempdir(), TEMP_MEDIA_NAME)


def clearTempMedia() -> None:
	"""Remove the media downloaded to open them: they are other people's photos and documents, and must not
	pile up. A file still open in its program stays until next time."""
	shutil.rmtree(tempMediaPath(), ignore_errors=True)


def updatingPath(configPath: str) -> str:
	return os.path.join(configPath, UPDATING_NAME)


def updatePending(addonPath: str) -> bool:
	"""Whether the add-on at addonPath is being replaced by a new version waiting to be installed."""
	addonsDir, name = os.path.split(os.path.normpath(addonPath))
	if name.endswith(PENDING_INSTALL_SUFFIX):
		return False
	return os.path.isdir(os.path.join(addonsDir, name + PENDING_INSTALL_SUFFIX))


def keepThroughUpdate(
	configPath: str,
	stopRunning: Callable[[], None],
	forceClose: Callable[[], None],
	waitSeconds: float = 8.0,
) -> bool:
	"""Move the data aside, after stopping what holds it open. Returns whether it was moved.

	stopRunning stops the running add-on's hidden browser; forceClose closes it the hard way if it
	still holds its files after a while.
	"""
	data, updating = dataPath(configPath), updatingPath(configPath)
	if os.path.isdir(updating):
		# Installed again before NVDA restarted: the login kept by the first install is the real one. What
		# is in data now can only be new since then, such as an empty profile, so it goes, never the kept one.
		stopRunning()
		shutil.rmtree(data, ignore_errors=True)
		return True
	if not os.path.isdir(data):
		return False
	stopRunning()
	deadline = time.monotonic() + waitSeconds
	forced = False
	while True:
		try:
			os.replace(data, updating)
			return True
		except OSError:
			if time.monotonic() > deadline:
				return False
			if not forced and time.monotonic() > deadline - waitSeconds / 2:
				forceClose()
				forced = True
			time.sleep(0.3)


def restoreAfterUpdate(configPath: str) -> bool:
	"""Put the data back where the add-on keeps it. Returns whether there was data to put back."""
	data, updating = dataPath(configPath), updatingPath(configPath)
	if not os.path.isdir(updating):
		return False
	if os.path.isdir(data):
		# Made while the data was aside, such as an empty profile of a browser started meanwhile.
		shutil.rmtree(data, ignore_errors=True)
	os.replace(updating, data)
	return True


def removeAll(configPath: str, otherPaths: tuple[str, ...] = ()) -> None:
	"""The add-on is removed for good: its data goes with it.

	:param configPath: NVDA's configuration folder.
	:param otherPaths: Other folders with the add-on's data, such as the one in LocalAppData.
	"""
	for path in (dataPath(configPath), updatingPath(configPath), *otherPaths):
		if path:
			shutil.rmtree(path, ignore_errors=True)
