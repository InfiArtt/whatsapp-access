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
