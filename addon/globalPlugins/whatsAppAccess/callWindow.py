# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Calls: what NVDA says as a call rings, connects and ends, and a small window to answer, mute and hang up."""

import threading
import time
from collections.abc import Callable
from typing import Any

import ui
import wx
from logHandler import log

from . import messageText, sounds, volumes
from .whatsApp import WhatsAppError, WhatsAppSession


def callKind(call: dict) -> str:
	return (
		# Translators: The kind of call, said with who is calling.
		_("video call")
		if call.get("video")
		# Translators: The kind of call, said with who is calling.
		else _("voice call")
	)


def callStatus(call: dict, connectedAt: float | None) -> str:
	"""One line about the call: who, which kind, and where it stands, with its length once connected."""
	who = call.get("name", "")
	if call.get("ended"):
		# Translators: The state of a call that has ended.
		state = _("ended")
	elif call.get("connected") and connectedAt:
		state = messageText.duration(time.monotonic() - connectedAt)
	elif call.get("incoming"):
		# Translators: The state of a call someone is making to the user.
		state = _("ringing")
	else:
		# Translators: The state of a call the user is making, before the other person answers.
		state = _("calling")
	return f"{who}, {callKind(call)}, {state}"


class CallWindow(wx.Dialog):
	"""Answer or decline a call, then mute and hang up. Escape only hides it; the call goes on."""

	def __init__(self, parent: wx.Window, session: WhatsAppSession, onClosed: Callable[[], None]) -> None:
		# Translators: The title of the call window.
		super().__init__(parent, title=_("WhatsApp call"))
		self.session = session
		self._onClosed = onClosed
		self.call: dict | None = None
		self.connectedAt: float | None = None
		self.muted = False
		self.declined = False
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.statusBox = wx.TextCtrl(self, style=wx.TE_READONLY, size=(420, -1))
		sizer.Add(self.statusBox, 0, wx.EXPAND | wx.ALL, 8)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button that answers a call. NVDA+Alt+A does this from anywhere.
		self.answerButton = wx.Button(self, label=_("&Answer (NVDA+Alt+A)"))
		self.answerButton.Bind(wx.EVT_BUTTON, lambda evt: self.answer())
		# Translators: A button that declines a ringing call. NVDA+Alt+H does this from anywhere.
		self.declineButton = wx.Button(self, label=_("&Decline (NVDA+Alt+H)"))
		self.declineButton.Bind(wx.EVT_BUTTON, lambda evt: self.hangUp())
		self.muteButton = wx.Button(self, label="")
		self.muteButton.Bind(wx.EVT_BUTTON, lambda evt: self.toggleMute())
		# Translators: A button that ends the call. NVDA+Alt+H does this from anywhere.
		self.endButton = wx.Button(self, label=_("&End call (NVDA+Alt+H)"))
		self.endButton.Bind(wx.EVT_BUTTON, lambda evt: self.hangUp())
		for button in (self.answerButton, self.declineButton, self.muteButton, self.endButton):
			buttons.Add(button, 0, wx.RIGHT, 6)
		sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
		self.SetSizerAndFit(sizer)
		self.CentreOnScreen()
		self.Bind(wx.EVT_CHAR_HOOK, self._onKey)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, lambda evt: self._refresh(), self.timer)
		self.timer.Start(1000)

	# Background calls ----------------------------------------------------------------------------------

	def _run(self, work: Callable[[], Any], onDone: Callable[[Any], None] | None = None) -> None:
		def target() -> None:
			try:
				result = work()
			except Exception as e:  # noqa: BLE001 - reported to the user
				if not isinstance(e, WhatsAppError):
					log.exception("WhatsApp Access: call")
				# Translators: Reported when a call action failed.
				wx.CallAfter(
					ui.message, _("The call did not respond. {detail}").format(detail=getattr(e, "code", ""))
				)
				return
			if onDone is not None:
				wx.CallAfter(onDone, result)

		threading.Thread(target=target, name="whatsAppAccess.call", daemon=True).start()

	# Actions -------------------------------------------------------------------------------------------

	def answer(self) -> None:
		if self.call and self.call.get("incoming") and self.call.get("ringing"):
			self._run(self.session.answerCall)

	def hangUp(self) -> None:
		if not self.call or self.call.get("ended"):
			return
		if self.call.get("incoming") and self.call.get("ringing") and not self.call.get("connected"):
			self.declined = True
			self._run(self.session.declineCall)
		else:
			self._run(self.session.endCall)

	def toggleMute(self) -> None:
		if not self.call or not self.call.get("connected"):
			return

		def done(muted: bool) -> None:
			self.muted = muted
			self._updateButtons()
			ui.message(
				# Translators: Reported when the user's microphone is muted during a call.
				_("Microphone off")
				if muted
				# Translators: Reported when the user's microphone is on again during a call.
				else _("Microphone on")
			)

		target = not self.muted
		self._run(lambda: self.session.muteCall(target), done)

	# Showing the call ----------------------------------------------------------------------------------

	def update(self, call: dict, connectedAt: float | None) -> None:
		self.call = call
		self.connectedAt = connectedAt
		self._refresh()
		self._updateButtons()

	def _refresh(self) -> None:
		if self.call:
			text = callStatus(self.call, self.connectedAt)
			if self.statusBox.GetValue() != text:
				self.statusBox.SetValue(text)

	def _updateButtons(self) -> None:
		call = self.call or {}
		ringingIn = bool(call.get("incoming") and call.get("ringing") and not call.get("connected"))
		active = not call.get("ended") and not ringingIn
		self.muteButton.SetLabel(
			# Translators: A button that turns the microphone back on during a call.
			_("Un&mute (Ctrl+M)")
			if self.muted
			# Translators: A button that turns the microphone off during a call.
			else _("&Mute (Ctrl+M)")
		)
		for button, show in (
			(self.answerButton, ringingIn),
			(self.declineButton, ringingIn),
			(self.muteButton, active and bool(call.get("connected"))),
			(self.endButton, active),
		):
			button.Show(show)
		self.Layout()
		self.Fit()

	def focusAction(self) -> None:
		"""Put focus on what the user most likely wants now: Answer while ringing, End during a call."""
		for button in (self.answerButton, self.endButton):
			if button.IsShown():
				button.SetFocus()
				return
		self.statusBox.SetFocus()

	def _onKey(self, evt: wx.KeyEvent) -> None:
		key, modifiers = evt.GetKeyCode(), evt.GetModifiers()
		if volumes.handleKey(key, modifiers, self.session):
			return
		if key == wx.WXK_ESCAPE and not evt.HasAnyModifiers():
			# Hiding the window leaves the call going; NVDA+Alt+A brings it back.
			self.Hide()
			return
		if modifiers == wx.MOD_CONTROL and key == ord("M"):
			self.toggleMute()
			return
		evt.Skip()

	def _onClose(self, evt: wx.CloseEvent) -> None:
		self.timer.Stop()
		self._onClosed()
		self.Destroy()


class CallAnnouncer:
	"""Follows the call's state as WhatsApp reports it, says what changed, and keeps the call window."""

	def __init__(self, session: WhatsAppSession, hints: Callable[[], bool]) -> None:
		self.session = session
		self.hints = hints
		self.window: CallWindow | None = None
		self.call: dict | None = None
		self.connectedAt: float | None = None

	def onCall(self, call: dict | None) -> None:
		before = self.call or {}
		if call is None:
			if before and not before.get("ended"):
				self._ended(before)
			self.call = None
			self._closeSoon()
			return
		new = call.get("id") != before.get("id")
		if new:
			self.connectedAt = None
			if call.get("incoming"):
				sounds.play(sounds.RING)
				# Translators: Read out when someone calls the user: the kind of call and who.
				message = _("Incoming {kind} from {name}").format(
					kind=callKind(call), name=call.get("name", "")
				)
				if self.hints():
					# Translators: A hint after an incoming call is announced.
					message += ". " + _("NVDA+Alt+A answers, NVDA+Alt+H declines")
				ui.message(message)
			else:
				# Translators: Reported when the user's call to someone starts ringing.
				ui.message(_("Calling {name}…").format(name=call.get("name", "")))
			self._showWindow(focus=not call.get("incoming"))
		if call.get("connected") and not before.get("connected"):
			self.connectedAt = time.monotonic()
			sounds.play(sounds.SENT)
			# Translators: Reported when a call connects.
			ui.message(_("Connected"))
		if call.get("ended") and not before.get("ended"):
			self._ended(call)
			self._closeSoon()
		self.call = call
		if self.window:
			self.window.update(call, self.connectedAt)

	def _ended(self, call: dict) -> None:
		sounds.play(sounds.DISCARD)
		if self.connectedAt:
			# Translators: Reported when a call ends, with how long it lasted.
			ui.message(
				_("Call ended, {duration}").format(
					duration=messageText.duration(time.monotonic() - self.connectedAt)
				)
			)
		elif call.get("incoming") and self.window is not None and self.window.declined:
			# Translators: Reported after the user declined an incoming call.
			ui.message(_("Declined"))
		elif call.get("incoming"):
			# Translators: Reported when an incoming call stops ringing without being answered here.
			ui.message(_("Call ended"))
		else:
			# Translators: Reported when the person the user called did not answer.
			ui.message(_("No answer"))
		self.connectedAt = None

	def _showWindow(self, focus: bool) -> None:
		import gui

		if self.window is None:
			self.window = CallWindow(gui.mainFrame, self.session, self._windowClosed)
		if self.call:
			self.window.update(self.call, self.connectedAt)
		if not focus:
			# A ringing call must not take the user away from what they are doing; the announcement and
			# NVDA+Alt+A are enough. The window is there when they look for it.
			if not self.window.IsShown():
				self.window.ShowWithoutActivating()
			return
		gui.mainFrame.prePopup()
		self.window.Show()
		self.window.Raise()
		gui.mainFrame.postPopup()
		self.window.focusAction()

	def _windowClosed(self) -> None:
		self.window = None

	def _closeSoon(self) -> None:
		if self.window:
			wx.CallLater(2500, self._closeIfEnded)

	def _closeIfEnded(self) -> None:
		if self.window and (self.call is None or self.call.get("ended")):
			self.window.Close()

	# The global commands ------------------------------------------------------------------------------

	def answerOrShow(self) -> bool:
		"""NVDA+Alt+A: answer a ringing call, or bring the window of the current call back."""
		call = self.call
		if not call or call.get("ended"):
			return False
		if call.get("incoming") and call.get("ringing") and not call.get("connected"):
			self._showWindow(focus=True)
			self.window.answer()
		else:
			self._showWindow(focus=True)
		return True

	def hangUp(self) -> bool:
		"""NVDA+Alt+H: decline a ringing call or end the current one."""
		call = self.call
		if not call or call.get("ended"):
			return False
		if self.window is None:
			self._showWindow(focus=False)
		self.window.hangUp()
		return True
