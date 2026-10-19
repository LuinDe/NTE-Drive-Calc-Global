"""Rebuild the PyInstaller exe from a (multilingual) src tree - generalised rebuild_exe.py.

MUST run under the same Python the exe embeds (3.11 - cookie says python311.dll): the PYZ holds
marshalled 3.11 code objects and we write bytecode the frozen interpreter will execute.

Same surgical overlay rewrite as rebuild_exe.py (everything before the CArchive verbatim, every
CArchive entry except the PYZ byte-for-byte, every non-src PYZ entry byte-for-byte, src.* modules
recompiled with the ORIGINAL co_filename), with four generalisations:

  * an existing module keeps its ORIGINAL compressed record when the fresh compile is
    structurally equal to the original code object (bytecode, names, consts, line table, nested
    code objects, filenames).  rebuild_exe.py compared marshal bytes, which never match on this
    toolchain (same length, but marshal's FLAG_REF / interning bookkeeping depends on interpreter
    state at dump time), so it rewrote every record; comparing structure keeps the diff limited
    to genuinely changed modules.  Self-test: rebuilding from the pristine upstream tree keeps
    all 820 original records.

  * every module AND package present in the tree but absent from the original PYZ is added, at
    any depth (rebuild_exe.py only appended top-level src/i18n_*.py):
        foo.py              -> typecode 0 (PYZ_ITEM_MODULE)
        pkg/__init__.py     -> typecode 1 (PYZ_ITEM_PKG)
        dir without __init__ that contains modules and is unknown to the original PYZ
                            -> typecode 3 (PYZ_ITEM_NSPKG, zero-length record), which is how the
                               original build represents 'src', 'src.models', ... themselves
    co_filename follows the build's own style (relative, e.g. r"src\\app\\__init__.py").
  * deterministic order: original TOC order untouched, then 'src.i18n_display', 'src.i18n_desc'
    (continuity with the 2.x Korean releases), then the rest sorted by name.
  * the PYZ header keeps the original writer's layout (12-byte header + reserved bytes, first
    record at the original offset - 17 for PyInstaller 6); rebuild_exe.py started records at 12.
  * consistency guards - the build ABORTS (nothing written) when
        - a module/package of the original PYZ is missing from the tree,
        - a name changed kind (module <-> package <-> namespace dir),
        - a tree file looks like a leftover dev/test script, or is not an importable name.

usage: rebuild_exe_l10n.py <original exe> <root/src dir> <output exe> [--list-added] [--remove=<src.module> ...]
  --remove=<name>  drop that module of the original PYZ on purpose (it must be absent from the tree and a plain
                   module of the original build); every other missing module still aborts the build
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

assert sys.version_info[:2] == (3, 11), "run under Python 3.11 (the exe embeds python311.dll)"

PYZ_ITEM_MODULE, PYZ_ITEM_PKG, PYZ_ITEM_NSPKG = 0, 1, 3
FIRST_ADDED = ("src.i18n_display", "src.i18n_desc")
# leftover dev/test scripts must never be packaged
DENY_RE = re.compile(r"(^|\.)(cjk_dump|run_test|search_unit_test|conftest|tests?|test_\w+|\w+_test)$")
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def die(msg: str) -> "NoReturn":  # noqa: F821
    print("BUILD ABORTED:", msg, file=sys.stderr)
    sys.exit(2)


_CODE_ATTRS = ("co_code", "co_names", "co_varnames", "co_freevars", "co_cellvars", "co_flags",
               "co_argcount", "co_posonlyargcount", "co_kwonlyargcount", "co_nlocals",
               "co_stacksize", "co_name", "co_qualname", "co_firstlineno", "co_linetable",
               "co_exceptiontable", "co_filename")


def code_equal(a: types.CodeType, b: types.CodeType) -> bool:
    """Structural equality of two code objects (CodeType.__eq__ ignores filename/line table)."""
    for at in _CODE_ATTRS:
        if getattr(a, at) != getattr(b, at):
            return False
    if len(a.co_consts) != len(b.co_consts):
        return False
    return all(_const_equal(x, y) for x, y in zip(a.co_consts, b.co_consts))


def _const_equal(x, y) -> bool:
    if type(x) is not type(y):
        return False
    if isinstance(x, types.CodeType):
        return code_equal(x, y)
    if isinstance(x, tuple):
        return len(x) == len(y) and all(_const_equal(i, j) for i, j in zip(x, y))
    if isinstance(x, (float, complex)):
        return repr(x) == repr(y)           # tells 0.0 from -0.0, treats nan as equal to nan
    return x == y


def scan_tree(src: pathlib.Path) -> dict[str, tuple[int, pathlib.Path | None]]:
    """module name -> (typecode, file).  Namespace dirs (no __init__.py) get (3, None)."""
    out: dict[str, tuple[int, pathlib.Path | None]] = {}
    for f in sorted(src.rglob("*.py")):
        rel = f.relative_to(src)
        if "__pycache__" in rel.parts:
            continue
        parts = ("src",) + rel.with_suffix("").parts
        for p in parts:
            if not IDENT_RE.match(p):
                die(f"not an importable module path: {f}")
        if parts[-1] == "__init__":
            out[".".join(parts[:-1])] = (PYZ_ITEM_PKG, f)
        else:
            out[".".join(parts)] = (PYZ_ITEM_MODULE, f)
    for name in list(out):
        ps = name.split(".")
        for i in range(1, len(ps)):
            parent = ".".join(ps[:i])
            if parent not in out:
                out[parent] = (PYZ_ITEM_NSPKG, None)
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--") and not a.startswith("--remove=")}
    removes = {a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--remove=")}
    if len(args) != 3:
        die("usage: rebuild_exe_l10n.py <original exe> <root/src dir> <output exe> [--list-added]")
    orig_path, src_dir, out_path = (pathlib.Path(a) for a in args)
    if src_dir.name != "src" or not src_dir.is_dir():
        die(f"second argument must be the 'src' package directory: {src_dir}")
    if "program files" in str(out_path.resolve()).lower():
        die("refusing to write under Program Files")

    exe = orig_path.read_bytes()

    # ── CArchive ──────────────────────────────────────────────────────────
    MAGIC = b"MEI" + bytes([0x0C, 0x0B, 0x0A, 0x0B, 0x0E])
    cp = exe.rfind(MAGIC)
    if cp < 0 or cp + 88 != len(exe):
        die("CArchive cookie not found at the end of the original exe")
    magic, pkglen, tocpos, toclen, pyver, pylib = struct.unpack("!8sIIii64s", exe[cp:cp + 88])
    if pyver != 311:
        die(f"exe embeds python {pyver}, expected 311")
    start = cp + 88 - pkglen
    toc_raw = exe[start + tocpos:start + tocpos + toclen]

    entries = []                            # [raw_record, name, off, clen, ulen, cflag, typ]
    p = 0
    while p < len(toc_raw):
        elen, off, clen, ulen, cflag, typ = struct.unpack("!iIIIBc", toc_raw[p:p + 18])
        rec = toc_raw[p:p + elen]
        entries.append([rec, rec[18:].rstrip(b"\0"), off, clen, ulen, cflag, typ])
        p += elen

    # ── PYZ ───────────────────────────────────────────────────────────────
    (zi,) = [i for i, e in enumerate(entries) if e[6] == b"z"]
    z = exe[start + entries[zi][2]:start + entries[zi][2] + entries[zi][3]]
    if entries[zi][5]:
        z = zlib.decompress(z)
    assert z[:4] == b"PYZ\0"
    import importlib.util
    if z[4:8] != importlib.util.MAGIC_NUMBER:
        die("PYZ pyc magic differs from this interpreter's - wrong Python build")
    items = marshal.loads(z[struct.unpack("!i", z[8:12])[0]:])
    was_dict = isinstance(items, dict)
    if was_dict:
        items = list(items.items())

    def is_src(name: str) -> bool:
        return name == "src" or name.startswith("src.")

    tree = scan_tree(src_dir)
    orig_src = {name: tc for name, (tc, _, _) in items if is_src(name)}

    # guards: nothing dropped, nothing changed kind, nothing that smells like a test script
    problems = []
    for name in sorted(removes):
        if name not in orig_src:
            problems.append(f"--remove={name}: not a module of the original PYZ")
        elif orig_src[name] != PYZ_ITEM_MODULE:
            problems.append(f"--remove={name}: only plain modules can be removed (typecode {orig_src[name]})")
        elif name in tree:
            problems.append(f"--remove={name}: still present in the tree")
    for name, tc in orig_src.items():
        if name in removes:
            continue
        if name not in tree:
            problems.append(f"in the original PYZ but missing from the tree: {name} (typecode {tc})")
        elif tree[name][0] != tc:
            problems.append(f"kind changed for {name}: original typecode {tc}, tree {tree[name][0]}")
    for name in tree:
        if DENY_RE.search(name):
            problems.append(f"leftover dev/test module in the tree: {name}")
    if problems:
        die("\n  - " + "\n  - ".join(problems))

    if removes:
        items = [(name, entry) for name, entry in items if name not in removes]
        orig_src = {name: tc for name, tc in orig_src.items() if name not in removes}
    new_names = set(tree) - set(orig_src)
    first = [m for m in FIRST_ADDED if m in new_names]
    added = first + sorted(new_names - set(first))

    # ── recompile src.*, keep everything else byte-identical ───────────────
    sample_src_filename = None              # e.g. r"src\app\__init__.py" (relative, backslashes)
    stats = {"copied": 0, "recompiled": 0, "nonsrc": 0, "nspkg": 0}
    new_blobs: dict[str, bytes] = {}        # name -> compressed record to store
    for name, (tc, off, ln) in items:
        raw = z[off:off + ln]
        if not is_src(name):
            new_blobs[name] = raw
            stats["nonsrc"] += 1
            continue
        if tc == PYZ_ITEM_NSPKG:
            assert ln == 0, name
            new_blobs[name] = raw
            stats["nspkg"] += 1
            continue
        if tc not in (PYZ_ITEM_MODULE, PYZ_ITEM_PKG):
            die(f"unknown PYZ typecode {tc} for {name}")
        old_blob = zlib.decompress(raw)
        old_code = marshal.loads(old_blob)
        if sample_src_filename is None:
            sample_src_filename = old_code.co_filename
        text = tree[name][1].read_bytes().decode("utf-8-sig")
        code = compile(text, old_code.co_filename, "exec", dont_inherit=True, optimize=0)
        if code_equal(code, old_code):
            new_blobs[name] = raw           # untouched module: reuse original compressed bytes
            stats["copied"] += 1
        else:
            new_blobs[name] = zlib.compress(marshal.dumps(code), 9)
            stats["recompiled"] += 1

    assert sample_src_filename is not None
    sep = "/" if "/" in sample_src_filename else chr(92)
    if not sample_src_filename.startswith("src" + sep):
        die(f"unexpected co_filename style in the original build: {sample_src_filename!r}")

    existing = {n for n, _ in items}
    added_kinds = {PYZ_ITEM_MODULE: 0, PYZ_ITEM_PKG: 0, PYZ_ITEM_NSPKG: 0}
    for name in added:
        assert name not in existing, name
        tc, f = tree[name]
        added_kinds[tc] += 1
        if tc == PYZ_ITEM_NSPKG:
            new_blobs[name] = b""
        else:
            filename = sep.join(name.split(".")) + (sep + "__init__.py" if tc == PYZ_ITEM_PKG else ".py")
            code = compile(f.read_bytes().decode("utf-8-sig"), filename, "exec",
                           dont_inherit=True, optimize=0)
            new_blobs[name] = zlib.compress(marshal.dumps(code), 9)
        items.append((name, (tc, 0, 0)))

    # Header exactly as the original build wrote it: b"PYZ\0" + pyc magic + TOC pointer, followed by
    # the writer's reserved bytes (PyInstaller 6 reserves 12 + 5 bytes, so the first record of the
    # official PYZ sits at offset 17).  Copying up to the first original record keeps that layout
    # and therefore the offsets of every record in front of the first changed one.
    first_record = min(off for _, (_, off, ln) in items if ln)
    if not 12 <= first_record <= 64:
        die(f"unexpected PYZ layout: first record at offset {first_record}")
    pyz = bytearray(z[:first_record])
    new_items = []
    for name, (tc, _, _) in items:
        data = new_blobs[name]
        new_items.append((name, (tc, len(pyz), len(data))))
        pyz += data
    struct.pack_into("!i", pyz, 8, len(pyz))
    pyz += marshal.dumps(dict(new_items) if was_dict else new_items)
    pyz = bytes(pyz)

    # ── reassemble the archive ────────────────────────────────────────────
    data_sec = bytearray()
    new_toc = bytearray()
    for rec, name, off, clen, ulen, cflag, typ in entries:
        if typ == b"z":
            payload = zlib.compress(pyz, 9) if cflag else pyz
            new_off, new_clen, new_ulen = len(data_sec), len(payload), len(pyz)
        else:
            payload = exe[start + off:start + off + clen]
            new_off, new_clen, new_ulen = len(data_sec), clen, ulen
        data_sec += payload
        rec = bytearray(rec)
        struct.pack_into("!iIIIBc", rec, 0, len(rec), new_off, new_clen, new_ulen, cflag, typ)
        new_toc += rec

    new_pkglen = len(data_sec) + len(new_toc) + 88
    cookie = struct.pack("!8sIIii64s", magic, new_pkglen, len(data_sec), len(new_toc), pyver, pylib)
    out = bytearray(exe[:start] + bytes(data_sec) + bytes(new_toc) + cookie)

    # ── PE checksum (CheckSumMappedFile) ─────────────────────────────────
    def pe_checksum(buf: bytes | bytearray, csum_off: int) -> int:
        padded = bytes(buf) + (b"\0" if len(buf) % 2 else b"")
        words = array.array("H")
        words.frombytes(padded)             # little-endian on Windows
        i = csum_off // 2
        total = sum(words) - words[i] - words[i + 1]
        while total >> 16:
            total = (total & 0xFFFF) + (total >> 16)
        return (total + len(buf)) & 0xFFFFFFFF

    e_lfanew = struct.unpack_from("<I", exe, 0x3C)[0]
    assert exe[e_lfanew:e_lfanew + 4] == b"PE\0\0"
    csum_off = e_lfanew + 88                # optional header + 64
    check = pe_checksum(exe, csum_off)
    stored = struct.unpack_from("<I", exe, csum_off)[0]
    assert check == stored, f"checksum algo self-test failed: {check:#x} != stored {stored:#x}"
    new_csum = pe_checksum(out, csum_off)
    struct.pack_into("<I", out, csum_off, new_csum)

    out_path.write_bytes(out)
    print(f"original    : {orig_path.name}  sha256 {hashlib.sha256(exe).hexdigest()}")
    print(f"tree        : {len(tree)} names ({sum(1 for t, _ in tree.values() if t == 0)} modules, "
          f"{sum(1 for t, _ in tree.values() if t == 1)} packages, "
          f"{sum(1 for t, _ in tree.values() if t == 3)} namespace dirs)")
    print(f"PYZ src     : copied (unchanged, original record kept) {stats['copied']} | recompiled {stats['recompiled']} | "
          f"namespace kept {stats['nspkg']} | added {len(added)} "
          f"(modules {added_kinds[0]}, packages {added_kinds[1]}, namespace {added_kinds[3]})")
    print(f"PYZ non-src : {stats['nonsrc']} copied byte-for-byte")
    print(f"PYZ entries : {len(existing)} -> {len(new_items)}")
    print(f"size        : {len(exe):,} -> {len(out):,}")
    print(f"pe checksum : original verified ({stored:#010x}), new {new_csum:#010x}")
    print(f"sha256      : {hashlib.sha256(bytes(out)).hexdigest()}")
    print(f"output      : {out_path}")
    for name in sorted(removes):
        print(f"  - {name}  (removed on purpose: --remove)")
    if "--list-added" in flags:
        for name in added:
            print(f"  + {name}  (typecode {tree[name][0]})")


if __name__ == "__main__":
    main()
