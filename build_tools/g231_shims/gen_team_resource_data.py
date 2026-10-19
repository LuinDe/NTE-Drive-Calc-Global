"""tests_g231 shim: work_g231/teamsim_energy/tools/gen_team_resource_data.py run against NTE_G231_ROOT/src.

The generator merges the four reviewed resource-data chunks (teamsim_energy/data/chunk_0..3.json) into
src/services/team_resource_data.py (energy per hit, Esper-Cycle gauge, cooldowns, provenance per cell).  This shim
only supplies the tree: ``gen_team_resource_data.py <NTE_G231_ROOT>/src [--check] [...]``.  It writes nothing with
``--check``; without it, the module of that tree is (re)written.  finalize_g231.sh gen phase: run it after
gen_team_custom_actions (hand-off, teamsim_energy/reports/handoff_integration.md).
"""
import os
import pathlib
import runpy
import sys

_V = pathlib.Path(os.environ["NTE_G231_V"])
_ROOT = pathlib.Path(os.environ["NTE_G231_ROOT"])
_TOOL = _V / "work_g231" / "teamsim_energy" / "tools" / "gen_team_resource_data.py"
sys.argv = [str(_TOOL), str(_ROOT / "src")] + sys.argv[1:]
runpy.run_path(str(_TOOL), run_name="__main__")
