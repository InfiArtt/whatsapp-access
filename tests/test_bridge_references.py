from whatsAppAccess import whatsApp


def _references():
    with open(whatsApp.BRIDGE_PATH, encoding="utf-8") as file:
        return whatsApp.bridgeReferences(file.read())


def test_each_function_lists_the_whatsapp_members_it_uses():
    _bundles, refs = _references()
    found = {(function, module): members for function, module, members in refs}
    assert "previewCallLinkWithVoipInit" in found[("joinCallLink", "WAWebVoipPreviewCallLinkAction")]
    assert found[("meWid", "WAWebUserUtils")] == ["getMeUserOrThrow"]
    assert not any(module == "__debug" for _, module, _ in refs)


def test_the_bundles_the_bridge_loads_are_listed():
    bundles, _refs = _references()
    assert "WAWebProfileDrawer.react" in bundles
    assert "WAWebPollsCreatePollModal" in bundles
