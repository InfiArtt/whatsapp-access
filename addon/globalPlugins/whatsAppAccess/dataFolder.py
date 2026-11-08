# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Keeps the add-on's data (the WhatsApp login and the user's own sounds) through updates.

NVDA updates an add-on by installing the new version beside the old one and, at the next start,
removing the old one with its uninstall task. Up to 0.3.0 that task removed the data folder, so every
update meant linking the phone again. The new version therefore moves the data aside while it is
installed, and puts it back when it first runs. It imports nothing from NVDA, so installTasks can load
it by path and the tests can run it.
"""

import os
import shutil
import time
from collections.abc import Callable

DATA_NAME = "whatsAppAccess"
UPDATING_NAME = "whatsAppAccess.updating"
PENDING_INSTALL_SUFFIX = ".pendingInstall"


def dataPath(configPath: str) -> str:
	return os.path.join(configPath, DATA_NAME)


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
	waitSeconds: float = 15.0,
) -> bool:
	"""Move the data aside, after stopping what holds it open. Returns whether it was moved.

	stopRunning stops the running add-on's hidden browser; forceClose closes it the hard way if it
	still holds its files after a while.
	"""
	data, updating = dataPath(configPath), updatingPath(configPath)
	if not os.path.isdir(data):
		return False
	stopRunning()
	if os.path.isdir(updating):
		shutil.rmtree(updating, ignore_errors=True)
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


def removeAll(configPath: str) -> None:
	"""The add-on is removed for good: its data goes with it."""
	for path in (dataPath(configPath), updatingPath(configPath)):
		shutil.rmtree(path, ignore_errors=True)
