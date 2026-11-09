# WhatsApp Access

WhatsApp Access brings your WhatsApp into a simple window made for the NVDA screen reader: chats,
voice notes, status, calls, channels, communities and settings, all with the keyboard and with
clear speech and small sounds. WhatsApp Web runs hidden in the background, so you never have to
find your way around its web page.

It is a different way to see and use your own WhatsApp, not a bot. It sends only what you write,
record or choose, when you choose to send it. It never answers or sends anything on its own.

## What you need

- Windows 10 or 11, and NVDA 2025.1 or later, the 32-bit NVDA of 2025 as well as the 64-bit one.
- One of these browsers installed, version 120 or newer: Brave, Google Chrome, Chromium, Vivaldi,
  Opera or Microsoft Edge. You don't have to use it yourself; the add-on only borrows it.
- WhatsApp on your phone, to link this computer once, as for WhatsApp Web.

## Installing

1. Go to the [Releases page](https://github.com/InfiArtt/whatsapp-access/releases/latest) and
   download the file that ends in `.nvda-addon`.
2. Open the file, for example by pressing Enter on it in File Explorer. NVDA asks whether to install
   the add-on: choose Yes.
3. Restart NVDA when it asks.

New versions come the same way, by themselves: see [Updates](#updates).

## The first time

Press **NVDA+Shift+W**. The add-on asks how to reach WhatsApp:

- **A hidden browser of the add-on's own** (recommended). WhatsApp Web runs with no window, in its
  own profile, so your own browser and its tabs are never touched. It can start with NVDA, so new
  messages and calls reach you at any time. It uses about 1 GB of memory, as much as WhatsApp Web in a browser tab.
- **WhatsApp Web in your own browser**, if you already keep it open there. See
  [Using your own browser](#using-your-own-browser).

Then link it to your phone, once:

1. Type your phone number with its country code, such as +62 812 3456 7890, and press Enter.
2. The add-on reads out an 8-character code letter by letter, and shows it with a Copy button.
3. On your phone, open WhatsApp, then Settings, Linked devices, Link a device, and choose
   **Link with phone number instead**. Type the code. Your phone may also show a notification asking
   for it.
4. When your phone accepts it, the add-on says "Linked" and opens your chats.

The link stays. Closing the window, restarting NVDA or restarting Windows doesn't log you out. You
link again only if you unlink this computer, remove it on your phone, or don't use WhatsApp on your
phone for about 14 days, as for every linked device.

## The keys you need most

| Key | Where | What it does |
|---|---|---|
| NVDA+Shift+W | Anywhere | Open the WhatsApp window. |
| Enter | Chat list | Open the chat. |
| Alt+E | In a chat | Go to **Type a message**; Enter sends. |
| Ctrl+R | In a chat | Record a voice note; Ctrl+Shift+R sends it. |
| Applications | On a message or chat | Its menu: reply, react, forward, delete and more. |
| Alt+T | In a chat | Hear whether the person is online or when they were last seen. |
| Ctrl+Tab | In a chat | The next chat in the list; Ctrl+Shift+Tab the previous one. |
| Up arrow | Empty message box | Edit your last message, as in WhatsApp: Enter saves, Escape cancels. |
| Ctrl+1 to Ctrl+8 | Window | Chats, Status, Calls, Archived, Starred, Channels, Communities, Settings. |
| NVDA+Alt+A | Anywhere | Answer a call, or go back to the call window. |
| NVDA+Alt+H | Anywhere | Decline a call, or end it. |
| NVDA+Alt+M | Anywhere | Microphone off or on during a call. |
| NVDA+Alt+Backspace | Anywhere | Close WhatsApp fully, after saying what that means: no messages or calls until you open it again. |
| Escape | Window | Close the open chat, or close the window. WhatsApp keeps running. |
| Ctrl+W | Window | Close the open chat. The chat list stays beside it. |
| Ctrl+/ | Window | Every keyboard shortcut, by section. |

The five keys that work anywhere (NVDA+Shift+W, NVDA+Alt+A, NVDA+Alt+H, NVDA+Alt+M and
NVDA+Alt+Backspace) can be changed in NVDA's Input Gestures dialog, category WhatsApp Access. The keys inside the WhatsApp window can't be changed.

## The window

The window has sections, like WhatsApp's sidebar: **Chats** (Ctrl+1), **Status** (Ctrl+2),
**Calls** (Ctrl+3), **Archived** (Ctrl+4), **Starred** (Ctrl+5), **Channels** (Ctrl+6),
**Communities** (Ctrl+7) and **Settings** (Ctrl+8). Ctrl+Tab and Ctrl+Shift+Tab move to the next and
previous one; in a chat they move to the next and previous chat instead. They are not tabs: press Tab past a section's controls to reach the **Sections** list,
which says which one is current; choose another with the arrows and press Enter.

As in WhatsApp on a computer, an open chat sits beside the chat list, which stays. Tab goes through the
chat, from its name and buttons to the messages, the message box and the voice note button, then on
to the chat list. **Escape** or **Ctrl+W** closes the chat. While a chat is open, the window's title is
its name, such as "Budi - WhatsApp".

While the window is in front, you are online for your contacts, as with WhatsApp Web. When you switch
to another program or close the window, you are offline again; WhatsApp keeps running in the
background for new messages and calls.

### Chats

- Type in **Search chats** (Alt+S) to find a chat by name. Alt+1 to Alt+4 show all chats, unread
  chats, groups or favorites.
- Each chat in the list (Alt+C) says its name, how many messages you have not read, whether it is
  pinned or muted, whether its messages disappear, whether a group call is going on, and the last
  message. A message you started writing is kept as a draft, and the list says so.
- **Enter** opens a chat. **Alt+U** selects the next chat with unread messages.
- The Applications key opens the chat's menu: notifications for this chat, archive, mute, pin, mark
  as read or unread. **Delete** deletes the chat after asking.
- **Ctrl+N** starts a chat with a phone number, without saving the contact. **Ctrl+Shift+N** makes a
  new group. **Ctrl+Shift+F** searches the messages of every chat.

### A chat

- At the top is the chat's name, with what WhatsApp shows under it: online, last seen, or
  disappearing messages. When someone starts typing or recording, NVDA says so; in groups it says
  who. Press the name for the contact's or group's info.
- Beside the name are **Voice call** (Ctrl+Shift+C) and **More options**. From the messages,
  Shift+Tab reaches More options, then Voice call, then the name.
- The **Messages** list (Alt+M) starts where you stopped reading, at the first unread message, or at
  the newest one. Every message says who sent it ("You" for yours), what it says or holds, what it
  answers, its reactions, its time and, for yours, whether it was delivered and read. Up Arrow on the
  first message loads older ones. Opening a chat marks it as read.
- Notices such as "Anas added Qisti" are read in WhatsApp's words. Photos and videos that can be
  viewed once say to open them on your phone, since WhatsApp Web cannot.

**More options** holds what WhatsApp's chat menu and chat info hold:

- contact or group info, search in chat (Ctrl+F), select messages;
- pinned messages, media, links and documents, and in groups unread mentions (Ctrl+Shift+M);
- **Send**: a poll, a contact card, one of your stickers, or in a group an event;
- in a group, start a group voice call or join the one going on;
- notifications for this chat, archive, mute, pin, mark as read or unread, favorites (when your
  account has them), and disappearing messages (off, 24 hours, 7 days, 90 days);
- for a group's admins, **Manage group**: name, description, who may send or edit, approving new
  members, the invite link (copy or reset), adding members, and each member's menu to make them an
  admin or remove them;
- block or unblock, report, clear chat, exit group or delete chat, each asked before it is done.

### Writing and sending

- Write in **Type a message** (Alt+E) and press **Enter** to send. Type @ in a group to mention
  someone: Up and Down Arrow choose, Enter picks. Type : and part of an emoji's English name, such as
  :grin or :fire, for emoji: Left and Right Arrow choose, Enter picks.
- **Shift+Enter** starts a new line. **Ctrl+B**, **Ctrl+I** and **Ctrl+Shift+X** make the selected text
  bold, italic or struck through, as in WhatsApp; pressed again, they take it off. Messages are read
  without the formatting marks; Alt+C shows them as written.
- To answer one message, select it and press **Alt+R**; Escape cancels the reply.
- To send files, press **Alt+A** to choose them, or copy them in File Explorer and press **Ctrl+V** in
  the message box. Photos and videos go as photos and videos, audio as audio, anything else as a
  document. What you type becomes the caption.
- While you write, the other person sees "typing…", as in WhatsApp.
- **Translating**, only when you ask: **Ctrl+T** on a message reads it in your language (press it twice
  to show the translation to read line by line). **Ctrl+T** in the message box puts what you wrote
  into the language you chose, such as English, to check before you press Enter; Ctrl+T again gives
  back your own words. Choose both languages in the add-on's settings. Translation uses Google
  Translate and needs the internet.

### Voice notes

| Key | What it does |
|---|---|
| Ctrl+R | Start recording. While recording: stop and play it back. Afterwards: play it again. |
| Ctrl+Shift+R | Send it, stopping the recording first if needed. |
| Ctrl+Shift+D | Pause or resume recording. |
| Ctrl+D | Throw it away. |

Voice notes are recorded from your microphone's own sound, without the browser's echo
cancellation, noise suppression and automatic volume, in stereo if the microphone has two
channels, and at 128 kilobits per second, much clearer than WhatsApp's own recorder. You can change
all of this in the add-on's settings.

### Keys on a message

| Key | What it does |
|---|---|
| Enter | Play a voice message or a video's sound (Enter again stops); open a photo or document; vote in a poll; an event's details. Voice messages right after each other play one after another, and the cursor follows. |
| Ctrl+S | Voice messages at 1x, 1.5x or 2x, as in WhatsApp. |
| Alt+C | Show the message's text alone, to read it by character, word or line. |
| Ctrl+C | Copy the message's text. |
| Alt+Y | React with an emoji. |
| Alt+R | Reply to it. |
| Alt+F | Forward it to one or more chats. |
| Alt+D | Save its file to a folder you choose. |
| Alt+L | Open a link in it. |
| Alt+I | For your own message: who received, read and played it, and when. |
| Alt+P | Describe a photo with the AI Content Describer add-on, if you have it. |
| Delete | Delete it, for you or for everyone. |
| Applications | Its menu: also star, edit, pin for 24 hours, 7 days or 30 days, reply privately in a group, see who reacted, and answer an event. |

### Selecting several messages or chats

As in WhatsApp's Select mode, in the chat lists and in a chat's messages:

- **Shift+Down** and **Shift+Up** select as you move; **Space** selects or unselects one;
  **Ctrl+A** selects all. A soft tick plays when you reach a selected item. **Escape** clears it.
- With messages selected, **Ctrl+C** copies them as WhatsApp does (`[10:15, 8/11/2026] Name: text`),
  **Alt+F** forwards them, **Delete** deletes them, and the Applications key can also star them.
- With chats selected, the Applications key archives, mutes, pins, marks as read or unread, or
  deletes them all. Groups you are still in are kept: exit them first.

## Status

**Status** (Ctrl+2) lists the people who posted, unseen first. Enter shows their statuses:

- Arrows go to the next and previous status, Ctrl+arrows to the next and previous person.
- Voice and video statuses play by themselves, inside the add-on. Enter stops or plays them again,
  and describes a photo.
- Alt+Y likes, Alt+R replies in their chat, Alt+D saves the photo, video or voice as a file.
- Viewing a status shows you among its viewers, as in WhatsApp.

Below the list: **Write a status** (text, with a background colour and font), **Post a photo or
video**, and **My status**, which says who saw each of your statuses and can delete one.

## Calls

When someone calls, the add-on rings until you answer or decline and says who it is, wherever you are. **NVDA+Alt+A**
answers and **NVDA+Alt+H** declines. The call window shows the call without taking your focus.

During a call:

- **NVDA+Alt+M** turns your microphone off or on from any program, with a small sound for each.
  In the call window or the WhatsApp window, Ctrl+M does the same.
- **Escape** hides the call window and the call goes on, so you can keep chatting. The WhatsApp
  window then shows a bar at the top with **Return to call** and **Mute microphone**.
- NVDA+Alt+H ends the call. If someone else mutes you, NVDA says so.

To call: **Ctrl+Shift+C** in a chat, or More options, **Start a group voice call**, in a group.
Groups with a call going on say "call in progress" in the chat list and at the top of **Calls**
(Ctrl+3), where Enter joins it. When you are invited again, joining answers the call.

In a group call, the call window also has:

- the **Participants** list, those in the call first: who is muted, who raised a hand, who has not
  joined; the Applications key on someone asks them to mute;
- **Raise hand** (Ctrl+H) and **React**, which sends an emoji to everyone;
- **Ctrl+Shift+G**, in the call window or the WhatsApp window: who is speaking now.

NVDA says who joins, who leaves, who raises a hand and who reacts, each with its own small sound.

Calls are answered with your microphone and without your camera. In the add-on's settings you choose
the microphone, the speaker and how much sound processing calls use. To switch during a call, for
example from your headset to the laptop's speaker, press **Microphone and speaker** in the call
window: the call moves over at once. Voice notes and statuses play on the same speaker.

## Starred, Channels and Communities

- **Starred** (Ctrl+5) lists your starred messages from every chat. Enter opens the chat at the
  message; the Applications key copies or unstars.
- **Channels** (Ctrl+6) lists the channels you follow. Enter opens one: posts read like messages,
  Alt+Y reacts, and only a channel's admins can post. **Find channels** searches WhatsApp's
  directory; a channel's menu unfollows it.
- **Communities** (Ctrl+7) lists your communities. Enter shows a community's groups, announcements
  first. Enter opens a group you are in, or asks to join one you are not in.

## Your WhatsApp settings

**Settings** (Ctrl+8) holds WhatsApp's own settings:

- **Profile**: your name, About and photo.
- **Privacy**: last seen, online, profile photo, About, who can add you to groups, read receipts,
  and silencing unknown callers.
- **Blocked contacts**: Enter unblocks one.
- **Add-on settings**: opens the settings below.

## Notifications, sounds and volumes

New messages are read out with a sound, in place of WhatsApp's own notifications. In a chat's menu,
**Notifications for this chat** sets that chat's own rule: always read out (even when muted) or
never, its own sound (one of the add-on's or a WAV file of yours), and how much is said.

There are five volumes: new message sounds and the ring; the add-on's other sounds; voice notes and
videos in chats; statuses; and the other person in calls. In the WhatsApp window, the status window
or the call window, **F6** chooses which volume, **F7** lowers it and **F8** raises it by 5 percent.
The change applies at once and is kept.

## The add-on's settings

NVDA menu, Preferences, Settings, **WhatsApp Access**:

- how WhatsApp is reached (the hidden browser or your own), which browser, and starting with NVDA;
- **Unlink this computer**: logs out of WhatsApp here and removes what the hidden browser kept;
- which new messages are read out, and whether to hear what they say;
- the sounds for personal chats and for groups (different at first, so you can tell them apart) and the
  ringtone: the add-on's own, one of Windows' ringtones, none, or a WAV file of yours. Moving through a
  list plays each sound, and **Play** plays the chosen one again or stops it;
- **Open the folder for your own sounds**: a WAV file you put there named as one of the add-on's sounds,
  such as sent.wav or openChatMessage.wav (a message in the chat you have open), plays instead of it.
  The folder lists the names;
- the microphone and the speaker, and the sound processing in calls;
- voice notes: stereo, the microphone's own sound, quality;
- playback speed, the five volumes, the add-on's sounds, and hints (which keys to press next);
- checking for new versions.

## Updates

WhatsApp Access is published on its
[GitHub page](https://github.com/InfiArtt/whatsapp-access/releases), not in the NVDA Add-on Store.
Once a day, a little after NVDA starts, the add-on looks there for a new version. When there is one,
it shows what is new and offers **Download and install**; NVDA installs it and asks to restart.
**Not now** asks again the next day. You can also look now: add-on settings, **Check for updates
now**. The file is checked against GitHub's checksum before it is installed, and the add-on sends
nothing about you.

Sometimes WhatsApp Web changes so that older versions of the add-on stop working. The new version
is then a **required update**: at every start, even with daily checks turned off, the add-on looks
for one, and when there is one, WhatsApp closes (except during a call, which goes on) and stays
closed until it is installed. NVDA+Shift+W offers the update again.

## Using your own browser

If you choose WhatsApp Web in your own browser instead of the hidden one:

1. Open web.whatsapp.com and log in, in Brave, Google Chrome or Microsoft Edge.
2. Turn on remote debugging there, once: open a new tab with Ctrl+T, type
   `brave://inspect/#remote-debugging` (in Chrome `chrome://inspect/#remote-debugging`, in Edge
   `edge://inspect/#remote-debugging`), and check "Allow remote debugging for this browser instance".
3. Each time the browser starts, the first NVDA+Shift+W brings it to the front with the question
   "Allow remote debugging?". The focus is on Cancel: press Shift+Tab, then Enter, to allow it.

While the add-on is connected, the browser shows a bar saying it is being controlled by software:
that is this add-on.

## If something goes wrong

- **"Still connecting to WhatsApp Web"**: WhatsApp is starting, which takes up to half a minute after
  NVDA starts. Try again in a moment.
- **WhatsApp lost its connection**: NVDA says so after a few seconds and again when it is back.
  Messages you send meanwhile go when it is back.
- **A question is open but you can't reach it**: go back to the WhatsApp window; the add-on takes you
  to the open question.
- **You were asked to link again**: WhatsApp removed this computer from your linked devices. Link it
  again as the first time.

## Privacy

The add-on talks only to the browser on your own computer, and checks that the program it talks to
really is that browser. It does not send your messages anywhere else, with one exception you choose
each time: Ctrl+T sends the text it translates to Google Translate. Nothing is translated by itself.

WhatsApp does not offer this kind of access officially. The add-on uses WhatsApp Web the way you do,
from your own account, but WhatsApp's terms do not allow changing how its apps work. Use it at your
own judgement.

## License

GNU General Public License, version 2 or later. See COPYING.txt.
