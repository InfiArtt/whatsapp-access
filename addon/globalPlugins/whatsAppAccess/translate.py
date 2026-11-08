# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""Translating a message, only when the user asks: Google Translate's free web endpoint, which needs no
key, as many NVDA add-ons use it. The text goes to Google; nothing is sent anywhere unless the user
presses the key. It imports nothing from NVDA, so it can be tested on its own.
"""

import json
import urllib.parse
import urllib.request
from collections.abc import Callable

URL = "https://translate.googleapis.com/translate_a/single"
TIMEOUT_SECONDS = 15
# Long messages go in parts of about this many characters, split at the end of a line or sentence.
CHUNK_CHARS = 4000

# The languages offered in the settings, by their codes for Google Translate.
LANGUAGES = (
	"af", "ar", "bg", "bn", "ca", "cs", "da", "de", "el", "en", "es", "et", "fa", "fi", "fr", "he", "hi",
	"hr", "hu", "id", "it", "ja", "jv", "ko", "lt", "lv", "ms", "nl", "no", "pl", "pt", "ro", "ru", "sk",
	"sl", "sr", "su", "sv", "sw", "ta", "th", "tl", "tr", "uk", "ur", "vi", "zh-CN", "zh-TW",
)  # fmt: skip


class TranslationError(Exception):
	pass


def _post(text: str, target: str) -> bytes:
	data = urllib.parse.urlencode(
		{"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text}
	).encode()
	request = urllib.request.Request(URL, data=data, headers={"User-Agent": "Mozilla/5.0"})
	with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
		return response.read()


def parse(raw: bytes) -> tuple[str, str]:
	"""The translation and the language Google found the text to be in, from its answer."""
	answer = json.loads(raw.decode("utf-8"))
	sentences = answer[0] or []
	translation = "".join(part[0] for part in sentences if part and part[0])
	source = answer[2] if len(answer) > 2 and isinstance(answer[2], str) else ""
	return translation, source


def chunks(text: str, size: int = CHUNK_CHARS) -> list[str]:
	"""The text in parts no longer than size, cut after a line or a sentence where it can be."""
	parts = []
	while len(text) > size:
		cut = max(text.rfind("\n", 0, size), text.rfind(". ", 0, size), text.rfind(" ", 0, size))
		cut = cut + 1 if cut > 0 else size
		parts.append(text[:cut])
		text = text[cut:]
	if text:
		parts.append(text)
	return parts


def translate(text: str, target: str, post: Callable[[str, str], bytes] = _post) -> tuple[str, str]:
	"""Translate text into the target language. Returns the translation and the language it was in."""
	if not text.strip():
		return text, ""
	results, source = [], ""
	try:
		for part in chunks(text):
			translation, found = parse(post(part, target))
			results.append(translation)
			source = source or found
	except (OSError, ValueError, IndexError, TypeError) as e:
		raise TranslationError(str(e)) from e
	return "".join(results), source
