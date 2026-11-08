"""Run JavaScript in the hidden browser's WhatsApp Web page, to explore WhatsApp's modules while developing.

Usage: python tools/probe.py "expression"    or    python tools/probe.py -f body.js
A file is the body of an async function and ends with return; the value is printed as JSON.
It only reads unless the expression itself changes something. Never run it with code you have not read.
"""

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

ADDON_CODE = Path(__file__).resolve().parent.parent / "addon" / "globalPlugins" / "whatsAppAccess"


def _load(name: str) -> types.ModuleType:
    # Only cdp.py and webSocket.py, which need nothing from NVDA; the package's __init__ does.
    spec = importlib.util.spec_from_file_location(f"probed.{name}", ADDON_CODE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sys.modules["probed"] = types.ModuleType("probed")
sys.modules["probed"].__path__ = [str(ADDON_CODE)]
_load("webSocket")
cdp = _load("cdp")

PROFILE = Path(os.environ["APPDATA"]) / "nvda" / "whatsAppAccess" / "browser"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 3 and sys.argv[1] == "-f":
        # A file is a function body: it ends with return.
        body = Path(sys.argv[2]).read_text(encoding="utf-8")
    else:
        body = "return (" + " ".join(sys.argv[1:]) + ");"
    port, wsPath = cdp.readActivePort(PROFILE / "DevToolsActivePort")
    target = cdp.DebuggableBrowser(cdp.Browser("hidden", PROFILE, "browser.exe", ""), port, wsPath)
    connection = cdp.CdpConnection.open(target)
    try:
        pages = connection.call("Target.getTargets")["targetInfos"]
        page = next(p for p in pages if p["type"] == "page" and "web.whatsapp.com" in p["url"])
        session = connection.call("Target.attachToTarget", {"targetId": page["targetId"], "flatten": True})
        result = connection.call(
            "Runtime.evaluate",
            {
                "expression": "(async () => {\n" + body + "\n})()",
                "awaitPromise": True,
                "returnByValue": True,
            },
            sessionId=session["sessionId"],
            timeout=60,
        )
        if "exceptionDetails" in result:
            print("ERROR:", json.dumps(result["exceptionDetails"], ensure_ascii=False)[:2000])
        else:
            print(json.dumps(result["result"].get("value"), ensure_ascii=False, indent=1)[:20000])
    finally:
        connection.close()


if __name__ == "__main__":
    main()
