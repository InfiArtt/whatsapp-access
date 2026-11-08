import builtins
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "addon" / "globalPlugins" / "whatsAppAccess"

# The package's __init__ imports NVDA. Its other modules do not, so load them without running __init__.
_package = types.ModuleType("whatsAppAccess")
_package.__path__ = [str(PACKAGE_DIR)]
sys.modules["whatsAppAccess"] = _package
sys.path.insert(0, str(ROOT))
# addonHandler.initTranslation() installs _() in NVDA.
builtins._ = lambda text: text
