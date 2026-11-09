# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""New versions of the add-on, from its GitHub releases rather than the Add-on Store.

This module uses only Python's standard library, so it can be tested without NVDA.
"""

import hashlib
import json
import os
import re
import urllib.request
from dataclasses import dataclass

REPOSITORY = "InfiArtt/whatsapp-access"
# The newest releases, newest first: one of them may be a required update even when it is not the latest.
RELEASES_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=30"
USER_AGENT = "WhatsAppAccess-NVDA-addon"
# Release files are only taken from GitHub itself.
DOWNLOAD_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
MAX_NOTES = 4000
# A release whose notes have a line starting with these words must be installed before WhatsApp can be
# used again, for when WhatsApp Web changed in a way older versions cannot follow. In CHANGELOG.md:
# "**Required update.** WhatsApp Web changed how …".
REQUIRED_MARK = re.compile(r"^\W*required update\b", re.IGNORECASE | re.MULTILINE)


class UpdateError(Exception):
	pass


@dataclass
class Release:
	version: str
	notes: str
	url: str
	fileName: str
	sha256: str
	required: bool = False
	"""Whether this release, or one between the installed version and it, is a required update."""


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
	"""The newest published release, from GitHub's answer.

	It must carry a .nvda-addon file from this repository with GitHub's SHA-256 of it. Without the checksum
	nothing is installed: the file can't be checked, and NVDA would run whatever arrived.
	"""
	if data.get("draft") or data.get("prerelease"):
		raise UpdateError("noRelease")
	version = str(data.get("tag_name") or "")
	versionTuple(version)
	for asset in data.get("assets") or []:
		name = str(asset.get("name") or "")
		url = str(asset.get("browser_download_url") or "")
		if name.endswith(".nvda-addon") and url.startswith(DOWNLOAD_PREFIX):
			digest = str(asset.get("digest") or "")
			sha256 = digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else ""
			if not sha256:
				raise UpdateError("noChecksum")
			notes = str(data.get("body") or "").strip()
			if len(notes) > MAX_NOTES:
				notes = notes[:MAX_NOTES].rstrip() + "…"
			# Only the name: it becomes a file in the temporary folder.
			return Release(version.lstrip("v"), notes, url, os.path.basename(name.replace("\\", "/")), sha256)
	raise UpdateError("noAddonFile")


def _open(url: str, accept: str, timeout: float):
	request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
	return urllib.request.urlopen(request, timeout=timeout)


def isRequired(notes: str) -> bool:
	return bool(REQUIRED_MARK.search(notes or ""))


def _published(data: dict) -> bool:
	if data.get("draft") or data.get("prerelease"):
		return False
	try:
		versionTuple(str(data.get("tag_name") or ""))
	except UpdateError:
		return False
	return True


def newestRelease(releases: list[dict], current: str) -> Release:
	"""The newest published release, from GitHub's list, and whether updating to it is required.

	It is required when any published release newer than current says so: someone on 0.4 must update
	when 0.5 was required, even if 0.5.1, the newest, was not.
	"""
	published = [data for data in releases if isinstance(data, dict) and _published(data)]
	if not published:
		raise UpdateError("noRelease")
	newest = max(published, key=lambda data: versionTuple(str(data["tag_name"])))
	release = parseRelease(newest)
	release.required = any(
		isNewer(str(data["tag_name"]), current) and isRequired(str(data.get("body") or ""))
		for data in published
	)
	return release


def latestRelease(current: str, timeout: float = 15) -> Release:
	try:
		with _open(RELEASES_URL, "application/vnd.github+json", timeout) as response:
			data = json.load(response)
	except OSError as e:
		code = getattr(e, "code", None)
		# 404: the repository is not public.
		raise UpdateError("noRelease" if code == 404 else f"network: {e}") from e
	except ValueError as e:
		raise UpdateError(f"network: {e}") from e
	if not isinstance(data, list):
		raise UpdateError("noRelease")
	return newestRelease(data, current)


def download(release: Release, path: str, timeout: float = 60) -> str:
	"""Save the release's add-on file at path, checking it against GitHub's SHA-256.

	A download that fails or does not match is removed, so no partial or damaged file is left behind.
	"""
	digest = hashlib.sha256()
	try:
		try:
			with (
				_open(release.url, "application/octet-stream", timeout) as response,
				open(path, "wb") as file,
			):
				while chunk := response.read(64 * 1024):
					digest.update(chunk)
					file.write(chunk)
		except OSError as e:
			raise UpdateError(f"network: {e}") from e
		if digest.hexdigest() != release.sha256:
			raise UpdateError("badChecksum")
	except BaseException:
		try:
			os.remove(path)
		except OSError:
			pass
		raise
	return path
