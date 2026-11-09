# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""What NVDA says for chats and messages. Short and most important first, since it is read many times.

It imports nothing from NVDA apart from _(), which addonHandler.initTranslation() installs.
"""

import os
import re
import time

PREVIEW_CHARS = 120
QUOTE_CHARS = 50


def _shorten(text: str, limit: int) -> str:
	text = " ".join(text.split())
	return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def duration(seconds: float) -> str:
	seconds = max(0, round(seconds))
	minutes, seconds = divmod(seconds, 60)
	if minutes:
		# Translators: How long a voice message lasts, such as "1 min 5 sec".
		return _("{minutes} min {seconds} sec").format(minutes=minutes, seconds=seconds)
	# Translators: How long a short voice message lasts, such as "8 sec".
	return _("{seconds} sec").format(seconds=seconds)


# WhatsApp's formatting: ```monospace```, `code`, *bold*, _italic_ and ~strikethrough~. A mark counts only
# next to text and not inside a word, as in WhatsApp, so 2*3*4, snake_case and "a * b" stay as they are.
_FORMATTING = [re.compile(r"```(.+?)```", re.DOTALL)] + [
	re.compile(r"(?<![\w%s])%s(?=\S)([^\n]*?\S)%s(?![\w%s])" % ((re.escape(mark),) * 4))
	for mark in ("`", "*", "_", "~")
]


def plainText(text: str) -> str:
	"""A message's text without WhatsApp's formatting marks, so they are not read out."""
	for pattern in _FORMATTING:
		text = pattern.sub(r"\1", text)
	return text


def content(message: dict) -> str:
	"""What a message says or holds, without who sent it."""
	kind = message.get("type", "")
	text = plainText(message.get("text", ""))
	caption = plainText(message.get("caption", ""))
	if kind == "chat":
		return text
	if kind == "ptt":
		# Translators: A voice message (voice note), with how long it lasts.
		label = _("Voice message, {duration}").format(duration=duration(message.get("duration", 0)))
	elif kind == "audio":
		# Translators: An audio file sent in a chat, with how long it lasts.
		label = _("Audio, {duration}").format(duration=duration(message.get("duration", 0)))
	elif kind == "image":
		# Translators: A photo sent in a chat.
		label = _("Photo")
	elif kind in ("video", "ptv"):
		# Translators: A video sent in a chat.
		label = _("Video")
	elif kind == "document":
		# Translators: A file sent in a chat, with its name.
		label = _("Document {name}").format(name=message.get("filename", "")).strip()
	elif kind == "sticker":
		# Translators: A sticker sent in a chat.
		label = _("Sticker")
	elif kind == "location":
		# Translators: A location shared in a chat.
		label = _("Location")
	elif kind == "vcard":
		# Translators: A contact card shared in a chat, with the contact's name.
		label = _("Contact {name}").format(name=text).strip()
		text = ""
	elif kind == "revoked":
		# Translators: In place of a message its sender deleted for everyone.
		label = _("This message was deleted")
	elif kind == "call_log":
		# Translators: A voice or video call shown in a chat.
		label = _("Call")
	elif kind == "poll_creation":
		poll = message.get("poll") or {}
		# Translators: A poll in a chat: its question, how many options and how many people voted.
		label = _("Poll: {question}, {options} options, {votes} voted").format(
			question=text, options=poll.get("options", 0), votes=poll.get("votes", 0)
		)
		text = ""
	elif kind == "event_creation":
		event = message.get("event") or {}
		# Translators: An event in a group, with its name and when it starts.
		label = _("Event: {name}, {when}").format(name=text, when=timeText(event.get("start", 0)))
		if event.get("canceled"):
			# Translators: Added to an event that was canceled.
			label += ", " + _("canceled")
		text = ""
	elif text:
		# Notices and other kinds, in WhatsApp's own words.
		return text
	elif kind == "newsletter_notification":
		# Translators: A notice from a channel, such as a change to its name or settings.
		label = _("Channel update")
	else:
		# Translators: A message of a kind this add-on cannot show yet, with WhatsApp's name for the kind.
		label = _("Message of type {type}").format(type=kind)
	if message.get("viewOnce"):
		# Translators: Before a photo, video or voice message that can be opened only once, on the phone.
		label = _("View once, open it on your phone: {content}").format(content=label)
	extra = caption or text
	return f"{label}: {extra}" if extra else label


def eventText(event: dict) -> str:
	"""An event's details and who answered, one item per line, to read in a text box."""
	lines = [event.get("name", "")]
	if event.get("canceled"):
		# Translators: Added to an event that was canceled, in its details.
		lines.append(_("canceled"))
	# Translators: When an event starts, in its details.
	lines.append(_("Starts: {when}").format(when=timeText(event.get("start", 0))))
	if event.get("end"):
		# Translators: When an event ends, in its details.
		lines.append(_("Ends: {when}").format(when=timeText(event["end"])))
	if event.get("location"):
		# Translators: Where an event is, in its details.
		lines.append(_("Location: {place}").format(place=event["location"]))
	if event.get("link"):
		# Translators: An event's call link, in its details.
		lines.append(_("Call link: {link}").format(link=event["link"]))
	if event.get("description"):
		lines.append(event["description"])
	for key, label in (
		# Translators: Who answered an event, in its details, with their names.
		("going", _("Going ({count}): {names}")),
		# Translators: Who answered an event, in its details, with their names.
		("maybe", _("Maybe ({count}): {names}")),
		# Translators: Who answered an event, in its details, with their names.
		("notGoing", _("Not going ({count}): {names}")),
	):
		people = event.get(key) or []
		if people:
			lines.append(label.format(count=len(people), names=", ".join(people)))
	return "\n".join(line for line in lines if line)


def sender(message: dict) -> str:
	if message.get("fromMe"):
		# Translators: Who sent a message, when it was the user.
		return _("You")
	# Translators: Who sent a message, when WhatsApp does not know a name.
	return message.get("sender") or _("Unknown")


def timeText(timestamp: float, now: float | None = None) -> str:
	if not timestamp:
		return ""
	now = time.time() if now is None else now
	when = time.localtime(timestamp)
	today = time.localtime(now)
	clock = time.strftime("%H:%M", when)
	if when[:3] == today[:3]:
		return clock
	yesterday = time.localtime(now - 86400)
	if when[:3] == yesterday[:3]:
		# Translators: When a message was sent yesterday, such as "yesterday 21:30".
		return _("yesterday {time}").format(time=clock)
	return time.strftime("%d/%m/%Y %H:%M", when)


def ackText(ack: int | None) -> str:
	if ack is None or ack < 2:
		return ""
	if ack == 2:
		# Translators: The state of a message the user sent: it reached the other person's phone.
		return _("delivered")
	if ack == 3:
		# Translators: The state of a message the user sent: the other person opened it.
		return _("read")
	# Translators: The state of a voice message the user sent: the other person listened to it.
	return _("played")


def messageInChat(message: dict, now: float | None = None) -> str:
	"""A message in a list from several chats: the chat's name first, unless the sender already says it."""
	line = messageLine(message, True, now)
	chat = message.get("chatTitle", "")
	if not chat or (not message.get("fromMe") and message.get("sender") == chat):
		return line
	# Translators: A message in a list from several chats, such as starred messages: the chat, then the message.
	return _("{chat}: {message}").format(chat=chat, message=line)


def messageLine(message: dict, isGroup: bool, now: float | None = None) -> str:
	"""One message in a conversation: who sent it ("You" or their contact name), content, time, state.

	isGroup is kept for callers; the sender is named in every chat, as the user asked.
	"""
	parts = [f"{sender(message)}: {content(message)}"]
	quoted = message.get("quoted")
	if quoted:
		quotedText = _shorten(quoted.get("text") or content({"type": quoted.get("type", "")}), QUOTE_CHARS)
		# Translators: After a message that answers an earlier one: who wrote the earlier one, and its start
		# in quotation marks, such as: quoting Anas: "Ada yang tahu cara pasang add-on?"
		parts.append(_('quoting {sender}: "{text}"').format(sender=sender(quoted), text=quotedText))
	if message.get("edited"):
		# Translators: Said after a message its sender changed after sending it, as WhatsApp shows "Edited".
		parts.append(_("edited"))
	if message.get("isForwarded"):
		# Translators: Said after a message that was forwarded from another chat.
		parts.append(_("forwarded"))
	if message.get("starred"):
		# Translators: Said after a message the user starred.
		parts.append(_("starred"))
	reactions = reactionsText(message.get("reactions"))
	if reactions:
		parts.append(reactions)
	parts.append(timeText(message.get("t", 0), now))
	if message.get("fromMe"):
		parts.append(ackText(message.get("ack")))
	return ", ".join(p for p in parts if p)


def reactionsText(reactions: list[dict] | None) -> str:
	"""The reactions on a message, such as "reactions: 👍 2, ❤️ 1, yours 👍"."""
	if not reactions:
		return ""
	counts = ", ".join(f"{r['emoji']} {r['count']}" for r in reactions)
	mine = [r["emoji"] for r in reactions if r.get("mine")]
	if mine:
		# Translators: Reactions on a message and which one is the user's, such as "reactions: 👍 2, yours 👍".
		return _("reactions: {counts}, yours {mine}").format(counts=counts, mine=" ".join(mine))
	# Translators: Reactions on a message, such as "reactions: 👍 2, ❤️ 1".
	return _("reactions: {counts}").format(counts=counts)


def disappearingText(seconds: int) -> str:
	"""That a chat's new messages disappear, and after how long, as WhatsApp's timer says."""
	days = round(seconds / 86400)
	if days == 1:
		# Translators: Said for a chat whose new messages disappear after a day.
		return _("disappearing messages, 1 day")
	if days >= 2:
		# Translators: Said for a chat whose new messages disappear after some days, such as 7.
		return _("disappearing messages, {count} days").format(count=days)
	# Translators: Said for a chat whose new messages disappear after some hours, such as 24.
	return _("disappearing messages, {count} hours").format(count=max(1, round(seconds / 3600)))


def chatLine(chat: dict, now: float | None = None) -> str:
	"""One chat in the list: name, unread count, then the last message."""
	parts = [chat.get("title", "")]
	unread = chat.get("unread", 0)
	if unread:
		# Translators: How many messages in a chat the user has not read.
		parts.append(_("{count} unread").format(count=unread))
	if chat.get("pinned"):
		# Translators: Said for a chat the user pinned to the top of the list.
		parts.append(_("pinned"))
	if chat.get("muted"):
		# Translators: Said for a chat whose notifications the user turned off.
		parts.append(_("muted"))
	if chat.get("disappearing"):
		parts.append(disappearingText(chat["disappearing"]))
	if chat.get("ongoingCall"):
		# Translators: Said for a group with a voice or video call going on now, which the user can join.
		parts.append(_("call in progress"))
	last = chat.get("last")
	if last:
		preview = content(last)
		if last.get("fromMe") or chat.get("isGroup"):
			preview = f"{sender(last)}: {preview}"
		parts.append(_shorten(preview, PREVIEW_CHARS))
		parts.append(timeText(last.get("t", 0), now))
	return ", ".join(p for p in parts if p)


def announcement(
	message: dict, chatTitle: str, isGroup: bool, inOpenChat: bool, withContent: bool = True
) -> str:
	"""What to say when a message arrives, in place of WhatsApp's notification.

	In the open chat it is just the message, as in the list; elsewhere it says where it came from.
	Without content, only who it is from is said.
	"""
	if not withContent:
		if isGroup:
			# Translators: Read out for a new group message when the user chose not to hear what it says.
			return _("New message in {chat} from {sender}").format(chat=chatTitle, sender=sender(message))
		# Translators: Read out for a new message when the user chose not to hear what it says.
		return _("New message from {sender}").format(sender=chatTitle)
	if inOpenChat:
		return f"{sender(message)}: {content(message)}"
	if isGroup:
		# Translators: Read out when a message arrives in a group that is not open in the add-on's window.
		return _("New message in {chat} from {sender}: {message}").format(
			chat=chatTitle, sender=sender(message), message=content(message)
		)
	# Translators: Read out when a message arrives in a personal chat that is not open in the add-on's window.
	return _("New message from {sender}: {message}").format(sender=chatTitle, message=content(message))


PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".3gp", ".mov", ".m4v", ".webm", ".mkv"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".amr", ".flac"}


def fileKind(name: str) -> str:
	"""How WhatsApp should send a file, from its extension: photo, video, audio or document.
	Anything else, such as apk, exe, pdf or zip, goes as a document, as in WhatsApp's attach menu."""
	extension = os.path.splitext(name)[1].lower()
	if extension in PHOTO_EXTENSIONS:
		return "photo"
	if extension in VIDEO_EXTENSIONS:
		return "video"
	if extension in AUDIO_EXTENSIONS:
		return "audio"
	return "document"


def fileKindName(kind: str) -> str:
	if kind == "photo":
		# Translators: How an attached file will be sent.
		return _("photo")
	if kind == "video":
		# Translators: How an attached file will be sent.
		return _("video")
	if kind == "audio":
		# Translators: How an attached file will be sent.
		return _("audio")
	# Translators: How an attached file will be sent: as a file, not shown as a photo or video.
	return _("document")


def _names(names: list[str]) -> str:
	if len(names) <= 1:
		return "".join(names)
	# Translators: Joins the last two names in a list, such as "Anas and Budi".
	return _("{first} and {last}").format(first=", ".join(names[:-1]), last=names[-1])


def presenceText(presence: dict | None, now: float | None = None) -> str:
	"""What WhatsApp shows under a chat's name: online, last seen, typing, recording audio."""
	if not presence:
		return ""
	if presence.get("kind") == "group":
		typing, recording = presence.get("typing") or [], presence.get("recording") or []
		parts = []
		if typing:
			# Translators: Who is typing in a group, such as "Anas and Budi typing…".
			parts.append(_("{names} typing…").format(names=_names(typing)))
		if recording:
			# Translators: Who is recording a voice message in a group.
			parts.append(_("{names} recording audio…").format(names=_names(recording)))
		return ", ".join(parts)
	state = presence.get("state")
	if state == "typing":
		# Translators: The other person in a chat is typing.
		return _("typing…")
	if state == "recording":
		# Translators: The other person in a chat is recording a voice message.
		return _("recording audio…")
	if state == "online":
		# Translators: The other person in a chat is using WhatsApp now.
		return _("online")
	lastSeen = presence.get("lastSeen")
	if lastSeen:
		# Translators: When the other person in a chat last used WhatsApp, such as "last seen 09:55".
		return _("last seen {time}").format(time=timeText(lastSeen, now))
	# Translators: WhatsApp does not say when the other person was last online; they may hide it.
	return _("no info")


def isActivity(presence: dict | None) -> bool:
	"""Whether someone is typing or recording, which is read out as it happens."""
	if not presence:
		return False
	if presence.get("kind") == "group":
		return bool(presence.get("typing") or presence.get("recording"))
	return presence.get("state") in ("typing", "recording")


_LINK_PATTERN = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)


def linksIn(text: str) -> list[str]:
	"""Web links in a message, in order, without repeats or trailing punctuation."""
	links = []
	for match in _LINK_PATTERN.findall(text or ""):
		link = match.rstrip(".,;:!?)]}")
		if link not in links:
			links.append(link)
	return links


def receiptLines(receipts: dict, isGroup: bool) -> list[str]:
	"""What message info says, one line each: sent, then who received, read and played it."""
	lines = []
	if receipts.get("t"):
		# Translators: In message info: when the message was sent.
		lines.append(_("Sent {time}").format(time=timeText(receipts["t"])))
	groups = (
		# Translators: In message info: who opened the message, with times.
		(_("Read by"), receipts.get("read") or []),
		# Translators: In message info: who listened to the voice message, with times.
		(_("Played by"), receipts.get("played") or []),
		# Translators: In message info: whose phones the message reached, with times.
		(_("Delivered to"), receipts.get("delivered") or []),
	)
	for label, people in groups:
		if people:
			names = ", ".join(f"{p['name']} {timeText(p['t'])}" for p in people)
			lines.append(f"{label}: {names}")
	if isGroup:
		if receipts.get("readRemaining"):
			# Translators: In message info: how many people have not read the message yet.
			lines.append(_("Not read yet by {count}").format(count=receipts["readRemaining"]))
		if receipts.get("deliveryRemaining"):
			# Translators: In message info: how many people's phones have not received the message yet.
			lines.append(_("Not delivered yet to {count}").format(count=receipts["deliveryRemaining"]))
	elif len(lines) == 1:
		state = ackText(receipts.get("ack"))
		if state:
			lines.append(state)
	return lines


def firstUnreadId(messages: list[dict], unread: int) -> str | None:
	"""The first of the last `unread` messages from other people: where WhatsApp's "unread" divider is."""
	if unread <= 0:
		return None
	seen = 0
	for message in reversed(messages):
		if message.get("fromMe"):
			continue
		seen += 1
		if seen == unread:
			return message.get("id")
	# Fewer were loaded than were unread: the oldest loaded one from someone else.
	return next((m.get("id") for m in messages if not m.get("fromMe")), None)


def statusLine(person: dict, now: float | None = None) -> str:
	"""One person in the status list: name, how many statuses are new, and when the last was posted."""
	parts = [person.get("name", "")]
	unread = person.get("unread", 0)
	total = len(person.get("items") or [])
	if unread:
		# Translators: In the status list: how many of a person's statuses the user has not seen.
		parts.append(_("{count} new").format(count=unread))
	else:
		# Translators: In the status list: how many statuses a person posted, all seen.
		parts.append(_("{count} seen").format(count=total))
	items = person.get("items") or []
	if items:
		parts.append(timeText(items[-1].get("t", 0), now))
	return ", ".join(p for p in parts if p)


def statusItemText(person: dict, index: int, now: float | None = None) -> str:
	"""One status as the viewer says it: who, which of how many, when, and what it is."""
	items = person.get("items") or []
	item = items[index]
	# Translators: Which status of a person is shown, such as "2 of 5".
	position = _("{position} of {count}").format(position=index + 1, count=len(items))
	return ", ".join(
		p for p in (person.get("name", ""), position, timeText(item.get("t", 0), now), content(item)) if p
	)


def callLogLine(call: dict, now: float | None = None) -> str:
	"""One call in the recent calls: who, which way and kind, how long, and when."""
	if call.get("ongoing"):
		if call.get("joined"):
			# Translators: The group call the user is in, at the top of the recent calls.
			return _("{name}, call in progress, you are in it").format(name=call.get("name", ""))
		# Translators: A group call going on now, at the top of the recent calls; Enter joins it.
		return _("{name}, call in progress, join").format(name=call.get("name", ""))
	kind = (
		# Translators: A video call in the recent calls list.
		_("video call")
		if call.get("video")
		# Translators: A voice call in the recent calls list.
		else _("voice call")
	)
	if call.get("outgoing"):
		# Translators: In the recent calls list, a call the user made, such as "outgoing voice call".
		what = _("outgoing {kind}").format(kind=kind)
	elif call.get("missed"):
		# Translators: In the recent calls list, a call the user did not answer.
		what = _("missed {kind}").format(kind=kind)
	else:
		# Translators: In the recent calls list, a call the user answered.
		what = _("incoming {kind}").format(kind=kind)
	parts = [call.get("name", ""), what]
	if call.get("duration"):
		parts.append(duration(call["duration"]))
	parts.append(timeText(call.get("t", 0), now))
	return ", ".join(p for p in parts if p)


def copiedText(messages: list[dict]) -> str:
	"""Several messages as WhatsApp copies them: "[10:15, 8/11/2026] Anas: Oke", one per line."""
	lines = []
	for message in messages:
		when = time.localtime(message.get("t") or 0)
		stamp = f"{time.strftime('%H:%M', when)}, {when.tm_mday}/{when.tm_mon}/{when.tm_year}"
		text = message.get("text") or message.get("caption") or content(message)
		lines.append(f"[{stamp}] {sender(message)}: {text}")
	return "\n".join(lines)


def participantLine(person: dict) -> str:
	"""One person in a group call: their name, then whether they joined, are muted or raised a hand."""
	parts = [person.get("name", "")]
	if not person.get("connected"):
		# Translators: Said for someone invited to a group call who has not joined.
		parts.append(_("not joined"))
	else:
		if person.get("hand"):
			# Translators: Said for someone in a group call who raised their hand.
			parts.append(_("hand raised"))
		if person.get("muted"):
			# Translators: Said for someone in a group call whose microphone is off.
			parts.append(_("muted"))
	return ", ".join(p for p in parts if p)


def callChanges(before: list[dict], after: list[dict]) -> list[tuple[str, str]]:
	"""What changed among a group call's people: (kind, name) with kind joined, left, hand or reaction;
	for a reaction, name also holds the emoji."""
	old = {p["id"]: p for p in before}
	changes = []
	for person in after:
		was = old.get(person["id"], {})
		name = person.get("name", "")
		if person.get("connected") and not was.get("connected"):
			changes.append(("joined", name))
		elif was.get("connected") and not person.get("connected"):
			changes.append(("left", name))
		if person.get("connected") and person.get("hand") and not was.get("hand"):
			changes.append(("hand", name))
		reaction = person.get("reaction") or ""
		if person.get("connected") and reaction and reaction != was.get("reaction"):
			changes.append(("reaction", f"{name} {reaction}"))
	return changes
