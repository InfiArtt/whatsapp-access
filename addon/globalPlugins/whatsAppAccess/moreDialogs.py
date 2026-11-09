# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Dialogs for polls, events, your status, profile, privacy and managing a group."""

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import addonHandler
import api
import ui
import wx

from .questions import askYesNo

if TYPE_CHECKING:
	from .chatWindow import ChatWindow

addonHandler.initTranslation()


def _labeled(parent: wx.Window, sizer: wx.Sizer, label: str, make: Callable[[], wx.Window]) -> Any:
	"""A label above a control. Screen readers name a control by the text made just before it, so the label
	is made first and the control after it."""
	text = wx.StaticText(parent, label=label)
	control = make()
	sizer.Add(text, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
	sizer.Add(control, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
	return control


def _okCancel(dialog: wx.Dialog, sizer: wx.Sizer, okLabel: str) -> None:
	buttons = wx.StdDialogButtonSizer()
	ok = wx.Button(dialog, wx.ID_OK, label=okLabel)
	ok.SetDefault()
	buttons.AddButton(ok)
	# Translators: The button that closes a dialog without doing anything.
	buttons.AddButton(wx.Button(dialog, wx.ID_CANCEL, label=_("Cancel")))
	buttons.Realize()
	sizer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 8)


class CreatePollDialog(wx.Dialog):
	"""A question, its options one per line, and whether several answers are allowed, as WhatsApp's poll."""

	def __init__(self, parent: wx.Window) -> None:
		# Translators: The title of the dialog that makes a poll.
		super().__init__(parent, title=_("Create poll"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of a poll's question.
		self.question = _labeled(self, sizer, _("&Question:"), lambda: wx.TextCtrl(self, size=(420, -1)))
		self.options = _labeled(
			self,
			sizer,
			# Translators: The label of a poll's options, typed one per line.
			_("&Options, one per line:"),
			lambda: wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(420, 140)),
		)
		# Translators: A checkbox in the poll dialog, like WhatsApp's.
		self.multiple = wx.CheckBox(self, label=_("Allow &multiple answers"))
		self.multiple.SetValue(True)
		sizer.Add(self.multiple, 0, wx.ALL, 8)
		# Translators: The button that sends a poll.
		_okCancel(self, sizer, _("&Send"))
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.question.SetFocus()

	def values(self) -> tuple[str, list[str], bool]:
		options = [line.strip() for line in self.options.GetValue().splitlines() if line.strip()]
		return self.question.GetValue().strip(), options[:12], not self.multiple.GetValue()


class CreateEventDialog(wx.Dialog):
	"""A group event: name, date and time, and optionally an end time, place and description."""

	def __init__(self, parent: wx.Window) -> None:
		# Translators: The title of the dialog that makes an event in a group.
		super().__init__(parent, title=_("Create event"))
		tomorrow = time.localtime(time.time() + 86400)
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of an event's name.
		self.name = _labeled(self, sizer, _("Event &name:"), lambda: wx.TextCtrl(self, size=(420, -1)))
		self.date = _labeled(
			self,
			sizer,
			# Translators: The label of an event's date, typed as day/month/year.
			_("&Date (day/month/year):"),
			lambda: wx.TextCtrl(self, value=time.strftime("%d/%m/%Y", tomorrow)),
		)
		self.start = _labeled(
			self,
			sizer,
			# Translators: The label of an event's start time, typed as hours:minutes.
			_("&Start time (hours:minutes):"),
			lambda: wx.TextCtrl(self, value="10:00"),
		)
		# Translators: The label of an event's end time; it may stay empty.
		self.end = _labeled(self, sizer, _("&End time (may be empty):"), lambda: wx.TextCtrl(self))
		# Translators: The label of an event's place; it may stay empty.
		self.location = _labeled(self, sizer, _("&Location (may be empty):"), lambda: wx.TextCtrl(self))
		self.description = _labeled(
			self,
			sizer,
			# Translators: The label of an event's description; it may stay empty.
			_("Desc&ription (may be empty):"),
			lambda: wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(420, 80)),
		)
		# Translators: A checkbox in the event dialog: adds a WhatsApp voice call link to the event.
		self.call = wx.CheckBox(self, label=_("Add a voice &call link"))
		sizer.Add(self.call, 0, wx.ALL, 8)
		# Translators: The button that sends an event.
		_okCancel(self, sizer, _("&Send"))
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.name.SetFocus()

	def _time(self, text: str) -> int | None:
		try:
			return int(time.mktime(time.strptime(f"{self.date.GetValue().strip()} {text}", "%d/%m/%Y %H:%M")))
		except ValueError:
			return None

	def values(self) -> dict | None:
		name = self.name.GetValue().strip()
		start = self._time(self.start.GetValue().strip())
		if not name or start is None:
			# Translators: Reported when an event has no name, or its date or time cannot be read.
			ui.message(_("Type the event's name, and its date and time like 25/12/2026 and 10:00"))
			return None
		options: dict[str, Any] = {"name": name, "start": start}
		endText = self.end.GetValue().strip()
		if endText:
			end = self._time(endText)
			if end and end > start:
				options["end"] = end
		for key, control in (("location", self.location), ("description", self.description)):
			if control.GetValue().strip():
				options[key] = control.GetValue().strip()
		if self.call.GetValue():
			options["callType"] = "voice"
		return options


def statusFonts() -> list[tuple[int, str]]:
	"""The fonts WhatsApp Web's status composer offers, by WhatsApp's own number for them."""
	return [
		# Translators: A font for a text status, like WhatsApp's.
		(0, _("Default")),
		# Translators: A font for a text status, like WhatsApp's.
		(1, _("Serif")),
		# Translators: A font for a text status, like WhatsApp's.
		(2, _("Script")),
	]


class TextStatusDialog(wx.Dialog):
	"""A text status: what it says, its background colour and its font."""

	def __init__(self, parent: wx.Window) -> None:
		# Translators: The title of the dialog that writes a text status.
		super().__init__(parent, title=_("Write a status"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.text = _labeled(
			self,
			sizer,
			# Translators: The label of a text status.
			_("&Status:"),
			lambda: wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(420, 120)),
		)
		self.color = _labeled(
			self,
			sizer,
			# Translators: The label of the choice of a text status's background colour.
			_("Background &colour:"),
			# Translators: One of the background colours of a text status, by number.
			lambda: wx.Choice(self, choices=[_("Colour {number}").format(number=n) for n in range(1, 22)]),
		)
		self.color.SetSelection(0)
		self.font = _labeled(
			self,
			sizer,
			# Translators: The label of the choice of a text status's font.
			_("&Font:"),
			lambda: wx.Choice(self, choices=[name for number, name in statusFonts()]),
		)
		self.font.SetSelection(0)
		# Translators: The button that posts a status.
		_okCancel(self, sizer, _("&Post"))
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.text.SetFocus()

	def values(self) -> tuple[str, int, int]:
		return (
			self.text.GetValue().strip(),
			self.color.GetSelection(),
			statusFonts()[self.font.GetSelection()][0],
		)


class ProfileDialog(wx.Dialog):
	"""The user's name, About text and photo, as in WhatsApp's profile."""

	def __init__(self, parent: wx.Window, profile: dict) -> None:
		# Translators: The title of the dialog with the user's own profile.
		super().__init__(parent, title=_("Profile"))
		self.photo: str | None = None
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of the user's name, as others see it.
		self.name = _labeled(
			self,
			sizer,
			# Translators: The label of the user's name in the profile dialog.
			_("Your &name:"),
			lambda: wx.TextCtrl(self, value=profile.get("name", ""), size=(420, -1)),
		)
		self.about = _labeled(
			self,
			sizer,
			# Translators: The label of the user's About text.
			_("&About:"),
			lambda: wx.TextCtrl(self, value=profile.get("about", "")),
		)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button that chooses a picture for the user's profile photo.
		choose = wx.Button(self, label=_("Choose &photo…"))
		choose.Bind(wx.EVT_BUTTON, self._choosePhoto)
		# Translators: A button that removes the user's profile photo.
		remove = wx.Button(self, label=_("&Remove photo"))
		remove.Bind(wx.EVT_BUTTON, self._removePhoto)
		buttons.Add(choose, 0, wx.RIGHT, 6)
		buttons.Add(remove)
		sizer.Add(buttons, 0, wx.ALL, 8)
		self.photoText = wx.StaticText(self, label="")
		sizer.Add(self.photoText, 0, wx.LEFT | wx.RIGHT, 8)
		# Translators: The button that saves the profile.
		_okCancel(self, sizer, _("&Save"))
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.name.SetFocus()

	def _choosePhoto(self, evt: wx.CommandEvent) -> None:
		dialog = wx.FileDialog(
			self,
			# Translators: The title of the dialog for choosing a profile photo.
			_("Choose a profile photo"),
			# Translators: The file type in the dialog for choosing a profile photo.
			wildcard=_("Pictures") + "|*.jpg;*.jpeg;*.png;*.webp;*.bmp",
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		try:
			if dialog.ShowModal() == wx.ID_OK:
				self.photo = dialog.GetPath()
				# Translators: Shown and read out after choosing a new profile photo, with its file name.
				self.photoText.SetLabel(_("New photo: {name}").format(name=dialog.GetFilename()))
				ui.message(self.photoText.GetLabel())
		finally:
			dialog.Destroy()

	def _removePhoto(self, evt: wx.CommandEvent) -> None:
		self.photo = ""
		# Translators: Shown and read out after choosing to remove the profile photo.
		self.photoText.SetLabel(_("The photo will be removed"))
		ui.message(self.photoText.GetLabel())

	def values(self) -> tuple[str, str, str | None]:
		"""The name, About, and the new photo's path: "" removes it, None leaves it."""
		return self.name.GetValue().strip(), self.about.GetValue().strip(), self.photo


def privacyChoices() -> list[tuple[str, str, list[tuple[str, str]]]]:
	"""Each privacy setting: its key, label, and the values with their labels."""
	# Translators: A choice in a privacy setting, like WhatsApp's.
	everyone = ("all", _("Everyone"))
	# Translators: A choice in a privacy setting, like WhatsApp's.
	contacts = ("contacts", _("My contacts"))
	# Translators: A choice in a privacy setting, like WhatsApp's.
	except_ = ("contact_blacklist", _("My contacts except some (set on your phone)"))
	# Translators: A choice in a privacy setting, like WhatsApp's.
	nobody = ("none", _("Nobody"))
	return [
		# Translators: A privacy setting, like WhatsApp's.
		("lastSeen", _("&Last seen:"), [everyone, contacts, except_, nobody]),
		# Translators: A privacy setting, like WhatsApp's.
		(
			"online",
			# Translators: The label of a privacy choice, like WhatsApp's.
			_("&Who can see when I'm online:"),
			# Translators: A choice for who can see when the user is online: the same people as for last seen.
			[everyone, ("match_last_seen", _("Same as last seen"))],
		),
		# Translators: A privacy setting, like WhatsApp's.
		("profilePicture", _("Profile &photo:"), [everyone, contacts, except_, nobody]),
		# Translators: A privacy setting, like WhatsApp's.
		("about", _("&About:"), [everyone, contacts, except_, nobody]),
		# Translators: A privacy setting, like WhatsApp's.
		("groupAdd", _("Who can add me to &groups:"), [everyone, contacts, except_]),
		# Translators: A privacy setting, like WhatsApp's: whether others see blue ticks.
		("readReceipts", _("&Read receipts:"), [("all", _("On")), ("none", _("Off"))]),
		# Translators: A privacy setting, like WhatsApp's.
		("callAdd", _("Silence &unknown callers:"), [("all", _("Off")), ("known", _("On"))]),
	]


class PrivacyDialog(wx.Dialog):
	"""WhatsApp's privacy settings, each a choice; only the ones changed are saved."""

	def __init__(self, parent: wx.Window, current: dict) -> None:
		# Translators: The title of the dialog with the privacy settings.
		super().__init__(parent, title=_("Privacy"))
		self.current = current
		self.controls: dict[str, tuple[wx.Choice, list[str]]] = {}
		sizer = wx.BoxSizer(wx.VERTICAL)
		first = None
		for key, label, values in privacyChoices():
			choice = _labeled(
				self,
				sizer,
				label,
				lambda values=values: wx.Choice(self, choices=[text for value, text in values]),
			)
			keys = [value for value, text in values]
			value = current.get(key, "")
			choice.SetSelection(keys.index(value) if value in keys else 0)
			self.controls[key] = (choice, keys)
			first = first or choice
		# Translators: The button that saves the privacy settings.
		_okCancel(self, sizer, _("&Save"))
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		if first:
			first.SetFocus()

	def changes(self) -> dict[str, str]:
		result = {}
		for key, (choice, keys) in self.controls.items():
			value = keys[choice.GetSelection()]
			if value != self.current.get(key, ""):
				result[key] = value
		return result


class ManageGroupDialog(wx.Dialog):
	"""A group's name, description, settings, invite link and members, for its admins."""

	SETTINGS = (
		# Translators: A group setting, like WhatsApp's.
		("announcement", "announce", lambda: _("Only &admins can send messages")),
		# Translators: A group setting, like WhatsApp's.
		("restrict", "restrict", lambda: _("Only admins can &edit group info")),
		# Translators: A group setting, like WhatsApp's.
		("membership_approval_mode", "approval", lambda: _("A&pprove new members")),
		# Translators: A group setting, like WhatsApp's.
		("member_add_mode", "memberAdd", lambda: _("All members can add &others")),
	)

	def __init__(self, parent: "ChatWindow", chat: dict, abilities: dict) -> None:
		# Translators: The title of the dialog that manages a group, with its name.
		super().__init__(parent, title=_("Manage {name}").format(name=chat.get("title", "")))
		self.window = parent
		self.chat = chat
		chatId = chat["id"]
		session = parent.session
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.name = _labeled(
			self,
			sizer,
			# Translators: The label of a group's name in Manage group.
			_("Group &name:"),
			lambda: wx.TextCtrl(self, value=chat.get("title", ""), size=(420, -1)),
		)
		# Translators: A button that saves a group's new name.
		self._button(sizer, _("Save na&me"), lambda: self._save("subject", self.name.GetValue().strip()))
		self.description = _labeled(
			self,
			sizer,
			# Translators: The label of a group's description.
			_("&Description:"),
			lambda: wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(420, 80)),
		)
		# Translators: A button that saves a group's description.
		self.saveDescription = self._button(
			sizer,
			# Translators: A button that saves a group's description.
			_("Save descr&iption"),
			lambda: self._save("description", self.description.GetValue().strip()),
		)
		# Until WhatsApp has given the description, an empty box would save an empty description over it.
		self.description.Disable()
		self.saveDescription.Disable()
		for setting, key, label in self.SETTINGS:
			box = wx.CheckBox(self, label=label())
			box.SetValue(bool(abilities.get(key)))
			box.Bind(wx.EVT_CHECKBOX, lambda evt, setting=setting, box=box: self._setting(setting, box))
			sizer.Add(box, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		row = wx.BoxSizer(wx.HORIZONTAL)
		for label, action in (
			# Translators: A button that copies a group's invite link.
			(_("&Copy invite link"), lambda: self._link(False)),
			# Translators: A button that makes a new invite link, so the old one stops working.
			(_("Rese&t invite link"), lambda: self._link(True)),
			# Translators: A button that adds people to a group.
			(_("Add mem&bers…"), lambda: parent._addMembers(chat)),
			# Translators: A button that lists a group's members, to remove them or make them admins.
			(_("Membe&rs…"), self._members),
		):
			button = wx.Button(self, label=label)
			button.Bind(wx.EVT_BUTTON, lambda evt, action=action: action())
			row.Add(button, 0, wx.RIGHT, 6)
		sizer.Add(row, 0, wx.ALL, 8)
		# Translators: The button that closes Manage group.
		sizer.Add(wx.Button(self, wx.ID_CANCEL, label=_("Close")), 0, wx.ALIGN_RIGHT | wx.ALL, 8)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.name.SetFocus()
		parent._run(lambda: session.contactInfo(chatId), self._gotDescription)

	def _gotDescription(self, info: dict) -> None:
		if not self:
			# Closed before WhatsApp answered.
			return
		self.description.ChangeValue(info.get("description", "") or "")
		self.description.Enable()
		self.saveDescription.Enable()

	def _button(self, sizer: wx.Sizer, label: str, action: Callable[[], None]) -> wx.Button:
		button = wx.Button(self, label=label)
		button.Bind(wx.EVT_BUTTON, lambda evt: action())
		sizer.Add(button, 0, wx.LEFT | wx.TOP, 8)
		return button

	def _save(self, field: str, value: str) -> None:
		if field == "subject" and not value:
			return
		# Translators: Reported after a group's name or description was saved.
		self.window._run(
			lambda: self.window.session.setGroupInfo(self.chat["id"], field, value),
			# Translators: Reported after a group's name or description was saved.
			lambda r: ui.message(_("Saved")),
		)

	def _setting(self, setting: str, box: wx.CheckBox) -> None:
		on = box.GetValue()

		def failed(error: Exception) -> None:
			if box:
				box.SetValue(not on)

		self.window._run(
			lambda: self.window.session.setGroupSetting(self.chat["id"], setting, on),
			# Translators: Reported after a group setting was turned on or off.
			lambda r: ui.message(_("On") if on else _("Off")),
			failed,
		)

	def _link(self, reset: bool) -> None:
		def done(link: str) -> None:
			if link and api.copyToClip(link):
				# Translators: Reported after a group's invite link was copied, or made again and copied.
				ui.message(_("New link copied") if reset else _("Invite link copied"))

		if reset and not askYesNo(
			self,
			# Translators: Asked before making a new invite link for a group.
			_("Reset the invite link? The old link stops working."),
			# Translators: The title of a question in Manage group.
			_("Manage group"),
		):
			return
		self.window._run(lambda: self.window.session.inviteLink(self.chat["id"], reset), done)

	def _members(self) -> None:
		chatId = self.chat["id"]
		session = self.window.session

		def show(people: list[dict]) -> None:
			if not people or not self:
				# Nothing to show, or the dialog was closed before WhatsApp answered.
				return
			# Translators: Added to a group member who is an admin.
			lines = [p["name"] + (", " + _("admin") if p.get("isAdmin") else "") for p in people]
			from .chatWindow import ListDialog

			# Translators: The title of the list of a group's members; its button shows what can be done.
			picker = ListDialog(self, _("Members"), lines, okLabel=_("&Choose"))
			try:
				if picker.ShowModal() != wx.ID_OK:
					return
				person = people[picker.selection()]
			finally:
				picker.Destroy()
			menu = wx.Menu()
			actions = (
				# Translators: An item in a group member's menu, like WhatsApp's.
				("demote", _("Dismiss as admin"))
				if person.get("isAdmin")
				# Translators: An item in a group member's menu, like WhatsApp's.
				else ("promote", _("Make group admin")),
				# Translators: An item in a group member's menu, like WhatsApp's.
				("remove", _("Remove from group")),
			)
			for action, label in actions:
				item = menu.Append(wx.ID_ANY, label)
				menu.Bind(
					wx.EVT_MENU,
					lambda evt, action=action, label=label: self._change(person, action, label),
					item,
				)
			self.PopupMenu(menu)
			menu.Destroy()

		self.window._run(lambda: session.participants(chatId), show)

	def _change(self, person: dict, action: str, label: str) -> None:
		if action == "remove" and not askYesNo(
			self,
			# Translators: Asked before removing someone from a group, with their name.
			_("Remove {name} from the group?").format(name=person["name"]),
			# Translators: The title of a question in Manage group.
			_("Manage group"),
		):
			return
		self.window._run(
			lambda: self.window.session.changeParticipants(self.chat["id"], action, [person["id"]]),
			# Translators: Reported after changing a group member, such as "Done: Make group admin".
			lambda r: ui.message(_("Done: {action}").format(action=label)),
		)
