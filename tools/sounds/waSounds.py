"""The WhatsApp Access add-on's sounds, made with the Twinkle Lullaby toolkit (twinkle.py).

Run: python tools/sounds/waSounds.py addon/sounds
Each sound is short and sits under NVDA's voice. The room is kept small (wet 0.28, 1.2 s) so the
tails end before the next thing NVDA says.
"""

import os
import sys

import numpy as np
from twinkle import (
    Track,
    airy,
    bell,
    darken,
    done,
    flute_pair,
    kalimba,
    n,
    pad,
    report,
    seed,
    wood,
    write_wav,
)

WET, ROOM = 0.28, 1.2


def sent():
    """Sent: a soft breath sweeping left to right with two quick music-box notes rising
    D6 to A6, as if the message lifts off and flies."""
    seed(101)
    tr = Track(1.2)
    a = airy(0.3, 1200, 2200, 3200, 5200, voices=120)
    tr.add(a * np.sin(np.pi * np.linspace(0, 1, len(a))) ** 2, 0.0, np.linspace(-0.6, 0.6, len(a)), 0.07)
    tr.add(darken(bell("D6", 0.9, 0.4, 0.3), 4000), 0.02, -0.3, 0.3)
    tr.add(darken(bell("A6", 1.0, 0.45, 0.3), 4000), 0.11, 0.3, 0.3)
    return done(tr, WET, ROOM)


def received():
    """A new message: a music-box answer from the right, A5 then D6 then F#6, over a
    short warm D chord, landing softly in the middle."""
    seed(102)
    tr = Track(1.8)
    tr.add(pad((n("D4"), n("A4"), n("F#5")), 1.0, swell=0.12, release=0.6, brightness=2), 0.0, 0.0, 0.3)
    for i, (note, pan) in enumerate((("A5", 0.5), ("D6", 0.25), ("F#6", 0.0))):
        tr.add(darken(bell(note, 1.2, 0.55, 0.35), 4500), i * 0.12, pan, 0.3)
    return done(tr, WET, ROOM)


def record_start():
    """Recording starts: a soft wooden tock and a flute pair gliding up from D5 to A5,
    like the microphone opening."""
    seed(103)
    tr = Track(0.9)
    tr.add(darken(wood(n("D5"), 0.3, 0.06), 2200), 0.0, 0.0, 0.25)
    flute_pair(tr, "D5", 0.45, at=0.02, gain=0.2, to="A5", glide=0.18)
    return done(tr, WET, ROOM)


def record_stop():
    """Recording stops: the flute pair gliding back down from A5 to D5 and a low
    kalimba D settling under it, like the microphone closing."""
    seed(104)
    tr = Track(1.0)
    flute_pair(tr, "A5", 0.42, at=0.0, gain=0.2, to="D5", glide=0.18)
    tr.add(kalimba(n("D4"), 0.8, 0.25), 0.18, 0.0, 0.35)
    return done(tr, WET, ROOM)


def pause():
    """Paused: two soft, dim kalimba notes on A4, left then right, like a held breath."""
    seed(105)
    tr = Track(0.9)
    tr.add(darken(kalimba(n("A4"), 0.6, 0.18), 3000), 0.0, -0.3, 0.4)
    tr.add(darken(kalimba(n("A4"), 0.6, 0.18), 3000), 0.16, 0.3, 0.4)
    return done(tr, WET, ROOM)


def discard():
    """Thrown away: a breath sweeping right to left and three dim bells falling A5, F#5,
    D5, as if the note drifts off."""
    seed(106)
    tr = Track(1.2)
    a = airy(0.32, 2400, 1100, 5000, 2600, voices=120)
    tr.add(a * np.sin(np.pi * np.linspace(0, 1, len(a))) ** 2, 0.0, np.linspace(0.6, -0.6, len(a)), 0.06)
    for i, (note, pan) in enumerate((("A5", 0.3), ("F#5", 0.0), ("D5", -0.3))):
        tr.add(darken(bell(note, 0.8, 0.35, 0.3), 3200), i * 0.08, pan, 0.28)
    return done(tr, WET, ROOM)


def ring():
    """Someone is calling: a music-box phrase rising D6, F#6, A6 and answering A6, D7, over a warm
    D chord, played once with each announcement rather than looping."""
    seed(107)
    tr = Track(2.6)
    tr.add(pad((n("D4"), n("A4"), n("F#5")), 1.8, swell=0.2, release=0.9, brightness=2), 0.0, 0.0, 0.3)
    phrase = (("D6", -0.4, 0.0), ("F#6", -0.2, 0.14), ("A6", 0.0, 0.28), ("A6", 0.3, 0.62), ("D7", 0.4, 0.76))
    for note, pan, at in phrase:
        tr.add(darken(bell(note, 1.2, 0.5, 0.35), 4500), at, pan, 0.3)
    return done(tr, WET, ROOM)


def notify_bell():
    """A new message, as a single music-box bell on A6 with a soft D under it."""
    seed(108)
    tr = Track(1.6)
    tr.add(pad((n("D4"), n("A4")), 0.8, swell=0.08, release=0.5, brightness=2), 0.0, 0.0, 0.22)
    tr.add(darken(bell("A6", 1.3, 0.6, 0.35), 4500), 0.0, 0.1, 0.34)
    tr.add(darken(bell("D6", 1.2, 0.55, 0.3), 4000), 0.1, -0.1, 0.22)
    return done(tr, WET, ROOM)


def notify_kalimba():
    """A new message, as two warm kalimba notes, D5 then A5, left to right."""
    seed(109)
    tr = Track(1.4)
    tr.add(darken(kalimba(n("D5"), 0.9, 0.3), 3500), 0.0, -0.3, 0.45)
    tr.add(darken(kalimba(n("A5"), 1.0, 0.35), 3500), 0.13, 0.3, 0.45)
    return done(tr, WET, ROOM)


def notify_flute():
    """A new message, as a flute pair gliding up from A5 to D6, like a soft call."""
    seed(110)
    tr = Track(1.3)
    flute_pair(tr, "A5", 0.55, at=0.0, gain=0.22, to="D6", glide=0.2)
    return done(tr, WET, ROOM)


def tick():
    """Reaching a selected item: one tiny, dim wooden tick on A6, far quieter than a bell."""
    seed(111)
    tr = Track(0.4)
    tr.add(darken(wood(n("A6"), 0.12, 0.02), 2200), 0.0, 0.0, 0.2)
    return done(tr, 0.12, 0.6)


def mic_off():
    """Microphone off: two soft notes falling A5 to D5, then a dim wooden tock, like a lid closing."""
    seed(112)
    tr = Track(0.9)
    tr.add(darken(bell("A5", 0.5, 0.25, 0.25), 3200), 0.0, 0.15, 0.26)
    tr.add(darken(bell("D5", 0.6, 0.3, 0.25), 3000), 0.09, -0.15, 0.26)
    tr.add(darken(wood(n("D4"), 0.14, 0.03), 1800), 0.17, 0.0, 0.18)
    return done(tr, 0.2, 1.0)


def mic_on():
    """Microphone on: two bright notes rising D5 to A5, the lid opening again."""
    seed(113)
    tr = Track(0.9)
    tr.add(darken(bell("D5", 0.5, 0.25, 0.25), 3600), 0.0, -0.15, 0.26)
    tr.add(darken(bell("A5", 0.7, 0.35, 0.28), 4000), 0.09, 0.15, 0.28)
    return done(tr, 0.2, 1.0)


def call_join():
    """Someone joins the group call: one small, soft glass note on A5, from the right."""
    seed(114)
    tr = Track(0.7)
    tr.add(darken(bell("A5", 0.5, 0.3, 0.2), 3400), 0.0, 0.35, 0.22)
    return done(tr, 0.18, 0.9)


def call_leave():
    """Someone leaves the group call: one small, dim note on D5, from the left."""
    seed(115)
    tr = Track(0.7)
    tr.add(darken(bell("D5", 0.5, 0.3, 0.2), 2600), 0.0, -0.35, 0.22)
    return done(tr, 0.18, 0.9)


def call_hand():
    """A hand is raised in the group call: two light wooden knocks, as on a desk."""
    seed(116)
    tr = Track(0.6)
    tr.add(darken(wood(n("E5"), 0.12, 0.03), 2400), 0.0, 0.0, 0.22)
    tr.add(darken(wood(n("E5"), 0.12, 0.03), 2400), 0.11, 0.0, 0.18)
    return done(tr, 0.15, 0.7)


def call_reaction():
    """Someone reacts in the group call: a tiny, soft music-box plink on D6, barely there."""
    seed(117)
    tr = Track(0.5)
    tr.add(darken(bell("D6", 0.3, 0.15, 0.2), 4200), 0.0, 0.0, 0.16)
    return done(tr, 0.15, 0.7)


def chat_open():
    """Opening a chat: a soft breath and two quick music-box notes rising A5 to D6, a door opening."""
    seed(118)
    tr = Track(0.8)
    a = airy(0.18, 1400, 2400, 3400, 5000, voices=80)
    tr.add(a * np.sin(np.pi * np.linspace(0, 1, len(a))) ** 2, 0.0, np.linspace(-0.3, 0.3, len(a)), 0.05)
    tr.add(darken(bell("A5", 0.5, 0.25, 0.22), 3600), 0.0, -0.15, 0.24)
    tr.add(darken(bell("D6", 0.6, 0.3, 0.22), 3800), 0.07, 0.15, 0.24)
    return done(tr, 0.2, 1.0)


def chat_close():
    """Closing a chat: the same two notes falling D6 to A5, softer, the door closing."""
    seed(119)
    tr = Track(0.8)
    tr.add(darken(bell("D6", 0.45, 0.22, 0.2), 3200), 0.0, 0.15, 0.22)
    tr.add(darken(bell("A5", 0.55, 0.28, 0.2), 3000), 0.07, -0.15, 0.22)
    return done(tr, 0.2, 1.0)


def open_chat_message():
    """A message in the chat you have open: one round, low music-box "blup", D5 over a soft A4, short and
    quieter than a notification, so it sits inside the conversation."""
    seed(120)
    tr = Track(0.6)
    tr.add(darken(bell("A4", 0.45, 0.2, 0.22), 1800), 0.0, -0.1, 0.18)
    tr.add(darken(bell("D5", 0.5, 0.22, 0.22), 2200), 0.03, 0.1, 0.26)
    return done(tr, 0.18, 0.9)


def voice_next():
    """The next voice message starts after one ends: a light step up, F#5 to A5, quick and small."""
    seed(121)
    tr = Track(0.5)
    tr.add(darken(bell("F#5", 0.3, 0.16, 0.22), 3400), 0.0, -0.2, 0.2)
    tr.add(darken(bell("A5", 0.35, 0.18, 0.22), 3600), 0.06, 0.2, 0.22)
    return done(tr, 0.16, 0.8)


def voice_end():
    """A run of voice messages is over: A5 settling down to D5 over a quiet low D, the end of a story."""
    seed(122)
    tr = Track(1.0)
    tr.add(darken(bell("A5", 0.4, 0.22, 0.22), 3400), 0.0, 0.15, 0.2)
    tr.add(darken(bell("D5", 0.7, 0.35, 0.22), 2800), 0.1, -0.1, 0.24)
    tr.add(darken(bell("D4", 0.6, 0.3, 0.22), 1800), 0.1, 0.0, 0.1)
    return done(tr, 0.24, 1.2)


SOUNDS = {
    "sent": sent,
    "received": received,
    "recordStart": record_start,
    "recordStop": record_stop,
    "pause": pause,
    "discard": discard,
    "ring": ring,
    "notifyBell": notify_bell,
    "notifyKalimba": notify_kalimba,
    "notifyFlute": notify_flute,
    "tick": tick,
    "micOff": mic_off,
    "micOn": mic_on,
    "callJoin": call_join,
    "callLeave": call_leave,
    "callHand": call_hand,
    "callReaction": call_reaction,
    "chatOpen": chat_open,
    "chatClose": chat_close,
    "openChatMessage": open_chat_message,
    "voiceNext": voice_next,
    "voiceEnd": voice_end,
}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for name, make in SOUNDS.items():
        data = make()
        write_wav(os.path.join(out, name + ".wav"), data)
        report(name, data)
