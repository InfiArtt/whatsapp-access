# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""The add-on's short sounds, so the user hears what happened without waiting for speech."""

import array
import os
import sys
import threading
import time
import wave

import config
import nvwave
from logHandler import log

from . import dataFolder
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
MIC_OFF = "micOff"
MIC_ON = "micOn"
CALL_JOIN = "callJoin"
CALL_LEAVE = "callLeave"
CALL_HAND = "callHand"
CALL_REACTION = "callReaction"
CHAT_OPEN = "chatOpen"
CHAT_CLOSE = "chatClose"
OPEN_CHAT_MESSAGE = "openChatMessage"
VOICE_NEXT = "voiceNext"
VOICE_END = "voiceEnd"

# Which volume setting a sound follows: new messages and the ring, or everything else.
NOTIFICATION = "notificationVolume"
EFFECTS = "effectsVolume"
NOTIFICATION_SOUNDS = {RECEIVED, RING, OPEN_CHAT_MESSAGE, "notifyBell", "notifyKalimba", "notifyFlute"}


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
	path = _path(name)
	if not os.path.isfile(path):
		log.debugWarning(f"WhatsApp Access: missing sound {path}")
		return
	if kind is None:
		kind = NOTIFICATION if name in NOTIFICATION_SOUNDS or os.path.isabs(name) else EFFECTS
	volume = int(settings[kind]) / 100
	if volume <= 0:
		return
	threading.Thread(target=_play, args=(path, volume), name="whatsAppAccess.sound", daemon=True).start()


def ownSoundsFolder() -> str:
	"""The user's own sounds: a WAV file here named as one of the add-on's, such as sent.wav, plays instead."""
	base = dataFolder.addonDataPath()
	return os.path.join(base, "mySounds") if base else ""


def _path(name: str) -> str:
	if os.path.isabs(name):
		return name
	folder = ownSoundsFolder()
	own = os.path.join(folder, f"{name}.wav") if folder else ""
	if own and os.path.isfile(own):
		return own
	return os.path.join(SOUNDS_DIR, f"{name}.wav")


# The ring: played again and again until the call is answered, declined or over, as a phone rings.
RING_GAP_SECONDS = 1.0
# WhatsApp stops ringing by itself after about a minute; so does the add-on, should it miss the end.
RING_LIMIT_SECONDS = 75.0
_ringStop = threading.Event()
_ringPlayer = None
_ringLock = threading.Lock()


def startRing(name: str) -> None:
	"""Ring with this sound (an add-on sound or a WAV file's path) until stopRing; "none" is silent."""
	stopRing()
	settings = config.conf[CONFIG_SECTION]
	path = _path(name or RING)
	if name == "none" or not settings["sounds"]:
		return
	if not os.path.isfile(path):
		log.debugWarning(f"WhatsApp Access: missing ring {path}; using the add-on's own")
		path = _path(RING)
	stop = threading.Event()
	global _ringStop
	_ringStop = stop
	threading.Thread(target=_ring, args=(path, stop), name="whatsAppAccess.ring", daemon=True).start()


def _ring(path: str, stop: threading.Event) -> None:
	deadline = time.monotonic() + RING_LIMIT_SECONDS
	while not stop.is_set() and time.monotonic() < deadline:
		# Read each time, so F7 and F8 change the ring while it rings.
		volume = int(config.conf[CONFIG_SECTION][NOTIFICATION]) / 100
		if volume > 0:
			_play(path, volume, keep=True)
		stop.wait(RING_GAP_SECONDS)


def windowsRingtones() -> list[tuple[str, str]]:
	"""Windows' own ringtones in its Media folder, as (full path, name), such as Ring01.wav as "Ring 01"."""
	media = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Media")
	try:
		names = sorted(os.listdir(media))
	except OSError:
		return []
	found = []
	for name in names:
		stem, extension = os.path.splitext(name)
		if extension.lower() != ".wav":
			continue
		if stem.lower().startswith("ring") and stem[4:].isdigit():
			found.append((os.path.join(media, name), f"Ring {stem[4:]}"))
		elif stem.lower() == "windows ringin":
			found.append((os.path.join(media, name), "Windows Ringin"))
	return found


def preview(name: str) -> None:
	"""Play a sound once to hear it in the settings, stopping the one heard before, however long."""
	stopRing()
	settings = config.conf[CONFIG_SECTION]
	path = _path(name)
	if name == "none" or not settings["sounds"] or not os.path.isfile(path):
		return
	volume = int(settings[NOTIFICATION]) / 100
	if volume > 0:
		threading.Thread(
			target=_play,
			args=(path, volume),
			kwargs={"keep": True},
			name="whatsAppAccess.preview",
			daemon=True,
		).start()


def previewPlaying() -> bool:
	"""Whether a sound heard in the settings, or the ring, is playing now."""
	with _ringLock:
		return _ringPlayer is not None


def stopRing() -> None:
	"""Stop the ring at once, in the middle of the sound too."""
	_ringStop.set()
	with _ringLock:
		player = _ringPlayer
	if player is not None:
		try:
			player.stop()
		except Exception:  # noqa: BLE001 - it may have just finished
			log.debugWarning("WhatsApp Access: stopping the ring", exc_info=True)


def _play(path: str, volume: float, keep: bool = False) -> None:
	"""Play a WAV file to its end. With keep, it is the ring, which stopRing can cut short."""
	global _ringPlayer
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
		if keep:
			with _ringLock:
				_ringPlayer = player
		try:
			player.feed(frames)
			player.idle()
		finally:
			if keep:
				with _ringLock:
					_ringPlayer = None
	except Exception:  # noqa: BLE001 - a sound that cannot play must not break anything
		log.debugWarning(f"WhatsApp Access: could not play {path}", exc_info=True)
