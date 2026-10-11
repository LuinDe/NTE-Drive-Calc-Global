"""Load an ORIGINAL v230/tools generator with its hard-coded paths re-pointed (tests_g231 harness).

The generators (gen_team_rotation_data / gen_team_form_actions / gen_team_custom_actions) hard-code
work/l10n_root and app_test/_internal.  This loader executes the original file unchanged (so __file__ and the
"generator sha256" it embeds stay the original's), then rebases every module-level Path - and every Path default
of a module-level function - that lies under the old root / runtime onto NTE_G231_ROOT / NTE_G231_INTERNAL.
Inputs outside those trees (work/rotation_research/*) are left as they are (read-only).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

V = Path(os.environ["NTE_G231_V"])
ORIGINAL_TOOLS = Path(os.environ.get("NTE_G231_ORIGINAL_TOOLS", str(V / "tools")))
REBASE = (
    (V / "work" / "l10n_root", Path(os.environ["NTE_G231_ROOT"])),
    (V / "app_test" / "_internal", Path(os.environ["NTE_G231_INTERNAL"])),
)


def _rebase(value):
    if isinstance(value, Path):
        for old, new in REBASE:
            try:
                rel = value.relative_to(old)
            except ValueError:
                continue
            return new / rel
    return value


def load(name: str) -> types.ModuleType:
    if name in sys.modules and getattr(sys.modules[name], "_G231_REBASED", False):
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ORIGINAL_TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    for attr, value in list(vars(mod).items()):
        new = _rebase(value)
        if new is not value:
            setattr(mod, attr, new)
        if isinstance(value, types.FunctionType) and value.__module__ == name:
            if value.__defaults__:
                value.__defaults__ = tuple(_rebase(d) for d in value.__defaults__)
            if value.__kwdefaults__:
                value.__kwdefaults__ = {k: _rebase(d) for k, d in value.__kwdefaults__.items()}
    mod._G231_REBASED = True
    return mod
