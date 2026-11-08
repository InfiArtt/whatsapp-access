from whatsAppAccess import shortcuts


def test_every_section_has_shortcuts():
    for title, items in shortcuts.sections():
        assert title
        assert items
        for keys, action in items:
            assert keys and action


def test_the_list_reads_as_lines():
    text = shortcuts.shortcutsText()
    assert "Ctrl+/: Keyboard shortcuts" in text.splitlines()
    assert "Ctrl+S: Voice message speed: 1x, 1.5x, 2x" in text.splitlines()
