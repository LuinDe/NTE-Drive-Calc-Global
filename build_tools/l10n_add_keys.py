"""Add translations for newly written _L()/_LF() keys to a language data module (S / T tables).

usage: l10n_add_keys.py <src dir> <lang> <json file {zh key: translation}> <source files...>
Lists keys found in the source files that the table lacks; with a JSON file, merges them in.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

src = pathlib.Path(sys.argv[1])
lang = sys.argv[2]
tr_file = sys.argv[3]
files = sys.argv[4:]

KEY = re.compile(r"_(L|LF)\('((?:[^'\\]|\\.)*)'\)")
found = []
for f in files:
    text = (src / f).read_text(encoding="utf-8")
    for m in KEY.finditer(text):
        kind, raw = m.group(1), m.group(2)
        value = ast.literal_eval("'" + raw + "'")
        if (kind, value) not in found:
            found.append((kind, value))

data_path = src / f"i18n_data_{lang}.py"
tree = ast.parse(data_path.read_text(encoding="utf-8"))
tables = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        tables[node.targets[0].id] = ast.literal_eval(node.value)
S, T = tables.get("S", {}), tables.get("T", {})

missing = [(k, v) for k, v in found if v not in (S if k == "L" else T)]
print(f"{lang}: keys in sources {len(found)} | missing {len(missing)}")
for k, v in missing:
    print(f"  {k} {v!r}")

if tr_file != "-":
    add = json.loads(pathlib.Path(tr_file).read_text(encoding="utf-8"))
    for k, v in found:
        if v in add:
            (S if k == "L" else T)[v] = add[v]
    lines = [f"# {lang} language table (generated). S: strings, T: f-string templates ({{n}} slots)",
             f'"""{lang} language table consulted by src.i18n_runtime."""', ""]
    for name, table in tables.items():
        if name == "S":
            table = S
        elif name == "T":
            table = T
        lines.append(f"{name} = {{")
        for key, val in table.items():
            lines.append(" " + json.dumps(key, ensure_ascii=False) + ": " + json.dumps(val, ensure_ascii=False) + ",")
        lines.append("}")
        lines.append("")
    data_path.write_text("\n".join(lines), encoding="utf-8", newline="")
    compile(data_path.read_text(encoding="utf-8"), str(data_path), "exec")
    still = [(k, v) for k, v in found if v not in (S if k == "L" else T)]
    print(f"merged; still missing {len(still)}")
