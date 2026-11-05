"""Make the repo's code importable from the tests."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "data-generator"), str(ROOT / "systems")]


def load_service(name: str):
    """Import systems/<name>/app.py under a unique module name (every service file is called app.py)."""
    spec = importlib.util.spec_from_file_location(f"{name}_app", ROOT / "systems" / name / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
