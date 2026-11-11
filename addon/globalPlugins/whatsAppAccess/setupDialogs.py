# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""The first-time setup, and linking the hidden browser to the user's phone with a code."""

import threading
import time
from collections.abc import Callable

import addonHandler
import api
import ui
import wx
from logHandler import log

from .whatsApp import WhatsAppError

addonHandler.initTranslation()

# WhatsApp keeps a link code valid for a few minutes; the add-on waits that long for the phone.
LINK_WAIT_SECONDS = 300


class SetupDialog(wx.Dialog):
	"""Asked once, before the first connection: how to reach WhatsApp."""

	def __init__(self, parent: wx.Window, browserName: str | None) -> None:
		# Translators: The title of the dialog shown the first time the user opens WhatsApp Access.
		super().__init__(parent, title=_("Set up WhatsApp Access"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		hiddenLabel = (
			# Translators: The first way to reach WhatsApp, with the browser the add-on found.
			_(
				"&Hidden {browser} (recommended). WhatsApp runs in its own hidden browser, with no window. "
				"You link it once with a code on your phone. It uses about 400 to 600 MB of memory."
			).format(browser=browserName)
			if browserName
			# Translators: The first way to reach WhatsApp, when no suitable browser is installed.
			else _(
				"&Hidden browser. Needs Brave, Google Chrome or another Chromium browser, version 120 or newer. "
				"None was found on this computer."
			)
		)
		self.hiddenChoice = wx.RadioButton(self, label=hiddenLabel, style=wx.RB_GROUP)
		self.ownChoice = wx.RadioButton(
			self,
			# Translators: The second way to reach WhatsApp.
			label=_(
				"&WhatsApp Web in your own browser. Uses the WhatsApp Web tab you have open in Brave or Chrome. "
				"Your browser asks for permission each time it starts."
			),
		)
		for choice in (self.hiddenChoice, self.ownChoice):
			sizer.Add(choice, 0, wx.ALL, 6)
		self.hiddenChoice.SetValue(bool(browserName))
		self.ownChoice.SetValue(not browserName)
		self.hiddenChoice.Enable(bool(browserName))
		self.startBox = wx.CheckBox(
			self,
			# Translators: A checkbox in the setup dialog.
			label=_("&Start WhatsApp when NVDA starts, so new messages are read out"),
		)
		self.startBox.SetValue(True)
		sizer.Add(self.startBox, 0, wx.ALL, 6)
		buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
		sizer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 6)
		self.SetSizerAndFit(sizer)
		self.CentreOnScreen()
		(self.hiddenChoice if browserName else self.ownChoice).SetFocus()

	@property
	def connection(self) -> str:
		return "hidden" if self.hiddenChoice.GetValue() else "ownBrowser"


class LinkDialog(wx.Dialog):
	"""Link the hidden browser to WhatsApp with the user's phone number and an 8-character code."""

	def __init__(
		self,
		parent: wx.Window,
		requestCode: Callable[[str], str],
		waitUntilLinked: Callable[[float], bool],
		describeError: Callable[[Exception], str],
	) -> None:
		# Translators: The title of the dialog for linking WhatsApp to the user's phone.
		super().__init__(parent, title=_("Link WhatsApp"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._requestCode = requestCode
		self._waitUntilLinked = waitUntilLinked
		self._describeError = describeError
		self._waiting = False
		self._codeAt = 0.0
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(
			# Translators: The label of the box for the phone number to link.
			wx.StaticText(self, label=_("Your &phone number, with country code, such as +62 812 3456 7890:"))
		)
		self.phoneBox = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.phoneBox.Bind(wx.EVT_TEXT_ENTER, lambda evt: self._getCode())
		sizer.Add(self.phoneBox, 0, wx.EXPAND | wx.BOTTOM, 6)
		# Translators: A button that asks WhatsApp for the code to type on the phone.
		self.codeButton = wx.Button(self, label=_("&Get code"))
		self.codeButton.Bind(wx.EVT_BUTTON, lambda evt: self._getCode())
		sizer.Add(self.codeButton, 0, wx.BOTTOM, 6)
		# Translators: The label of the box showing the code to type on the phone.
		sizer.Add(wx.StaticText(self, label=_("C&ode to type on your phone:")))
		self.codeBox = wx.TextCtrl(self, style=wx.TE_READONLY)
		sizer.Add(self.codeBox, 0, wx.EXPAND | wx.BOTTOM, 6)
		# Translators: A button that copies the link code.
		self.copyButton = wx.Button(self, label=_("&Copy code"))
		self.copyButton.Bind(wx.EVT_BUTTON, lambda evt: self._copy())
		self.copyButton.Disable()
		sizer.Add(self.copyButton, 0, wx.BOTTOM, 6)
		# Translators: The label of the box that says how to use the link code on the phone.
		sizer.Add(wx.StaticText(self, label=_("How to link:")))
		help = wx.TextCtrl(
			self,
			value=_(
				# Translators: How to use the link code on the phone.
				"On your phone, open WhatsApp, then Settings, Linked devices, Link a device. Choose "
				"Link with phone number instead, and type the code. Your phone may also show a notification "
				"asking for it."
			),
			style=wx.TE_MULTILINE | wx.TE_READONLY,
			size=(480, 90),
		)
		sizer.Add(help, 0, wx.EXPAND | wx.BOTTOM, 6)
		self.status = wx.StaticText(self, label="")
		sizer.Add(self.status, 0, wx.BOTTOM, 6)
		sizer.Add(self.CreateStdDialogButtonSizer(wx.CANCEL), 0, wx.ALIGN_RIGHT)
		outer = wx.BoxSizer(wx.VERTICAL)
		outer.Add(sizer, 1, wx.EXPAND | wx.ALL, 10)
		self.SetSizerAndFit(outer)
		self.CentreOnScreen()
		self.phoneBox.SetFocus()

	def _say(self, text: str) -> None:
		self.status.SetLabel(text)
		self.Layout()
		ui.message(text)

	def _getCode(self) -> None:
		phone = self.phoneBox.GetValue().strip()
		if not phone:
			self.phoneBox.SetFocus()
			return
		self.codeButton.Disable()
		# Translators: Reported while WhatsApp makes a link code.
		self._say(_("Getting a code…"))

		def work() -> None:
			try:
				code = self._requestCode(phone)
			except Exception as e:  # noqa: BLE001 - reported to the user
				if not isinstance(e, WhatsAppError):
					log.exception("WhatsApp Access: link code")
				wx.CallAfter(self._failed, e)
				return
			wx.CallAfter(self._gotCode, code)

		threading.Thread(target=work, name="whatsAppAccess.linkCode", daemon=True).start()

	def _gotCode(self, code: str) -> None:
		if not self:
			return
		# Each new code may be typed for the whole wait again, however long the earlier one waited.
		self._codeAt = time.monotonic()
		shown = f"{code[:4]}-{code[4:]}" if len(code) == 8 else code
		self.codeBox.SetValue(shown)
		self.copyButton.Enable()
		# Translators: A button that asks for another link code.
		self.codeButton.SetLabel(_("&New code"))
		self.codeButton.Enable()
		self.codeBox.SetFocus()
		# The code letter by letter, so a screen reader says each one clearly.
		spelled = " ".join(code)
		self._say(
			# Translators: Read out when the link code is ready, spelled out letter by letter.
			_("Code: {code}. Type it on your phone. Waiting for your phone…").format(code=spelled)
		)
		if not self._waiting:
			self._waiting = True
			threading.Thread(target=self._wait, name="whatsAppAccess.linkWait", daemon=True).start()

	def _wait(self, seconds: float = LINK_WAIT_SECONDS) -> None:
		try:
			linked = self._waitUntilLinked(seconds)
		except Exception as e:  # noqa: BLE001 - reported to the user
			wx.CallAfter(self._failed, e)
			return
		finally:
			self._waiting = False
		wx.CallAfter(self._finished, linked)

	def _finished(self, linked: bool) -> None:
		if not self:
			return
		if linked:
			# Translators: Reported when the phone accepted the code and WhatsApp is linked.
			ui.message(_("Linked. Loading your chats…"))
			self.EndModal(wx.ID_OK)
			return
		remaining = LINK_WAIT_SECONDS - (time.monotonic() - self._codeAt)
		if remaining > 5 and not self._waiting:
			# The wait that just ended was for an earlier code; the newest one is still fresh.
			self._waiting = True
			threading.Thread(
				target=self._wait, args=(remaining,), name="whatsAppAccess.linkWait", daemon=True
			).start()
			return
		# Translators: Reported when the code was not typed on the phone in time.
		self._say(_("The code expired. Press New code to get another one."))

	def _failed(self, error: Exception) -> None:
		if not self:
			return
		self.codeButton.Enable()
		self._say(self._describeError(error))

	def _copy(self) -> None:
		code = self.codeBox.GetValue().replace("-", "")
		if code and api.copyToClip(code):
			# Translators: Reported after the link code was copied.
			ui.message(_("Code copied"))
