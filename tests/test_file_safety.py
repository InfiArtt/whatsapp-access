"""Files from other people's messages: names on disk, and which ones Enter may open."""

import sys

import pytest
from whatsAppAccess import fileSafety


@pytest.mark.parametrize(
    ("sent", "saved"),
    [
        ('lapor:an?"1"/2.pdf', "2.pdf"),
        ("a<b>c|d*e.txt", "a_b_c_d_e.txt"),
        ("...", "WhatsApp file"),
        ("", "WhatsApp file"),
        ("..\\..\\Windows\\win.ini", "win.ini"),
        # U+202E would show "fdp.exe" as "exe.pdf".
        ("tagihan\u202efdp.exe", "tagihanfdp.exe"),
        ("baris\nbaru.txt", "baris_baru.txt"),
        ("NUL", "_NUL"),
        ("nul.txt", "_nul.txt"),
        ("com1.tar.gz", "_com1.tar.gz"),
        ("console.txt", "console.txt"),
        ("foto. ", "foto"),
    ],
)
def test_names_become_safe(sent, saved):
    assert fileSafety.safeFileName(sent) == saved


def test_long_names_are_shortened_with_their_extension():
    name = fileSafety.safeFileName("a" * 400 + ".docx")
    assert len(name) == fileSafety.MAX_NAME_CHARS
    assert name.endswith(".docx")


@pytest.mark.parametrize("name", ["foto.JPG", "video.mp4", "suara.opus", "surat.pdf", "data.xlsx"])
def test_pictures_video_sound_and_documents_open(name):
    assert fileSafety.hasOpenableKind(name)


@pytest.mark.parametrize(
    "name",
    [
        "invoice.pdf.exe",
        "setup.msi",
        "run.bat",
        "run.cmd",
        "script.js",
        "script.vbs",
        "page.hta",
        "shortcut.lnk",
        "screensaver.scr",
        "macro.docm",
        "macro.xlsm",
        # Old Office formats can hold macros under their usual names; RTF often carries attacks on Word.
        "old.doc",
        "old.XLS",
        "old.ppt",
        "letter.rtf",
        "archive.zip",
        "page.html",
        "no extension",
    ],
)
def test_anything_that_can_run_is_not_opened(name, tmp_path):
    assert not fileSafety.hasOpenableKind(name)
    path = tmp_path / name
    path.write_bytes(b"x")
    fileSafety.markFromInternet(str(path))
    assert not fileSafety.isSafeToOpen(str(path))


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS alternate data streams")
def test_only_a_file_marked_as_from_the_internet_is_opened(tmp_path):
    path = tmp_path / "foto.jpg"
    path.write_bytes(b"x")
    # Not marked, as on a drive that cannot hold the mark.
    assert not fileSafety.isMarkedFromInternet(str(path))
    assert not fileSafety.isSafeToOpen(str(path))
    assert fileSafety.markFromInternet(str(path))
    assert fileSafety.isMarkedFromInternet(str(path))
    assert fileSafety.isSafeToOpen(str(path))


def test_a_missing_file_is_not_opened(tmp_path):
    assert not fileSafety.isSafeToOpen(str(tmp_path / "gone.jpg"))
