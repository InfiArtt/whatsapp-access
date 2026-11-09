import os
import subprocess
import sys

import pytest
from whatsAppAccess import browserLauncher


def install(root, folder, executable, version):
    application = root / folder
    application.mkdir(parents=True)
    (application / executable).write_bytes(b"")
    (application / version).mkdir()
    return application / executable


def test_versions():
    assert browserLauncher.parseVersion("157.1.99.55") == (157, 1, 99, 55)
    assert browserLauncher.parseVersion("SetupMetrics") == ()


def test_installed_browsers_are_found_in_order_of_preference(tmp_path):
    install(tmp_path, r"Google\Chrome\Application", "chrome.exe", "150.0.1.2")
    install(tmp_path, r"BraveSoftware\Brave-Browser\Application", "brave.exe", "157.1.99.55")
    found = browserLauncher.findBrowsers([str(tmp_path)], registry=lambda exe: None, fileVersion=lambda p: ())
    assert [(b.key, b.major) for b in found] == [("brave", 157), ("chrome", 150)]


def test_a_browser_only_in_the_registry_is_found(tmp_path):
    path = install(tmp_path, "Somewhere", "vivaldi.exe", "140.0.0.1")
    found = browserLauncher.findBrowsers(
        [str(tmp_path / "empty")], registry=lambda exe: str(path) if exe == "vivaldi.exe" else None
    )
    assert [b.key for b in found] == ["vivaldi"]


def browser(key, major):
    return browserLauncher.InstalledBrowser(key, key.title(), f"C:/{key}.exe", (major, 0, 0, 0))


def test_automatic_choice_skips_browsers_that_are_too_old():
    browsers = [browser("brave", 110), browser("chrome", 157), browser("edge", 157)]
    assert browserLauncher.chooseBrowser(browsers).key == "chrome"


def test_the_users_choice_wins_when_it_is_new_enough():
    browsers = [browser("brave", 157), browser("chrome", 157), browser("vivaldi", 119)]
    assert browserLauncher.chooseBrowser(browsers, "chrome").key == "chrome"
    # Too old: fall back to the automatic choice.
    assert browserLauncher.chooseBrowser(browsers, "vivaldi").key == "brave"
    assert browserLauncher.chooseBrowser([browser("brave", 100)]) is None


def test_the_hidden_browser_says_it_is_chrome_not_headless():
    arguments = browserLauncher.launchArguments(browser("brave", 157), r"C:\profile", (11, 22))
    assert "--headless=new" in arguments
    assert r"--user-data-dir=C:\profile" in arguments
    agent = next(a for a in arguments if a.startswith("--user-agent="))
    assert "Chrome/157.0.0.0" in agent
    assert "Headless" not in agent
    # Site isolation stays on.
    assert not [
        a
        for a in arguments
        if "site-per-process" in a or "site-isolation" in a or "renderer-process-limit" in a
    ]
    assert arguments[-1] == "about:blank"
    metadata = browserLauncher.chromeUserAgentMetadata((157, 1, 99, 55))
    assert [b["brand"] for b in metadata["brands"]] == ["Chromium", "Google Chrome", "Not=A?Brand"]
    assert metadata["fullVersionList"][1]["version"] == "157.0.0.0"


def test_a_profile_is_in_use_while_its_lockfile_is_open(tmp_path):
    assert not browserLauncher.profileInUse(str(tmp_path))
    lock = tmp_path / "lockfile"
    with open(lock, "w"):
        assert browserLauncher.profileInUse(str(tmp_path))
    # Once the browser is gone the stale lockfile is cleared.
    assert not browserLauncher.profileInUse(str(tmp_path))
    assert not lock.exists()


def test_devtools_goes_over_a_pipe_never_a_port():
    arguments = browserLauncher.launchArguments(browser("brave", 157), r"C:\profile", (11, 22))
    assert "--remote-debugging-pipe" in arguments
    assert "--remote-debugging-io-pipes=11,22" in arguments
    assert not [
        a for a in arguments if a.startswith(("--remote-debugging-port", "--remote-debugging-address"))
    ]


def fake_browser(profile):
    """A process whose command line has the profile, as the hidden browser's has."""
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)", f"--user-data-dir={profile}", "--headless=new"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows processes")
def test_a_process_is_the_hidden_browser_only_with_this_profile(tmp_path):
    # [ ] and ' would be wildcards or quotes inside a pattern; here they are plain characters.
    profile = str(tmp_path / "D Tools [portable]" / "Rafli's profile")
    executable = os.path.basename(sys.executable)
    process = fake_browser(profile)
    try:
        assert browserLauncher.isHiddenBrowser(process.pid, profile, executable)
        # The id now names another program, or the same program with another profile.
        assert not browserLauncher.isHiddenBrowser(process.pid, profile, "brave.exe")
        assert not browserLauncher.isHiddenBrowser(process.pid, profile[:-1], executable)
        assert not browserLauncher.isHiddenBrowser(process.pid, str(tmp_path / "other"), executable)
    finally:
        process.kill()
        process.wait()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows processes")
def test_leftovers_are_found_by_their_profile(tmp_path):
    profile = str(tmp_path / "D Tools [portable]" / "profile")
    other = str(tmp_path / "D Tools [portable]" / "profile2")
    executable = os.path.basename(sys.executable)
    leftover, bystander = fake_browser(profile), fake_browser(other)
    try:
        browserLauncher.stopHiddenBrowsers(profile, executable)
        assert leftover.wait(15) is not None
        assert bystander.poll() is None
    finally:
        for process in (leftover, bystander):
            process.kill()
            process.wait()


def test_a_reused_process_id_is_never_closed(tmp_path, monkeypatch):
    """The pid file names a process that is no longer the hidden browser, such as the user's own Brave."""
    (tmp_path / "lockfile").write_text("")
    (tmp_path / browserLauncher.PID_FILE).write_text("4242", encoding="ascii")
    ran = []
    monkeypatch.setattr(browserLauncher.sys, "platform", "win32")
    monkeypatch.setattr(browserLauncher, "profileInUse", lambda profile: True)
    monkeypatch.setattr(browserLauncher, "_waitUntilFree", lambda profile, seconds: False)
    monkeypatch.setattr(browserLauncher, "isHiddenBrowser", lambda pid, profile, exe: False)
    monkeypatch.setattr(browserLauncher, "stopHiddenBrowsers", lambda profile, exe: ran.append("byProfile"))
    monkeypatch.setattr(browserLauncher, "_quiet", lambda arguments, timeout, env=None: ran.append(arguments))
    browserLauncher.closeLeftovers(str(tmp_path), "brave.exe")
    assert ran == ["byProfile"]
    # Once confirmed as the hidden browser, it is closed with its own processes.
    ran.clear()
    monkeypatch.setattr(browserLauncher, "isHiddenBrowser", lambda pid, profile, exe: pid == 4242)
    browserLauncher.closeLeftovers(str(tmp_path), "brave.exe")
    assert "PID eq 4242" in ran[0]
    assert ran[1] == "byProfile"
