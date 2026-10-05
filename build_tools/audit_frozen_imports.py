"""Frozen import audit: would every import in the src tree resolve inside the PyInstaller app?

Running from source uses a full CPython stdlib, so an import of a module that the frozen app
does not bundle only fails once frozen.  This tool answers that statically (ast only - nothing
from the application is imported or executed).

For every module of the tree it collects every import statement
    absolute / relative (resolved against the module's package), at module level, inside
    functions, under `if TYPE_CHECKING:`, inside try/except ImportError, plus constant-argument
    importlib.import_module("...") / __import__("...") calls and string literals naming src modules
and decides for each imported dotted module (every prefix must resolve) whether the frozen app
can provide it:
    pyz      entry in the exe's PYZ TOC (src.* and third-party / stdlib modules)
    carchive bootstrap module stored in the exe's CArchive itself (typecode 'm': struct, pyimod*)
    baselib  member of _internal/base_library.zip
    builtin  CPython 3.11 builtin module (names cross-checked against _internal/python311.dll)
    frozen   module frozen into python311.dll (importlib bootstrap etc.)
    disk     extension module (.pyd) / source module / package directory under _internal
For `from X import name` it also checks `name`: a bundled submodule, a top-level name of a src
module (static scan), or a name used by a bundled package's __init__ code object.

usage (python 3.11):
  audit_frozen_imports.py <exe> <root/src dir> <_internal dir>
                          [--baseline-src <upstream src dir>] [--json <out.json>] [--verbose]
Exit code 1 when a NOT-resolvable import is found outside TYPE_CHECKING / ImportError guards, when
this tree introduces a `from X import name` that cannot be confirmed, when a tree module is missing
from the PYZ, or when a string literal names a src module that does not exist.
"""
from __future__ import annotations

import _imp
import ast
import collections
import json
import marshal
import pathlib
import re
import struct
import sys
import types
import zipfile
import zlib

assert sys.version_info[:2] == (3, 11), "run under Python 3.11"

ENTRY_ROOTS = ("src.ui.app",)                       # main.py: from src.ui.app import run_gui
HIDDEN_ROOTS = ("src.scanner.gamepad_controller",)  # --hidden-import in upstream build_exe.py
GUARD_NAMES = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
SRC_NAME_RE = re.compile(r"^src(\.[A-Za-z_][A-Za-z0-9_]*)+$")
EXT_SUFFIXES = (".cp311-win_amd64.pyd", ".pyd")


# ───────────────────────────── bundle universe ─────────────────────────────
def read_pyz(exe_path: pathlib.Path):
    exe = exe_path.read_bytes()
    magic = b"MEI" + bytes([0x0C, 0x0B, 0x0A, 0x0B, 0x0E])
    cp = exe.rfind(magic)
    _, pkglen, tocpos, toclen, _, _ = struct.unpack("!8sIIii64s", exe[cp:cp + 88])
    start = cp + 88 - pkglen
    toc = exe[start + tocpos:start + tocpos + toclen]
    p = 0
    z = None
    scripts = {}
    boot_modules = set()
    while p < len(toc):
        elen, off, clen, ulen, cflag, typ = struct.unpack("!iIIIBc", toc[p:p + 18])
        name = toc[p + 18:p + elen].rstrip(b"\0").decode()
        data = exe[start + off:start + off + clen]
        if typ == b"z":
            z = zlib.decompress(data) if cflag else data
        elif typ in (b"s", b"m"):
            scripts[name] = zlib.decompress(data) if cflag else data
            if typ == b"m":
                boot_modules.add(name)
        p += elen
    items = marshal.loads(z[struct.unpack("!i", z[8:12])[0]:])
    if isinstance(items, dict):
        items = list(items.items())
    toc_map = {n: (tc, off, ln) for n, (tc, off, ln) in items}
    return z, toc_map, scripts, boot_modules


class Bundle:
    def __init__(self, exe: pathlib.Path, internal: pathlib.Path):
        self.pyz_data, self.pyz, self.scripts, self.carchive = read_pyz(exe)
        self.internal = internal
        self.baselib: dict[str, bool] = {}          # name -> is package
        self._baselib_init: dict[str, bytes] = {}
        with zipfile.ZipFile(internal / "base_library.zip") as zf:
            for n in zf.namelist():
                if n.endswith(".pyc"):
                    parts = n[:-4].split("/")
                    if parts[-1] == "__init__":
                        parts = parts[:-1]
                        self.baselib[".".join(parts)] = True
                        self._baselib_init[".".join(parts)] = zf.read(n)
                    else:
                        self.baselib[".".join(parts)] = False
        dll = (internal / "python311.dll").read_bytes()
        self.dll_versions = sorted(set(re.findall(rb"3\.11\.\d+", dll)))
        self.builtin = {n for n in sys.builtin_module_names if b"\0" + n.encode() + b"\0" in dll}
        self.builtin_unconfirmed = sorted(set(sys.builtin_module_names) - self.builtin)
        self.disk: dict[str, str] = {}
        for f in internal.rglob("*"):
            rel = f.relative_to(internal)
            if "__pycache__" in rel.parts:
                continue
            if f.is_dir():
                if all(p.isidentifier() for p in rel.parts):
                    self.disk.setdefault(".".join(rel.parts), "dir")
                continue
            name = f.name
            stem = None
            for suf in EXT_SUFFIXES:
                if name.endswith(suf):
                    stem, kind = name[:-len(suf)], "pyd"
                    break
            else:
                if name.endswith(".py"):
                    stem, kind = name[:-3], "py"
            if stem is None or not stem.isidentifier():
                continue
            parts = list(rel.parts[:-1])
            if not all(p.isidentifier() for p in parts):
                continue
            if stem == "__init__":
                kind = "pkg-" + kind                # package directory with an __init__
            else:
                parts.append(stem)
            if parts:
                self.disk[".".join(parts)] = kind
        self._pkg_names_cache: dict[str, tuple[set[str], bool]] = {}

    def how(self, name: str) -> str | None:
        """How a single dotted name (not its prefixes) is provided, or None."""
        if name in self.pyz:
            return "pyz"
        if name in self.carchive:
            return "carchive"
        if name in self.baselib:
            return "baselib"
        if "." not in name and name in self.builtin:
            return "builtin"
        if self.disk.get(name) in ("pyd", "py", "pkg-pyd", "pkg-py"):
            return "disk"
        if _imp.is_frozen(name):
            return "frozen"
        if self.disk.get(name) == "dir":
            return "disk-dir"
        return None

    def resolve(self, name: str) -> tuple[bool, str]:
        """(resolvable, explanation) - every prefix of the dotted name must be importable."""
        parts = name.split(".")
        how = None
        for i in range(1, len(parts) + 1):
            prefix = ".".join(parts[:i])
            how = self.how(prefix)
            if how is None:
                parent = ".".join(parts[:i - 1])
                return False, (f"'{prefix}' is not bundled" + (f" (its parent '{parent}' is)" if parent else ""))
        return True, how or ""

    def is_package(self, name: str) -> bool:
        if name in self.pyz:
            return self.pyz[name][0] in (1, 3)
        return self.disk.get(name) in ("dir", "pkg-py", "pkg-pyd") or bool(self.baselib.get(name))

    def package_init_names(self, name: str) -> tuple[set[str], bool] | None:
        """Names referenced by a bundled package __init__ (PYZ or base_library.zip) and whether the
        namespace is filled dynamically (__getattr__, star import, globals().update)."""
        in_pyz = name in self.pyz and self.pyz[name][0] == 1
        if not in_pyz and name not in self._baselib_init:
            return None
        if name not in self._pkg_names_cache:
            if in_pyz:
                tc, off, ln = self.pyz[name]
                code = marshal.loads(zlib.decompress(self.pyz_data[off:off + ln]))
            else:
                code = marshal.loads(self._baselib_init[name][16:])
            import dis
            # only names the __init__ really binds at module level count (a name that merely
            # appears in __all__ - e.g. PySide6's list of Qt modules - is NOT an attribute)
            names = set()
            dynamic = False
            for ins in dis.get_instructions(code):
                if ins.opname in ("STORE_NAME", "STORE_GLOBAL"):
                    names.add(ins.argval)
                elif ins.opname == "IMPORT_STAR":
                    dynamic = True
                elif ins.opname in ("LOAD_NAME", "LOAD_GLOBAL") and ins.argval in ("globals", "setattr"):
                    dynamic = True
            if "__getattr__" in names:
                dynamic = True
            self._pkg_names_cache[name] = (names, dynamic)
        return self._pkg_names_cache[name]


# ───────────────────────────── source scanning ─────────────────────────────
Rec = collections.namedtuple(
    "Rec", "module file line kind target names level in_func type_checking guarded in_handler")


def scan_tree(src: pathlib.Path) -> dict[str, tuple[bool, pathlib.Path]]:
    out = {}
    for f in sorted(src.rglob("*.py")):
        rel = f.relative_to(src)
        if "__pycache__" in rel.parts:
            continue
        parts = ("src",) + rel.with_suffix("").parts
        if parts[-1] == "__init__":
            out[".".join(parts[:-1])] = (True, f)
        else:
            out[".".join(parts)] = (False, f)
    return out


def _is_type_checking(test: ast.AST) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")


def _handler_guards(handlers: list[ast.ExceptHandler]) -> bool:
    for h in handlers:
        t = h.type
        if t is None:
            return True
        elts = t.elts if isinstance(t, ast.Tuple) else [t]
        for e in elts:
            n = e.id if isinstance(e, ast.Name) else e.attr if isinstance(e, ast.Attribute) else None
            if n in GUARD_NAMES:
                return True
    return False


def collect(module: str, is_pkg: bool, path: pathlib.Path, rel: str):
    """-> (import records, string literals naming src modules, top-level names, has_star/getattr)"""
    tree = ast.parse(path.read_bytes().decode("utf-8-sig"), filename=str(path))
    recs: list[Rec] = []
    literals: list[tuple[str, int]] = []
    computed: list[tuple[int, str, str, str, bool]] = []    # (line, call, expression, prefix, guarded)
    package = module if is_pkg else module.rpartition(".")[0]

    def absolute(level: int, name: str | None) -> str:
        if level == 0:
            return name or ""
        base = package.split(".")
        if level > 1:
            base = base[:len(base) - (level - 1)]
        return ".".join(base + ([name] if name else []))

    def walk(node, in_func, tc, guarded, in_handler):
        if isinstance(node, ast.Import):
            for a in node.names:
                recs.append(Rec(module, rel, node.lineno, "import", a.name, (), 0,
                                in_func, tc, guarded, in_handler))
            return
        if isinstance(node, ast.ImportFrom):
            recs.append(Rec(module, rel, node.lineno, "from", absolute(node.level, node.module),
                            tuple(a.name for a in node.names), node.level,
                            in_func, tc, guarded, in_handler))
            return
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and SRC_NAME_RE.match(node.value):
            literals.append((node.value, node.lineno))
        if isinstance(node, ast.Call):
            f = node.func
            fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if fname in ("import_module", "__import__", "find_spec") and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if fname != "find_spec":
                        recs.append(Rec(module, rel, node.lineno, "dynamic", arg.value, (), 0,
                                        in_func, tc, guarded, in_handler))
                else:                               # computed module name: reported for review
                    prefix = ""
                    if isinstance(arg, ast.JoinedStr) and arg.values and \
                            isinstance(arg.values[0], ast.Constant):
                        prefix = str(arg.values[0].value)
                    computed.append((node.lineno, fname, ast.unparse(arg), prefix, guarded or in_handler))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for child in ast.iter_child_nodes(node):
                walk(child, True, tc, guarded, in_handler)
            return
        if isinstance(node, ast.If) and _is_type_checking(node.test):
            for child in node.body:
                walk(child, in_func, True, guarded, in_handler)
            for child in node.orelse:
                walk(child, in_func, tc, guarded, in_handler)
            return
        if isinstance(node, (ast.Try, ast.TryStar)):
            g = guarded or _handler_guards(node.handlers)
            for child in node.body:
                walk(child, in_func, tc, g, in_handler)
            for h in node.handlers:
                for child in h.body:
                    walk(child, in_func, tc, guarded, True)
            for child in node.orelse + node.finalbody:
                walk(child, in_func, tc, guarded, in_handler)
            return
        for child in ast.iter_child_nodes(node):
            walk(child, in_func, tc, guarded, in_handler)

    walk(tree, False, False, False, False)

    # names a `from <this module> import name` can find without importing a submodule
    top: set[str] = set()
    dynamic = False

    def top_names(stmts):
        nonlocal dynamic
        for s in stmts:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                top.add(s.name)
                if s.name == "__getattr__":
                    dynamic = True
            elif isinstance(s, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = s.targets if isinstance(s, ast.Assign) else [s.target]
                for t in targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            top.add(n.id)
            elif isinstance(s, ast.Import):
                for a in s.names:
                    top.add((a.asname or a.name).split(".")[0])
            elif isinstance(s, ast.ImportFrom):
                for a in s.names:
                    if a.name == "*":
                        dynamic = True
                    else:
                        top.add(a.asname or a.name)
            elif isinstance(s, (ast.If, ast.For, ast.While, ast.With)):
                top_names(s.body)
                top_names(getattr(s, "orelse", []))
            elif isinstance(s, (ast.Try, ast.TryStar)):
                top_names(s.body)
                for h in s.handlers:
                    top_names(h.body)
                top_names(s.orelse)
                top_names(s.finalbody)
            elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
                dynamic = dynamic or "globals" in ast.dump(s.value)

    top_names(tree.body)
    return recs, literals, top, dynamic, computed


# ───────────────────────────────── audit ─────────────────────────────────
def audit(tree: dict, src_dir: pathlib.Path, bundle: Bundle | None):
    """Collect everything; when bundle is None only the import facts are gathered."""
    all_recs: list[Rec] = []
    literals: dict[str, list[tuple[str, int]]] = {}
    tops: dict[str, tuple[set[str], bool]] = {}
    computed: list[tuple[str, int, str, str, str, bool]] = []
    for module, (is_pkg, path) in tree.items():
        rel = "src/" + path.relative_to(src_dir).as_posix()
        recs, lits, top, dyn, comp = collect(module, is_pkg, path, rel)
        all_recs.extend(recs)
        literals[module] = lits
        tops[module] = (top, dyn)
        computed.extend((rel, *c) for c in comp)
    return all_recs, literals, tops, computed


def targets_of(rec: Rec, tree: dict, bundle: Bundle | None) -> list[str]:
    """Modules a record imports: the base module, plus `from X import n` names that are modules."""
    out = [rec.target] if rec.target else []
    if rec.kind == "from":
        for n in rec.names:
            if n == "*":
                continue
            cand = f"{rec.target}.{n}" if rec.target else n
            if cand in tree or (bundle is not None and bundle.how(cand) is not None):
                out.append(cand)
    return out


def main() -> int:
    argv = sys.argv[1:]
    opts = {}
    pos = []
    i = 0
    while i < len(argv):
        if argv[i] in ("--baseline-src", "--json"):
            opts[argv[i]] = argv[i + 1]
            i += 2
        elif argv[i] == "--verbose":
            opts["--verbose"] = True
            i += 1
        else:
            pos.append(argv[i])
            i += 1
    exe, src_dir, internal = (pathlib.Path(p) for p in pos[:3])
    bundle = Bundle(exe, internal)
    tree = scan_tree(src_dir)
    recs, literals, tops, computed = audit(tree, src_dir, bundle)

    print(f"exe      : {exe}")
    print(f"tree     : {src_dir}  ({len(tree)} modules/packages)")
    print(f"_internal: {internal}")
    print(f"universe : PYZ {len(bundle.pyz)} entries ({sum(1 for n in bundle.pyz if n == 'src' or n.startswith('src.'))} src) | "
          f"base_library.zip {len(bundle.baselib)} | builtin {len(bundle.builtin)} "
          f"(python311.dll reports {', '.join(v.decode() for v in bundle.dll_versions)}; "
          f"unconfirmed: {bundle.builtin_unconfirmed or 'none'}) | "
          f"on-disk modules {sum(1 for k in bundle.disk.values() if k != 'dir')} "
          f"(.pyd {sum(1 for k in bundle.disk.values() if k.endswith('pyd'))}, .py {sum(1 for k in bundle.disk.values() if k.endswith('py'))})")

    # tree <-> PYZ consistency (every tree module must be in the PYZ)
    not_in_pyz = sorted(m for m in tree if m not in bundle.pyz)
    if not_in_pyz:
        print(f"!! tree modules missing from the PYZ: {not_in_pyz}")

    # ── reachability over src modules (TYPE_CHECKING imports excluded) ──
    edges_all: dict[str, set[str]] = collections.defaultdict(set)
    edges_eager: dict[str, set[str]] = collections.defaultdict(set)

    def with_parents(name: str) -> list[str]:
        ps = name.split(".")
        return [".".join(ps[:k]) for k in range(2, len(ps) + 1) if ".".join(ps[:k]) in tree]

    for r in recs:
        if r.type_checking:
            continue
        for t in targets_of(r, tree, bundle):
            if t == "src" or t.startswith("src."):
                for m in with_parents(t):
                    edges_all[r.module].add(m)
                    if not r.in_func and not r.in_handler:
                        edges_eager[r.module].add(m)
    for module, lits in literals.items():
        for value, _ in lits:
            if value in tree:
                edges_all[module].add(value)        # possible dynamic import by name
            else:                                   # prefix of a computed name (f"src.i18n_data_{x}")
                edges_all[module].update(m for m in tree if m.startswith(value))

    def closure(roots, edges):
        seen, todo = set(), [m for r in roots for m in with_parents(r)]
        while todo:
            m = todo.pop()
            if m in seen:
                continue
            seen.add(m)
            todo.extend(edges.get(m, ()))
        return seen

    reach_all = closure(ENTRY_ROOTS + HIDDEN_ROOTS, edges_all)
    reach_eager = closure(ENTRY_ROOTS, edges_eager)
    unreachable = sorted(set(tree) - reach_all)

    # ── baseline (upstream) facts for triage ──
    base_pairs: set[tuple[str, str]] = set()
    base_names: set[tuple[str, str, str]] = set()
    base_ext: set[str] = set()
    btree: dict = {}
    if "--baseline-src" in opts:
        bsrc = pathlib.Path(opts["--baseline-src"])
        btree = scan_tree(bsrc)
        brecs, _, _, _ = audit(btree, bsrc, None)
        for r in brecs:
            for n in r.names:
                base_names.add((r.module, r.target, n))
            for t in targets_of(r, btree, bundle):
                base_pairs.add((r.module, t))
                if not (t == "src" or t.startswith("src.")):
                    base_ext.add(t)

    # ── resolve ──
    problems = []           # unresolvable module imports
    name_issues = []        # from X import name: name not provably available
    resolved_how = collections.Counter()
    ext_modules: dict[str, str] = {}
    counts = collections.Counter()
    for r in recs:
        counts["statements"] += 1
        counts["type_checking" if r.type_checking else "in_function" if r.in_func else "module_level"] += 1
        if r.guarded:
            counts["inside try/except ImportError"] += 1
        if r.level:
            counts["relative"] += 1
        if r.kind == "dynamic":
            counts["dynamic (constant argument)"] += 1
        if not r.target:
            problems.append((r, r.target, "relative import beyond top-level package"))
            continue
        okay, how = bundle.resolve(r.target)
        if not okay:
            problems.append((r, r.target, how))
            continue
        resolved_how[how] += 1
        if not r.target.startswith("src.") and r.target != "src":
            ext_modules[r.target] = how
        if r.kind != "from":
            continue
        for n in r.names:
            if n == "*":
                continue
            cand = f"{r.target}.{n}"
            sub_ok, sub_how = bundle.resolve(cand)
            if sub_ok:
                resolved_how[sub_how] += 1
                if not cand.startswith("src."):
                    ext_modules[cand] = sub_how
                continue
            if r.target in tree:                                  # attribute of a src module
                top, dyn = tops[r.target]
                if n in top or dyn:
                    continue
                name_issues.append((r, n, "not a submodule and not a top-level name of the src module"))
            elif bundle.is_package(r.target):
                info = bundle.package_init_names(r.target)
                if info is None:
                    if r.target == "__future__":
                        continue
                    name_issues.append((r, n, "package on disk / namespace: cannot confirm the name statically"))
                else:
                    names, lazy = info
                    if n in names:
                        continue
                    name_issues.append((r, n, "not a bundled submodule and not bound by the package __init__"
                                        + (" (its namespace is filled dynamically: __getattr__ / star import / "
                                           "globals())" if lazy else " - ImportError if it is a submodule")))
            # plain module / extension module / builtin: `name` is an attribute - nothing to bundle

    # string literals naming src modules that do not exist (possible dynamic imports)
    literal_misses = []
    for module, lits in literals.items():
        for value, line in lits:
            if value not in bundle.pyz and not any(m.startswith(value) for m in bundle.pyz):
                literal_misses.append((module, line, value))

    # ── report ──
    def flags(r: Rec) -> str:
        f = []
        f.append("TYPE_CHECKING" if r.type_checking else "function-level" if r.in_func else "module-level")
        if r.guarded:
            f.append("inside try/except ImportError")
        if r.in_handler:
            f.append("in except-handler (fallback path)")
        if r.module in reach_eager:
            f.append("module imported at startup")
        elif r.module in reach_all:
            f.append("module reachable lazily")
        else:
            f.append("module NOT reachable from the entry point")
        return ", ".join(f)

    print(f"imports  : {counts['statements']} statements in {len(tree)} files - "
          f"{counts['module_level']} module-level, {counts['in_function']} in functions, "
          f"{counts['type_checking']} under TYPE_CHECKING, {counts['inside try/except ImportError']} inside "
          f"try/except ImportError, {counts['relative']} relative, {counts['dynamic (constant argument)']} dynamic")
    print(f"resolved : " + ", ".join(f"{k} {v}" for k, v in sorted(resolved_how.items())))
    print(f"reachable: {len(reach_eager)} modules imported at startup (eager chain from {ENTRY_ROOTS[0]}), "
          f"{len(reach_all)} reachable incl. function-level/dynamic, {len(unreachable)} never imported")
    if opts.get("--verbose"):
        for m in unreachable:
            print(f"      unreachable: {m}")

    ext_top = collections.Counter(m.split(".")[0] for m in ext_modules)
    print(f"external : {len(ext_modules)} distinct non-src modules imported "
          f"({len(ext_top)} top-level packages)")
    if base_pairs:
        new_ext = sorted(m for m in ext_modules if m not in base_ext)
        print(f"baseline : {len(base_ext)} external modules imported by upstream; "
              f"{len(new_ext)} external module(s) imported ONLY by this tree:")
        for m in new_ext:
            users = sorted({r.file for r in recs if m in targets_of(r, tree, bundle)})
            print(f"      {m:<34} [{ext_modules[m]}]  used by {', '.join(users[:4])}{' ...' if len(users) > 4 else ''}")

    hard = []
    print()
    print(f"NOT RESOLVABLE in the frozen app: {len(problems)} import(s)")
    for r, target, why in sorted(problems, key=lambda x: (x[0].file, x[0].line)):
        inherited = (r.module, target) in base_pairs
        harmless = r.type_checking or r.guarded
        tag = "harmless" if harmless else "PROBLEM"
        if not harmless:
            hard.append((r, target, why))
        print(f"  [{tag}] {r.file}:{r.line}  {r.kind} {target}"
              f"{' import ' + ', '.join(r.names) if r.names else ''}")
        print(f"           {why}; {flags(r)}"
              f"{'; identical import exists upstream' if inherited else ''}")

    print()
    inherited_names = [x for x in name_issues if (x[0].module, x[0].target, x[1]) in base_names]
    own_names = [x for x in name_issues if (x[0].module, x[0].target, x[1]) not in base_names]
    print(f"`from X import name` where name is neither a bundled submodule nor statically visible: "
          f"{len(name_issues)} ({len(inherited_names)} identical in upstream = proven by the official "
          f"build, {len(own_names)} introduced by this tree)")
    for r, n, why in sorted(own_names, key=lambda x: (x[0].file, x[0].line)):
        print(f"  {r.file}:{r.line}  from {r.target} import {n} - {why}; {flags(r)}")
    if opts.get("--verbose"):
        for r, n, why in sorted(inherited_names, key=lambda x: (x[0].file, x[0].line)):
            print(f"  (upstream) {r.file}:{r.line}  from {r.target} import {n} - {why}")

    print()
    print(f"computed module names (importlib.import_module / __import__ / find_spec with a "
          f"non-constant argument): {len(computed)}")
    for rel, line, fname, expr, prefix, guarded in sorted(computed):
        if prefix:
            matches = sorted(m for m in bundle.pyz if m.startswith(prefix))
            note = f"prefix {prefix!r} matches {len(matches)} bundled module(s): {', '.join(matches) or 'NONE'}"
        else:
            note = "name comes from a variable"
        print(f"  {rel}:{line}  {fname}({expr}) - {note}{'; inside try/except' if guarded else ''}")

    if btree:
        new_modules = sorted(m for m in tree if m not in btree)
        print()
        print(f"modules that do not exist upstream: {len(new_modules)} - external imports of each:")
        for m in new_modules:
            ext = collections.OrderedDict()
            for r in recs:
                if r.module != m:
                    continue
                for t in targets_of(r, tree, bundle):
                    if not (t == "src" or t.startswith("src.")):
                        okay, how = bundle.resolve(t)
                        ext[t] = how if okay else "NOT BUNDLED"
            state = "startup" if m in reach_eager else "lazy" if m in reach_all else "unreachable"
            print(f"  {m} [{state}]: " + (", ".join(f"{t} ({h})" for t, h in ext.items()) or "(none)"))

    print()
    print(f"string literals naming a src module that is not in the PYZ: {len(literal_misses)}")
    for module, line, value in literal_misses:
        print(f"  {module}:{line}  {value!r}")

    if "--json" in opts:
        out = {
            "exe": str(exe), "tree_modules": len(tree), "statements": counts["statements"],
            "counts": dict(counts), "resolved_how": dict(resolved_how),
            "external_modules": ext_modules,
            "reachable_eager": len(reach_eager), "reachable_all": len(reach_all),
            "unreachable": unreachable,
            "not_resolvable": [dict(r._asdict(), target=t, why=w,
                                    harmless=bool(r.type_checking or r.guarded))
                               for r, t, w in problems],
            "name_issues": [dict(r._asdict(), name=n, why=w) for r, n, w in name_issues],
            "literal_misses": literal_misses,
        }
        pathlib.Path(opts["--json"]).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    print()
    own_unguarded = [x for x in own_names if not (x[0].type_checking or x[0].guarded)]
    if hard or not_in_pyz or own_unguarded or literal_misses:
        print(f"AUDIT_FAILED: {len(hard)} unguarded import(s) cannot resolve in the frozen app, "
              f"{len(own_unguarded)} new `from X import name` unconfirmed, "
              f"{len(not_in_pyz)} tree module(s) missing from the PYZ, "
              f"{len(literal_misses)} dangling src module literal(s)")
        return 1
    print("AUDIT_OK: every import outside TYPE_CHECKING / ImportError guards resolves in the frozen app; "
          "no new unconfirmed from-import names; every tree module is in the PYZ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
