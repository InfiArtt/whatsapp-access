import importlib.util
from pathlib import Path

CONFIG_SPEC = Path(__file__).parent.parent / "addon" / "globalPlugins" / "whatsAppAccess" / "configSpec.py"


def load():
    spec = importlib.util.spec_from_file_location("whatsAppAccessConfigSpec", CONFIG_SPEC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_voice_notes_are_mono_by_default():
    # WhatsApp on the iPhone does not play stereo voice notes: it says they are no longer available.
    spec = load().CONFIG_SPEC
    assert spec["stereoVoiceNotes"] == "boolean(default=False)"
    # The old setting, on for everyone until 0.6.5, must not be read again: everyone starts in mono.
    assert "stereo" not in spec
