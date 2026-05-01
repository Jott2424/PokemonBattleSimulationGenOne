import importlib
from logic.base_profile import BaseProfile


def load_profile(name: str) -> BaseProfile:
    """
    Dynamically load a logic profile by module name.
    The module must live in the logic/ directory and expose a module-level
    `profile` attribute that is a BaseProfile instance.
    """
    try:
        mod = importlib.import_module(f"logic.{name}")
    except ModuleNotFoundError:
        raise ValueError(f"Logic profile '{name}' not found. Add logic/{name}.py to register it.")
    if not hasattr(mod, "profile"):
        raise ValueError(f"logic/{name}.py must define a module-level `profile` instance.")
    return mod.profile
