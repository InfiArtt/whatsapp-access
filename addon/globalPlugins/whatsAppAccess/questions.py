# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Questions before something that cannot be undone, with NVDA's own message dialog.

NVDA 2025.1 replaced wx.MessageBox and gui.messageBox with gui.message.MessageDialog: it plays the right
sound, has context help, and other add-ons and NVDA can find and focus it. The safe answer is always the
default and what Escape or closing the window gives, so Enter alone never deletes or leaves anything.
"""

import wx
from gui.message import DialogType, MessageDialog, ReturnCode


def askYesNo(parent: wx.Window | None, message: str, title: str, warning: bool = True) -> bool:
	"""Ask Yes or No; No is focused first and is also the answer to Escape.

	:param parent: The window the question belongs to.
	:param message: The question.
	:param title: The dialog's title.
	:param warning: Whether it is about something that cannot be undone, which sounds and looks like a warning.
	:return: Whether the user chose Yes.
	"""
	dialog = MessageDialog(
		parent,
		message,
		title,
		dialogType=DialogType.WARNING if warning else DialogType.STANDARD,
		buttons=None,
	)
	dialog.addYesButton().addNoButton(defaultFocus=True, fallbackAction=True)
	# The dialog destroys itself when it closes.
	return dialog.ShowModal() == ReturnCode.YES


def askThreeWay(
	parent: wx.Window | None,
	message: str,
	title: str,
	yesLabel: str,
	noLabel: str,
	cancelLabel: str,
) -> ReturnCode:
	"""Ask between two ways of doing something, or not doing it; Cancel is focused first and is Escape.

	:param yesLabel: The first way, such as "Report and &block".
	:param noLabel: The second way, such as "&Report only".
	:param cancelLabel: Not doing it.
	:return: ReturnCode.YES for the first way, ReturnCode.NO for the second, ReturnCode.CANCEL for neither.
	"""
	dialog = MessageDialog(parent, message, title, dialogType=DialogType.WARNING, buttons=None)
	dialog.addYesButton().addNoButton().addCancelButton(defaultFocus=True, fallbackAction=True)
	dialog.setYesNoCancelLabels(yesLabel, noLabel, cancelLabel)
	return dialog.ShowModal()
