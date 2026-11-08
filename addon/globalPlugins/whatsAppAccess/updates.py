# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""New versions of the add-on, from its GitHub releases rather than the Add-on Store.

This module uses only Python's standard library, so it can be tested without NVDA.
"""

import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass

REPOSITORY = "InfiArtt/whatsapp-access"
LATEST_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
USER_AGENT = "WhatsAppAccess-NVDA-addon"
# Release files are only taken from GitHub itself.
DOWNLOAD_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
MAX_NOTES = 4000


class UpdateError(Exception):
	pass


@dataclass
class Release:
	version: str
	notes: str
	url: str
	fileName: str
	sha256: str | None


def versionTuple(version: str) -> tuple[int, ...]:
	"""'v1.2.10' -> (1, 2, 10). Anything after the numbers, such as '-beta', is ignored."""
	match = re.match(r"v?(\d+(?:\.\d+)*)", version.strip())
	if not match:
		raise UpdateError(f"badVersion: {version}")
	return tuple(int(part) for part in match.group(1).split("."))


def isNewer(latest: str, current: str) -> bool:
	a, b = versionTuple(latest), versionTuple(current)
	length = max(len(a), len(b))
	return a + (0,) * (length - len(a)) > b + (0,) * (length - len(b))


def parseRelease(data: dict) -> Release:
	"""The newest published release, from GitHub's answer; it must carry a .nvda-addon file."""
	if data.get("draft") or data.get("prerelease"):
		raise UpdateError("noRelease")
	version = str(data.get("tag_name") or "")
	versionTuple(version)
	for asset in data.get("assets") or []:
		name = str(asset.get("name") or "")
		url = str(asset.get("browser_download_url") or "")
		if name.endswith(".nvda-addon") and url.startswith(DOWNLOAD_PREFIX):
			digest = str(asset.get("digest") or "")
			sha256 = digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else None
			notes = str(data.get("body") or "").strip()
			if len(notes) > MAX_NOTES:
				notes = notes[:MAX_NOTES].rstrip() + "…"
			return Release(version.lstrip("v"), notes, url, name, sha256)
	raise UpdateError("noAddonFile")


def _open(url: str, accept: str, timeout: float):
	request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
	return urllib.request.urlopen(request, timeout=timeout)


def latestRelease(timeout: float = 15) -> Release:
	try:
		with _open(LATEST_URL, "application/vnd.github+json", timeout) as response:
			data = json.load(response)
	except OSError as e:
		code = getattr(e, "code", None)
		# 404: the repository has no published release yet, or is not public.
		raise UpdateError("noRelease" if code == 404 else f"network: {e}") from e
	return parseRelease(data)


def download(release: Release, path: str, timeout: float = 60) -> str:
	"""Save the release's add-on file at path, checking it against GitHub's SHA-256 when there is one."""
	digest = hashlib.sha256()
	try:
		with _open(release.url, "application/octet-stream", timeout) as response, open(path, "wb") as file:
			while chunk := response.read(64 * 1024):
				digest.update(chunk)
				file.write(chunk)
	except OSError as e:
		raise UpdateError(f"network: {e}") from e
	if release.sha256 and digest.hexdigest() != release.sha256:
		raise UpdateError("badChecksum")
	return path
