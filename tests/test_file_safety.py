"""Files from other people's messages: names on disk, and which ones Enter may open."""

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
        ("tagihan‮fdp.exe", "tagihanfdp.exe"),
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
    assert fileSafety.isSafeToOpen(name)


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
        "archive.zip",
        "page.html",
        "no extension",
    ],
)
def test_anything_that_can_run_is_not_opened(name):
    assert not fileSafety.isSafeToOpen(name)
