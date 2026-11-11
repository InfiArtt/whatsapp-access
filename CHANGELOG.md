# Changelog

All notable changes to WhatsApp Access are listed here. Each release on GitHub uses its section as the
notes the add-on shows before it installs an update.

## [Unreleased]

- New keys, from anywhere in the window: Alt+1 goes to the open chat's messages, Alt+2 to its first
  unread message, Alt+3 to the chat list (the chat stays open) and Alt+4 to its pinned message. The chat
  list's filters (all, unread, groups, favorites) moved to Alt+Shift+1 to Alt+Shift+4.
- The window title says how many chats are unread, as WhatsApp Web's tab does: "(5) WhatsApp". The open
  chat is not counted.
- When Windows shut down or restarted, NVDA said "WhatsApp stopped. Starting it again…" and started it
  again: Windows closes the hidden browser first. Nothing is said or started then now.
- With NVDA in Indonesian, much of the add-on spoke English: the chat window, call window, first-time
  setup and the lines read for chats and messages did not load the add-on's translations.
- Errors that should stay silent were spoken, such as "Something went wrong" while typing on a weak
  connection, after marking a chat read, or when looking up emoji.
- A message typed while a voice note or files were still sending stayed unsent until the next message.
  Sending files or a voice note while something else is still going out now says so instead of nothing.
- A message that arrived while a chat was opening disappeared from the list.
- When the computer starts without internet, WhatsApp is tried again every minute, a few times, instead
  of staying closed until NVDA+Shift+W.
- Closing WhatsApp fully while it was still starting could start it again by itself.
- "WhatsApp lost its connection" could be said after WhatsApp was already closed.
- A voice note that could not be recorded, such as with a microphone the browser cannot use, is said at
  once, not only when stopping it minutes later. A recording started twice quickly could leave the
  microphone on.
- Changing a privacy setting could fail before WhatsApp's own settings had been opened once.
- Archiving, muting or deleting several chats stopped at the first one that failed.
- Pinning a message when the chat already had the most pins could fail to unpin the oldest.
- Alt+U from another section, such as Calls, moved the focus to the hidden chat list. The chat list no
  longer jumps to the top after new messages while the Archived section is open.
- Files attached as documents could go out as photos when another chat was opened during sending.
- Opening a chat no longer pulls the focus away from the message box when you started typing.
- Deleting a chat no longer closes another chat opened meanwhile. Message info no longer opens after
  leaving the chat. An event's window is named after the event.
- In a call, when the focused button goes away, such as Answer once the call connects, the focus moves to
  End instead of to nowhere.
- Checking for updates: a dropped connection during the download is reported, a release whose file is not
  uploaded yet no longer blocks the one before it, and checking while a check is running says so.
- The help text in the Link WhatsApp window has a label.

Security:

- One very long message full of formatting marks, sent by anyone, kept NVDA busy for a minute or more each
  time it was read. Formatting is now removed in an instant, and a long message read out as it arrives is
  cut after 1,000 characters ("the rest is in the chat").
- An event with an impossible start time no longer breaks the chat list.
- Read receipts (blue ticks) are no longer sent for messages that arrive while you are in another program;
  they are sent when you come back to the window.
- A group call asks first: one key rang everyone in the group.
- A group call is said to be one ("group voice call"), so a group named like a contact cannot pass for
  that person calling. The window title of a chat with someone outside your contacts says "not a
  contact".
- Text that a wa.me link puts in the message box is read out, so it is not sent unheard.
- Only web addresses (http and https) are opened from messages.
- An update is installed only if its file really is this add-on at the version its release names.
- Photos and documents opened during a session are removed when NVDA closes. NVDA's log no longer gets
  the text WhatsApp Web showed when it failed to load, or the names of opened files.
- Choosing WhatsApp Web in your own browser now says what it risks, and the connecting message says to
  choose Cancel when the browser asks at any other time.
- Releases are published only from the main branch, with GitHub's actions pinned to exact versions.

## [0.6.6]

**Required update.** Voice notes sent from WhatsApp Access could not be played on an iPhone. WhatsApp
stays closed until this version is installed.

- Voice notes are recorded in mono. People on an iPhone could not play voice notes recorded in stereo,
  from a microphone with two channels: WhatsApp told them the audio was "no longer available" and to
  ask for it again. Everyone starts in mono, also those who had turned stereo on. Stereo can still be
  turned on in the add-on's settings, which now say that iPhones cannot play it; leave it off unless
  you know everyone you send voice notes to can play it. Thanks to Moon, who found it.
- A chat's pinned message is shown above its messages, as in WhatsApp: Shift+Tab from the messages
  reaches it, and Enter goes to it. With more than one, the newest is shown, and "Go to pinned
  messages" beside it lists them all. A pinned message older than the messages loaded in the chat was
  left out of that list, which could say there were none; it is there now too.

## [0.6.5]

- Exit group is in the chat list's and the archive's menu (the Applications key), not only in an open
  chat's More options. Delete on a group you are still in offers to exit it, or exit and delete it;
  before, it did nothing and said nothing, as WhatsApp deletes a group only once you left it.
- Changing a privacy setting, such as last seen, failed with "Something went wrong": WhatsApp now loads
  that code only with its own settings screen, and the add-on loads it first.

## [0.6.4]

- With "Record voice notes in stereo" unchecked, voice notes are now sent in mono. A microphone with
  two channels gave two anyway, so they went out in stereo; now both sides are mixed into one.
- An open chat is on the screen again. The chat list asked to be as wide as its longest line, took the
  whole window and left the open chat no width at all, so OCR said "content is not visible" and
  anyone looking at the screen saw no messages. The two now share the window.

## [0.6.3]

**Required update.** In 0.6.2, Enter on a playing voice message did nothing, and voice messages could
stop playing altogether. WhatsApp stays closed until this version is installed.

- Voice messages could stop playing altogether, silently: blank tabs had gathered in the hidden
  browser, and Chromium does not load sound in a tab behind another. WhatsApp's tab is now the only one
  and stays in front; tabs opened later are closed.
- Enter on a voice message that was playing did nothing in 0.6.2 but write an error to NVDA's log:
  pausing it called the voice note recorder's pause by mistake. It pauses and goes on again now.
- The position slider is read as the time, such as "12 sec of 45 sec", not as a percentage.
- Reloading NVDA's plugins (NVDA+Ctrl+F3) while a voice message played, or during a call, could make
  NVDA crash: a timer of the closed window went on firing.

## [0.6.2]

- Enter on the voice message playing pauses it, and Enter again goes on from there, as WhatsApp's
  play button does; Escape stops. Before, Enter stopped it.
- On a voice message, Tab from the messages reaches a slider with where it plays, in seconds: Left
  and Right go back and on 5 seconds, Page Up and Page Down 30. Moved before playing, Enter plays
  from there.
- Pressing Enter again while a voice message was still being got ready said "Something went wrong";
  playing is now simply stopped, or paused.
- Linking a new computer works with WhatsApp's new login page. WhatsApp is moving logging in to a page
  of its own (web.whatsapp.com/login/), which some people already get; there the add-on said "Still
  connecting" forever instead of offering to link with a phone number.

## [0.6.1]

- When the hidden browser cannot open WhatsApp Web, for example because there is no connection or a
  firewall or antivirus blocks the browser, the add-on says so, with what the browser's page says,
  instead of "Still connecting" again and again. NVDA's log tells what the page showed.
- Once WhatsApp is connected, the add-on waits up to about three and a half minutes for it to load
  the chats, as a slow computer or a first sync of many chats needs, instead of giving up after one.
- A hidden browser starting on a new profile could be asked for its page before it had opened one.

## [0.6.0]

**Required update.** WhatsApp Web changed how it marks chats unread and how Meta AI answers, so older
versions marked chats read when asked to mark them unread and read out only "Thinking" from Meta AI.
WhatsApp stays closed until this version is installed.

- Alt+P describes a photo with Meta AI, with no other add-on needed: the photo goes to your chat with
  Meta AI with a question in your language, and its answer is read out when it is finished. The
  question asks for a short answer, what the photo is first; you can write your own in the add-on's
  settings. It also
  works on statuses. The photo and the answer stay in the chat with Meta AI. The AI Content Describer
  add-on is no longer used.
- Chats with Meta AI: its answer is read out once it has finished writing it, whole, instead of
  "Thinking" and then nothing. Its answers are no longer called "edited", the empty message it shows
  while it starts is left out, and its chat no longer says "no info" for its online status.
- In a group where only admins send messages, a community's announcements, a group you left, or a
  channel you do not run, the message box is replaced by what WhatsApp says there, such as "Only
  admins can send messages". Before, the box was there and what you typed could not be sent. In
  such groups Alt+R replies privately to the message's sender.
- Replies to community announcements. An announcement says how many replies it has, such as
  "13 replies"; Alt+R on it, or Replies in its menu, lists them with who wrote them and lets you reply,
  as WhatsApp shows them under the announcement.
- Join a group from its invite link, follow a channel from its link, and open a wa.me link as a chat,
  with its message ready in the box. Alt+L on a message opens WhatsApp links this way instead of in
  the browser, and the new Options button under the chat list has Open a WhatsApp link, with a link
  you copied filled in. Before joining you hear the group's name, community, members and whether its
  admins approve new members; a link that was reset says so. Call links are not supported yet.
- Mark all as read, in the Options button, as in WhatsApp's menu. It asks first, since read receipts
  are sent.
- Mark as unread marked the chat read instead: WhatsApp changed how it is asked. It works again, and a
  chat marked unread says "marked unread", counts in the Unread filter and for Alt+U.
- Copy invite link in a group's settings failed until WhatsApp's own invite window had been opened.

- Questions before deleting, leaving, reporting or unlinking use NVDA's own message dialog: the safe
  answer is the one focused first and the one Escape gives.
- The list in list dialogs, and the box in the call window, now have names NVDA reads.
- The README says plainly that NVDA 2025 is 32-bit and NVDA is 64-bit from 2026.1 on.

## [0.5.0]

Safer files and a safer place for your WhatsApp login.

- Everything that can be sent is in the Attach button's menu, as in WhatsApp: Document, Photos and
  videos, Audio, Contact, Poll, Event in groups, and Sticker. More options no longer has a Send menu.
  A photo chosen with Document goes as a document.

- Required updates. When WhatsApp Web changes so that older versions stop working, a release can be
  marked required: the add-on looks for one at every start, closes WhatsApp until it is installed,
  and offers it again on NVDA+Shift+W. A release is marked by a line of its section that begins with
  the words "required update" (see updates.py). This look at GitHub happens even when daily update
  checks are off, as the settings now say; it asks only for the list of releases.

- An open chat now sits beside the chat list, as in WhatsApp on a computer, instead of taking its
  place. Tab goes from the chat's last button to the chat list. Escape or the new Ctrl+W closes the
  chat; Escape again closes the window. While a chat is open, the window is named after it, such as
  "Budi - WhatsApp", without the phone number of someone outside your contacts.

- WhatsApp Access now works with NVDA 2025.1 and later, including the 32-bit NVDA of 2025, not only
  NVDA 2026.3. On a 32-bit NVDA, 64-bit browsers such as Brave are now found in Program Files and
  in the registry.

- In the chat you have open, a new message is read as "name: message" even when you chose to hear
  only who messages are from. That choice now applies only to messages from other chats.
- The message box empties as soon as you press Enter, as in WhatsApp, so you can type the next
  message straight away. Messages typed quickly one after another go out in order, each on its own;
  before, the next one was added to the one still being sent, and "test", "test", "test" became one
  message saying "testtesttest". A message that cannot be sent comes back to the box.
- A deleted message is read as "This message was deleted" once, not twice in a row.
- When someone opens your chat and reads several of your messages at once, "read" is said once, not
  once for each message. The same goes for "delivered".

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
- The hidden browser no longer opens a debugging port. The add-on now talks to it over a private pipe
  that only the add-on holds. Before, any program running on the computer could have connected to that
  port and read your chats or sent messages. The hidden browser also closes by itself if NVDA stops
  without closing it. WhatsApp Web in your own browser still uses that browser's remote debugging, as
  before.

- The hidden browser keeps each website in its own sandboxed process again (site isolation). It uses
  somewhat more memory, but a flaw shown through someone's link preview or media can't reach WhatsApp.
- Updates are installed only with GitHub's checksum of the file, and a damaged download is removed.
- Photos, videos, voice messages and documents are checked against WhatsApp's own seal (MAC) before
  they are played, opened or saved, so a damaged or altered file is refused.

Fixed, so nothing goes to the wrong chat or twice:

- A voice note recorded and stopped in one chat could be sent to the next chat opened, after going back
  to the chat list. Leaving a chat now throws its voice note away, as Ctrl+Tab already refused to move
  on with one. A voice note thrown away while it was still stopping can no longer come back and be sent.
- Pressing Enter or Ctrl+Shift+R again before WhatsApp answered sent the message, files or voice note
  twice.
- When files stop sending partway, those already sent are taken off the list, so Enter sends only the
  rest.
- Moving to another chat right after sending no longer clears that chat's draft or reply.
- A chat that failed to load no longer closes another chat opened meanwhile, and More options no longer
  pops up for a chat already left.
- In Archived, Starred, Channels, Communities, Calls and Status, the selection stays on the same item when
  the list updates by itself, so Enter, Delete or the menu act on the item you last heard.
- In groups, mentioning "An" no longer changes "@Andi" into a mention of An.

Steadier:

- NVDA no longer goes quiet for up to half a minute when the add-on's settings or the call's Microphone
  and speaker dialog open while WhatsApp is slow: the devices are listed in the background, and the
  lists fill in when WhatsApp answers.
- When a WhatsApp update breaks one feature, such as reactions or calls, only that feature stops, and
  NVDA says once which ones are off. Before, new messages could be read out twice, or nothing could be
  heard at all without a word why.
- After the add-on is updated, a WhatsApp Web page that stayed open gets the new version's code instead
  of keeping the old one, and a page that reloads is picked up again without failing the next action.
- A connection that fails halfway is closed properly, so trying again works, and the hidden browser is
  no longer started twice.
- Reloading NVDA's plugins right after NVDA starts no longer leaves an extra hidden browser running.
- Pressing NVDA+Shift+W just as WhatsApp starts with NVDA no longer starts it a second time, which could
  wrongly ask to link the phone again. If WhatsApp is still starting, the window opens once it is ready.
- Deleting, starring and sending contacts now wait for WhatsApp, so a failure, such as deleting for
  everyone too late, is said instead of "Deleted".
- Files that are too large to download (over 200 MB) are refused with a clear message, and files whose
  download or upload never finished no longer stay in the hidden browser's memory.
- Only WhatsApp's own page can tell the add-on about messages and calls; another frame inside it can no
  longer make NVDA announce a message that never came.
- Manage group no longer saves an empty description when Save description is pressed before the
  description has loaded; the box waits for it. Closing a dialog before WhatsApp answers no longer
  causes an error.
- In calls, NVDA now says when the microphone, raising your hand or "who is speaking" did not work,
  instead of saying nothing.
- Moving quickly through statuses no longer stops the next voice or video status as it starts.
- A message deleted for everyone, by you or by its sender, now shows as deleted at once, instead of only
  after the chat is opened again.
- Liking a status (Alt+Y) failed with an error, because WhatsApp Web cannot react to a status. It now
  sends a heart as a reply to the status in the poster's chat, as a quick reaction on the phone does, and
  says so. A status can be liked once each time the viewer is open.
- A sticker chosen from the list is the one sent, even if a sticker sent from the phone meanwhile
  changed the order of recent stickers.
- Ctrl+Shift+C in a group now starts a group voice call, as More options and the Calls section do.
- A new link code waits its full time on its own; it is no longer reported as expired because an earlier
  code ran out.
- A call that follows a declined one is no longer announced as "Declined" when it ends.
- A ringtone that starts while another is ending can be stopped again.
- Describing a photo (Alt+P) puts back copied files or pictures on the clipboard afterwards, not only text.
- Emptying About in the profile now says it was not emptied, instead of "Profile saved".

Safer, from a second check of the code:

- In the mode that uses your own browser, a page at a look-alike address such as
  web.whatsapp.com.example could have been taken for WhatsApp. Only web.whatsapp.com itself is now.
- People not in your contacts are named with "~" before the name they chose and "not a contact" after
  it, such as "~Budi (not a contact)", so a stranger can no longer appear as "Mom" or "Bank BCA". The
  words are there because NVDA reads "~" only at its higher punctuation levels. To hear their phone
  number too, such as "+62812… ~Budi (not a contact)", check "Show the phone number of people who are
  not in your contacts" in the settings.
- A photo, video or voice message is no longer read whole before its size is checked, so one pointing at
  a huge file can't make the hidden browser run out of memory.
- A message is never sent twice when WhatsApp reloads while it sends.
- Old Word, Excel and PowerPoint files (.doc, .xls, .ppt) and .rtf files are no longer opened with Enter,
  as they can carry macros; save them with Alt+D. A file that cannot get the mark Windows gives files from
  the internet is not opened either.
- Saving a file over one that is there no longer destroys it when the download fails.
- A leftover hidden browser is closed only when it really is the add-on's, so your own Brave is never
  closed by mistake; folders with [ ] or an apostrophe in their name work.
- Updates are checked and installed one at a time, each in a folder of its own that is removed after.
- Photos, videos and documents opened with Enter no longer pile up in TEMP: they are cleared when the
  add-on starts, on unlink and on uninstall.
- A voice note stops by itself after 30 minutes, and NVDA says so; it can still be sent.

Fixed, from the same check:

- Installing an update again before restarting NVDA deleted the kept WhatsApp login. It now keeps it, and
  WhatsApp waits for NVDA to restart before it opens again.
- A ring or a sound preview stopped while it was still loading no longer plays in full afterwards.
- When the connection is lost, WhatsApp is closed fully or NVDA exits during a call, the call ends in the
  add-on too: the ring stops and NVDA+Alt+A and NVDA+Alt+M no longer act on a call that is gone.
- Escape no longer throws away a recorded voice note; it says to send it or throw it away first.
- Stopping a recording twice no longer says something went wrong, Ctrl+D while the microphone opens throws
  the note away, and listening to your own note no longer starts the next voice message.
- Up Arrow edit and the delete question act only in the chat they were asked in.
- A status stops playing however its viewer is closed, and Alt+P there plays, stops or describes.
- Ctrl+T on two messages at once no longer mixes up their translations.
- Sound previews stop when the settings or a chat's notification dialog close.
- Unlink says when the data could not all be removed, or when WhatsApp could not be told.
- Installing an update no longer leaves NVDA silent for up to 45 seconds.

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
