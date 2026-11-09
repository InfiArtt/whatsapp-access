import time

import pytest
from whatsAppAccess import messageText

NOW = time.mktime((2026, 11, 8, 10, 0, 0, 0, 0, -1))
TODAY_0815 = time.mktime((2026, 11, 8, 8, 15, 0, 0, 0, -1))
YESTERDAY_2130 = time.mktime((2026, 11, 7, 21, 30, 0, 0, 0, -1))


def test_duration():
    assert messageText.duration(8.4) == "8 sec"
    assert messageText.duration(65) == "1 min 5 sec"


def test_times():
    assert messageText.timeText(TODAY_0815, NOW) == "08:15"
    assert messageText.timeText(YESTERDAY_2130, NOW) == "yesterday 21:30"
    assert messageText.timeText(time.mktime((2026, 10, 1, 9, 5, 0, 0, 0, -1)), NOW) == "01/10/2026 09:05"


def test_personal_chat_message_names_the_contact():
    message = {"type": "chat", "text": "Halo", "t": TODAY_0815, "sender": "Budi"}
    assert messageText.messageLine(message, isGroup=False, now=NOW) == "Budi: Halo, 08:15"


def test_an_edited_message_says_so():
    message = {"type": "chat", "text": "Halo semua", "t": TODAY_0815, "sender": "Budi", "edited": True}
    assert messageText.messageLine(message, isGroup=False, now=NOW) == "Budi: Halo semua, edited, 08:15"


def test_own_message_says_you_and_its_state():
    message = {"type": "chat", "text": "Siap", "t": TODAY_0815, "fromMe": True, "ack": 3}
    assert messageText.messageLine(message, isGroup=False, now=NOW) == "You: Siap, 08:15, read"


def test_group_voice_message_with_reply_and_forward():
    message = {
        "type": "ptt",
        "duration": 8,
        "sender": "Dimas",
        "t": TODAY_0815,
        "isForwarded": True,
        "quoted": {"text": "Ada yang tahu cara pasang add-on?", "type": "chat", "sender": "Anas"},
    }
    assert messageText.messageLine(message, isGroup=True, now=NOW) == (
        'Dimas: Voice message, 8 sec, quoting Anas: "Ada yang tahu cara pasang add-on?", forwarded, 08:15'
    )


def test_media_shows_caption_not_thumbnail():
    assert messageText.content({"type": "image", "caption": "Pemandangan"}) == "Photo: Pemandangan"
    assert messageText.content({"type": "document", "filename": "laporan.pdf"}) == "Document laporan.pdf"


def test_chat_line():
    chat = {
        "title": "KartunetClub",
        "isGroup": True,
        "unread": 291,
        "muted": True,
        "last": {"type": "chat", "text": "Selamat pagi   semua", "sender": "Dimas", "t": TODAY_0815},
    }
    assert messageText.chatLine(chat, now=NOW) == (
        "KartunetClub, 291 unread, muted, Dimas: Selamat pagi semua, 08:15"
    )


def test_long_previews_are_shortened():
    chat = {"title": "A", "last": {"type": "chat", "text": "x" * 500, "t": 0}}
    line = messageText.chatLine(chat, now=NOW)
    assert len(line) < 140
    assert line.endswith("…")


def test_announcements():
    message = {"type": "chat", "text": "Halo", "sender": "Budi"}
    assert (
        messageText.announcement(message, "Budi", isGroup=False, inOpenChat=False)
        == "New message from Budi: Halo"
    )
    assert messageText.announcement(message, "Budi", isGroup=False, inOpenChat=True) == "Budi: Halo"
    assert messageText.announcement(message, "Tim", isGroup=True, inOpenChat=True) == "Budi: Halo"
    assert messageText.announcement(message, "Tim", isGroup=True, inOpenChat=False) == (
        "New message in Tim from Budi: Halo"
    )


def test_the_open_chat_says_the_message_even_when_content_is_off():
    message = {"type": "chat", "text": "Halo", "sender": "Claude"}
    assert (
        messageText.announcement(message, "Claude", isGroup=False, inOpenChat=True, withContent=False)
        == "Claude: Halo"
    )
    assert (
        messageText.announcement(message, "Claude", isGroup=False, inOpenChat=False, withContent=False)
        == "New message from Claude"
    )


def test_the_window_title_names_the_chat_without_a_phone_number():
    assert messageText.windowTitleName("Qisti") == "Qisti"
    assert messageText.windowTitleName("+6285640306004 ~Prima Agus Setiyawan") == "~Prima Agus Setiyawan"
    assert messageText.windowTitleName("~Prima Agus Setiyawan") == "~Prima Agus Setiyawan"
    assert messageText.windowTitleName("+6285640306004") == "+6285640306004"
    assert messageText.windowTitleName("Tim ~Kreatif") == "Tim ~Kreatif"


def test_a_deleted_message_is_said_deleted_once():
    deleted = {"type": "revoked", "text": "This message was deleted", "sender": "~Ali"}
    assert messageText.content(deleted) == "This message was deleted"
    chat = {"title": "VoiceOver Accessibility", "isGroup": True, "last": deleted}
    assert messageText.chatLine(chat).count("This message was deleted") == 1


def test_messages_read_together_are_said_once():
    assert messageText.acksText([3, 3, 3, 3, 3]) == "read"
    assert messageText.acksText([2, 3]) == "read"
    assert messageText.acksText([2]) == "delivered"
    assert messageText.acksText([]) == ""


def test_reply_to_own_message_says_you():
    message = {
        "type": "chat",
        "text": "Oke",
        "sender": "Anas",
        "t": TODAY_0815,
        "quoted": {"text": "Jadi?", "fromMe": True},
    }
    assert messageText.messageLine(message, isGroup=True, now=NOW) == 'Anas: Oke, quoting You: "Jadi?", 08:15'


def test_presence_of_a_person():
    assert messageText.presenceText({"kind": "user", "state": "typing"}) == "typing…"
    assert messageText.presenceText({"kind": "user", "state": "recording"}) == "recording audio…"
    assert messageText.presenceText({"kind": "user", "state": "online"}) == "online"
    seen = {"kind": "user", "state": "offline", "lastSeen": TODAY_0815}
    assert messageText.presenceText(seen, now=NOW) == "last seen 08:15"
    assert messageText.presenceText({"kind": "user", "state": "offline", "lastSeen": None}) == "no info"


def test_presence_in_a_group():
    group = {"kind": "group", "typing": ["Anas", "Budi"], "recording": ["Citra"]}
    assert messageText.presenceText(group) == "Anas and Budi typing…, Citra recording audio…"
    assert messageText.presenceText({"kind": "group", "typing": [], "recording": []}) == ""


def test_only_typing_and_recording_are_read_out_as_they_happen():
    assert messageText.isActivity({"kind": "user", "state": "typing"})
    assert not messageText.isActivity({"kind": "user", "state": "online"})
    assert messageText.isActivity({"kind": "group", "typing": ["Anas"], "recording": []})
    assert not messageText.isActivity(None)


def test_poll_in_the_message_list():
    message = {"type": "poll_creation", "text": "Teknis relawan", "poll": {"options": 4, "votes": 22}}
    assert messageText.content(message) == "Poll: Teknis relawan, 4 options, 22 voted"


def test_file_kinds_follow_whatsapps_attach_menu():
    assert messageText.fileKind(r"C:\foto\Liburan.JPG") == "photo"
    assert messageText.fileKind("klip.mp4") == "video"
    assert messageText.fileKind("lagu.mp3") == "audio"
    for name in ("app.apk", "setup.exe", "laporan.pdf", "arsip.zip", "README"):
        assert messageText.fileKind(name) == "document"


def test_reactions_are_shown_with_the_users_own():
    message = {
        "type": "chat",
        "text": "Oke",
        "sender": "Anas",
        "t": TODAY_0815,
        "reactions": [
            {"emoji": "\U0001f44d", "count": 2, "mine": True},
            {"emoji": "\u2764\ufe0f", "count": 1},
        ],
    }
    assert messageText.messageLine(message, isGroup=True, now=NOW) == (
        "Anas: Oke, reactions: \U0001f44d 2, \u2764\ufe0f 1, yours \U0001f44d, 08:15"
    )
    message["reactions"] = [{"emoji": "\U0001f602", "count": 3}]
    assert "reactions: \U0001f602 3, 08:15" in messageText.messageLine(message, isGroup=True, now=NOW)


def test_links_in_a_message():
    text = "Lihat https://infiartt.com/blog, dan www.nvaccess.org. Juga https://infiartt.com/blog lagi."
    assert messageText.linksIn(text) == ["https://infiartt.com/blog", "www.nvaccess.org"]
    assert messageText.linksIn("tanpa tautan") == []


def test_message_info_in_a_group():
    # receiptLines compares with the real clock, so this message was sent today.
    today = time.mktime(time.localtime()[:3] + (8, 15, 0, 0, 0, -1))
    receipts = {
        "t": today,
        "read": [{"name": "Anas", "t": today}],
        "delivered": [{"name": "Rexya", "t": today}],
        "played": [],
        "readRemaining": 6,
        "deliveryRemaining": 1,
    }
    assert messageText.receiptLines(receipts, isGroup=True) == [
        "Sent 08:15",
        "Read by: Anas 08:15",
        "Delivered to: Rexya 08:15",
        "Not read yet by 6",
        "Not delivered yet to 1",
    ]


def test_first_unread_message_skips_the_users_own():
    messages = [
        {"id": "a"},
        {"id": "b"},
        {"id": "mine", "fromMe": True},
        {"id": "c"},
        {"id": "d"},
    ]
    assert messageText.firstUnreadId(messages, 0) is None
    assert messageText.firstUnreadId(messages, 2) == "c"
    assert messageText.firstUnreadId(messages, 3) == "b"
    assert messageText.firstUnreadId(messages, 50) == "a"


def test_status_list_and_viewer():
    person = {
        "name": "moon",
        "unread": 2,
        "items": [
            {"type": "video", "caption": "pantai", "t": TODAY_0815},
            {"type": "chat", "text": "selamat pagi", "t": TODAY_0815},
        ],
    }
    assert messageText.statusLine(person, now=NOW) == "moon, 2 new, 08:15"
    assert messageText.statusItemText(person, 1, now=NOW) == "moon, 2 of 2, 08:15, selamat pagi"
    assert messageText.statusItemText(person, 0, now=NOW) == "moon, 1 of 2, 08:15, Video: pantai"


def test_recent_calls():
    assert messageText.callLogLine({"name": "Rafli", "duration": 15, "t": TODAY_0815}, now=NOW) == (
        "Rafli, incoming voice call, 15 sec, 08:15"
    )
    assert messageText.callLogLine(
        {"name": "Qisti", "missed": True, "video": True, "t": TODAY_0815}, now=NOW
    ) == ("Qisti, missed video call, 08:15")
    assert messageText.callLogLine({"name": "Anas", "outgoing": True, "t": TODAY_0815}, now=NOW) == (
        "Anas, outgoing voice call, 08:15"
    )


def test_several_messages_are_copied_as_whatsapp_does():
    messages = [
        {"type": "chat", "text": "Gimana?", "sender": "Rexya", "t": TODAY_0815},
        {"type": "chat", "text": "Oke", "fromMe": True, "t": TODAY_0815},
        {"type": "ptt", "duration": 8, "sender": "Rexya", "t": TODAY_0815},
    ]
    assert messageText.copiedText(messages) == (
        "[08:15, 8/11/2026] Rexya: Gimana?\n[08:15, 8/11/2026] You: Oke\n[08:15, 8/11/2026] Rexya: Voice message, 8 sec"
    )


def test_notices_are_read_in_whatsapps_words():
    notice = {"type": "gp2", "text": "Anas added Qisti"}
    assert messageText.content(notice) == "Anas added Qisti"
    assert messageText.content({"type": "gp2"}) == "Message of type gp2"


def test_view_once_says_to_open_it_on_the_phone():
    message = {"type": "image", "viewOnce": True}
    assert messageText.content(message) == "View once, open it on your phone: Photo"


def test_event_details_list_who_answered():
    event = {
        "name": "Rapat Relawan",
        "start": TODAY_0815,
        "location": "Aula",
        "going": ["Anas", "Qisti"],
        "maybe": [],
        "notGoing": ["Rexya"],
    }
    lines = messageText.eventText(event).split("\n")
    assert lines[0] == "Rapat Relawan"
    assert "Location: Aula" in lines
    assert "Going (2): Anas, Qisti" in lines
    assert "Not going (1): Rexya" in lines
    assert not any(line.startswith("Maybe") for line in lines)


def test_messages_from_several_chats_name_the_chat_once():
    personal = {"type": "chat", "text": "Halo", "sender": "Gwen", "chatTitle": "Gwen", "t": TODAY_0815}
    group = {"type": "chat", "text": "Halo", "sender": "Anas", "chatTitle": "Relawan", "t": TODAY_0815}
    assert messageText.messageInChat(personal, now=NOW).startswith("Gwen: Halo")
    assert messageText.messageInChat(group, now=NOW).startswith("Relawan: Anas: Halo")


def test_chats_with_disappearing_messages_say_so():
    chat = {"title": "Rafli", "disappearing": 604800}
    assert messageText.chatLine(chat) == "Rafli, disappearing messages, 7 days"
    assert messageText.disappearingText(86400) == "disappearing messages, 1 day"
    assert messageText.disappearingText(7776000) == "disappearing messages, 90 days"


def test_group_call_people_and_changes():
    before = [
        {"id": "1", "name": "Anas", "connected": True},
        {"id": "2", "name": "Qisti", "connected": False},
        {"id": "3", "name": "Rexya", "connected": True},
    ]
    after = [
        {"id": "1", "name": "Anas", "connected": True, "hand": True},
        {"id": "2", "name": "Qisti", "connected": True, "muted": True},
        {"id": "3", "name": "Rexya", "connected": False},
    ]
    assert messageText.callChanges(before, after) == [
        ("hand", "Anas"),
        ("joined", "Qisti"),
        ("left", "Rexya"),
    ]
    assert messageText.participantLine(after[0]) == "Anas, hand raised"
    assert messageText.participantLine(after[1]) == "Qisti, muted"
    assert messageText.participantLine(after[2]) == "Rexya, not joined"


def test_group_call_reactions_are_noticed_once():
    before = [{"id": "1", "name": "Anas", "connected": True, "reaction": ""}]
    after = [{"id": "1", "name": "Anas", "connected": True, "reaction": "👍"}]
    assert messageText.callChanges(before, after) == [("reaction", "Anas 👍")]
    assert messageText.callChanges(after, after) == []


def test_ongoing_group_calls_offer_to_join():
    assert messageText.callLogLine({"name": "Relawan", "ongoing": True}) == "Relawan, call in progress, join"
    assert messageText.callLogLine({"name": "Relawan", "ongoing": True, "joined": True}) == (
        "Relawan, call in progress, you are in it"
    )
    assert messageText.chatLine({"title": "Relawan", "ongoingCall": True}) == "Relawan, call in progress"


def test_replies_say_what_they_quote():
    reply = {
        "type": "chat",
        "text": "hello",
        "fromMe": True,
        "t": TODAY_0815,
        "quoted": {"type": "chat", "text": "a", "fromMe": True},
    }
    assert 'quoting You: "a"' in messageText.messageLine(reply, False, now=NOW)


def test_formatting_marks_are_not_read():
    assert messageText.plainText("*PENTING* besok _jam 8_") == "PENTING besok jam 8"
    assert messageText.plainText("~salah~ benar, ```kode```, `x = 1`") == "salah benar, kode, x = 1"
    assert messageText.plainText("*_tebal miring_*") == "tebal miring"


def test_marks_that_are_not_formatting_stay():
    for text in ("2*3*4", "snake_case_name", "a * b * c", "harga 5*", "* poin", "_ awal", "**", "a__b"):
        assert messageText.plainText(text) == text


def test_formatting_ends_at_the_line():
    assert messageText.plainText("*satu\ndua*") == "*satu\ndua*"


def test_a_formatted_message_is_read_without_marks():
    message = {"type": "chat", "text": "*Rapat* jam 9", "t": TODAY_0815, "sender": "Budi"}
    assert messageText.messageLine(message, isGroup=False, now=NOW) == "Budi: Rapat jam 9, 08:15"


def test_polls_whatsapp_would_refuse_are_caught_first():
    assert messageText.pollProblem("Makan?", ["Nasi", "Mie"]) == ""
    assert "two options" in messageText.pollProblem("Makan?", ["Nasi"])
    assert "at most 12" in messageText.pollProblem("Makan?", [str(n) for n in range(13)])
    assert messageText.pollProblem("Makan?", [str(n) for n in range(12)]) == ""
    assert "the same" in messageText.pollProblem("Makan?", ["Nasi", "nasi"])
    assert "255 characters" in messageText.pollProblem("x" * 256, ["a", "b"])
    assert "100 characters" in messageText.pollProblem("Makan?", ["a", "b" * 101])


def test_chats_marked_unread_say_so_and_count_as_unread():
    chat = {"title": "Budi", "unread": 0, "markedUnread": True, "last": None}
    assert messageText.chatLine(chat, now=NOW) == "Budi, marked unread"
    assert messageText.isUnread(chat)
    assert messageText.isUnread({"unread": 2})
    assert not messageText.isUnread({"unread": 0, "markedUnread": False})


@pytest.mark.parametrize(
    "link",
    [
        "https://chat.whatsapp.com/AbCdEfGhIjKlMnOpQrStUv",
        "chat.whatsapp.com/invite/AbCdEfGhIjKlMnOpQrStUv",
        "https://whatsapp.com/channel/0029VaAbCdEfGhIjKlMnOp12",
        "https://www.whatsapp.com/channel/0029VaAbCdEfGhIjKlMnOp12",
        "https://call.whatsapp.com/voice/AbCdEfGhIjKlMnOpQr",
        "https://wa.me/6281234567890?text=halo",
        "wa.me/6281234567890",
        "https://api.whatsapp.com/send?phone=6281234567890",
    ],
)
def test_whatsapp_links_open_in_the_addon(link):
    assert messageText.isWhatsAppLink(link)


@pytest.mark.parametrize(
    "link",
    [
        "https://example.com/chat.whatsapp.com/AbCd",
        "https://chat.whatsapp.com.example.com/AbCd",
        "https://www.whatsapp.com/download",
        "https://web.whatsapp.com/",
        "https://infiartt.com",
    ],
)
def test_other_links_open_in_the_browser(link):
    assert not messageText.isWhatsAppLink(link)


def test_community_announcements_say_how_many_replies():
    message = {"type": "chat", "text": "Rapat besok", "sender": "Admin", "t": TODAY_0815, "replies": 13}
    assert messageText.messageLine(message, isGroup=True, now=NOW) == "Admin: Rapat besok, 13 replies, 08:15"
    assert messageText.repliesText(1) == "1 reply"


def test_chats_where_the_user_cannot_send_say_why():
    assert "Only admins" in messageText.cannotSendText({"isGroup": True, "canSend": False})
    assert "replies" in messageText.cannotSendText({"isGroup": True, "announcementGroup": True})
    assert "no longer a member" in messageText.cannotSendText({"isGroup": True, "left": True})
    assert "channel" in messageText.cannotSendText({"isChannel": True})
