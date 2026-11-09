# Changelog

All notable changes to WhatsApp Access are listed here. Each release on GitHub uses its section as the
notes the add-on shows before it installs an update.

## [Unreleased]

Safer files and a safer place for your WhatsApp login.

- Enter on a file opens it only when it is a picture, video, sound or document. Anyone can send a
  program named like a document, such as "invoice.pdf.exe", so the add-on no longer opens programs,
  scripts, shortcuts, archives or Office files with macros; it says so, and Alt+D still saves them.
- Every file the add-on downloads gets the mark Windows gives files from the internet, so SmartScreen
  and Office's Protected View check it, as they do for files from a browser.
- File names from messages are cleaned more carefully: hidden characters that can disguise a name's
  real ending are removed, Windows device names such as NUL can no longer be used, long names are
  shortened, a file that is already there is never replaced, and a download that fails halfway leaves
  nothing behind.
- With an installed NVDA, the WhatsApp login now lives in your Windows account's own folder
  (LocalAppData\NVDA WhatsApp Access), and is moved there by itself the first time. In NVDA's
  configuration folder it was copied, with the rest of that folder, when you chose "Use currently saved
  settings during sign-in and on secure screens", to a place every account on the computer can read.
  If you ever pressed that button, press it again once after updating, so the old copy is replaced.
  A portable NVDA keeps the login with its own settings, as before.
- The add-on does nothing on the Windows sign-in screen and other secure screens.

## [0.4.1]

Translation, closing WhatsApp fully, and fixes for groups. This includes everything from 0.4.0.

- Translate, only when you ask. Ctrl+T on a message reads it in your language; twice shows the
  translation to read line by line. Ctrl+T in the message box puts what you wrote into the language you
  chose, such as English, to check before sending; Ctrl+T again gives back your own words. Both
  languages are chosen in the settings. The text goes to Google Translate only when you press Ctrl+T.
- Close WhatsApp fully with NVDA+Alt+Backspace, or with a button in the add-on's settings. A dialog
  says first what that means: no new messages or calls on this computer, a call going on ends, and you
  stay linked, so NVDA+Shift+W opens WhatsApp again. Close WhatsApp or Cancel. The key can be changed in
  Input Gestures.

Fixed:

- Saving a group's description in Manage group failed, as WhatsApp moved how it is saved.
- People not in your contacts showed as a long hidden number in group participants, group info, poll
  voters, who read a message, reactions and status viewers; they now show their phone number, after
  the people with names.

## [0.4.0]

- Translate, only when you ask. Ctrl+T on a message reads it in your language; twice shows the
  translation to read line by line. Ctrl+T in the message box puts what you wrote into the language you
  chose, such as English, to check before sending; Ctrl+T again gives back your own words. Both
  languages are chosen in the settings. The text goes to Google Translate only when you press Ctrl+T.

Fixed:

- Saving a group's description in Manage group failed, as WhatsApp moved how it is saved.
- People not in your contacts showed as a long hidden number in group participants, group info, poll
  voters, who read a message, reactions and status viewers; they now show their phone number, after
  the people with names.

## [0.3.2]

- Ctrl+/ lists every keyboard shortcut, by section and in WhatsApp's words, as WhatsApp does.
- Voice messages play one after another, as in WhatsApp: when one ends, the voice message right after
  it plays, until a text or anything else comes between. In the messages list the cursor follows, and
  NVDA reads the next one; a setting keeps NVDA quiet. A small sound plays as the next one starts, and
  another when the run is over.

Fixed:

- Muted chats were never shown as muted, their menu offered to mute them again, and new messages in
  muted chats were read out. WhatsApp changed how it marks a muted chat; the add-on now asks WhatsApp.

## [0.3.1]

Fixed:

- Updating the add-on removed the WhatsApp login, so the phone had to be linked again, and the folder of
  your own sounds went with it. Both now stay through updates, starting with this one. Removing the
  add-on still removes them.

## [0.3.0]

Writing as in WhatsApp, your own choice of sounds, and the speaker you want for calls.

Writing messages:

- Messages can have several lines: Shift+Enter starts a new one. Pasting puts in plain text only.
- Ctrl+B, Ctrl+I and Ctrl+Shift+X make text bold, italic or struck through, as in WhatsApp. Formatted
  messages are read without their marks: *Meeting* is read as "Meeting".
- Emoji by name: type : and part of a name, such as :grin, then Left and Right Arrow choose and Enter
  adds. Your recent emoji come first.
- Editing works as in WhatsApp: the message's text goes into the message box, where Enter saves and
  Escape cancels. Up Arrow in the empty message box edits your last message. A message that can no
  longer be edited says why. Edited messages say "edited", also when someone edits one while you read.
- Ctrl+Tab and Ctrl+Shift+Tab in a chat open the next and previous chat of the list. A voice note being
  recorded or not sent yet must be sent or thrown away first, so it never goes to the wrong chat.

Sounds:

- The ring repeats until you answer or decline, as a phone rings, and stops at once when you do.
- Choose the ringtone: the add-on's own, one of Windows' ringtones, none, or a WAV file of yours.
  Personal chats and groups can have WAV files of yours too. Moving through the sounds plays each one,
  and Play plays the chosen one again or stops it.
- Group messages have their own sound at first (Kalimba), so they can be told from personal chats.
- A message in the chat you have open has its own softer sound, as WhatsApp's conversation tone.
- Opening and closing a chat have their own small sounds.
- Your own sounds: WAV files in a folder of yours, named as the add-on's sounds, play instead of them.
  Open the folder from the settings; it lists the names.

Calls and the hidden browser:

- Choose the speaker as well as the microphone, in the settings or with Microphone and speaker in the
  call window. A change takes effect at once, during a call too. Voice notes and statuses play on the
  same speaker.
- The hidden browser uses less memory: two fewer processes, and browser services it doesn't need are
  off. Through long sessions, such as a call all night, it gives memory back every few minutes when
  WhatsApp holds too much, and at the end of every call.

Fixed:

- After NVDA restarted, WhatsApp could fail with "Something went wrong" because the last hidden browser
  was still running; it is now closed first.
- Replies show the message they quote again.
- Volumes changed with F7 and F8 are saved at once, and pressing OK in the add-on's settings no longer
  puts back volumes that F7 and F8 changed while they were open.
- A microphone chosen in the settings is used at once, not only after saving them a second time.
- Alt+R with no message chosen says to choose one in the messages list first.

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
