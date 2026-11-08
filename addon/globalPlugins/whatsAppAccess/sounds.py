# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""The add-on's short sounds, so the user hears what happened without waiting for speech."""

import array
import os
import sys
import threading
import wave

import config
import nvwave
from logHandler import log

from .configSpec import CONFIG_SECTION

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sounds")

SENT = "sent"
RECEIVED = "received"
RECORD_START = "recordStart"
RECORD_STOP = "recordStop"
PAUSE = "pause"
DISCARD = "discard"
RING = "ring"
TICK = "tick"

# Which volume setting a sound follows: new messages and the ring, or everything else.
NOTIFICATION = "notificationVolume"
EFFECTS = "effectsVolume"
NOTIFICATION_SOUNDS = {RECEIVED, RING, "notifyBell", "notifyKalimba", "notifyFlute"}


def scaled(frames: bytes, sampleWidth: int, volume: float) -> bytes:
	"""16-bit PCM made quieter; other sample widths are left as they are."""
	if volume >= 1 or sampleWidth != 2:
		return frames
	samples = array.array("h")
	samples.frombytes(frames)
	if sys.byteorder != "little":
		samples.byteswap()
	samples = array.array("h", (int(s * volume) for s in samples))
	if sys.byteorder != "little":
		samples.byteswap()
	return samples.tobytes()


def play(name: str, kind: str | None = None) -> None:
	"""Play one of the add-on's sounds by name, or a WAV file the user chose by its full path.

	kind is NOTIFICATION or EFFECTS; by default, notification sounds and custom files follow the
	notification volume and the rest the effects volume.
	"""
	settings = config.conf[CONFIG_SECTION]
	if not settings["sounds"]:
		return
	path = name if os.path.isabs(name) else os.path.join(SOUNDS_DIR, f"{name}.wav")
	if not os.path.isfile(path):
		log.debugWarning(f"WhatsApp Access: missing sound {path}")
		return
	if kind is None:
		kind = NOTIFICATION if name in NOTIFICATION_SOUNDS or os.path.isabs(name) else EFFECTS
	volume = int(settings[kind]) / 100
	if volume <= 0:
		return
	threading.Thread(target=_play, args=(path, volume), name="whatsAppAccess.sound", daemon=True).start()


def _play(path: str, volume: float) -> None:
	try:
		with wave.open(path, "rb") as file:
			channels, width, rate = file.getnchannels(), file.getsampwidth(), file.getframerate()
			frames = scaled(file.readframes(file.getnframes()), width, volume)
		player = nvwave.WavePlayer(
			channels=channels,
			samplesPerSec=rate,
			bitsPerSample=width * 8,
			outputDevice=config.conf["audio"]["outputDevice"],
			wantDucking=False,
			purpose=nvwave.AudioPurpose.SOUNDS,
		)
		player.feed(frames)
		player.idle()
	except Exception:  # noqa: BLE001 - a sound that cannot play must not break anything
		log.debugWarning(f"WhatsApp Access: could not play {path}", exc_info=True)
