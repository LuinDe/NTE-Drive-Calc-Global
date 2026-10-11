"""tests_g231 shim: the original v230/tools/gen_team_rotation_data.py with its paths re-pointed (see _g231_gen.py).

Global 2.3.1 (rev2, translation review 10-08): the Korean step tooltips (label_ko, Korean only) use the official term
援护技 = 서포트 스킬; four approved rotations (Hathor, Adler, Zankou, Fadia) said 지원 스킬 in research_result.json.
The map is applied to the generated module text (label_ko is the only Korean in it) and the header names this shim
as the generator.  The original tool and its input stay unchanged (Global 2.3.0 reproduces as before).
"""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from _g231_gen import load as _load  # noqa: E402

_mod = _load("gen_team_rotation_data")

LABEL_TERMS = (("지원 스킬", "서포트 스킬"),)
_HEADER_OLD = "# GENERATED FILE - DO NOT EDIT.  Regenerate with scratchpad/v230/tools/gen_team_rotation_data.py\n"
_HEADER_NEW = ("# GENERATED FILE - DO NOT EDIT.  Regenerate with work_g231/tests_g231/tools_shim/gen_team_rotation_data.py "
               "(scratchpad/v230/tools/gen_team_rotation_data.py + the Global 2.3.1 label_ko term map)\n")

if not getattr(_mod, "_G231_TERMS", False):
    _original_build = _mod.build

    def _build(*args, **kwargs):
        text, errors, info = _original_build(*args, **kwargs)
        if text:
            assert text.count(_HEADER_OLD) == 1, "generator header changed"
            text = text.replace(_HEADER_OLD, _HEADER_NEW)
            replaced = 0
            for old, new in LABEL_TERMS:
                replaced += text.count(old)
                text = text.replace(old, new)
            compile(text, "team_rotation_data.py", "exec")
            info = list(info) + [f"Global 2.3.1 label_ko term map: {replaced} replacement(s) {LABEL_TERMS}"]
        return text, errors, info

    _mod.build = _build
    _mod._G231_TERMS = True
    _mod.G231_LABEL_TERMS = LABEL_TERMS

if __name__ == "__main__":
    _sys.exit(_mod.main(_sys.argv[1:]))
_sys.modules[__name__] = _mod
