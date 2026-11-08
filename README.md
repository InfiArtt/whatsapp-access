# WhatsApp Access

WhatsApp Access shows your WhatsApp chats in a simple window made for the NVDA screen reader.
You read and answer messages and send clear voice notes there, while WhatsApp Web stays open in
Brave, Google Chrome or Microsoft Edge. The browser can stay in the background, minimized or on
another virtual desktop.

It is a different way to see and use WhatsApp, not a bot. It sends only what you write or record,
when you choose to send it. It never answers or sends messages on its own.

## Two ways to reach WhatsApp

- **A hidden browser of the add-on's own** (recommended). The add-on runs WhatsApp Web in Brave,
  Google Chrome or another Chromium browser, version 120 or newer, with no window and with its own
  profile, so your own browser is never touched and nothing asks for permission. You link it once to
  your phone with a code, and it appears on your phone under Linked devices. It can start with NVDA,
  so new messages are read out at any time. It uses about 400 to 600 MB of memory.
- **WhatsApp Web in your own browser**, described below. Your browser asks for permission each time
  it starts.

The first time you press NVDA+Shift+W, the add-on asks which way you want. You can change it in
NVDA's settings, WhatsApp Access, which also has **Unlink this computer**: it logs out of WhatsApp and
removes what the hidden browser kept. Removing the add-on removes that too.

### Linking the hidden browser

1. Type your phone number with its country code and press Enter.
2. The add-on reads out an 8-character code letter by letter, and shows it in a box with a Copy button.
3. On your phone, open WhatsApp, then Settings, Linked devices, Link a device, and choose
   **Link with phone number instead**. Type the code. Your phone may also show a notification asking for it.
4. When your phone accepts it, the add-on says "Linked" and opens your chats.

## What you need for WhatsApp Web in your own browser

- NVDA 2026.3 or later.
- WhatsApp Web open and logged in at web.whatsapp.com, in Brave, Google Chrome or Microsoft Edge.
- Remote debugging turned on in that browser, once:
  1. Open a new tab with Control+T.
  2. Type `brave://inspect/#remote-debugging` and press Enter.
     In Chrome it is `chrome://inspect/#remote-debugging`, in Edge `edge://inspect/#remote-debugging`.
  3. Check "Allow remote debugging for this browser instance".

## Using it

Press **NVDA+Shift+W** to open the WhatsApp window.

The first time after the browser starts, the add-on connects to it. The browser comes to the front
and asks "Allow remote debugging?". The focus is on Cancel: press **Shift+Tab**, then **Enter** to
choose Allow. While the add-on is connected, the browser shows a bar saying that it is being
controlled by software. That is this add-on.

### The chat list

- Type in **Search chats** (Alt+S) to find a chat by name.
- In the **Chats** list (Alt+C), each chat says its name, how many messages you have not read, and
  the last message. Press **Enter** to open it.
- **Escape** closes the window. WhatsApp Web stays open, and new messages are still read out.

### Sections

The window has sections, as WhatsApp's sidebar does: **Chats** (Ctrl+1), **Status** (Ctrl+2),
**Calls** (Ctrl+3) and **Archived** (Ctrl+4). Ctrl+Tab and Ctrl+Shift+Tab move to the next and
previous one. They are not tabs: press Tab past a section's controls to reach the **Sections** list,
which says which one is current; choose another with the arrows and press Enter.

- **Status** lists the people who posted, unseen first. Enter shows their statuses: arrows go to the
  next and previous one, Ctrl+arrows to the next and previous person. Voice and video statuses play
  by themselves, in the add-on, with no other program; Enter stops or plays them again, and describes
  a photo. Alt+Y likes it, Alt+R replies (in their chat), Alt+D downloads its photo, video or voice
  as a file, in a folder you choose.
  Viewing a status shows you among its viewers, as in WhatsApp.
- **Calls** lists recent calls, missed ones included. Enter calls back.
- **Archived** lists your archived chats.

### Calls

When someone calls, the add-on plays a ring and says who it is. **NVDA+Alt+A** answers and
**NVDA+Alt+H** declines, from anywhere; a call window shows the call without taking focus. During a call,
Ctrl+M mutes the microphone and NVDA+Alt+H ends it. In a chat, **Ctrl+Shift+C** calls the person.
Group calls are not supported yet. In NVDA's settings you choose the microphone and how much sound
processing calls use.

### Notifications

New messages are read out with a sound. In NVDA's settings you choose the sound for personal chats and
for groups, and whether to hear what a message says or only who it is from. In a chat's menu,
**Notifications for this chat** sets that chat's own rule: always read out (even when muted) or never,
its own sound (one of the add-on's or a WAV file of yours), and how much is said.

### Selecting several messages or chats

As in WhatsApp's Select mode, in the chat lists and in a chat's messages:

- **Shift+Down** and **Shift+Up** select as you move; **Space** selects or unselects the current one;
  **Ctrl+A** selects all. A soft tick plays when you reach a selected item.
- **Escape** clears the selection.
- With messages selected, **Ctrl+C** copies them as WhatsApp does (`[10:15, 8/11/2026] Name: text`, one
  per line), **Alt+F** forwards them, **Delete** deletes them, and the context menu can also star them.
- With chats selected, the context menu archives, mutes, pins, marks as read or unread, or deletes them
  all, and **Delete** deletes them after asking. Groups you are still in are kept: exit them first.

In the message list, **Enter** plays or opens a message; Space now selects.

### Anywhere in the window

| Key | What it does |
|---|---|
| Alt+1 to Alt+4 | Show all chats, unread chats, groups or favorites, as WhatsApp's tabs. |
| Alt+U | In a chat, go to its first unread message, where WhatsApp says "5 unread messages". In the chat list, select the next chat with unread messages. |
| Ctrl+N | Start a chat with a phone number, without saving the contact. |

A message you started writing is kept as a draft when you leave the chat, and the chat list says so.

### A conversation

- At the top, a button with the chat's name and what WhatsApp shows under it: online, when the person was last seen,
  or "no info" when they hide it. When someone starts typing or recording a voice message, NVDA says
  so right away; in groups it says who. Press **Alt+T** to hear it at any time. Press the button
  for the contact's info: phone number, About and groups in common; for a group, its description,
  who created it and its participants.
- Beside the name, as in WhatsApp, are **Voice call** (Ctrl+Shift+C, not in groups) and **More options**.
  From the messages, Shift+Tab reaches More options, then Voice call, then the name.
  More options holds contact or group info, search in chat (Ctrl+F), select messages, notifications
  for this chat, archive, mute, pin, mark as read or unread, and close chat.
- The **Messages** list (Alt+M) starts at the newest message. Every message says who sent it:
  "You" for yours, the contact's name for theirs. A reply also says what it answers, for example
  `Anas: Oke, quoting You: "Jadi?"`. Opening a chat marks it as read, as in WhatsApp.
- Press **Up Arrow** on the first message to load older ones.
- Press **Enter** on a voice message to listen to it, and again to stop. **Ctrl+S** changes the
  speed: 1x, 1.5x or 2x, as in WhatsApp.
- Keys on a message:

  | Key | What it does |
  |---|---|
  | Enter | Play a voice message or a video's sound in the add-on (Enter again stops); open a photo or document in its usual Windows program (the menu's Open does this for a video); vote in a poll. |
  | Alt+C | Show the message's text alone, to read it by character, word or line. Long messages are always whole. |
  | Ctrl+C | Copy the message's text. |
  | Alt+Y | React with an emoji. |
  | Alt+D | Download the message's file to a folder you choose. |
  | Delete | Delete it, for you or for everyone. |
  | Alt+R | Reply to it. |
  | Alt+F | Forward it to one or more chats. |
  | Alt+L | Open a link in it; with several links, choose one. |
  | Alt+I | Message info for your own message: who received, read and played it, and when. |
  | Alt+P | Describe a photo with the AI Content Describer add-on, if you have it. |
  | Ctrl+F | Search this chat's messages, older ones too. |

  While you write, the other person sees "typing…", as in WhatsApp. WhatsApp Web has no voice
  message transcripts; they exist only in WhatsApp on phones.

- To send files, press **Alt+A** to choose them, or copy them in File Explorer and press **Ctrl+V** in
  the message box. Photos and videos go as photos and videos, audio as audio, anything else (apk, exe,
  pdf, zip) as a document. What you type becomes the caption.
- Press the **Applications** key or **Shift+F10** on a message for WhatsApp's menu: reply, react,
  copy, star, edit your message, delete for you or for everyone.
- Write in **Type a message** (Alt+E) and press **Enter** to send. While it is empty, the window offers
  a voice note; once you write, it offers Send.
- To answer one message, select it and press **Alt+R**. **Escape** cancels the reply.
- **Escape** goes back to the chat list. In the chat list, the Applications key opens the chat's menu:
  archive, mute, pin, mark as read or unread.

### Voice notes

| Key | What it does |
|---|---|
| Ctrl+R | Start recording. While recording: stop and play it back. Afterwards: play it again. |
| Ctrl+Shift+R | Send it, stopping the recording first if needed. |
| Ctrl+Shift+D | Pause or resume recording. |
| Ctrl+D | Throw it away. |

Voice notes are recorded from your microphone's own sound, without the browser's echo
cancellation, noise suppression and automatic volume, in stereo if the microphone has two
channels, and at 128 kilobits per second. WhatsApp's own recorder uses much less. You can change
all of this in NVDA's settings.

## Settings

NVDA menu, Preferences, Settings, **WhatsApp Access**:

- **Read out new messages from**: all chats that are not muted, personal chats only, only the chat
  open in the window, or none.
- **Microphone for voice notes**: connect first with NVDA+Shift+W to see all your microphones.
- **Read out new messages instead of WhatsApp's notifications and sound**, **Play the add-on's sounds**
  and **Use hints** (which keys to press, said after messages such as "Recording").
- **Voice message playback speed**.
- Five volumes, in percent: new message sounds and the ring; the other sounds (sent, recording,
  selecting); voice notes and videos in chats; statuses; the other person in calls. 0 silences that
  kind of sound. You can also change them without opening the settings: in the WhatsApp window, the
  status window or the call window, **F6** chooses which volume (sound effects, notifications, voice
  notes, statuses, in call), **F7** lowers it and **F8** raises it by 5 percent. The change applies at
  once, to what is playing too, and is kept.
- **Record voice notes in stereo**, **Use the microphone's own sound** and **Voice note quality**.
- **Check for new versions on GitHub once a day** and **Check for updates now**.

## Updates

WhatsApp Access is published on its [GitHub page](https://github.com/InfiArtt/whatsapp-access/releases),
not in the NVDA Add-on Store. Once a day, a little after NVDA starts, the add-on looks there for a new
version. When there is one, it shows what is new and offers **Download and install**; NVDA's own
installer then installs it and asks to restart NVDA. **Not now** asks again the next day. The file is
checked against the checksum GitHub publishes before it is installed. The add-on sends nothing about
you: it only asks GitHub for the latest release.

## Privacy

The add-on talks only to the browser on your own computer, and checks that the program it talks to
really is that browser. It does not send your messages anywhere else.

WhatsApp does not offer this kind of access officially. The add-on uses WhatsApp Web the way you do,
from your own account and browser, but WhatsApp's terms do not allow changing how its apps work.
Use it at your own judgement.

## License

GNU General Public License, version 2 or later. See COPYING.txt.
