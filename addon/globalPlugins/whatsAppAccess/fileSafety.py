# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Files that come from other people's messages: safe names on disk, the mark Windows gives files from the
internet, and which ones may be opened with Enter.

Anyone can send a file with any name, so a name is never trusted. It imports nothing from NVDA, so it can
be tested on its own.
"""

import os
import sys
import unicodedata

FALLBACK_NAME = "WhatsApp file"
# Windows allows 255 characters in a name; this leaves room for " (12)" and a long folder.
MAX_NAME_CHARS = 150
_RESERVED_CHARACTERS = frozenset('<>:"/\\|?*')
# Names Windows keeps for devices, with or without an extension: "nul.txt" is the NUL device too.
_RESERVED_STEMS = frozenset(
	["CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"]
	+ [f"{prefix}{number}" for prefix in ("COM", "LPT") for number in "123456789¹²³"]
)

# Opened with Enter in their usual program. Everything else, such as programs, scripts, shortcuts and
# Office files with macros, can only be saved, so a file named "invoice.pdf.exe" never runs by itself.
OPENABLE_EXTENSIONS = frozenset(
	{
		# Pictures
		".jpg",
		".jpeg",
		".png",
		".gif",
		".webp",
		".bmp",
		".heic",
		".heif",
		".tif",
		".tiff",
		# Video
		".mp4",
		".m4v",
		".3gp",
		".mov",
		".mkv",
		".webm",
		".avi",
		# Sound
		".mp3",
		".m4a",
		".aac",
		".ogg",
		".opus",
		".wav",
		".flac",
		# Documents. Office opens files marked as from the internet in Protected View.
		".pdf",
		".txt",
		".rtf",
		".csv",
		".doc",
		".docx",
		".xls",
		".xlsx",
		".ppt",
		".pptx",
		".odt",
		".ods",
		".odp",
		".epub",
	}
)

# Zone 3 is the internet. Windows SmartScreen and Office's Protected View look for this mark.
_ZONE_IDENTIFIER = "[ZoneTransfer]\r\nZoneId=3\r\nReferrerUrl=https://web.whatsapp.com/\r\n"


def _cleanCharacter(character: str) -> str:
	category = unicodedata.category(character)
	if category == "Cf":
		return ""
	if category == "Cc" or character in _RESERVED_CHARACTERS:
		return "_"
	return character


def safeFileName(name: str) -> str:
	"""A name Windows accepts, from a name the sender chose.

	Only the last part of a path is kept. Reserved and control characters become "_". Invisible format
	characters are removed, so U+202E (right-to-left override) cannot show "fdp.exe" as "exe.pdf". Device
	names such as NUL get a "_" in front, and long names are shortened with their extension kept.

	:param name: The file name from the message.
	:return: A name that can be used in any folder.
	"""
	name = os.path.basename(name.replace("\\", "/"))
	cleaned = "".join(_cleanCharacter(c) for c in name).strip(" .")
	if not cleaned:
		return FALLBACK_NAME
	stem, extension = os.path.splitext(cleaned)
	if len(extension) > 16:
		# Not a real extension, just a dot somewhere in a long name.
		stem, extension = cleaned, ""
	if stem.split(".")[0].rstrip(" ").upper() in _RESERVED_STEMS:
		stem = f"_{stem}"
	if len(stem) + len(extension) > MAX_NAME_CHARS:
		stem = stem[: MAX_NAME_CHARS - len(extension)].rstrip(" .")
	return (stem or "_") + extension


def isSafeToOpen(path: str) -> bool:
	"""Whether a file from a message may be opened with its usual program, judging by its extension.

	:param path: The downloaded file.
	:return: True for pictures, video, sound and documents without macros.
	"""
	return os.path.splitext(path)[1].lower() in OPENABLE_EXTENSIONS


def markFromInternet(path: str) -> bool:
	"""Give the file the mark Windows gives downloads, so SmartScreen and Protected View check it.

	:param path: The downloaded file.
	:return: Whether the mark was written. NTFS has it; FAT32 drives such as many USB sticks do not.
	"""
	if sys.platform != "win32":
		return False
	try:
		with open(f"{path}:Zone.Identifier", "w", encoding="ascii") as stream:
			stream.write(_ZONE_IDENTIFIER)
	except OSError:
		return False
	return True
