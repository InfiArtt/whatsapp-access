# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Asking about a new version from GitHub, and installing it with NVDA's own add-on installer."""

import os
import shutil
import tempfile
import threading
import time
from collections.abc import Callable

import addonHandler
import config
import gui
import ui
import wx
from gui import addonGui
from logHandler import log

from . import updates
from .configSpec import CONFIG_SECTION

addonHandler.initTranslation()

# Checked by itself at most once a day, a while after NVDA starts.
AUTO_CHECK_DELAY_MS = 30000
AUTO_CHECK_EVERY_SECONDS = 24 * 3600

_busy = False
"""Set from the start of a check until its offer is declined or its download is installed or fails, so two
checks never open two windows or download into the same file."""

_required: updates.Release | None = None
"""The required update the last check found, offered again when WhatsApp is asked to start."""

onRequired: Callable[[], None] | None = None
"""Set by the plugin: called when a required update is found, to stop WhatsApp until it is installed."""


def currentVersion() -> str:
	return addonHandler.getCodeAddon().version


def isUpdateRequired() -> bool:
	"""Whether a required update was found and is not installed yet: WhatsApp cannot be used until it is."""
	version = config.conf[CONFIG_SECTION]["requiredVersion"]
	if not version:
		return False
	try:
		return updates.isNewer(version, currentVersion())
	except updates.UpdateError:
		return False


def scheduleAutoCheck() -> wx.CallLater:
	"""Check by itself a while after NVDA starts.

	New versions are offered at most once a day, when the user wants that. A required update is looked
	for at every start whatever the setting, since WhatsApp Web may have changed so that this version no
	longer works; nothing is said unless one is found.

	:return: The timer, for the plugin to stop if it is stopped first.
	"""
	settings = config.conf[CONFIG_SECTION]
	daily = (
		settings["checkUpdates"] and time.time() - int(settings["lastUpdateCheck"]) > AUTO_CHECK_EVERY_SECONDS
	)
	return wx.CallLater(AUTO_CHECK_DELAY_MS, check, False, not daily)


def _checked(when: int) -> None:
	# config.conf is not safe to change from another thread.
	config.conf[CONFIG_SECTION]["lastUpdateCheck"] = when


def _done() -> None:
	global _busy
	_busy = False


def _setRequired(version: str) -> None:
	config.conf[CONFIG_SECTION]["requiredVersion"] = version


def check(manual: bool, onlyIfRequired: bool = False) -> None:
	"""Look for a newer release. manual says whether the user asked: only then is "no update" said.
	onlyIfRequired offers a new version only when it is a required update."""
	global _busy
	if _busy:
		if manual:
			# Translators: Said when the user checks for updates while a check or download is already
			# going on.
			ui.message(_("Already checking for updates. The answer comes in a moment"))
		return
	_busy = True
	if manual:
		# Translators: Said while the add-on looks for a new version.
		ui.message(_("Checking for updates…"))

	def work() -> None:
		offered = False
		try:
			try:
				release = updates.latestRelease(currentVersion())
			except updates.UpdateError as e:
				log.info(f"WhatsApp Access: update check: {e}")
				if manual:
					wx.CallAfter(_failed, str(e))
				return
			newer = updates.isNewer(release.version, currentVersion())
			if not onlyIfRequired:
				wx.CallAfter(_checked, int(time.time()))
			if newer and release.required:
				wx.CallAfter(_requiredFound, release)
				offered = True
				return
			wx.CallAfter(_setRequired, "")
			if onlyIfRequired:
				return
			if newer:
				wx.CallAfter(_offer, release)
				offered = True
			elif manual:
				wx.CallAfter(
					ui.message,
					# Translators: Said when the user checked for a new version and has the newest one.
					_("You have the newest version, {version}").format(version=currentVersion()),
				)
		finally:
			# Once offered, the offer says when it is over.
			if not offered:
				_done()

	try:
		threading.Thread(target=work, name="whatsAppAccess.updates", daemon=True).start()
	except BaseException:
		_done()
		raise


def _failed(error: str) -> None:
	if error == "noRelease":
		# Translators: Said when the add-on's GitHub page has no published version yet.
		message = _("No version has been published on GitHub yet.")
	else:
		# Translators: Said when looking for a new version failed, such as with no internet connection.
		message = _("Could not check for updates. Check your internet connection and try again.")
	ui.message(message)


def _requiredFound(release: updates.Release) -> None:
	global _required
	_required = release
	_setRequired(release.version)
	if onRequired is not None:
		try:
			onRequired()
		except Exception:  # noqa: BLE001 - the update is offered all the same
			log.exception("WhatsApp Access: stopping for a required update")
	_offer(release)


def offerRequired() -> None:
	"""WhatsApp was asked to start while a required update waits: offer it, or look for it again."""
	global _busy
	if _busy:
		# Translators: Said when WhatsApp is asked to start while the required update is being offered or
		# downloaded.
		ui.message(_("The update needed to use WhatsApp is on its way"))
		return
	if _required is None:
		check(True)
		return
	_busy = True
	_offer(_required)


def _offer(release: updates.Release) -> None:
	answer = wx.ID_CANCEL
	try:
		dialog = UpdateDialog(gui.mainFrame, release)
		gui.mainFrame.prePopup()
		try:
			answer = dialog.ShowModal()
		finally:
			dialog.Destroy()
			gui.mainFrame.postPopup()
	finally:
		if answer != wx.ID_OK:
			_done()
	if answer == wx.ID_OK:
		_download(release)


def _removeFolder(folder: str) -> None:
	shutil.rmtree(folder, ignore_errors=True)


def _download(release: updates.Release) -> None:
	def work() -> None:
		# A folder of its own for each download: nobody else's file is used or replaced, and it is all
		# removed afterwards.
		folder = ""
		installing = False
		try:
			folder = tempfile.mkdtemp(prefix="whatsAppAccess-update-")
			path = os.path.join(folder, release.fileName)
			updates.download(release, path)
			wx.CallAfter(_install, folder, path)
			installing = True
		except (updates.UpdateError, OSError) as e:
			log.info(f"WhatsApp Access: update download: {e}")
			wx.CallAfter(
				ui.message,
				# Translators: Said when the new version could not be downloaded or was damaged.
				_("The new version could not be downloaded. Try again later."),
			)
		finally:
			# Once handed to the installer, it removes the folder when done.
			if not installing:
				if folder:
					_removeFolder(folder)
				_done()

	try:
		# Translators: Said while a new version of the add-on downloads.
		ui.message(_("Downloading version {version}…").format(version=release.version))
		threading.Thread(target=work, name="whatsAppAccess.updateDownload", daemon=True).start()
	except BaseException:
		_done()
		raise


def _install(folder: str, path: str) -> None:
	try:
		# NVDA's own installer checks the file, asks about compatibility, and copies the add-on for the
		# restart, so the downloaded file is no longer needed once it returns.
		installed = addonGui.installAddon(gui.mainFrame, path)
	finally:
		_removeFolder(folder)
		_done()
	if installed:
		addonGui.promptUserForRestart()


class UpdateDialog(wx.Dialog):
	"""A new version, what changed in it, and whether to install it now."""

	def __init__(self, parent: wx.Window, release: updates.Release) -> None:
		# Translators: The title of the window that offers a new version of the add-on.
		super().__init__(parent, title=_("WhatsApp Access update"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		if release.required:
			intro = _(
				# Translators: The top of the window that offers a required update, with both version numbers.
				"WhatsApp Web changed, and WhatsApp Access {current} no longer works with it. Install version "
				"{new} to use WhatsApp again; until then WhatsApp stays closed."
			).format(new=release.version, current=currentVersion())
		else:
			intro = _(
				# Translators: The top of the window that offers a new version, with both version numbers.
				"Version {new} is available. You have version {current}."
			).format(new=release.version, current=currentVersion())
		introText = wx.StaticText(self, label=intro)
		introText.Wrap(520)
		sizer.Add(introText, 0, wx.ALL, 8)
		# Translators: The label of the text that says what changed in the new version.
		sizer.Add(wx.StaticText(self, label=_("&What's new:")), 0, wx.LEFT | wx.RIGHT, 8)
		notes = wx.TextCtrl(
			self,
			# Translators: Shown when a new version has no description of its changes.
			value=release.notes or _("No description."),
			style=wx.TE_MULTILINE | wx.TE_READONLY,
			size=(520, 220),
		)
		sizer.Add(notes, 1, wx.EXPAND | wx.ALL, 8)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button that downloads and installs the new version.
		install = wx.Button(self, wx.ID_OK, label=_("&Download and install"))
		install.SetDefault()
		buttons.Add(install, 0, wx.RIGHT, 6)
		buttons.Add(
			wx.Button(
				self,
				wx.ID_CANCEL,
				# Translators: A button that closes the window of a required update; WhatsApp stays closed.
				label=_("&Later")
				if release.required
				# Translators: A button that closes the update window; the add-on asks again another day.
				else _("&Not now"),
			)
		)
		sizer.Add(buttons, 0, wx.ALL, 8)
		self.SetSizerAndFit(sizer)
		self.CentreOnScreen()
		notes.SetFocus()
