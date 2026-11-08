"""The WhatsApp login and the user's own sounds stay through an update, and go when the add-on is removed."""

from whatsAppAccess import dataFolder


def make_data(config):
    data = config / "whatsAppAccess"
    (data / "browser").mkdir(parents=True)
    (data / "browser" / "login").write_text("linked")
    (data / "mySounds").mkdir()
    (data / "mySounds" / "sent.wav").write_bytes(b"RIFF")
    return data


def test_an_update_moves_the_data_aside_and_puts_it_back(tmp_path):
    data = make_data(tmp_path)
    stopped = []
    assert dataFolder.keepThroughUpdate(str(tmp_path), lambda: stopped.append(True), lambda: None)
    assert stopped == [True]
    assert not data.exists()
    # The old version's uninstall task removes whatsAppAccess, which is no longer there.
    assert dataFolder.restoreAfterUpdate(str(tmp_path))
    assert (data / "browser" / "login").read_text() == "linked"
    assert (data / "mySounds" / "sent.wav").exists()
    assert not (tmp_path / "whatsAppAccess.updating").exists()


def test_a_profile_made_meanwhile_gives_way_to_the_kept_one(tmp_path):
    make_data(tmp_path)
    dataFolder.keepThroughUpdate(str(tmp_path), lambda: None, lambda: None)
    (tmp_path / "whatsAppAccess" / "browser").mkdir(parents=True)
    assert dataFolder.restoreAfterUpdate(str(tmp_path))
    assert (tmp_path / "whatsAppAccess" / "browser" / "login").exists()


def test_nothing_to_keep_or_restore(tmp_path):
    assert not dataFolder.keepThroughUpdate(str(tmp_path), lambda: None, lambda: None)
    assert not dataFolder.restoreAfterUpdate(str(tmp_path))


def test_an_update_is_told_from_a_removal(tmp_path):
    addons = tmp_path / "addons"
    (addons / "whatsAppAccess").mkdir(parents=True)
    assert not dataFolder.updatePending(str(addons / "whatsAppAccess"))
    (addons / "whatsAppAccess.pendingInstall").mkdir()
    assert dataFolder.updatePending(str(addons / "whatsAppAccess"))
    assert not dataFolder.updatePending(str(addons / "whatsAppAccess.pendingInstall"))


def test_removing_the_add_on_removes_its_data(tmp_path):
    make_data(tmp_path)
    (tmp_path / "whatsAppAccess.updating").mkdir()
    dataFolder.removeAll(str(tmp_path))
    assert not (tmp_path / "whatsAppAccess").exists()
    assert not (tmp_path / "whatsAppAccess.updating").exists()
