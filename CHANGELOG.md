# Changelog

All notable changes to WhatsApp Access are listed here. Each release on GitHub uses its section as the
notes the add-on shows before it installs an update.

## [0.2.0]

Almost everything WhatsApp Web does, now in the add-on.

- New sections: **Starred** (Ctrl+5), **Channels** (Ctrl+6), **Communities** (Ctrl+7) and
  **Settings** (Ctrl+8).
- Channels: read posts, react, follow and unfollow, and find new channels.
- Communities: their groups and announcements; join a group or ask to.
- Settings: your profile (name, About, photo), privacy settings and blocked contacts.
- Status: write a text status, post a photo or video, and see who saw your statuses.
- Messages: create polls, pin and unpin, reply privately in groups, see who reacted, send contact
  cards and stickers, and answer or create events.
- Search the messages of every chat (Ctrl+Shift+F); a chat's media, links and documents; pinned
  messages; unread mentions in groups (Ctrl+Shift+M).
- Groups: create one (Ctrl+Shift+N); for admins, name, description, settings, invite link and
  members. Exit a group, block, report, clear or delete a chat, disappearing messages, favorites.
- Group voice calls: start one, or join the one going on; groups with a call say so in the chat list
  and at the top of Calls, where Enter joins. Joining a call you are invited to again answers it.
- In a group call: the participants, who is muted or raised a hand; raise your hand (Ctrl+H), send
  reactions, ask someone to mute, and hear who is speaking (Ctrl+Shift+G). Joins, leaves, raised
  hands and reactions are said with small sounds.
- During a call: NVDA+Alt+M mutes or unmutes from any program, with a sound for each; the WhatsApp
  window shows Return to call and Mute microphone; NVDA says when someone else mutes you.
- Last seen, online, typing and recording now arrive: you are online while the WhatsApp window is in
  front, and offline when you switch away or close it, as with WhatsApp Web.
- Chats with disappearing messages say so, with how long.
- People not in your contacts are named by their contact or phone number, not a long number.
- NVDA says when WhatsApp loses its connection and when it is back.
- Notices and other special messages are read in WhatsApp's words; view-once media says to open it
  on the phone.

Fixed:

- Labels in the new dialogs were read for the wrong boxes.
- When a dialog or a question from NVDA was open, coming back to WhatsApp said "unavailable"; it now
  goes to the open question.
- Menus and call buttons no longer have clashing or extra Alt keys.
- The Open chat button is gone (Enter opens a chat); the Sections list opens with Enter.

## [0.1.0]

The first version.

- Your WhatsApp chats in a window made for NVDA, with WhatsApp Web kept in a hidden browser (Brave,
  Chrome or another Chromium browser) or in your own browser.
- Chats, Status, Calls and Archived sections, with filters for unread chats, groups and favorites.
- Read, write, reply, react, edit, delete, forward, star and copy messages; mentions in groups; polls;
  message info; search in a chat.
- Clear voice notes: stereo, 128 kbps, with the browser's sound processing off.
- Send photos, videos, audio and documents, also by pasting them.
- Select several messages or chats with Shift+arrows and act on them all.
- Status updates that play by themselves; like, reply and download them.
- Voice calls: answer, decline, mute and end from anywhere, and call people from a chat.
- Notifications read out by the add-on, with sounds and rules for each chat.
- Five volumes, changed at once with F6, F7 and F8.
- Updates from the add-on's GitHub page, checked once a day.
