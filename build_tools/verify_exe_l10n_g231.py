"""[Global 2.3.1 copy of tools/verify_exe_l10n.py: checks 1-7 unchanged + check 8 (seed vs payload DB)]
Prove the multilingual exe differs from the original ONLY in the intended places.

Generalised verify_exe.py for builds made by rebuild_exe_l10n.py.  Nothing is executed from the
application; the only foreign code run is PyInstaller's own archive reader (pyimod01_archive),
taken from the exe's CArchive, to prove the frozen importer can read the rewritten PYZ.

Checks
  1. PE part (everything before the CArchive) identical except the 4-byte checksum field; the new
     checksum is valid per CheckSumMappedFile (algorithm self-tested against the original).
  2. CArchive: cookie fields, entry names / order / typecodes identical; every entry except the
     PYZ byte-identical (payload, sizes, compression flag); archive ends exactly at EOF.
  3. PYZ container: header identical apart from the TOC pointer (magic, pyc magic, the writer's
     reserved bytes, offset of the first record), TOC records contiguous and in bounds, original
     entry order preserved, nothing dropped; every non-src entry byte-identical with the same
     typecode.
  4. every src.* entry equals a fresh compile of the tree file (structural code equality incl.
     co_filename / line tables, recursively); typecode matches the tree (module / package /
     namespace dir); co_filename of added entries follows the build's style.
  5. added set == (tree names - original PYZ src names), in the documented order; listed.
  6. no leftover dev/test file packaged (cjk_dump, run_test, test_*, conftest, ...); no src entry
     without a tree file.
  7. PyInstaller's own ZlibArchiveReader (from the new exe) reads the new PYZ: same TOC, and
     extract() of every src.* entry yields the same code object.

  8. (Global 2.3.1) the efficiency-table seed's DATASET (sha256, dataset id, schema) equals the payload's
     data/manifest.json and the shipped game_static.sqlite3 (hash + size).

usage (python 3.11): verify_exe_l10n_g231.py <original exe> <new exe> <root/src dir> [<payload data dir>]
       (payload data dir default: <original exe dir>/_internal/data)
"""
from __future__ import annotations

import array
import hashlib
import marshal
import pathlib
import re
import struct
import sys
import types
import zlib

assert sys.version_info[:2] == (3, 11), "run under Python 3.11"
orig_p, new_p, src_dir = (pathlib.Path(a) for a in sys.argv[1:4])

PYZ_ITEM_MODULE, PYZ_ITEM_PKG, PYZ_ITEM_NSPKG = 0, 1, 3
FIRST_ADDED = ("src.i18n_display", "src.i18n_desc")
DENY_RE = re.compile(r"(^|\.)(cjk_dump|run_test|search_unit_test|conftest|tests?|test_\w+|\w+_test)$")
MAGIC = b"MEI" + bytes([0x0C, 0x0B, 0x0A, 0x0B, 0x0E])
fail: list[str] = []
passed: list[str] = []


def ok(msg: str) -> None:
    passed.append(msg)
    print("  ok  ", msg)


def bad(msg: str) -> None:
    fail.append(msg)
    print("  FAIL", msg)


def is_src(name: str) -> bool:
    return name == "src" or name.startswith("src.")


def parse(exe: bytes):
    cp = exe.rfind(MAGIC)
    magic, pkglen, tocpos, toclen, pyver, pylib = struct.unpack("!8sIIii64s", exe[cp:cp + 88])
    start = cp + 88 - pkglen
    toc = exe[start + tocpos:start + tocpos + toclen]
    p, ents = 0, []
    while p < len(toc):
        elen, off, clen, ulen, cflag, typ = struct.unpack("!iIIIBc", toc[p:p + 18])
        ents.append({"name": toc[p + 18:p + elen].rstrip(b"\0"), "off": off, "clen": clen,
                     "ulen": ulen, "cflag": cflag, "typ": typ,
                     "data": exe[start + off:start + off + clen]})
        p += elen
    return {"cookie_pos": cp, "start": start, "pkglen": pkglen, "tocpos": tocpos, "toclen": toclen,
            "pyver": pyver, "pylib": pylib, "magic": magic, "entries": ents}


def pyz_of(arch):
    (e,) = [e for e in arch["entries"] if e["typ"] == b"z"]
    data = zlib.decompress(e["data"]) if e["cflag"] else e["data"]
    assert data[:4] == b"PYZ\0"
    tocpos = struct.unpack("!i", data[8:12])[0]
    items = marshal.loads(data[tocpos:])
    kind = type(items)
    if isinstance(items, dict):
        items = list(items.items())
    return {"entry": e, "data": data, "tocpos": tocpos, "kind": kind,
            "items": [(n, tc, off, ln) for n, (tc, off, ln) in items]}


_CODE_ATTRS = ("co_code", "co_names", "co_varnames", "co_freevars", "co_cellvars", "co_flags",
               "co_argcount", "co_posonlyargcount", "co_kwonlyargcount", "co_nlocals",
               "co_stacksize", "co_name", "co_qualname", "co_firstlineno", "co_linetable",
               "co_exceptiontable", "co_filename")


def code_diff(a, b, path):
    """None when structurally equal, else a description of the first difference."""
    for at in _CODE_ATTRS:
        if getattr(a, at) != getattr(b, at):
            return f"{path}:{at}"
    if len(a.co_consts) != len(b.co_consts):
        return f"{path}:nconsts"
    for i, (x, y) in enumerate(zip(a.co_consts, b.co_consts)):
        r = const_diff(x, y, f"{path}/const{i}")
        if r:
            return r
    return None


def const_diff(x, y, path):
    if type(x) is not type(y):
        return path + ":type"
    if isinstance(x, types.CodeType):
        return code_diff(x, y, path + "<" + x.co_name + ">")
    if isinstance(x, tuple):
        if len(x) != len(y):
            return path + ":len"
        for i, (a, b) in enumerate(zip(x, y)):
            r = const_diff(a, b, f"{path}[{i}]")
            if r:
                return r
        return None
    if isinstance(x, (float, complex)):
        return None if repr(x) == repr(y) else path + ":value"
    return None if x == y else path + ":value"


def filenames(code, out):
    out.add(code.co_filename)
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            filenames(c, out)
    return out


def scan_tree(src: pathlib.Path):
    out = {}
    for f in sorted(src.rglob("*.py")):
        rel = f.relative_to(src)
        if "__pycache__" in rel.parts:
            continue
        parts = ("src",) + rel.with_suffix("").parts
        if parts[-1] == "__init__":
            out[".".join(parts[:-1])] = (PYZ_ITEM_PKG, f)
        else:
            out[".".join(parts)] = (PYZ_ITEM_MODULE, f)
    for name in list(out):
        ps = name.split(".")
        for i in range(1, len(ps)):
            out.setdefault(".".join(ps[:i]), (PYZ_ITEM_NSPKG, None))
    return out


def pe_checksum(buf, off):
    padded = bytes(buf) + (b"\0" if len(buf) % 2 else b"")
    w = array.array("H")
    w.frombytes(padded)
    t = sum(w) - w[off // 2] - w[off // 2 + 1]
    while t >> 16:
        t = (t & 0xFFFF) + (t >> 16)
    return (t + len(buf)) & 0xFFFFFFFF


orig, new = orig_p.read_bytes(), new_p.read_bytes()
print(f"original : {orig_p}\n           sha256 {hashlib.sha256(orig).hexdigest()}  size {len(orig):,}")
print(f"new      : {new_p}\n           sha256 {hashlib.sha256(new).hexdigest()}  size {len(new):,}")
ao, an = parse(orig), parse(new)

# ── 1. PE part ────────────────────────────────────────────────────────────
print("[1] PE image")
e_lfanew = struct.unpack_from("<I", orig, 0x3C)[0]
csum_off = e_lfanew + 88
if ao["start"] != an["start"]:
    bad(f"overlay start moved: {ao['start']} -> {an['start']}")
so = ao["start"]
if orig[:csum_off] + orig[csum_off + 4:so] == new[:csum_off] + new[csum_off + 4:so]:
    ok(f"{so:,} bytes before the CArchive identical except the checksum dword")
else:
    bad("PE part differs beyond the checksum field")
if struct.unpack_from("<I", orig, csum_off)[0] != pe_checksum(orig, csum_off):
    bad("checksum algorithm self-test failed on the original")
stored_new = struct.unpack_from("<I", new, csum_off)[0]
if stored_new == pe_checksum(new, csum_off):
    ok(f"PE checksum valid ({stored_new:#010x}); algorithm reproduces the original's stored value")
else:
    bad(f"new PE checksum wrong: stored {stored_new:#010x}, computed {pe_checksum(new, csum_off):#010x}")

# ── 2. CArchive ───────────────────────────────────────────────────────────
print("[2] CArchive")
if an["cookie_pos"] + 88 != len(new):
    bad("CArchive cookie is not at the end of the new file")
if (ao["magic"], ao["pyver"], ao["pylib"]) != (an["magic"], an["pyver"], an["pylib"]):
    bad("cookie magic / python version / python dll name changed")
else:
    ok(f"cookie: python {an['pyver']}, {an['pylib'].rstrip(bytes(1)).decode()}, archive ends at EOF")
eo, en = ao["entries"], an["entries"]
if [(e["name"], e["typ"]) for e in eo] != [(e["name"], e["typ"]) for e in en]:
    bad("CArchive entry names/order/typecodes changed")
n_same = 0
for a, b in zip(eo, en):
    if a["typ"] == b"z":
        continue
    if (a["data"], a["clen"], a["ulen"], a["cflag"]) != (b["data"], b["clen"], b["ulen"], b["cflag"]):
        bad(f"CArchive entry changed: {a['name']!r}")
    else:
        n_same += 1
pos = 0
for b in en:                                # records must be laid out back to back
    if b["off"] != pos:
        bad(f"CArchive entry {b['name']!r} not contiguous (offset {b['off']}, expected {pos})")
    pos += b["clen"]
if pos != an["tocpos"]:
    bad("CArchive TOC does not follow the data section directly")
ok(f"{n_same} of {len(en)} entries byte-identical (all but PYZ.pyz); layout contiguous")

# ── 3. PYZ container ──────────────────────────────────────────────────────
print("[3] PYZ container")
po, pn = pyz_of(ao), pyz_of(an)
if po["data"][:8] != pn["data"][:8]:
    bad("PYZ header (magic / pyc magic) changed")
# the original writer reserves bytes after the 12-byte header (PyInstaller 6: 5, first record at 17)
first_o = min(off for _, _, off, ln in po["items"] if ln)
first_n = min(off for _, _, off, ln in pn["items"] if ln)
if first_n != first_o:
    bad(f"PYZ records start at offset {first_n}, the original's start at {first_o}")
elif po["data"][12:first_o] != pn["data"][12:first_o]:
    bad("PYZ reserved header bytes changed")
if po["kind"] is not pn["kind"]:
    bad("PYZ TOC container type changed")
if pn["entry"]["ulen"] != len(pn["data"]):
    bad("CArchive ulen of the PYZ entry does not match its size")
pos = first_n
for n, tc, off, ln in pn["items"]:
    if off != pos:
        bad(f"PYZ record not contiguous: {n} at {off}, expected {pos}")
        break
    pos += ln
if pos != pn["tocpos"]:
    bad("PYZ TOC pointer does not follow the last record")
names_o = [n for n, *_ in po["items"]]
names_n = [n for n, *_ in pn["items"]]
if len(set(names_n)) != len(names_n):
    bad("duplicate names in the new PYZ TOC")
if names_n[:len(names_o)] != names_o:
    bad("original PYZ entry order not preserved / entries dropped")
do = {n: (tc, po["data"][off:off + ln]) for n, tc, off, ln in po["items"]}
dn = {n: (tc, pn["data"][off:off + ln]) for n, tc, off, ln in pn["items"]}
nonsrc_same = 0
for n, (tc, blob) in do.items():
    if is_src(n):
        continue
    if dn.get(n) != (tc, blob):
        bad(f"non-src PYZ entry changed or dropped: {n}")
    else:
        nonsrc_same += 1
extra_nonsrc = [n for n in dn if not is_src(n) and n not in do]
if extra_nonsrc:
    bad(f"non-src entries added: {extra_nonsrc}")
ok(f"header identical apart from the TOC pointer (magic, pyc magic, {first_o - 12} reserved bytes; "
   f"first record at offset {first_n} as in the original), {len(names_n)} records contiguous, "
   f"original order kept ({len(names_o)} -> {len(names_n)} entries)")
ok(f"{nonsrc_same} non-src entries byte-identical, none added, none dropped")

# ── 4. src.* entries vs the tree ──────────────────────────────────────────
print("[4] src.* entries")
tree = scan_tree(src_dir)
orig_src = {n: tc for n, (tc, _) in do.items() if is_src(n)}
new_src = {n: tc for n, (tc, _) in dn.items() if is_src(n)}
sep = chr(92)
kept = rewritten = ns = 0
decoded: dict[str, types.CodeType] = {}
for n, tc in new_src.items():
    if n not in tree:
        bad(f"src entry without a tree file: {n}")
        continue
    if tree[n][0] != tc:
        bad(f"typecode mismatch for {n}: PYZ {tc}, tree {tree[n][0]}")
        continue
    blob = dn[n][1]
    if tc == PYZ_ITEM_NSPKG:
        if blob:
            bad(f"namespace entry with data: {n}")
        ns += 1
        continue
    try:
        code = marshal.loads(zlib.decompress(blob))
    except Exception as exc:                # noqa: BLE001
        bad(f"cannot unmarshal {n}: {exc!r}")
        continue
    if not isinstance(code, types.CodeType):
        bad(f"{n} is not a code object")
        continue
    decoded[n] = code
    style = sep.join(n.split(".")) + (sep + "__init__.py" if tc == PYZ_ITEM_PKG else ".py")
    if n in do:
        expected_fn = marshal.loads(zlib.decompress(do[n][1])).co_filename
        if expected_fn != style:
            bad(f"original co_filename of {n} is not in the assumed style: {expected_fn!r}")
    else:
        expected_fn = style
    fns = filenames(code, set())
    if fns != {expected_fn}:
        bad(f"co_filename of {n}: {sorted(fns)} != {expected_fn!r}")
    ours = compile(tree[n][1].read_bytes().decode("utf-8-sig"), expected_fn, "exec",
                   dont_inherit=True, optimize=0)
    why = code_diff(code, ours, n)
    if why:
        bad(f"src entry differs from a fresh compile of the tree: {why}")
    if n in do and do[n][1] == blob:
        kept += 1
    else:
        rewritten += 1
ok(f"{kept + rewritten} code entries == fresh compile of the tree "
   f"({kept} original records kept byte-identical, {rewritten} rewritten/added), {ns} namespace dirs")

# ── 5. added set ──────────────────────────────────────────────────────────
print("[5] added modules")
added = [n for n in names_n if n not in do]
expected_added = set(tree) - set(orig_src)
dropped = set(orig_src) - set(new_src)
if dropped:
    bad(f"original src modules dropped: {sorted(dropped)}")
if set(added) != expected_added:
    bad(f"added set != tree - original: unexpected {sorted(set(added) - expected_added)}, "
        f"missing {sorted(expected_added - set(added))}")
first = [m for m in FIRST_ADDED if m in expected_added]
if added != first + sorted(expected_added - set(first)):
    bad("added entries are not in the documented order")
if set(new_src) != set(tree):
    bad(f"PYZ src set != tree set: only PYZ {sorted(set(new_src) - set(tree))}, "
        f"only tree {sorted(set(tree) - set(new_src))}")
ok(f"added set == tree ({len(tree)}) - original PYZ src ({len(orig_src)}) = {len(added)} entries, "
   f"documented order; PYZ src set == tree set")
kinds = {PYZ_ITEM_MODULE: "module", PYZ_ITEM_PKG: "package", PYZ_ITEM_NSPKG: "namespace"}
for n in added:
    tc, blob = dn[n]
    print(f"      + {n:<62} {kinds[tc]:<9} {len(blob):>9,} B")

# ── 6. leftovers ──────────────────────────────────────────────────────────
print("[6] leftover dev/test files")
leftovers = [n for n in dn if DENY_RE.search(n) and n not in do]
if leftovers:
    bad(f"dev/test modules packaged: {leftovers}")
else:
    ok("no cjk_dump / run_test / test_* / conftest module among the added entries")

# ── 7. PyInstaller's own reader ───────────────────────────────────────────
print("[7] PyInstaller ZlibArchiveReader (code taken from the new exe)")
try:
    (m01,) = [e for e in en if e["name"] == b"pyimod01_archive"]
    raw = zlib.decompress(m01["data"]) if m01["cflag"] else m01["data"]
    mod = types.ModuleType("pyimod01_archive")
    exec(marshal.loads(raw), mod.__dict__)  # PyInstaller's archive reader only
    pyz_abs = an["start"] + pn["entry"]["off"]
    reader = mod.ZlibArchiveReader(f"{new_p}?{pyz_abs}")
    if {n: tuple(v) for n, v in reader.toc.items()} != {n: (tc, off, ln) for n, tc, off, ln in pn["items"]}:
        bad("reader TOC differs from the parsed TOC")
    n_read = 0
    for n, tc in new_src.items():
        got = reader.extract(n)
        if tc == PYZ_ITEM_NSPKG:
            if got is not None:
                bad(f"reader returned data for namespace {n}")
            continue
        if not isinstance(got, types.CodeType) or code_diff(got, decoded[n], n):
            bad(f"reader.extract({n!r}) differs")
        n_read += 1
    for n in names_o[::97]:                 # spot-check untouched third-party entries too
        if not is_src(n) and do[n][0] in (0, 1) and not isinstance(reader.extract(n), types.CodeType):
            bad(f"reader cannot extract {n}")
    ok(f"reader TOC has {len(reader.toc)} entries; extract() returned the expected code object "
       f"for all {n_read} src modules/packages")
except Exception as exc:                    # noqa: BLE001
    bad(f"reader emulation failed: {exc!r}")

# ── 8. Global 2.3.1: the efficiency-table seed belongs to the shipped static DB ─────────────────────────────
print("[8] arc efficiency seed (src/services/arc_efficiency_data.py) vs the payload's static DB")
try:
    import ast as _ast
    import json as _json
    _seed = src_dir / "services" / "arc_efficiency_data.py"
    _vals = {n.targets[0].id: _ast.literal_eval(n.value) for n in _ast.parse(_seed.read_text(encoding="utf-8")).body
             if isinstance(n, _ast.Assign) and isinstance(n.targets[0], _ast.Name)
             and n.targets[0].id in ("DATASET", "ENGINE_FP")}
    _payload = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else orig_p.parent / "_internal" / "data"
    _manifest = _json.loads((_payload / "manifest.json").read_text(encoding="utf-8"))["database"]
    _db = _payload / _manifest["filename"]
    _h = hashlib.sha256()
    with open(_db, "rb") as _f:
        for _chunk in iter(lambda: _f.read(1 << 20), b""):
            _h.update(_chunk)
    _real = _h.hexdigest().upper()
    _ds = _vals["DATASET"]
    if _ds["sha256"].upper() == _manifest["sha256"].upper() == _real and _ds["dataset_id"] == _manifest["dataset_id"] \
            and _ds["schema"] == _manifest["schema_version"] and _db.stat().st_size == _manifest["size_bytes"]:
        ok(f"seed DATASET.sha256 == payload manifest == {_db.name} ({_real[:16]}..., {_manifest['dataset_id']}, "
           f"schema {_manifest['schema_version']}); ENGINE_FP {_vals['ENGINE_FP']}")
    else:
        bad(f"seed DATASET {_ds} != payload manifest {_manifest['sha256'][:16]} / file {_real[:16]}")
except Exception as exc:                    # noqa: BLE001
    bad(f"seed check failed: {exc!r}")

print()
if fail:
    print(f"VERIFY_FAILED: {len(fail)} problem(s)")
    for f_ in fail[:40]:
        print("  -", f_)
    sys.exit(1)
print(f"VERIFY_OK: {len(passed)} checks passed - diff is limited to src.* PYZ records + PE checksum")
