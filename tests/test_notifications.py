from whatsAppAccess import notifications
from whatsAppAccess.notifications import Rule

PERSONAL = {"id": "1@c.us", "isGroup": False}
GROUP = {"id": "2@g.us", "isGroup": True}
MUTED_GROUP = {"id": "3@g.us", "isGroup": True, "muted": True}


def decide(chat, rule=None, mode="all", inOpenChat=False, readContent=True):
    return notifications.decide(rule, chat, inOpenChat, mode, "received", "notifyBell", readContent)


def test_general_settings_without_a_rule():
    assert decide(PERSONAL) == notifications.Decision(True, "received", True)
    assert decide(GROUP).sound == "notifyBell"
    assert not decide(MUTED_GROUP).announce
    assert not decide(GROUP, mode="personal").announce
    assert decide(MUTED_GROUP, inOpenChat=True).announce
    assert not decide(PERSONAL, mode="off").announce


def test_a_chat_can_always_or_never_be_read_out():
    assert decide(MUTED_GROUP, Rule(announce="always")).announce
    assert decide(GROUP, Rule(announce="always"), mode="personal").announce
    assert not decide(PERSONAL, Rule(announce="never")).announce
    assert not decide(PERSONAL, Rule(announce="never"), inOpenChat=True).announce


def test_a_chat_can_have_its_own_sound_and_say_less():
    assert decide(PERSONAL, Rule(sound="notifyFlute")).sound == "notifyFlute"
    assert decide(PERSONAL, Rule(sound=r"C:\sounds\ding.wav")).sound == r"C:\sounds\ding.wav"
    assert decide(PERSONAL, Rule(sound="none")).sound is None
    assert not decide(PERSONAL, Rule(content="nameOnly")).withContent
    assert decide(PERSONAL, Rule(content="full"), readContent=False).withContent
    assert not decide(PERSONAL, readContent=False).withContent


def test_rules_are_kept_as_json_without_defaults():
    rules = {"1@c.us": Rule(announce="always", sound="notifyBell"), "2@g.us": Rule()}
    text = notifications.saveRules(rules)
    assert "2@g.us" not in text
    assert notifications.loadRules(text) == {"1@c.us": Rule(announce="always", sound="notifyBell")}
    assert notifications.loadRules("not json") == {}
    assert notifications.loadRules('{"x": {"announce": "loud"}}') == {"x": Rule()}
