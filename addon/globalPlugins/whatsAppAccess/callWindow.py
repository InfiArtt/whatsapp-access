# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Calls: what NVDA says as a call rings, connects and ends, and a small window to answer, mute and hang up."""

import threading
import time
from collections.abc import Callable
from typing import Any

import addonHandler
import config
import ui
import wx
from logHandler import log

from . import messageText, sounds, volumes
from .configSpec import CONFIG_SECTION
from .whatsApp import WhatsAppError, WhatsAppSession

addonHandler.initTranslation()


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

	def __init__(
		self,
		parent: wx.Window,
		session: WhatsAppSession,
		onClosed: Callable[[], None],
		announcer: "CallAnnouncer",
	) -> None:
		self.announcer = announcer
		# Translators: The title of the call window.
		super().__init__(parent, title=_("WhatsApp call"))
		self.session = session
		self._onClosed = onClosed
		self.call: dict | None = None
		self.connectedAt: float | None = None
		self.declined = False
		self._askingDevices = False
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the box in the call window that says who is calling and how it goes.
		sizer.Add(wx.StaticText(self, label=_("Call:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.statusBox = wx.TextCtrl(self, style=wx.TE_READONLY, size=(420, -1))
		sizer.Add(self.statusBox, 0, wx.EXPAND | wx.ALL, 8)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button that answers a call. NVDA+Alt+A does this from anywhere.
		self.answerButton = wx.Button(self, label=_("Answer (NVDA+Alt+A)"))
		self.answerButton.Bind(wx.EVT_BUTTON, lambda evt: self.answer())
		# Translators: A button that declines a ringing call. NVDA+Alt+H does this from anywhere.
		self.declineButton = wx.Button(self, label=_("Decline (NVDA+Alt+H)"))
		self.declineButton.Bind(wx.EVT_BUTTON, lambda evt: self.hangUp())
		self.muteButton = wx.Button(self, label="")
		self.muteButton.Bind(wx.EVT_BUTTON, lambda evt: self.toggleMute())
		# Translators: A button that ends the call. NVDA+Alt+H does this from anywhere.
		self.endButton = wx.Button(self, label=_("End call (NVDA+Alt+H)"))
		self.endButton.Bind(wx.EVT_BUTTON, lambda evt: self.hangUp())
		self.handButton = wx.Button(self, label="")
		self.handButton.Bind(wx.EVT_BUTTON, lambda evt: self.announcer.toggleHand())
		# Translators: A button in a group call: sends a reaction, such as a thumbs up, to everyone.
		self.reactButton = wx.Button(self, label=_("Rea&ct\u2026"))
		self.reactButton.Bind(wx.EVT_BUTTON, lambda evt: self._react())
		# Translators: A button in a call: choose the microphone and the speaker or headphones.
		self.devicesButton = wx.Button(self, label=_("Microphone and &speaker…"))
		self.devicesButton.Bind(wx.EVT_BUTTON, lambda evt: self._showDevices())
		for button in (
			self.answerButton,
			self.declineButton,
			self.muteButton,
			self.handButton,
			self.reactButton,
			self.devicesButton,
			self.endButton,
		):
			buttons.Add(button, 0, wx.RIGHT, 6)
		sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
		# Translators: The label of the list of people in a group call.
		self.peopleLabel = wx.StaticText(self, label=_("&Participants:"))
		self.peopleList = wx.ListBox(self, style=wx.LB_SINGLE, size=(420, 200))
		self.peopleList.Bind(wx.EVT_CONTEXT_MENU, lambda evt: self._personMenu())
		self._people: list[dict] = []
		sizer.Add(self.peopleLabel, 0, wx.LEFT | wx.RIGHT, 8)
		sizer.Add(self.peopleList, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
		self.SetSizerAndFit(sizer)
		self.CentreOnScreen()
		self.Bind(wx.EVT_CHAR_HOOK, self._onKey)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		# The call's time, each second. Not a wx.Timer owned by this window: one firing after the window was
		# destroyed, as on reloading plugins, crashes NVDA. A CallLater checks the window is still there.
		self.timer = wx.CallLater(1000, self._tick)

	# Background calls ----------------------------------------------------------------------------------

	def _run(self, work: Callable[[], Any], onDone: Callable[[Any], None] | None = None) -> None:
		def target() -> None:
			try:
				result = work()
			except Exception as e:  # noqa: BLE001 - reported to the user
				if not isinstance(e, WhatsAppError):
					log.exception("WhatsApp Access: call")
				wx.CallAfter(
					ui.message,
					# Translators: Reported when a call action failed.
					_("The call did not respond. {detail}").format(detail=getattr(e, "code", "")),
				)
				return
			if onDone is not None:
				wx.CallAfter(onDone, result)

		threading.Thread(target=target, name="whatsAppAccess.call", daemon=True).start()

	def _showDevices(self) -> None:
		"""The microphone and speaker dialog, once WhatsApp has listed its devices off the main thread."""
		if self._askingDevices:
			return
		self._askingDevices = True

		def listDevices() -> None:
			try:
				devices = self.session.audioDevices()
			except WhatsAppError as e:
				log.debugWarning(f"WhatsApp Access: could not list microphones and speakers: {e}")
				devices = {}
			wx.CallAfter(show, devices)

		def show(devices: dict) -> None:
			self._askingDevices = False
			if not self:
				# The call ended and its window closed meanwhile.
				return
			dialog = AudioDevicesDialog(self, self.session, devices)
			try:
				dialog.ShowModal()
			finally:
				dialog.Destroy()

		threading.Thread(target=listDevices, name="whatsAppAccess.listDevices", daemon=True).start()

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
		self.announcer.toggleMute()

	# Showing the call ----------------------------------------------------------------------------------

	def update(self, call: dict, connectedAt: float | None) -> None:
		self.call = call
		self.connectedAt = connectedAt
		self._refresh()
		self._updateButtons()

	def _tick(self) -> None:
		if not self:
			return
		self._refresh()
		self.timer = wx.CallLater(1000, self._tick)

	def _refresh(self) -> None:
		if self.call:
			text = callStatus(self.call, self.connectedAt)
			if self.statusBox.GetValue() != text:
				self.statusBox.SetValue(text)

	def _updateButtons(self) -> None:
		focused = wx.Window.FindFocus()
		if focused is not None and focused.GetTopLevelParent() is not self:
			focused = None
		call = self.call or {}
		ringingIn = bool(call.get("incoming") and call.get("ringing") and not call.get("connected"))
		active = not call.get("ended") and not ringingIn
		self.muteButton.SetLabel(
			# Translators: A button that turns the microphone back on during a call.
			_("Unmute (Ctrl+M)")
			if self.announcer.muted
			# Translators: A button that turns the microphone off during a call.
			else _("Mute (Ctrl+M)")
		)
		inGroup = active and bool(call.get("connected")) and bool(call.get("group"))
		self.handButton.SetLabel(
			# Translators: A button in a group call: lowers the user's raised hand.
			_("Lower hand (Ctrl+H)")
			if call.get("myHand")
			# Translators: A button in a group call: raises the user's hand, as WhatsApp's button does.
			else _("Raise hand (Ctrl+H)")
		)
		for button, show in (
			(self.answerButton, ringingIn),
			(self.declineButton, ringingIn),
			(self.muteButton, active and bool(call.get("connected"))),
			(self.handButton, inGroup),
			(self.reactButton, inGroup),
			(self.devicesButton, active),
			(self.endButton, active),
			(self.peopleLabel, inGroup),
			(self.peopleList, inGroup),
		):
			button.Show(show)
		if inGroup:
			self._fillPeople(call.get("participants") or [])
		self.Layout()
		self.Fit()
		if focused is not None and not focused.IsShown():
			# The button that had focus went away, as Answer once the call connects: focus moves on to
			# what is there now, instead of to nowhere.
			self.focusAction()

	def _fillPeople(self, people: list[dict]) -> None:
		# Those in the call first, then those invited who have not joined.
		people = sorted(people, key=lambda p: (not p.get("connected"), not p.get("hand"), p.get("name", "")))
		self._people = people
		lines = [messageText.participantLine(p) for p in people]
		if self.peopleList.GetItems() != lines:
			selection = self.peopleList.GetSelection()
			self.peopleList.Set(lines)
			if lines:
				self.peopleList.SetSelection(min(max(selection, 0), len(lines) - 1))

	def _personMenu(self) -> None:
		index = self.peopleList.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._people):
			return
		person = self._people[index]
		if not person.get("connected") or person.get("muted"):
			return
		menu = wx.Menu()
		# Translators: An item in a group call participant's menu: asks them to mute their microphone.
		item = menu.Append(wx.ID_ANY, _("&Ask to mute"))
		self.Bind(
			wx.EVT_MENU,
			lambda evt: self._run(
				lambda: self.session.askToMute(person["id"]),
				# Translators: Reported after asking someone in a group call to mute, with their name.
				lambda r: ui.message(_("Asked {name} to mute").format(name=person.get("name", ""))),
			),
			item,
		)
		self.peopleList.PopupMenu(menu)
		menu.Destroy()

	def _react(self) -> None:
		menu = wx.Menu()
		for emoji in CALL_REACTIONS:
			item = menu.Append(wx.ID_ANY, emoji)
			self.Bind(
				wx.EVT_MENU,
				lambda evt, emoji=emoji: self._run(
					lambda: self.session.callReaction(emoji),
					# Translators: Reported after sending a reaction in a group call, with the emoji.
					lambda r: ui.message(_("Sent {emoji}").format(emoji=emoji)),
				),
				item,
			)
		self.PopupMenu(menu)
		menu.Destroy()

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
		if modifiers == wx.MOD_CONTROL and key == ord("H"):
			self.announcer.toggleHand()
			return
		if modifiers == wx.MOD_CONTROL | wx.MOD_SHIFT and key == ord("G"):
			self.announcer.saySpeakers()
			return
		evt.Skip()

	def _onClose(self, evt: wx.CloseEvent) -> None:
		self.timer.Stop()
		self._onClosed()
		self.Destroy()


# The reactions WhatsApp offers first in a call.
CALL_REACTIONS = ("👍", "❤️", "😂", "😮", "😢", "🙏", "👏")


class CallAnnouncer:
	"""Follows the call's state as WhatsApp reports it, says what changed, and keeps the call window."""

	def __init__(self, session: WhatsAppSession, hints: Callable[[], bool]) -> None:
		self.session = session
		self.hints = hints
		self.window: CallWindow | None = None
		self.call: dict | None = None
		self.connectedAt: float | None = None
		self.muted = False
		# What the user asked the microphone to become, until WhatsApp confirms it.
		self._expectedMute: bool | None = None
		# Told when the call starts, changes or ends, so the WhatsApp window can show it.
		self.onChange: Callable[[], None] | None = None

	@property
	def inCall(self) -> bool:
		call = self.call
		return bool(call and call.get("connected") and not call.get("ended"))

	def saySpeakers(self) -> None:
		"""Ctrl+Shift+G: who is speaking in the call now."""
		if not self.inCall:
			return

		def work() -> None:
			try:
				names = self.session.speakers()
			except WhatsAppError as e:
				log.debugWarning(f"WhatsApp Access: speakers: {e}")
				wx.CallAfter(
					ui.message,
					# Translators: Said when the add-on could not find out who is speaking in a call.
					# {reason} is a short code for what went wrong.
					_("Could not find out who is speaking ({reason})").format(reason=e.code),
				)
				return
			wx.CallAfter(
				ui.message,
				# Translators: Said when the user asks who is speaking in a call and nobody is.
				", ".join(names) if names else _("Nobody is speaking"),
			)

		threading.Thread(target=work, name="whatsAppAccess.speakers", daemon=True).start()

	def toggleHand(self) -> None:
		"""Ctrl+H in a group call: raise or lower the user's hand."""
		call = self.call or {}
		if not self.inCall or not call.get("group"):
			return
		target = not call.get("myHand")

		def work() -> None:
			try:
				self.session.raiseHand(target)
			except WhatsAppError as e:
				log.debugWarning(f"WhatsApp Access: hand: {e}")
				wx.CallAfter(
					ui.message,
					# Translators: Said when raising or lowering the user's hand in a group call failed.
					# {reason} is a short code for what went wrong.
					_("The hand could not be raised or lowered ({reason})").format(reason=e.code),
				)
				return
			# Translators: Reported after the user raised or lowered their hand in a group call.
			wx.CallAfter(ui.message, _("Hand raised") if target else _("Hand lowered"))

		threading.Thread(target=work, name="whatsAppAccess.hand", daemon=True).start()

	def toggleMute(self) -> None:
		"""Ctrl+M: microphone off or on again, from the call window or the WhatsApp window."""
		if not self.inCall:
			return
		target = not self.muted
		self._expectedMute = target

		def work() -> None:
			try:
				muted = self.session.muteCall(target)
			except WhatsAppError as e:
				log.debugWarning(f"WhatsApp Access: mute: {e}")
				wx.CallAfter(failed, e)
				return
			wx.CallAfter(done, bool(muted))

		def failed(error: WhatsAppError) -> None:
			# Otherwise "Someone in the call muted your microphone" would stay silent for the rest of the call.
			self._expectedMute = None
			ui.message(
				# Translators: Said when the microphone could not be turned off or on during a call.
				# {reason} is a short code for what went wrong.
				_("The microphone could not be changed ({reason})").format(reason=error.code)
			)

		def done(muted: bool) -> None:
			self._expectedMute = None
			self.muted = muted
			sounds.play(sounds.MIC_OFF if muted else sounds.MIC_ON)
			if self.window:
				self.window._updateButtons()
			self._changed()
			ui.message(
				# Translators: Reported when the user's microphone is muted during a call.
				_("Microphone off")
				if muted
				# Translators: Reported when the user's microphone is on again during a call.
				else _("Microphone on")
			)

		threading.Thread(target=work, name="whatsAppAccess.mute", daemon=True).start()

	def _changed(self) -> None:
		if self.onChange is not None:
			try:
				self.onChange()
			except Exception:  # noqa: BLE001 - the WhatsApp window may be closing
				log.debugWarning("WhatsApp Access: call change", exc_info=True)

	def connectionGone(self, announce: bool = True) -> None:
		"""WhatsApp stopped: the connection was lost, it was closed, or NVDA is exiting. No call can go on
		without it, and WhatsApp will not say so, so the call is forgotten here: the ring stops, the call
		window closes, and NVDA+Alt+A or NVDA+Alt+M no longer act on a call that is gone."""
		sounds.stopRing()
		if self.call is None:
			return
		if announce:
			self.onCall(None)
			return
		self.call = None
		self.muted = False
		if self.window:
			self.window.Close()
		self._changed()

	def onCall(self, call: dict | None) -> None:
		before = self.call or {}
		ringing = bool(
			call
			and call.get("incoming")
			and call.get("ringing")
			and not call.get("connected")
			and not call.get("ended")
		)
		if not ringing:
			# Answered, declined, missed or over: the ring stops at once.
			sounds.stopRing()
		if call is None:
			if before and not before.get("ended"):
				self._ended(before)
			self.call = None
			self.muted = False
			self._closeSoon()
			self._changed()
			return
		new = call.get("id") != before.get("id")
		if new:
			self.connectedAt = None
			self.muted = False
			self._expectedMute = None
			if self.window is not None:
				# A window kept open for the last call's end must not say "Declined" for this one.
				self.window.declined = False
			if call.get("incoming"):
				sounds.startRing(config.conf[CONFIG_SECTION]["ringSound"])
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
		# WhatsApp knows whether the microphone is on, also after joining muted or muting elsewhere.
		if "muted" in call:
			muted = bool(call["muted"])
			if (
				muted
				and not self.muted
				and self._expectedMute is None
				and call.get("connected")
				and before.get("connected")
				and not new
			):
				# Someone else muted the user, as a group's admin can.
				sounds.play(sounds.MIC_OFF)
				# Translators: Said when someone else in the call turned the user's microphone off.
				ui.message(_("Someone in the call muted your microphone"))
			self.muted = muted
			if self.window:
				self.window._updateButtons()
		# Joins, leaves and raised hands in a group call, with a small sound each; not the people
		# already there when the user joined.
		if call.get("group") and call.get("connected") and before.get("connected") and not new:
			self._announceChanges(before.get("participants") or [], call.get("participants") or [])
		self.call = call
		if self.window:
			self.window.update(call, self.connectedAt)
		self._changed()

	def _announceChanges(self, before: list[dict], after: list[dict]) -> None:
		changes = messageText.callChanges(before, after)
		if not changes:
			return
		texts = []
		for kind, name in changes:
			if kind == "joined":
				# Translators: Said when someone joins the group call the user is in.
				texts.append(_("{name} joined").format(name=name))
			elif kind == "left":
				# Translators: Said when someone leaves the group call the user is in.
				texts.append(_("{name} left").format(name=name))
			elif kind == "hand":
				# Translators: Said when someone in the group call raises their hand.
				texts.append(_("{name} raised a hand").format(name=name))
			else:
				# Someone's reaction: their name and the emoji.
				texts.append(name)
		kinds = {kind for kind, name in changes}
		for kind, sound in (
			("hand", sounds.CALL_HAND),
			("joined", sounds.CALL_JOIN),
			("left", sounds.CALL_LEAVE),
			("reaction", sounds.CALL_REACTION),
		):
			if kind in kinds:
				sounds.play(sound)
				break
		ui.message(", ".join(texts))

	def _ended(self, call: dict) -> None:
		sounds.play(sounds.DISCARD)
		if self.connectedAt:
			ui.message(
				# Translators: Reported when a call ends, with how long it lasted.
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
			self.window = CallWindow(gui.mainFrame, self.session, self._windowClosed, self)
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


class AudioDevicesDialog(wx.Dialog):
	"""Choose the microphone and the speaker; each change takes effect at once, during the call too."""

	def __init__(self, parent: wx.Window, session: WhatsAppSession, devices: dict) -> None:
		"""
		:param devices: WhatsApp's microphones and speakers, asked for before, off NVDA's main thread.
		"""
		# Translators: The title of the dialog that chooses the microphone and speaker.
		super().__init__(parent, title=_("Microphone and speaker"))
		self.session = session
		settings = config.conf[CONFIG_SECTION]
		# Translators: The first choice in the list of microphones: whatever the browser uses.
		self.microphones = [("", _("Browser default"))]
		self.microphones += [(name, name) for name in devices.get("microphones", [])]
		# Translators: The first choice in the list of speakers: the one Windows uses.
		self.speakers = [("", _("Windows default"))]
		self.speakers += [(name, name) for name in devices.get("speakers", [])]
		for items, key in ((self.microphones, "microphone"), (self.speakers, "speaker")):
			if settings[key] and settings[key] not in [name for name, label in items]:
				items.append((settings[key], settings[key]))
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the list of microphones in the call's device dialog.
		sizer.Add(wx.StaticText(self, label=_("&Microphone:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.microphoneChoice = wx.Choice(self, choices=[label for name, label in self.microphones])
		sizer.Add(self.microphoneChoice, 0, wx.EXPAND | wx.ALL, 8)
		# Translators: The label of the list of speakers in the call's device dialog.
		sizer.Add(wx.StaticText(self, label=_("&Speaker:")), 0, wx.LEFT | wx.RIGHT, 8)
		self.speakerChoice = wx.Choice(self, choices=[label for name, label in self.speakers])
		sizer.Add(self.speakerChoice, 0, wx.EXPAND | wx.ALL, 8)
		self.microphoneChoice.SetSelection([n for n, label in self.microphones].index(settings["microphone"]))
		self.speakerChoice.SetSelection([n for n, label in self.speakers].index(settings["speaker"]))
		self.microphoneChoice.Bind(wx.EVT_CHOICE, lambda evt: self._apply())
		self.speakerChoice.Bind(wx.EVT_CHOICE, lambda evt: self._apply())
		closeButton = wx.Button(self, wx.ID_CLOSE)
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CLOSE))
		self.SetEscapeId(wx.ID_CLOSE)
		sizer.Add(closeButton, 0, wx.ALIGN_RIGHT | wx.ALL, 8)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.microphoneChoice.SetFocus()

	def _apply(self) -> None:
		settings = config.conf[CONFIG_SECTION]
		settings["microphone"] = self.microphones[self.microphoneChoice.GetSelection()][0]
		settings["speaker"] = self.speakers[self.speakerChoice.GetSelection()][0]
		volumes.saveSoon()
		microphone, speaker, processing = (
			settings["microphone"],
			settings["speaker"],
			settings["callProcessing"],
		)

		def apply() -> None:
			try:
				self.session.setCallAudio(microphone, processing, speaker)
			except WhatsAppError as e:
				log.debugWarning(f"WhatsApp Access: switching devices: {e}")
				# Translators: Reported when the microphone or speaker could not be changed.
				wx.CallAfter(ui.message, _("Could not change the device. {detail}").format(detail=e.code))

		threading.Thread(target=apply, name="whatsAppAccess.devices", daemon=True).start()
