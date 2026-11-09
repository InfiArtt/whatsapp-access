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


def test_the_data_moves_out_of_the_configuration_folder(tmp_path):
    data = make_data(tmp_path / "config")
    local = tmp_path / "local" / dataFolder.LOCAL_DATA_NAME
    assert dataFolder.moveData(str(data), str(local))
    assert not data.exists()
    assert (local / "browser" / "login").read_text() == "linked"
    assert (local / "mySounds" / "sent.wav").exists()


def test_data_already_moved_wins_and_the_old_copy_goes(tmp_path):
    data = make_data(tmp_path / "config")
    local = tmp_path / "local"
    (local / "browser").mkdir(parents=True)
    (local / "browser" / "login").write_text("newer")
    (local / "mySounds").mkdir()
    assert not dataFolder.moveData(str(data), str(local))
    assert not data.exists()
    assert (local / "browser" / "login").read_text() == "newer"


def test_a_new_folder_with_only_sounds_still_gets_the_login(tmp_path):
    data = make_data(tmp_path / "config")
    local = tmp_path / "local"
    (local / "mySounds").mkdir(parents=True)
    assert dataFolder.moveData(str(data), str(local))
    assert not data.exists()
    assert (local / "browser" / "login").read_text() == "linked"


def test_nothing_to_move(tmp_path):
    assert not dataFolder.moveData(str(tmp_path / "none"), str(tmp_path / "local"))
    data = make_data(tmp_path / "config")
    assert not dataFolder.moveData(str(data), str(data))
    assert data.exists()


def test_a_move_across_drives_copies_then_removes(tmp_path, monkeypatch):
    data = make_data(tmp_path / "config")
    local = tmp_path / "local"
    replace = dataFolder.os.replace

    def acrossDrives(source, target):
        if str(source) == str(data):
            raise OSError(17, "The system cannot move the file to a different disk drive")
        replace(source, target)

    monkeypatch.setattr(dataFolder.os, "replace", acrossDrives)
    assert dataFolder.moveData(str(data), str(local))
    assert not data.exists()
    assert (local / "browser" / "login").read_text() == "linked"
    assert not (tmp_path / "local.moving").exists()


def test_removing_the_add_on_removes_every_copy(tmp_path):
    config = tmp_path / "config"
    make_data(config)
    local = tmp_path / "local"
    (local / "browser").mkdir(parents=True)
    dataFolder.removeAll(str(config), (str(local), ""))
    assert not (config / "whatsAppAccess").exists()
    assert not local.exists()


def test_installing_again_before_restarting_keeps_the_first_kept_login(tmp_path):
    make_data(tmp_path)
    assert dataFolder.keepThroughUpdate(str(tmp_path), lambda: None, lambda: None)
    # Before NVDA restarted, WhatsApp was started again: an empty profile appeared where the login was.
    (tmp_path / "whatsAppAccess" / "browser").mkdir(parents=True)
    assert dataFolder.keepThroughUpdate(str(tmp_path), lambda: None, lambda: None)
    assert dataFolder.restoreAfterUpdate(str(tmp_path))
    assert (tmp_path / "whatsAppAccess" / "browser" / "login").read_text() == "linked"


def test_media_opened_with_enter_are_cleared(tmp_path, monkeypatch):
    monkeypatch.setattr(dataFolder.tempfile, "gettempdir", lambda: str(tmp_path))
    media = tmp_path / dataFolder.TEMP_MEDIA_NAME
    media.mkdir()
    (media / "photo.jpg").write_bytes(b"x")
    dataFolder.clearTempMedia()
    assert not media.exists()
