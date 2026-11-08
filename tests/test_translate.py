import json

import pytest
from whatsAppAccess import translate


def answer(parts, source):
    return json.dumps([[[t, o, None, None, 3] for t, o in parts], None, source]).encode()


def test_a_translation_and_the_language_it_was_in():
    raw = answer(
        [("Hello, see you at 8. ", "Halo, sampai jumpa jam 8. "), ("*Don't be late*", "*Jangan telat*")], "id"
    )
    assert translate.parse(raw) == ("Hello, see you at 8. *Don't be late*", "id")


def test_long_text_goes_in_parts_cut_between_sentences():
    text = "Kalimat pendek. " * 600
    parts = translate.chunks(text, 4000)
    assert "".join(parts) == text
    assert all(len(p) <= 4000 for p in parts)
    assert all(p.endswith(" ") for p in parts[:-1])


def test_each_part_is_translated_and_joined():
    asked = []

    def post(text, target):
        asked.append((len(text), target))
        return answer([(text.upper(), text)], "en")

    translation, source = translate.translate("ab. " * 1500, "id", post=post)
    assert translation == ("ab. " * 1500).upper()
    assert source == "en"
    assert len(asked) == 2 and all(target == "id" for _, target in asked)


def test_empty_text_is_not_sent():
    def post(text, target):
        raise AssertionError("nothing should be sent")

    assert translate.translate("  ", "en", post=post) == ("  ", "")


def test_no_connection_is_reported():
    def post(text, target):
        raise OSError("no internet")

    with pytest.raises(translate.TranslationError):
        translate.translate("halo", "en", post=post)
