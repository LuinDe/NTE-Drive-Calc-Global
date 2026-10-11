"""tests_g231 shim: the original v230/tools/gen_team_form_actions.py with its paths re-pointed (see _g231_gen.py)."""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from _g231_gen import load as _load  # noqa: E402

_mod = _load("gen_team_form_actions")
if __name__ == "__main__":
    _sys.exit(_mod.main(_sys.argv[1:]))
_sys.modules[__name__] = _mod
