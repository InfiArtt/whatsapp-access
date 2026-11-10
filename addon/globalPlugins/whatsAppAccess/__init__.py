# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""WhatsApp in a simple window made for NVDA, while WhatsApp Web stays open in the browser.

The add-on talks to the WhatsApp Web tab through the browser's remote debugging, so the browser can stay
in the background. It is a different way to see and use WhatsApp, not a bot: it sends only what the user
writes or records, when the user chooses to send it.
"""

import os
import shutil
import threading
import time

import addonHandler
import config
import globalPluginHandler
import globalVars
import gui
import ui
import wx
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import NVDASettingsDialog, SettingsPanel
from logHandler import log
from NVDAObjects import NVDAObject
from scriptHandler import script

from . import browserLauncher, dataFolder, messageText, notifications, sounds, updateCheck
from .callWindow import CallAnnouncer
from .chatWindow import ChatWindow, errorText
from .configSpec import ANNOUNCE_CHOICES, CONFIG_SECTION, CONFIG_SPEC
from .questions import askYesNo
from .setupDialogs import LinkDialog, SetupDialog
from .whatsApp import HiddenOptions, WhatsAppError, WhatsAppSession

addonHandler.initTranslation()

# Translators: The name of the category of this add-on's commands in the Input Gestures dialog.
SCRCAT_WHATSAPP = _("WhatsApp Access")
# A connection attempt that has not finished after this long is given up, so the user can try again.
# The browser waits up to three minutes for its question to be answered.
CONNECT_STALE_SECONDS = 240
# If the hidden browser stops by itself more often than this, the add-on stops starting it again.
MAX_RESTARTS = 3
RESTART_WINDOW_SECONDS = 600
# Starting WhatsApp with NVDA waits a little, so NVDA's own start is not slowed down.
AUTO_START_DELAY_MS = 4000
START_RETRY_SECONDS = 3
# A lost connection is said only after this long, so a short drop stays silent.
CONNECTION_LOST_DELAY_MS = 8000


def _profileDir() -> str:
	"""The hidden browser's own profile, with the WhatsApp login. See dataFolder for where it is."""
	return os.path.join(dataFolder.addonDataPath(), "browser")


def _ensureConfigSection() -> None:
	# installTasks registers the section for the next start; this covers copies made by hand during development.
	if CONFIG_SECTION not in config.conf.spec:
		config.conf.spec[CONFIG_SECTION] = CONFIG_SPEC
		return
	sectionSpec = config.conf.spec[CONFIG_SECTION]
	for key, spec in CONFIG_SPEC.items():
		if key not in sectionSpec:
			sectionSpec[key] = spec


def _disabledOnSecureScreens(
	pluginClass: type[globalPluginHandler.GlobalPlugin],
) -> type[globalPluginHandler.GlobalPlugin]:
	"""On the sign-in screen, UAC prompts and other secure screens, the add-on does nothing at all.

	NVDA runs there as SYSTEM, so a browser started there would run as SYSTEM too, and WhatsApp is not
	the user's to open on a shared sign-in screen. NVDA's plain GlobalPlugin is used instead, so none of
	the add-on's commands, settings or timers exist there.
	"""
	if globalVars.appArgs.secure:
		return globalPluginHandler.GlobalPlugin
	return pluginClass


@_disabledOnSecureScreens
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self) -> None:
		super().__init__()
		_ensureConfigSection()
		# After an update the WhatsApp login waits aside; it must be back before the browser starts.
		try:
			if dataFolder.restoreAfterUpdate(globalVars.appArgs.configPath):
				log.info("WhatsApp Access: the WhatsApp data was kept through the update")
		except OSError:
			log.exception("WhatsApp Access: putting the WhatsApp data back after the update")
		# Older versions kept the data in NVDA's configuration folder. Moving it can mean copying about
		# 1 GB, so it happens in the background; starting WhatsApp waits for it.
		self._dataMoved = threading.Thread(
			target=self._moveDataOutOfConfig, name="whatsAppAccess.moveData", daemon=True
		)
		self._dataMoved.start()
		self.session = WhatsAppSession(onEvent=self._onEvent, onDisconnect=self._onDisconnect)
		# Translators: Said after the name of someone who is not in the user's contacts, such as
		# "~Budi (not a contact)", so that a stranger calling themselves "Mom" is not taken for a contact.
		self.session.notContactWords = _("not a contact")
		self.window: ChatWindow | None = None
		self._connecting = False
		self._connectingSince = 0.0
		self.hidden: browserLauncher.HiddenBrowser | None = None
		self.calls = CallAnnouncer(self.session, lambda: config.conf[CONFIG_SECTION]["hints"])
		self._restarts: list[float] = []
		self._stopping = False
		self._closeDialog: wx.Dialog | None = None
		self._connectionLost = False
		self._saidLost = False
		self._lostTimer: wx.CallLater | None = None
		self._terminated = False
		"""Set by terminate. Work still running in other threads then does nothing more, so a plugin
		reloaded with NVDA+Control+F3 never leaves a second browser or window behind."""
		self._saidMissingFeatures = False
		self._showWhenStarted = False
		"""NVDA+Shift+W was pressed while a start was already on its way: open the window when it is done."""
		self._autoStartTimer: wx.CallLater | None = None
		settings = config.conf[CONFIG_SECTION]
		if settings["setupDone"] and settings["connection"] == "hidden" and settings["startWithNVDA"]:
			self._autoStartTimer = wx.CallLater(AUTO_START_DELAY_MS, self._startHidden, False, False)
		updateCheck.onRequired = self._requiredUpdateFound
		self._updateTimer = updateCheck.scheduleAutoCheck()
		WhatsAppSettingsPanel.plugin = self
		PositionSlider.plugin = self
		NVDASettingsDialog.categoryClasses.append(WhatsAppSettingsPanel)

	def _moveDataOutOfConfig(self) -> None:
		# Media opened in an earlier session are no longer needed.
		dataFolder.clearTempMedia()
		try:
			if dataFolder.moveData(
				dataFolder.dataPath(globalVars.appArgs.configPath), dataFolder.addonDataPath()
			):
				log.info("WhatsApp Access: moved the WhatsApp data out of NVDA's configuration folder")
		except OSError:
			log.exception("WhatsApp Access: moving the WhatsApp data out of NVDA's configuration folder")

	def _callChanged(self) -> None:
		if self.window:
			self.window.onCallChanged()

	def chooseNVDAObjectOverlayClasses(self, obj, clsList) -> None:
		window = self.window
		if window and getattr(obj, "windowHandle", 0) == window.positionSlider.GetHandle():
			clsList.insert(0, PositionSlider)

	def event_gainFocus(self, obj, nextHandler) -> None:
		"""Coming back to the WhatsApp window while one of its dialogs is open goes to that dialog.

		Alt+Tab lists only the main window; while a dialog is open that window is locked, so the user would
		hear "unavailable" and could not reach the dialog's buttons."""
		dialog = self._openDialogOf(obj)
		if dialog:
			# Straight to the dialog, without first saying the locked window.
			import ctypes

			ctypes.windll.user32.SetForegroundWindow(dialog)
			return
		window = self.window
		if window and window.isQuietFocus(getattr(obj, "windowHandle", 0)):
			# The messages list followed the voice messages and the user wants quiet: NVDA still tracks
			# the focus, but says nothing.
			import speech

			mode = speech.getState().speechMode
			speech.setSpeechMode(speech.SpeechMode.off)
			try:
				nextHandler()
			finally:
				speech.setSpeechMode(mode)
			return
		nextHandler()

	def _openDialogOf(self, obj) -> int:
		"""The dialog open over the WhatsApp window, when obj is that window while it is locked; else 0."""
		window = self.window
		if window is None or not window or window.IsEnabled():
			return 0
		try:
			handle = window.GetHandle()
		except RuntimeError:
			return 0
		if obj.windowHandle != handle:
			return 0
		import ctypes
		from ctypes import wintypes

		user32 = ctypes.windll.user32
		owned: list[int] = []
		others: list[int] = []

		# Usually the dialog is one the WhatsApp window owns; GetLastActivePopup misses it once the user
		# went to another program. A question from NVDA or another add-on, such as NVDA MCP asking to allow
		# key presses, locks this window too: then it is the other window NVDA shows, visible and usable.
		@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
		def collect(hwnd, lParam):
			if hwnd != handle and user32.IsWindowVisible(hwnd) and user32.IsWindowEnabled(hwnd):
				if user32.GetWindow(hwnd, 4) == handle:
					owned.append(hwnd)
				elif user32.GetWindowTextLengthW(hwnd):
					others.append(hwnd)
			return True

		user32.EnumThreadWindows(user32.GetWindowThreadProcessId(handle, None), collect, 0)
		found = owned or others
		return found[0] if found else 0

	def terminate(self) -> None:
		self._terminated = True
		self._stopping = True
		for timer in (self._autoStartTimer, self._updateTimer, self._lostTimer):
			if timer is not None and timer.IsRunning():
				timer.Stop()
		self._autoStartTimer = self._updateTimer = self._lostTimer = None
		if updateCheck.onRequired == self._requiredUpdateFound:
			updateCheck.onRequired = None
		sounds.stopRing()
		self.calls.connectionGone(announce=False)
		if PositionSlider.plugin is self:
			PositionSlider.plugin = None
		if WhatsAppSettingsPanel in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.remove(WhatsAppSettingsPanel)
		if self.window:
			self.window.Destroy()
		self.window = None
		self._stopping = True
		self.session.close()
		if self.hidden is not None:
			self.hidden.stop()
		super().terminate()

	# Opening the window -------------------------------------------------------------------------------

	@script(
		# Translators: Describes a command in the Input Gestures dialog.
		description=_("Opens the WhatsApp window, connecting to WhatsApp Web first if needed"),
		category=SCRCAT_WHATSAPP,
		gesture="kb:NVDA+shift+w",
	)
	def script_openWindow(self, gesture) -> None:
		settings = config.conf[CONFIG_SECTION]
		if self._waitForRequiredUpdate():
			return
		# Dialogs open after this command has finished: a modal dialog opened from inside a command would hold
		# NVDA's queue, and NVDA would say nothing until the dialog closed.
		if not settings["setupDone"]:
			wx.CallAfter(self._runSetup)
			return
		# While connecting, the session is already connected but has not yet learned whether WhatsApp is
		# linked; asking it then would wrongly offer to link the phone again.
		if self.session.connected and not self._connecting:
			if self.session.linked:
				self._showWindow()
			else:
				wx.CallAfter(self._showLink)
			return
		if self._connecting:
			if time.monotonic() - self._connectingSince < CONNECT_STALE_SECONDS:
				self._showWhenStarted = True
				# Translators: Reported when the user asks again while the add-on is still connecting.
				ui.message(_("Still connecting to WhatsApp Web"))
				return
			# The last attempt never reported back; start again rather than staying stuck.
			log.warning("WhatsApp Access: the last connection attempt never finished; trying again")
			self.session.close()
		if settings["connection"] == "hidden":
			self._startHidden(announce=True, thenShow=True)
		else:
			self._connectOwnBrowser()

	@script(
		# Translators: Describes a command in the Input Gestures dialog.
		description=_(
			"Closes WhatsApp fully, after asking: no messages or calls arrive until it is opened again"
		),
		category=SCRCAT_WHATSAPP,
		gesture="kb:NVDA+alt+backspace",
	)
	def script_closeFully(self, gesture) -> None:
		# After this command has finished, as with opening the window: a dialog would hold NVDA's queue.
		wx.CallAfter(self.askToCloseFully, gui.mainFrame)

	def _waitForRequiredUpdate(self) -> bool:
		"""When a required update is not installed yet, say so and offer it. Returns whether one is."""
		if not updateCheck.isUpdateRequired():
			return False
		# Translators: Said when the user opens WhatsApp but a required update of the add-on is not installed.
		ui.message(_("WhatsApp Access must be updated before WhatsApp can be used again"))
		wx.CallAfter(updateCheck.offerRequired)
		return True

	def _requiredUpdateFound(self) -> None:
		"""A required update was found: WhatsApp stops until it is installed, except during a call, which
		goes on; WhatsApp then stays closed when it is opened next."""
		if self.calls.inCall or not self.isRunning():
			return
		self.disconnectForChange()
		self._connecting = False

	def isRunning(self) -> bool:
		return self.session.connected or self._connecting or bool(self.hidden and self.hidden.running)

	def askToCloseFully(self, parent: wx.Window) -> None:
		"""Explain what closing WhatsApp means, then close it if the user says so."""
		if not self.isRunning():
			# Translators: Said when the user asks to close WhatsApp but it is not running.
			ui.message(_("WhatsApp is not running. NVDA+Shift+W opens it"))
			return
		if self._closeDialog:
			# Already asking: bring that question back rather than asking twice.
			self._closeDialog.Raise()
			return
		dialog = self._closeDialog = CloseFullyDialog(parent)
		if parent is gui.mainFrame:
			gui.mainFrame.prePopup()
		try:
			answer = dialog.ShowModal()
		finally:
			self._closeDialog = None
			dialog.Destroy()
			if parent is gui.mainFrame:
				gui.mainFrame.postPopup()
		if answer == wx.ID_OK:
			self.closeFully()

	def closeFully(self) -> None:
		"""Stop WhatsApp on this computer: the window, the connection and the hidden browser. The login stays."""
		sounds.stopRing()
		self.disconnectForChange()
		self._connecting = False
		# Translators: Said after WhatsApp was closed fully.
		ui.message(_("WhatsApp closed. NVDA+Shift+W opens it again"))

	@script(
		# Translators: Describes a command in the Input Gestures dialog.
		description=_("Answers a WhatsApp call, or shows the window of the call in progress"),
		category=SCRCAT_WHATSAPP,
		gesture="kb:NVDA+alt+a",
	)
	def script_answerCall(self, gesture) -> None:
		if not self.calls.answerOrShow():
			# Translators: Reported when there is no WhatsApp call to answer or show.
			ui.message(_("No WhatsApp call"))

	@script(
		# Translators: Describes a command in the Input Gestures dialog.
		description=_("Turns the microphone off or on again during a WhatsApp call, from any program"),
		category=SCRCAT_WHATSAPP,
		gesture="kb:NVDA+alt+m",
	)
	def script_toggleCallMute(self, gesture) -> None:
		if not self.calls.inCall:
			# Translators: Said when the user asks to mute the microphone but no call is going on.
			ui.message(_("Not in a call"))
			return
		self.calls.toggleMute()

	@script(
		# Translators: Describes a command in the Input Gestures dialog.
		description=_("Declines a ringing WhatsApp call, or ends the call in progress"),
		category=SCRCAT_WHATSAPP,
		gesture="kb:NVDA+alt+h",
	)
	def script_hangUp(self, gesture) -> None:
		if not self.calls.hangUp():
			# Translators: Reported when there is no WhatsApp call to decline or end.
			ui.message(_("No WhatsApp call"))

	# The first time --------------------------------------------------------------------------------------

	def _runSetup(self) -> None:
		browser = self._chooseHiddenBrowser()
		dialog = SetupDialog(gui.mainFrame, browser.name if browser else None)
		gui.mainFrame.prePopup()
		dialog.Raise()
		try:
			result = dialog.ShowModal()
			connection, startWithNVDA = dialog.connection, dialog.startBox.GetValue()
		finally:
			dialog.Destroy()
			gui.mainFrame.postPopup()
		if result != wx.ID_OK:
			return
		settings = config.conf[CONFIG_SECTION]
		settings["connection"] = connection
		settings["startWithNVDA"] = startWithNVDA
		settings["setupDone"] = True
		wx.CallAfter(self.script_openWindow, None)

	# WhatsApp in the add-on's own hidden browser -------------------------------------------------------

	def _chooseHiddenBrowser(self) -> browserLauncher.InstalledBrowser | None:
		try:
			found = browserLauncher.findBrowsers()
		except OSError:
			log.exception("WhatsApp Access: looking for browsers")
			return None
		return browserLauncher.chooseBrowser(found, config.conf[CONFIG_SECTION]["hiddenBrowser"])

	def _startHidden(self, announce: bool, thenShow: bool) -> None:
		"""Start the hidden browser and connect. announce says what happens; thenShow opens the window."""
		self._autoStartTimer = None
		if self._terminated:
			return
		if updateCheck.isUpdateRequired():
			# Not even by itself with NVDA: WhatsApp Web changed so that this version no longer works.
			if announce:
				self._waitForRequiredUpdate()
			return
		if getattr(self, "_updateInstalled", False):
			# Translators: Said when WhatsApp is asked to start after an update was installed but before NVDA
			# restarted.
			ui.message(_("WhatsApp Access was updated. Restart NVDA to open WhatsApp again"))
			return
		if self._connecting and time.monotonic() - self._connectingSince < CONNECT_STALE_SECONDS:
			# One start at a time. A second one, such as the start with NVDA firing just after NVDA+Shift+W,
			# would find the first one's connection half made and answer "needsLink", asking the user to
			# link a phone that is linked already.
			if thenShow:
				self._showWhenStarted = True
			return
		browser = self._chooseHiddenBrowser()
		if browser is None:
			if announce:
				ui.message(errorText(WhatsAppError("noChromium")))
			return
		if self.hidden is None or self.hidden.browser.path != browser.path:
			if self.hidden is not None:
				self.hidden.stop()
			self.hidden = browserLauncher.HiddenBrowser(browser, _profileDir())
		hidden = self.hidden
		self._connecting = True
		self._connectingSince = time.monotonic()
		self.session.quietWhatsAppNotifications = config.conf[CONFIG_SECTION]["replaceNotifications"]
		self.session.showNumbers = config.conf[CONFIG_SECTION]["showNumbers"]
		self._applyCallAudio(connect=False)
		if announce:
			# Translators: Reported while the add-on starts its hidden browser with WhatsApp.
			ui.message(_("Starting WhatsApp…"))
		options = HiddenOptions(
			browserLauncher.chromeUserAgent(browser.major),
			browserLauncher.chromeUserAgentMetadata(browser.version),
			browserLauncher.WHATSAPP_URL,
		)

		def work() -> None:
			log.info(f"WhatsApp Access: starting hidden {browser.name} {'.'.join(map(str, browser.version))}")
			self._dataMoved.join()
			if self._terminated:
				return
			try:
				try:
					target = hidden.start()
					state = self.session.connect(target, options)
				except (OSError, WhatsAppError) as e:
					# Right after NVDA reloads, the last hidden browser may still be closing and hold the
					# profile; try once more when it is gone.
					log.info(f"WhatsApp Access: first start failed ({e}); trying again")
					hidden.stop()
					time.sleep(START_RETRY_SECONDS)
					target = hidden.start()
					state = self.session.connect(target, options)
			except Exception as e:  # noqa: BLE001 - reported to the user
				if isinstance(e, WhatsAppError):
					log.info(f"WhatsApp Access: could not start: {e}")
				else:
					log.exception("WhatsApp Access: starting the hidden browser")
				wx.CallAfter(self._connectFailed, e, browser.name, announce)
				return
			log.info(f"WhatsApp Access: hidden browser connected, {state}")
			if self._terminated:
				# NVDA stopped the plugin while the browser started; it must not stay behind.
				self.session.close()
				hidden.stop()
				return
			wx.CallAfter(self._hiddenStarted, state, thenShow)

		threading.Thread(target=work, name="whatsAppAccess.hidden", daemon=True).start()

	def _hiddenStarted(self, state: str, thenShow: bool) -> None:
		self._connecting = False
		thenShow = thenShow or self._showWhenStarted
		self._showWhenStarted = False
		if self._terminated:
			return
		self._sayMissingFeatures()
		if state == "needsLink":
			# At NVDA's start nothing is said; the user links it when they first open WhatsApp.
			if thenShow:
				self._showLink()
		elif thenShow:
			self._showWindow()

	def _showLink(self) -> None:
		dialog = LinkDialog(
			gui.mainFrame,
			self.session.requestLinkCode,
			self.session.waitUntilLinked,
			lambda error: errorText(error, self.session.browserName),
		)
		gui.mainFrame.prePopup()
		dialog.Raise()
		try:
			result = dialog.ShowModal()
		finally:
			dialog.Destroy()
			gui.mainFrame.postPopup()
		if result == wx.ID_OK:
			self._showWindow()

	def _restartHidden(self) -> None:
		"""The hidden browser stopped by itself: start it again, a few times at most."""
		now = time.monotonic()
		self._restarts = [t for t in self._restarts if now - t < RESTART_WINDOW_SECONDS] + [now]
		if len(self._restarts) > MAX_RESTARTS:
			# Translators: Reported when the hidden browser keeps stopping and the add-on gives up.
			ui.message(_("WhatsApp keeps stopping. Press NVDA+Shift+W to start it again."))
			return
		# Translators: Reported when the hidden browser stopped and the add-on starts it again.
		ui.message(_("WhatsApp stopped. Starting it again…"))
		self._startHidden(announce=False, thenShow=False)

	def _applyCallAudio(self, connect: bool = True) -> None:
		"""Give WhatsApp the chosen microphone and sound processing for calls."""
		settings = config.conf[CONFIG_SECTION]
		microphone, processing = settings["microphone"], settings["callProcessing"]
		speaker = settings["speaker"]
		self.session.callVolume = int(settings["callVolume"])
		if not connect:
			self.session.callAudio = (microphone, processing)
			self.session.speaker = speaker
			return

		def apply() -> None:
			try:
				self.session.setCallAudio(microphone, processing, speaker)
				self.session.setCallVolume(self.session.callVolume)
			except WhatsAppError as e:
				log.debugWarning(f"WhatsApp Access: call audio: {e}")

		threading.Thread(target=apply, name="whatsAppAccess.callAudio", daemon=True).start()

	def disconnectForChange(self) -> None:
		"""The connection settings changed: drop the current connection; the next one uses the new way."""
		self._stopping = True
		self.calls.connectionGone()
		if self.window:
			self.window.Close()
		self.session.close()
		if self.hidden is not None:
			self.hidden.stop()
			self.hidden = None
		self._stopping = False

	def unlink(self) -> None:
		"""Log out of WhatsApp and delete the hidden browser's profile with everything WhatsApp kept."""

		def work() -> None:
			self._dataMoved.join()
			loggedOut = True
			if self.session.connected and self.session.linked:
				try:
					self.session.logout()
				except WhatsAppError as e:
					loggedOut = False
					log.debugWarning(f"WhatsApp Access: logout: {e}")
			self._stopping = True
			self.session.close()
			if self.hidden is not None:
				self.hidden.stop()
			shutil.rmtree(_profileDir(), ignore_errors=True)
			dataFolder.clearTempMedia()
			removed = not os.path.exists(_profileDir())
			self._stopping = False
			# Say what really happened: the user relies on it to know whether this computer can still read.
			if not removed:
				# Translators: Reported when unlinking could not remove all of WhatsApp's data.
				text = _(
					"Some of WhatsApp's data on this computer could not be removed. Restart NVDA, then unlink again."
				)
			elif not loggedOut:
				# Translators: Reported when the data was removed but WhatsApp could not be told of the unlinking.
				text = _(
					"WhatsApp's data was removed from this computer, but WhatsApp could not be told. "
					"Remove this computer under Linked devices on your phone."
				)
			else:
				# Translators: Reported after WhatsApp was unlinked and its data removed from this computer.
				text = _("This computer was unlinked from WhatsApp, and its data was removed.")
			wx.CallAfter(ui.message, text)

		threading.Thread(target=work, name="whatsAppAccess.unlink", daemon=True).start()

	# WhatsApp Web in the user's own browser -----------------------------------------------------------

	def _connectOwnBrowser(self) -> None:
		browsers = self.session.debuggableBrowsers()
		if not browsers:
			ui.message(errorText(WhatsAppError("noBrowser")))
			return
		target = browsers[0]
		self._connecting = True
		self._connectingSince = time.monotonic()
		self.session.quietWhatsAppNotifications = config.conf[CONFIG_SECTION]["replaceNotifications"]
		self.session.showNumbers = config.conf[CONFIG_SECTION]["showNumbers"]
		self._applyCallAudio(connect=False)
		ui.message(
			# Translators: Reported when the add-on starts connecting. The browser then asks the user.
			_(
				"Connecting to WhatsApp Web in {browser}. If {browser} asks whether to allow remote debugging, "
				"choose Allow: press Shift+Tab, then Enter."
			).format(browser=target.browser.name)
		)

		def connect() -> None:
			log.info(f"WhatsApp Access: connecting to {target.browser.name} on port {target.port}")
			try:
				state = self.session.connect(target)
			except Exception as e:  # noqa: BLE001 - reported to the user
				if isinstance(e, WhatsAppError):
					log.info(f"WhatsApp Access: could not connect: {e}")
				else:
					log.exception("WhatsApp Access: connecting")
				wx.CallAfter(self._connectFailed, e, target.browser.name)
				return
			log.info(f"WhatsApp Access: connected, {state}")
			if state == "needsLink":
				wx.CallAfter(self._connectFailed, WhatsAppError("loggedOut"), target.browser.name)
				return
			wx.CallAfter(self._connected)

		threading.Thread(target=connect, name="whatsAppAccess.connect", daemon=True).start()

	def _connectFailed(self, error: Exception, browserName: str, announce: bool = True) -> None:
		self._connecting = False
		# The user asked for the window while it was starting, so they want to hear why it failed.
		announce = announce or self._showWhenStarted
		self._showWhenStarted = False
		if announce:
			ui.message(errorText(error, browserName))

	def _connected(self) -> None:
		self._connecting = False
		if self._terminated:
			return
		self._sayMissingFeatures()
		self._showWindow()

	def _sayMissingFeatures(self) -> None:
		"""Once per NVDA start: what the add-on cannot do since WhatsApp changed, so silence makes sense."""
		missing = [entry.split(":", 1)[0] for entry in self.session.missingFeatures]
		if not missing or self._saidMissingFeatures:
			return
		self._saidMissingFeatures = True
		names = missingFeatureNames()
		ui.message(
			# Translators: Said after connecting when a WhatsApp update stopped some of the add-on's
			# features from working. {features} lists them, such as "reactions, calls".
			_("WhatsApp has changed, so these are off until the add-on is updated: {features}").format(
				features=", ".join(names.get(name, name) for name in missing)
			)
		)

	def _showWindow(self) -> None:
		if self.window is None:
			self.window = ChatWindow(gui.mainFrame, self.session, self._windowClosed)
			self.window.calls = self.calls
			self.calls.onChange = self._callChanged
			self.window.onCallChanged()
			gui.mainFrame.prePopup()
			self.window.Show()
			gui.mainFrame.postPopup()
			self.window.refreshChats(focus=True)
		else:
			self.window.Raise()
			self.window.Show()
		self.window.SetFocus()

	def _windowClosed(self) -> None:
		self.window = None

	# Events from WhatsApp, on the connection's thread -------------------------------------------------

	def _onEvent(self, event: dict) -> None:
		wx.CallAfter(self._handleEvent, event)

	def _onDisconnect(self) -> None:
		wx.CallAfter(self._disconnected)

	def _disconnected(self) -> None:
		# A call cannot outlive the connection; WhatsApp will not say it ended.
		self.calls.connectionGone()
		if self.window:
			self.window.Close()
		if self._stopping:
			return
		if config.conf[CONFIG_SECTION]["connection"] == "hidden":
			self._restartHidden()
			return
		ui.message(errorText(WhatsAppError("disconnected")))

	def _handleEvent(self, event: dict) -> None:
		kind = event.get("type")
		window = self.window
		if kind == "message":
			message, chat = event.get("message", {}), event.get("chat", {})
			inOpenChat = bool(window and window.onMessage(message, chat))
			# Meta AI's answer is said when it is finished, which comes as this event again.
			if not message.get("fromMe") and not message.get("aiWriting") and not message.get("describing"):
				settings = config.conf[CONFIG_SECTION]
				rule = notifications.loadRules(settings["chatRules"]).get(chat.get("id", ""))
				decision = notifications.decide(
					rule,
					chat,
					inOpenChat,
					settings["announce"],
					settings["personalSound"],
					settings["groupSound"],
					settings["readContent"],
				)
				if decision.announce:
					if decision.sound:
						sounds.play(decision.sound)
					ui.message(
						messageText.announcement(
							message,
							chat.get("title", ""),
							chat.get("isGroup", False),
							inOpenChat,
							decision.withContent,
						)
					)
		elif kind == "chatsChanged":
			if window and window.tabs.IsShown():
				window.refreshChats()
		elif kind == "ack" and window:
			window.onAck(event.get("messageId", ""), event.get("ack", 0))
		elif kind == "presence" and window:
			window.onPresence(event.get("chatId", ""), event.get("presence"))
		elif kind == "edited" and window:
			window.onEdited(event.get("message") or {})
		elif kind == "reactions" and window:
			window.onReactions(event.get("messageId", ""), event.get("reactions") or [])
		elif kind == "call":
			self.calls.onCall(event.get("call"))
		elif kind == "playbackEnded" and window:
			window.onPlaybackEnded(event.get("messageId"))
		elif kind == "recordingLimit" and window:
			window.onRecordingLimit()
		elif kind == "connection":
			self._onConnection(event.get("state") or {})

	def _onConnection(self, state: dict) -> None:
		"""Says when WhatsApp loses its connection and when it is back, so a message that waits makes sense.

		Short drops are common; only one that lasts a few seconds is said."""
		info = state.get("info", "")
		lost = info in ("OFFLINE", "CONNECTING", "OPENING") or not state.get("online", True)
		if lost and not self._connectionLost:
			self._connectionLost = True
			if self._lostTimer is None:
				self._lostTimer = wx.CallLater(CONNECTION_LOST_DELAY_MS, self._sayConnectionLost)
		elif info == "NORMAL" and self._connectionLost:
			self._connectionLost = False
			if self._lostTimer is not None:
				self._lostTimer.Stop()
				self._lostTimer = None
			if self._saidLost:
				self._saidLost = False
				# Translators: Said when WhatsApp is connected again after losing its connection.
				ui.message(_("WhatsApp is connected again"))

	def _sayConnectionLost(self) -> None:
		self._lostTimer = None
		if self._connectionLost:
			self._saidLost = True
			# Translators: Said when WhatsApp loses its connection; messages wait until it is back.
			ui.message(_("WhatsApp lost its connection. Messages are sent when it is back."))

	def _shouldAnnounce(self, chat: dict, inOpenChat: bool) -> bool:
		mode = config.conf[CONFIG_SECTION]["announce"]
		if mode == "off":
			return False
		if inOpenChat:
			return True
		if chat.get("muted") or mode == "openChat":
			return False
		if mode == "personal":
			return not chat.get("isGroup")
		return True


def missingFeatureNames() -> dict[str, str]:
	"""What to call each of the bridge's features when WhatsApp changed it and it is off."""
	return {
		# Translators: A feature that is off because WhatsApp changed: hearing about edited messages.
		"edits": _("edited messages"),
		# Translators: A feature that is off because WhatsApp changed: sent, delivered and read ticks.
		"receipts": _("delivered and read"),
		# Translators: A feature that is off because WhatsApp changed: reactions to messages.
		"reactions": _("reactions"),
		# Translators: A feature that is off because WhatsApp changed: choosing the microphone.
		"microphone": _("the chosen microphone"),
		# Translators: A feature that is off because WhatsApp changed: hearing about calls.
		"calls": _("calls"),
		# Translators: A feature that is off because WhatsApp changed: hearing when the connection drops.
		"connection": _("connection lost and back"),
		# Translators: A feature that is off because WhatsApp changed: the chat list updating by itself.
		"chatList": _("the chat list updating by itself"),
	}


def soundNames() -> list[str]:
	return [
		# Translators: A sound for new messages.
		_("Classic"),
		# Translators: A sound for new messages.
		_("Bell"),
		# Translators: A sound for new messages.
		_("Kalimba"),
		# Translators: A sound for new messages.
		_("Flute"),
		# Translators: No sound for new messages.
		_("None"),
	]


def openOwnSoundsFolder() -> None:
	"""Open the folder whose WAV files replace the add-on's sounds of the same name, making it first."""
	folder = sounds.ownSoundsFolder()
	try:
		os.makedirs(folder, exist_ok=True)
		names = sorted(
			os.path.splitext(name)[0] for name in os.listdir(sounds.SOUNDS_DIR) if name.endswith(".wav")
		)
		with open(os.path.join(folder, "sound names.txt"), "w", encoding="utf-8") as file:
			file.write(
				# Translators: The text file in the folder for the user's own sounds.
				_(
					"Put WAV files here named as the add-on's sounds below, such as sent.wav. "
					"Each one plays instead of the add-on's sound; the others stay as they are."
				)
				+ "\n\n"
				+ "\n".join(f"{name}.wav" for name in names)
				+ "\n"
			)
		os.startfile(folder)
	except OSError as e:
		log.debugWarning(f"WhatsApp Access: own sounds folder: {e}")
		# Translators: Said when the folder for the user's own sounds could not be opened.
		ui.message(_("The folder for your own sounds could not be opened"))


class CloseFullyDialog(wx.Dialog):
	"""What closing WhatsApp means, to read before choosing Close WhatsApp or Cancel."""

	def __init__(self, parent: wx.Window) -> None:
		# Translators: The title of the dialog that asks before closing WhatsApp fully.
		super().__init__(parent, title=_("Close WhatsApp"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		text = "\n".join(
			[
				# Translators: In the dialog before closing WhatsApp fully: what it means, one point per line.
				_("Closing WhatsApp stops it on this computer until you open it again:"),
				# Translators: In the dialog before closing WhatsApp fully.
				_("- No new messages, calls or notifications reach you here. Your phone still gets them."),
				# Translators: In the dialog before closing WhatsApp fully.
				_("- A call going on now ends."),
				# Translators: In the dialog before closing WhatsApp fully.
				_("- The hidden browser stops, and the memory it used is given back."),
				# Translators: In the dialog before closing WhatsApp fully.
				_("- You stay linked: NVDA+Shift+W opens WhatsApp again, without linking the phone."),
				# Translators: In the dialog before closing WhatsApp fully.
				_("- If WhatsApp starts with NVDA, it starts again the next time NVDA starts."),
			]
		)
		# Translators: The label of the explanation in the dialog before closing WhatsApp fully.
		sizer.Add(wx.StaticText(self, label=_("What happens:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
		box = wx.TextCtrl(
			self, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(520, 140)
		)
		sizer.Add(box, 1, wx.EXPAND | wx.ALL, 10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: The button that closes WhatsApp fully.
		closeButton = wx.Button(self, wx.ID_OK, label=_("&Close WhatsApp"))
		cancelButton = wx.Button(self, wx.ID_CANCEL)
		buttons.Add(closeButton, 0, wx.RIGHT, 6)
		buttons.Add(cancelButton)
		sizer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
		self.SetSizerAndFit(sizer)
		# Cancel is the safe choice for Enter.
		cancelButton.SetDefault()
		self.CentreOnScreen()
		box.SetFocus()


class SoundSetting:
	"""A choice of the add-on's sounds, None, or a WAV file of the user's own, with a button that picks
	the file. Moving through the choices plays each sound, so the user hears what they choose."""

	def __init__(
		self,
		panel: wx.Window,
		helper: "gui.guiHelper.BoxSizerHelper",
		label: str,
		fileLabel: str,
		builtIn: list[tuple[str, str]],
		value: str,
	) -> None:
		self.panel = panel
		self.builtIn = builtIn
		self.value = value
		self.choice = helper.addLabeledControl(label, wx.Choice, choices=[])
		row = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button after a choice of sound: plays it, or stops it if it is playing.
		self.playButton = wx.Button(panel, label=_("Play"))
		self.playButton.Bind(wx.EVT_BUTTON, lambda evt: self._playOrStop())
		self.button = wx.Button(panel, label=fileLabel)
		self.button.Bind(wx.EVT_BUTTON, lambda evt: self._chooseFile())
		row.Add(self.playButton, 0, wx.RIGHT, 6)
		row.Add(self.button)
		helper.addItem(row)
		self.choice.Bind(wx.EVT_CHOICE, lambda evt: self._chosen())
		self._fill()

	def _fill(self) -> None:
		self.items = list(self.builtIn)
		if os.path.isabs(self.value) and self.value not in [key for key, label in self.builtIn]:
			# Translators: In a choice of sounds: the WAV file the user picked, by its name.
			self.items.append((self.value, _("Your file: {name}").format(name=os.path.basename(self.value))))
		self.choice.Set([label for key, label in self.items])
		keys = [key for key, label in self.items]
		self.choice.SetSelection(keys.index(self.value) if self.value in keys else 0)
		if self.value not in keys:
			self.value = keys[0]

	def _chosen(self) -> None:
		self.value = self.items[self.choice.GetSelection()][0]
		self._preview()

	def _preview(self) -> None:
		sounds.preview(self.value)

	def _playOrStop(self) -> None:
		if sounds.previewPlaying():
			sounds.stopRing()
			# Translators: Said when the user stops a sound playing in the settings.
			ui.message(_("Stopped"))
		elif self.value == "none":
			# Translators: Said when the user presses Play while no sound is chosen.
			ui.message(_("No sound chosen"))
		else:
			self._preview()

	def _chooseFile(self) -> None:
		dialog = wx.FileDialog(
			self.panel,
			# Translators: The title of the file picker for a chat's own sound.
			_("Choose a WAV file"),
			wildcard="WAV (*.wav)|*.wav",
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			self.value = dialog.GetPath()
		finally:
			dialog.Destroy()
		self._fill()
		self.choice.SetFocus()
		self._preview()


class PositionSlider(NVDAObject):
	"""The voice message position slider: NVDA reads Windows sliders as a percentage; this one says the time,
	such as "12 sec of 45 sec"."""

	plugin: "GlobalPlugin | None" = None

	def _get_value(self) -> str:
		window = self.plugin.window if self.plugin else None
		if not window:
			return super().value
		return window.positionText()


class WhatsAppSettingsPanel(SettingsPanel):
	# Translators: The title of this add-on's panel in NVDA's settings dialog.
	title = _("WhatsApp Access")
	plugin: GlobalPlugin | None = None

	def makeSettings(self, settingsSizer: wx.BoxSizer) -> None:
		settings = config.conf[CONFIG_SECTION]
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.connectionChoice = helper.addLabeledControl(
			# Translators: The label of a choice in this add-on's settings: how to reach WhatsApp.
			_("&Connect to WhatsApp through:"),
			wx.Choice,
			choices=[
				# Translators: A way to reach WhatsApp, in this add-on's settings.
				_("A hidden browser of the add-on's own"),
				# Translators: A way to reach WhatsApp, in this add-on's settings.
				_("WhatsApp Web in your own browser"),
			],
		)
		self.connectionChoice.SetSelection(0 if settings["connection"] == "hidden" else 1)
		self.startBox = helper.addItem(
			# Translators: A checkbox in this add-on's settings.
			wx.CheckBox(self, label=_("Start WhatsApp &when NVDA starts (hidden browser only)"))
		)
		self.startBox.SetValue(settings["startWithNVDA"])
		try:
			self.installed = browserLauncher.findBrowsers()
		except OSError:
			self.installed = []
		usable = [b for b in self.installed if b.major >= browserLauncher.MINIMUM_MAJOR_VERSION]
		self.browserKeys = ["auto"] + [b.key for b in usable]
		browserLabels = [
			# Translators: The first choice of browser for the hidden mode.
			_("Automatic (Brave first)")
		] + [f"{b.name} {b.major}" for b in usable]
		self.browserChoice = helper.addLabeledControl(
			# Translators: The label of the choice of browser that runs WhatsApp hidden.
			_("&Browser for the hidden mode:"),
			wx.Choice,
			choices=browserLabels,
		)
		current = settings["hiddenBrowser"]
		self.browserChoice.SetSelection(self.browserKeys.index(current) if current in self.browserKeys else 0)
		self.unlinkButton = helper.addItem(
			# Translators: A button that logs out of WhatsApp in the hidden browser and removes its data.
			wx.Button(self, label=_("Unlin&k this computer and remove its WhatsApp data…"))
		)
		self.unlinkButton.Bind(wx.EVT_BUTTON, self._onUnlink)
		self.closeFullyButton = helper.addItem(
			# Translators: A button in this add-on's settings: stops WhatsApp on this computer, after explaining.
			wx.Button(self, label=_("Close Wh&atsApp fully (NVDA+Alt+Backspace)…"))
		)
		self.closeFullyButton.Bind(
			wx.EVT_BUTTON, lambda evt: self.plugin and self.plugin.askToCloseFully(self)
		)
		announceLabels = (
			# Translators: A choice for which new messages NVDA reads out.
			_("All chats that are not muted"),
			# Translators: A choice for which new messages NVDA reads out.
			_("Personal chats only, not groups"),
			# Translators: A choice for which new messages NVDA reads out.
			_("Only the chat open in the WhatsApp window"),
			# Translators: A choice for which new messages NVDA reads out.
			_("None"),
		)
		self.announceChoice = helper.addLabeledControl(
			# Translators: The label of a choice in this add-on's settings.
			_("Read out new &messages from:"),
			wx.Choice,
			choices=list(announceLabels),
		)
		self.announceChoice.SetSelection(ANNOUNCE_CHOICES.index(settings["announce"]))
		# The lists start with the saved choice; WhatsApp is asked for every device in the background, since
		# it can take up to half a minute to answer and NVDA would say nothing meanwhile.
		self.microphones: list[str] = []
		self.microphoneChoice = helper.addLabeledControl(
			# Translators: The label of the list of microphones for voice notes.
			_("Micro&phone for voice notes and calls:"),
			wx.Choice,
			choices=[],
		)
		self._fillDevices(
			self.microphoneChoice, self.microphones, [], settings["microphone"], microphone=True
		)
		self.speakers: list[str] = []
		self.speakerChoice = helper.addLabeledControl(
			# Translators: The label of the list of speakers and headphones in this add-on's settings.
			_("Sp&eaker for calls, voice notes and statuses:"),
			wx.Choice,
			choices=[],
		)
		self._fillDevices(self.speakerChoice, self.speakers, [], settings["speaker"], microphone=False)
		plugin = self.plugin
		if plugin is not None and plugin.session.connected:
			session = plugin.session

			def listDevices() -> None:
				microphones: list[str] = []
				speakers: list[str] = []
				try:
					microphones = [microphone["label"] for microphone in session.microphones()]
					speakers = list(session.audioDevices().get("speakers", []))
				except WhatsAppError as e:
					log.debugWarning(f"WhatsApp Access: could not list microphones and speakers: {e}")
				wx.CallAfter(self._gotDevices, microphones, speakers)

			threading.Thread(target=listDevices, name="whatsAppAccess.listDevices", daemon=True).start()
		self.callProcessingChoice = helper.addLabeledControl(
			# Translators: The label of a choice in this add-on's settings: sound processing during calls.
			_("Sound processing in ca&lls:"),
			wx.Choice,
			choices=[
				# Translators: A choice of sound processing during calls.
				_("WhatsApp's own: echo cancellation and noise suppression (safest with speakers)"),
				# Translators: A choice of sound processing during calls.
				_("Echo cancellation only: more natural, still fine with speakers"),
				# Translators: A choice of sound processing during calls.
				_("None: clearest, for headphones only"),
			],
		)
		self.callProcessingChoice.SetSelection(
			("whatsapp", "echoOnly", "none").index(settings["callProcessing"])
		)
		self.replaceBox = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: A checkbox in this add-on's settings.
				label=_("Read out new messages &instead of WhatsApp's notifications and sound"),
			)
		)
		self.replaceBox.SetValue(settings["replaceNotifications"])
		# Translators: A checkbox in this add-on's settings.
		self.soundsBox = helper.addItem(wx.CheckBox(self, label=_("Play the add-on's so&unds")))
		self.soundsBox.SetValue(settings["sounds"])
		messageSounds = list(zip([*notifications.NOTIFICATION_SOUNDS, "none"], soundNames(), strict=True))
		self.personalSound = SoundSetting(
			self,
			helper,
			# Translators: The label of the choice of sound for new messages in personal chats.
			_("Sound for new messages in pe&rsonal chats:"),
			# Translators: A button after the choice of sound for personal chats.
			_("Choose a WAV file for personal chats…"),
			messageSounds,
			settings["personalSound"],
		)
		self.groupSound = SoundSetting(
			self,
			helper,
			# Translators: The label of the choice of sound for new messages in groups.
			_("Sound for new messages in &groups:"),
			# Translators: A button after the choice of sound for groups.
			_("Choose a WAV file for groups…"),
			messageSounds,
			settings["groupSound"],
		)
		self.ringSound = SoundSetting(
			self,
			helper,
			# Translators: The label of the choice of ringtone for incoming calls.
			_("Ri&ngtone for calls:"),
			# Translators: A button after the choice of ringtone.
			_("Choose a WAV file for the ringtone…"),
			[
				# Translators: The add-on's own ringtone.
				("ring", _("Ring")),
				# Translators: No ringtone: NVDA only says who is calling.
				("none", _("None, NVDA only says who calls")),
				# Translators: One of Windows' own ringtones in the choice of ringtone, such as "Windows: Ring 01".
				*[(path, _("Windows: {name}").format(name=name)) for path, name in sounds.windowsRingtones()],
			],
			settings["ringSound"],
		)
		self.ownSoundsButton = helper.addItem(
			# Translators: A button in this add-on's settings: opens the folder for the user's own sounds.
			wx.Button(self, label=_("&Open the folder for your own sounds"))
		)
		self.ownSoundsButton.Bind(wx.EVT_BUTTON, lambda evt: openOwnSoundsFolder())
		self.volumeSpins = {}
		for key, label in (
			# Translators: The label of a volume in this add-on's settings, in percent.
			("notificationVolume", _("Volume of new message sounds and the ring, in percent:")),
			# Translators: The label of a volume in this add-on's settings, in percent.
			("effectsVolume", _("Volume of other sounds (sent, recording, selecting), in percent:")),
			# Translators: The label of a volume in this add-on's settings, in percent.
			("voiceVolume", _("Volume of voice notes and videos in chats, in percent:")),
			# Translators: The label of a volume in this add-on's settings, in percent.
			("statusVolume", _("Volume of statuses, in percent:")),
			# Translators: The label of a volume in this add-on's settings, in percent.
			("callVolume", _("Volume of the other person in calls, in percent:")),
		):
			self.volumeSpins[key] = helper.addLabeledControl(
				label, nvdaControls.SelectOnFocusSpinCtrl, min=0, max=100, initial=settings[key]
			)
		self._volumesShown = {key: spin.GetValue() for key, spin in self.volumeSpins.items()}
		self.contentBox = helper.addItem(
			# Translators: A checkbox in this add-on's settings.
			wx.CheckBox(self, label=_("Read out what new messages say, not only who they are &from"))
		)
		self.contentBox.SetValue(settings["readContent"])
		self.numbersBox = helper.addItem(
			# Translators: A checkbox in this add-on's settings. People who are not in the contacts are named with "~"
			# and the name they chose; checked, their phone number comes first, such as "+62812… ~Budi".
			wx.CheckBox(self, label=_("Show the phone number of people who are not in your &contacts"))
		)
		self.numbersBox.SetValue(settings["showNumbers"])
		self.describeBox = helper.addLabeledControl(
			# Translators: The label of the box in this add-on's settings with what Meta AI is asked when Alt+P
			# sends it a photo to describe. The user can write their own question there.
			_("&Question Meta AI is asked to describe a photo (Alt+P):"),
			wx.TextCtrl,
			value=messageText.describeQuestion(settings["describeQuestion"]),
			style=wx.TE_MULTILINE,
			size=(-1, 70),
		)
		self.hintsBox = helper.addItem(
			# Translators: A checkbox in this add-on's settings: say which keys to press after messages.
			wx.CheckBox(self, label=_("Use &hints, such as which keys send or throw away a voice note"))
		)
		self.hintsBox.SetValue(settings["hints"])
		self.sayNextVoiceBox = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: A checkbox in this add-on's settings: voice messages play one after another, and
				# the messages list moves to the next one; this says whether NVDA reads it out too.
				label=_("Read out the next voice message when voice messages play one after another"),
			)
		)
		self.sayNextVoiceBox.SetValue(settings["sayNextVoiceMessage"])
		# Ctrl+T in a chat: messages into the user's language, what they write into the other one.
		from .chatWindow import languageName
		from .translate import LANGUAGES

		languages = sorted(LANGUAGES, key=lambda code: languageName(code).lower())
		self.messagesLanguages = ["", *languages]
		self.messagesLanguageChoice = helper.addLabeledControl(
			# Translators: The label of a choice in this add-on's settings: Ctrl+T on a message translates it
			# into this language.
			_("&Translate messages into (Ctrl+T):"),
			wx.Choice,
			choices=[
				# Translators: The first choice of language to translate messages into: NVDA's own.
				_("NVDA's language"),
				*(languageName(code) for code in languages),
			],
		)
		chosen = settings["translateMessagesTo"]
		self.messagesLanguageChoice.SetSelection(
			self.messagesLanguages.index(chosen) if chosen in self.messagesLanguages else 0
		)
		self.myLanguages = languages
		self.myLanguageChoice = helper.addLabeledControl(
			# Translators: The label of a choice in this add-on's settings: Ctrl+T in the message box translates
			# what the user wrote into this language.
			_("Translate what I write into (Ctrl+T in the message box):"),
			wx.Choice,
			choices=[languageName(code) for code in languages],
		)
		mine = settings["translateMyTextTo"]
		self.myLanguageChoice.SetSelection(
			languages.index(mine) if mine in languages else languages.index("en")
		)
		speedLabels = ("1x", "1.5x", "2x")
		self.speedChoice = helper.addLabeledControl(
			# Translators: The label of a choice in this add-on's settings: how fast voice messages play.
			_("Voice message pla&yback speed (Ctrl+S in a chat):"),
			wx.Choice,
			choices=list(speedLabels),
		)
		self.speedChoice.SetSelection(("1", "1.5", "2").index(settings["playbackSpeed"]))
		self.stereoBox = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: A checkbox in this add-on's settings.
				label=_(
					"Record voice notes in &stereo when the microphone has two channels (iPhones cannot play them)"
				),
			)
		)
		self.stereoBox.SetValue(settings["stereoVoiceNotes"])
		self.rawBox = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: A checkbox in this add-on's settings.
				label=_(
					"Use the microphone's own sound: no echo cancellation, noise suppression or automatic volume"
				),
			)
		)
		self.rawBox.SetValue(settings["rawMicrophone"])
		self.kbpsSpin = helper.addLabeledControl(
			# Translators: The label of a number in this add-on's settings: the voice note's quality.
			_("Voice note &quality, in kilobits per second:"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=16,
			max=256,
			initial=settings["voiceKbps"],
		)
		if plugin is None or not plugin.session.connected:
			helper.addItem(
				wx.StaticText(
					self,
					# Translators: Shown in this add-on's settings when WhatsApp Web is not connected.
					label=_("Connect with NVDA+Shift+W to choose from all your microphones."),
				)
			)

		self.checkUpdatesBox = helper.addItem(
			wx.CheckBox(
				self,
				label=_(
					# Translators: A checkbox in this add-on's settings. Required updates, needed when WhatsApp
					# Web changed, are looked for at every start whether it is checked or not.
					"Check for new versions on GitHub once a day (required updates are always looked for)"
				),
			)
		)
		self.checkUpdatesBox.SetValue(settings["checkUpdates"])
		# Translators: A button in this add-on's settings that looks for a new version now.
		checkNow = helper.addItem(wx.Button(self, label=_("Check for updates now")))
		checkNow.Bind(wx.EVT_BUTTON, lambda evt: updateCheck.check(manual=True))

	def _fillDevices(
		self, choice: wx.Choice, keys: list[str], names: list[str], selected: str, microphone: bool
	) -> None:
		"""Fill a list of devices, keeping selected chosen even when WhatsApp does not list it now.

		:param choice: The list.
		:param keys: Filled with what is saved for each item: "" for the default, else the device's name.
		:param names: The devices WhatsApp lists.
		:param selected: The device to choose.
		:param microphone: Whether these are microphones, which decides what the default is called.
		"""
		keys[:] = ["", *names]
		if selected and selected not in keys:
			keys.append(selected)
		default = (
			# Translators: The first choice in the list of microphones: whatever the browser uses.
			_("Browser default")
			if microphone
			# Translators: The first choice in the list of speakers: the one Windows uses.
			else _("Windows default")
		)
		choice.Set([default, *keys[1:]])
		choice.SetSelection(keys.index(selected) if selected in keys else 0)

	def _gotDevices(self, microphones: list[str], speakers: list[str]) -> None:
		if not self:
			# The settings were closed before WhatsApp answered.
			return
		for choice, keys, names, isMicrophone in (
			(self.microphoneChoice, self.microphones, microphones, True),
			(self.speakerChoice, self.speakers, speakers, False),
		):
			# What the user picked meanwhile stays picked.
			current = keys[choice.GetSelection()] if 0 <= choice.GetSelection() < len(keys) else ""
			self._fillDevices(choice, keys, names, current, isMicrophone)

	def _onUnlink(self, evt: wx.CommandEvent) -> None:
		answer = askYesNo(
			self,
			_(
				# Translators: Asked before unlinking the hidden browser from WhatsApp.
				"Log out of WhatsApp on this computer and remove the chats it keeps here? Your phone and your "
				"other linked devices keep everything. To use the hidden browser again, you link it again."
			),
			# Translators: The title of the question before unlinking.
			_("Unlink WhatsApp"),
		)
		if answer and self.plugin is not None:
			self.plugin.unlink()

	def onDiscard(self) -> None:
		# A sound heard with Play or while choosing stops with the settings.
		sounds.stopRing()

	def onSave(self) -> None:
		sounds.stopRing()
		settings = config.conf[CONFIG_SECTION]
		connection = "hidden" if self.connectionChoice.GetSelection() == 0 else "ownBrowser"
		changed = connection != settings["connection"] or (
			self.browserKeys[self.browserChoice.GetSelection()] != settings["hiddenBrowser"]
		)
		settings["connection"] = connection
		settings["startWithNVDA"] = self.startBox.GetValue()
		settings["hiddenBrowser"] = self.browserKeys[self.browserChoice.GetSelection()]
		settings["setupDone"] = True
		settings["checkUpdates"] = self.checkUpdatesBox.GetValue()
		# Before the call audio is applied, which includes the call volume.
		for key, spin in self.volumeSpins.items():
			# Only volumes changed here: F7 and F8 may have changed others since the panel opened.
			if spin.GetValue() != self._volumesShown[key]:
				settings[key] = spin.GetValue()
		# Before the call audio is applied, so a new microphone or speaker takes over at once.
		settings["microphone"] = self.microphones[self.microphoneChoice.GetSelection()]
		settings["speaker"] = self.speakers[self.speakerChoice.GetSelection()]
		settings["callProcessing"] = ("whatsapp", "echoOnly", "none")[
			self.callProcessingChoice.GetSelection()
		]
		plugin = self.plugin
		if plugin is not None:
			plugin._applyCallAudio()
		if changed and plugin is not None:
			# The next NVDA+Shift+W connects the new way.
			plugin.disconnectForChange()
		settings["announce"] = ANNOUNCE_CHOICES[self.announceChoice.GetSelection()]
		settings["stereoVoiceNotes"] = self.stereoBox.GetValue()
		settings["rawMicrophone"] = self.rawBox.GetValue()
		settings["voiceKbps"] = self.kbpsSpin.GetValue()
		settings["sounds"] = self.soundsBox.GetValue()
		settings["personalSound"] = self.personalSound.value
		settings["groupSound"] = self.groupSound.value
		settings["ringSound"] = self.ringSound.value
		settings["readContent"] = self.contentBox.GetValue()
		# The default question is kept as empty, so it follows the user's language if that changes.
		question = self.describeBox.GetValue().strip()
		settings["describeQuestion"] = "" if question == messageText.defaultDescribeQuestion() else question
		settings["hints"] = self.hintsBox.GetValue()
		settings["sayNextVoiceMessage"] = self.sayNextVoiceBox.GetValue()
		settings["translateMessagesTo"] = self.messagesLanguages[self.messagesLanguageChoice.GetSelection()]
		settings["translateMyTextTo"] = self.myLanguages[self.myLanguageChoice.GetSelection()]
		settings["playbackSpeed"] = ("1", "1.5", "2")[self.speedChoice.GetSelection()]
		replace = self.replaceBox.GetValue()
		settings["replaceNotifications"] = replace
		showNumbers = self.numbersBox.GetValue()
		settings["showNumbers"] = showNumbers
		plugin = self.plugin
		if plugin is not None:
			session = plugin.session

			def apply() -> None:
				try:
					session.setQuietNotifications(replace)
					session.setShowNumbers(showNumbers)
				except WhatsAppError as e:
					log.debugWarning(f"WhatsApp Access: could not change WhatsApp's notifications: {e}")

			threading.Thread(target=apply, name="whatsAppAccess.settings", daemon=True).start()
