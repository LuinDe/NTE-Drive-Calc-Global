# -*- coding: utf-8 -*-
"""Read-only extractor for Inno Setup 6.7.x installers (setup data version "6.7.0").

Nothing is executed: the installer exe is only read as bytes.

Pipeline
  1. SetupLdr offset table ("rDlPtS\\xcd\\xe6\\xd7\\x7b\\x0b\\x2a", 64 bytes, CRC-checked) -> Offset0 / Offset1.
  2. setup-0 at Offset0: 64-byte SetupID, then two "compressed blocks"
     (CRC32 + {StoredSize:Int64, Compressed:Byte} header, data in 4096-byte CRC'd chunks, LZMA1 raw):
       block 1 = TSetupHeader + languages, custom messages, permissions, types, components, tasks,
                 dirs, ISSig keys, FILES, icons, ini, registry, install/uninstall delete, run entries,
                 wizard images ...
       block 2 = TSetupFileLocationEntry[] (89 bytes each)
     Records are serialized as: each String (Int32 byte length + UTF-16LE), each AnsiString
     (Int32 length + bytes), then the rest of the packed record verbatim.  Layouts follow
     jrsoftware/issrc tag is-6_7_3 Projects/Src/Shared.Struct.pas.
  3. setup-1 data at Offset1 + StartOffset: "zlb\\x1a" + chunk stream (LZMA2: 1 prop byte, LZMA: 5 prop
     bytes, raw).  Each file = decompressed[ChunkSuboffset : +OriginalSize]; if
     floCallInstructionOptimized, Inno's x86 CALL/JMP inverse transform (64 KiB blocks) is applied.
  4. SELF-VERIFY: SHA-256 of every reconstructed file must equal TSetupFileLocationEntry.SHA256Sum
     and its length must equal OriginalSize.  Any mismatch aborts with exit code 2.

usage:
  inno_extract.py <setup.exe> <out_dir> [--list] [--json <entries.json>] [--manifest <manifest.json>]
     out_dir/app/...      files whose DestName starts with {app}
     out_dir/_other/...   files with any other destination constant (e.g. {tmp})
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import re
import struct
import sys
import zlib

LDR_MAGIC = b"rDlPtS\xcd\xe6\xd7\x7b\x0b\x2a"
SUPPORTED_IDS = (b"Inno Setup Setup Data (6.7.0)",)
ZLB_MAGIC = b"zlb\x1a"

VERSION_DATA = 10  # TSetupVersionData: WinVersion, NTVersion: Cardinal; NTServicePack: Word

# (strings, ansistrings, fixed tail bytes) per record type, Inno 6.7.x
REC = {
    "header":       (39, 4, 162),
    "language":     (4, 4, 2 + 4 * 3 + 4 + 1),                  # 19
    "custommsg":    (2, 0, 4),
    "permission":   (0, 1, 0),
    "type":         (4, 0, 2 * VERSION_DATA + 1 + 1 + 8),      # 30
    "component":    (5, 0, 8 + 1 + 1 + 2 * VERSION_DATA + 1 + 8),  # 39
    "task":         (6, 0, 1 + 1 + 2 * VERSION_DATA + 1),      # 23
    "dir":          (7, 0, 4 + 2 * VERSION_DATA + 2 + 1),      # 27
    "issigkey":     (3, 0, 0),
    "file":         (15, 1, 32 + 1 + 2 * VERSION_DATA + 4 + 4 + 8 + 2 + 8 + 1),  # 80
    "icon":         (13, 0, 16 + 2 * VERSION_DATA + 4 + 4 + 1 + 2 + 1),  # 48
    "ini":          (10, 0, 2 * VERSION_DATA + 1),             # 21
    "registry":     (9, 0, 2 * VERSION_DATA + 4 + 2 + 1 + 2),  # 29
    "delete":       (7, 0, 2 * VERSION_DATA + 1),              # 21
    "run":          (13, 0, 2 * VERSION_DATA + 4 + 1 + 2),     # 27 (13 strings in 6.7.x; 14 in 7.x)
}
LOC_SIZE = 89
FILE_STRING_NAMES = ["SourceFilename", "DestName", "InstallFontName", "StrongAssemblyName", "Components",
                     "Tasks", "Languages", "Check", "AfterInstall", "BeforeInstall", "Excludes",
                     "DownloadISSigSource", "DownloadUserName", "DownloadPassword", "ExtractArchivePassword"]
FILE_OPTIONS = ["ConfirmOverwrite", "UninsNeverUninstall", "RestartReplace", "DeleteAfterInstall",
                "RegisterServer", "RegisterTypeLib", "SharedFile", "CompareTimeStamp", "FontIsntTrueType",
                "SkipIfSourceDoesntExist", "OverwriteReadOnly", "OverwriteSameVersion", "CustomDestName",
                "OnlyIfDestFileExists", "NoRegError", "UninsRestartDelete", "OnlyIfDoesntExist",
                "IgnoreVersion", "PromptIfOlder", "DontCopy", "UninsRemoveReadOnly",
                "RecurseSubDirsExternal", "ReplaceSameVersionIfContentsDiffer", "DontVerifyChecksum",
                "UninsNoSharedFilePrompt", "CreateAllSubDirs", "32Bit", "64Bit", "ExternalSizePreset",
                "SetNTFSCompression", "UnsetNTFSCompression", "GacInstall", "Download", "ExtractArchive"]
LOC_FLAGS = ["VersionInfoValid", "TimeStampInUTC", "CallInstructionOptimized", "ChunkEncrypted",
             "ChunkCompressed"]
COMPRESS_METHODS = ["stored", "zip", "bzip", "lzma", "lzma2"]
HEADER_STRING_NAMES = ["AppName", "AppVerName", "AppId", "AppCopyright", "AppPublisher", "AppPublisherURL",
                       "AppSupportPhone", "AppSupportURL", "AppUpdatesURL", "AppVersion", "DefaultDirName",
                       "DefaultGroupName", "BaseFilename", "UninstallFilesDir", "UninstallDisplayName",
                       "UninstallDisplayIcon", "AppMutex", "DefaultUserInfoName", "DefaultUserInfoOrg",
                       "DefaultUserInfoSerial", "AppReadmeFile", "AppContact", "AppComments",
                       "AppModifyPath", "CreateUninstallRegKey", "Uninstallable", "CloseApplicationsFilter",
                       "SetupMutex", "ChangesEnvironment", "ChangesAssociations", "ArchitecturesAllowed",
                       "ArchitecturesInstallIn64BitMode", "CloseApplicationsFilterExcludes",
                       "SevenZipLibraryName", "UsePreviousAppDir", "UsePreviousGroup",
                       "UsePreviousSetupType", "UsePreviousTasks", "UsePreviousUserInfo"]
COUNT_NAMES = ["Language", "CustomMessage", "Permission", "Type", "Component", "Task", "Dir", "ISSigKey",
               "File", "FileLocation", "Icon", "Ini", "Registry", "InstallDelete", "UninstallDelete",
               "Run", "UninstallRun"]


class Corrupt(Exception):
    pass


# ── low level ──────────────────────────────────────────────────────────────
class Buf:
    def __init__(self, data: bytes):
        self.d = data
        self.p = 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.p + n > len(self.d):
            raise Corrupt(f"read past end of block (pos {self.p} + {n} > {len(self.d)})")
        r = self.d[self.p:self.p + n]
        self.p += n
        return r

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def string(self) -> str:
        n = self.i32()
        if n < 0 or n % 2:
            raise Corrupt(f"bad unicode string length {n} at {self.p - 4}")
        return self.take(n).decode("utf-16-le")

    def ansi(self) -> bytes:
        n = self.i32()
        if n < 0:
            raise Corrupt(f"bad ansi string length {n} at {self.p - 4}")
        return self.take(n)

    def record(self, kind: str):
        ns, na, tail = REC[kind]
        s = [self.string() for _ in range(ns)]
        a = [self.ansi() for _ in range(na)]
        return s, a, self.take(tail)


def read_ldr_table(exe: bytes) -> dict:
    hits = []
    for m in re.finditer(re.escape(LDR_MAGIC), exe):
        t = exe[m.start():m.start() + 64]
        if len(t) < 64:
            continue
        (ident, ver, total, off_exe, usize_exe, crc_exe, off0, off1, _pad,
         tcrc) = struct.unpack("<12sIqqIiqqIi", t)
        if (zlib.crc32(t[:60]) & 0xFFFFFFFF) != (tcrc & 0xFFFFFFFF):
            continue
        hits.append(dict(pos=m.start(), version=ver, total_size=total, offset_exe=off_exe,
                         uncompressed_size_exe=usize_exe, crc_exe=crc_exe & 0xFFFFFFFF,
                         offset0=off0, offset1=off1))
    if len(hits) != 1:
        raise Corrupt(f"expected exactly one CRC-valid SetupLdr offset table, found {len(hits)}")
    t = hits[0]
    if t["version"] != 2:
        raise Corrupt(f"unsupported offset table version {t['version']}")
    if t["total_size"] != len(exe):
        raise Corrupt(f"offset table TotalSize {t['total_size']} != file size {len(exe)}")
    return t


def read_block(exe: bytes, q: int):
    """Inno TCompressedBlockReader: CRC32 + packed {StoredSize: Int64; Compressed: Boolean}."""
    crc, stored, comp = struct.unpack("<IqB", exe[q:q + 13])
    if (zlib.crc32(exe[q + 4:q + 13]) & 0xFFFFFFFF) != crc or comp not in (0, 1) or stored <= 0:
        raise Corrupt(f"bad compressed-block header at {q}")
    q += 13
    raw = bytearray()
    left = stored
    while left > 0:
        if left <= 4:
            raise Corrupt("truncated block chunk")
        ccrc, = struct.unpack("<I", exe[q:q + 4])
        n = min(4096, left - 4)
        chunk = exe[q + 4:q + 4 + n]
        if len(chunk) != n or (zlib.crc32(chunk) & 0xFFFFFFFF) != ccrc:
            raise Corrupt(f"block chunk CRC mismatch at {q}")
        raw += chunk
        q += 4 + n
        left -= 4 + n
    if comp:
        pr = raw[:5]
        d = pr[0]
        lc, d = d % 9, d // 9
        lp, pb = d % 5, d // 5
        ds, = struct.unpack("<I", pr[1:5])
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[
            {"id": lzma.FILTER_LZMA1, "dict_size": max(ds, 4096), "lc": lc, "lp": lp, "pb": pb}])
        data = dec.decompress(bytes(raw[5:]))
    else:
        data = bytes(raw)
    return data, q


# ── setup-0 parsing ────────────────────────────────────────────────────────
def parse_setup0(exe: bytes, off0: int):
    sid = exe[off0:off0 + 64].rstrip(b"\0")
    if sid not in SUPPORTED_IDS:
        raise Corrupt(f"unsupported SetupID {sid!r} (this extractor knows {SUPPORTED_IDS})")
    # TSetupEncryptionHeader (6.4+): CRC32 + packed {EncryptionUse: (euNone, euFiles, euFull); KDFSalt[16];
    # KDFIterations: Integer; BaseNonce[24]; PasswordTest: Integer} = 4 + 49 bytes
    q = off0 + 64
    ecrc, = struct.unpack("<I", exe[q:q + 4])
    enc = exe[q + 4:q + 53]
    if (zlib.crc32(enc) & 0xFFFFFFFF) != ecrc:
        raise Corrupt("encryption header CRC mismatch (layout changed?)")
    if enc[0] != 0:
        raise Corrupt(f"installer uses encryption (EncryptionUse={enc[0]}); not supported")
    blk1, q = read_block(exe, q + 53)
    blk2, q2 = read_block(exe, q)

    b = Buf(blk1)
    hs, ha, ht = b.record("header")
    header = dict(zip(HEADER_STRING_NAMES, hs))
    counts = dict(zip(COUNT_NAMES, struct.unpack("<17i", ht[:68])))
    t = ht[68:]
    # MinVersion(10) OnlyBelowVersion(10) WizardSizePercentX/Y(8) DarkStyle(1) AlphaFormat(1)
    # colors 6x4 opacity 2 LightControlStyling 1 ExtraDiskSpaceRequired 8 SlicesPerDisk 4
    # UninstallLogMode DirExistsWarning PrivilegesRequired PrivOverrides ShowLanguageDialog
    # LanguageDetectionMethod CompressMethod DisableDirPage DisableProgramGroupPage  UninstallDisplaySize 8
    # Options 8
    o = 20 + 8 + 2 + 24 + 2 + 1
    extra_space, slices = struct.unpack("<qi", t[o:o + 12])
    o += 12
    (logmode, direxists, privreq, privover, showlang, langdetect, compress, ddir,
     dgroup) = t[o:o + 9]
    o += 9
    uninst_size, options = struct.unpack("<qQ", t[o:o + 16])
    o += 16
    if o != len(t):
        raise Corrupt("header tail size mismatch")
    if compress >= len(COMPRESS_METHODS):
        raise Corrupt(f"bad CompressMethod {compress}")
    header.update(counts={k: v for k, v in counts.items()}, slices_per_disk=slices,
                  privileges_required=privreq, compress_method=COMPRESS_METHODS[compress],
                  extra_disk_space=extra_space, uninstall_display_size=uninst_size)
    for k, v in counts.items():
        if v < 0 or v > 1_000_000:
            raise Corrupt(f"implausible count {k}={v} (header layout mismatch?)")

    for _ in range(counts["Language"]):
        b.record("language")
    for _ in range(counts["CustomMessage"]):
        b.record("custommsg")
    for _ in range(counts["Permission"]):
        b.record("permission")
    for _ in range(counts["Type"]):
        b.record("type")
    for _ in range(counts["Component"]):
        b.record("component")
    tasks = []
    for _ in range(counts["Task"]):
        s, _a, _t = b.record("task")
        tasks.append({"name": s[0], "description": s[1]})
    dirs = []
    for _ in range(counts["Dir"]):
        s, _a, _t = b.record("dir")
        dirs.append(s[0])
    for _ in range(counts["ISSigKey"]):
        b.record("issigkey")
    files = []
    for i in range(counts["File"]):
        s, a, tail = b.record("file")
        rec = dict(zip(FILE_STRING_NAMES, s))
        vhash = tail[0:32]
        vtyp = tail[32]
        o = 33 + 2 * VERSION_DATA
        loc, attribs, ext_size, perm = struct.unpack("<iiqh", tail[o:o + 18])
        o += 18
        opts, = struct.unpack("<Q", tail[o:o + 8])
        ftype = tail[o + 8]
        rec.update(index=i, location=loc, attribs=attribs, external_size=ext_size,
                   permissions=perm, file_type=ftype, verification_type=vtyp,
                   verification_hash=vhash.hex() if vtyp == 1 else None,
                   issig_allowed_keys=a[0].decode("latin1"),
                   options=[n for k, n in enumerate(FILE_OPTIONS) if opts >> k & 1])
        if ftype not in (0, 1):
            raise Corrupt(f"file entry {i}: bad FileType {ftype} (layout mismatch?)")
        files.append(rec)
    icons = []
    for _ in range(counts["Icon"]):
        s, _a, _t = b.record("icon")
        icons.append({"name": s[0], "target": s[1]})
    for _ in range(counts["Ini"]):
        b.record("ini")
    regs = []
    for _ in range(counts["Registry"]):
        s, _a, _t = b.record("registry")
        regs.append({"subkey": s[0], "name": s[1], "data": s[2]})
    deletes = []
    for kind in ("InstallDelete", "UninstallDelete"):
        for _ in range(counts[kind]):
            s, _a, t = b.record("delete")
            deletes.append({"section": kind, "name": s[0], "tasks": s[2], "check": s[4],
                            "type": ["files", "filesandordirs", "dirifempty"][t[-1]] if t[-1] < 3 else t[-1]})
    runs = []
    for _ in range(counts["Run"]):
        s, _a, _t = b.record("run")
        runs.append({"name": s[0], "parameters": s[1], "tasks": s[8], "check": s[10]})
    for _ in range(counts["UninstallRun"]):
        s, _a, _t = b.record("run")
        runs.append({"uninstall": True, "name": s[0], "parameters": s[1]})
    rest = len(blk1) - b.p
    # sanity: what follows the entries is the wizard image list (Integer count, then Integer len + data)
    img = []
    try:
        nimg = b.i32()
        for _ in range(nimg):
            d = b.ansi()
            img.append(("png" if d[:8] == b"\x89PNG\r\n\x1a\n" else "bmp" if d[:2] == b"BM" else "?", len(d)))
    except Corrupt:
        img.append("unparsable")

    # ── block 2: location entries ──
    if len(blk2) != counts["FileLocation"] * LOC_SIZE:
        raise Corrupt(f"location block {len(blk2)} bytes != {counts['FileLocation']} x {LOC_SIZE}")
    locs = []
    for i in range(counts["FileLocation"]):
        r = blk2[i * LOC_SIZE:(i + 1) * LOC_SIZE]
        (first_slice, last_slice, start, sub, size, csize) = struct.unpack("<iiqqqq", r[:40])
        sha = r[40:72]
        ftime, vms, vls = struct.unpack("<QII", r[72:88])
        fl = r[88]
        if fl >> len(LOC_FLAGS):
            raise Corrupt(f"location {i}: unknown flag bits {fl:#x}")
        locs.append(dict(index=i, first_slice=first_slice, last_slice=last_slice, start_offset=start,
                         chunk_suboffset=sub, size=size, chunk_compressed_size=csize,
                         sha256=sha.hex(), filetime=ftime, version_ms=vms, version_ls=vls,
                         flags=[n for k, n in enumerate(LOC_FLAGS) if fl >> k & 1]))
    for f in files:
        if not (-1 <= f["location"] < len(locs)):
            raise Corrupt(f"file entry {f['index']} location {f['location']} out of range")
    meta = dict(setup_id=sid.decode(), block1_size=len(blk1), block1_unparsed_tail=rest,
                first_wizard_images=img, block2_size=len(blk2), setup0_end=q2, deletes=deletes)
    return header, tasks, dirs, files, icons, regs, runs, locs, meta


# ── data chunks ────────────────────────────────────────────────────────────
def lzma2_dict_size(p: int) -> int:
    if p > 40:
        raise Corrupt(f"bad LZMA2 dictionary property {p}")
    if p == 40:
        return 0xFFFFFFFF
    return (2 | (p & 1)) << (p // 2 + 11)


def chunk_stream(f, pos: int, csize: int, method: str):
    f.seek(pos)
    if f.read(4) != ZLB_MAGIC:
        raise Corrupt(f"missing zlb\\x1a chunk magic at {pos}")
    remaining = csize
    if method == "lzma2":
        p = f.read(1)[0]
        remaining -= 1
        filters = [{"id": lzma.FILTER_LZMA2, "dict_size": min(lzma2_dict_size(p), 1 << 30)}]
    elif method == "lzma":
        pr = f.read(5)
        remaining -= 5
        d = pr[0]
        lc, d = d % 9, d // 9
        lp, pb = d % 5, d // 5
        ds, = struct.unpack("<I", pr[1:5])
        filters = [{"id": lzma.FILTER_LZMA1, "dict_size": max(ds, 4096), "lc": lc, "lp": lp, "pb": pb}]
    else:
        raise Corrupt(f"unsupported chunk compression {method}")
    dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters)
    while not dec.eof:
        if dec.needs_input:
            if remaining <= 0:
                break
            data = f.read(min(1 << 22, remaining))
            if not data:
                raise Corrupt("unexpected end of installer inside chunk")
            remaining -= len(data)
        else:
            data = b""
        out = dec.decompress(data, max_length=1 << 24)
        if out:
            yield out


class Cursor:
    """Sequential reader over a chunk's decompressed byte stream."""

    def __init__(self, gen):
        self.gen = gen
        self.buf = bytearray()
        self.pos = 0  # absolute offset of buf[0]

    def read_at(self, off: int, n: int) -> bytes:
        if off < self.pos:
            raise Corrupt("non-monotonic chunk suboffset")
        while self.pos + len(self.buf) < off + n:
            try:
                piece = next(self.gen)
            except StopIteration:
                raise Corrupt("chunk ended before all files were read")
            self.buf += piece
            # drop data before 'off' to bound memory
            drop = min(off - self.pos, len(self.buf))
            if drop > (1 << 26):
                del self.buf[:drop]
                self.pos += drop
        s = off - self.pos
        out = bytes(self.buf[s:s + n])
        del self.buf[:s + n]
        self.pos = off + n
        return out


_E8E9 = re.compile(rb"[\xe8\xe9]")


def call_untransform(data: bytes) -> bytes:
    """Inverse of Inno's TransformCallInstructions (applied per 64 KiB buffer, AddrOffset = bytes before)."""
    buf = bytearray(data)
    n = len(buf)
    search = _E8E9.search
    for bstart in range(0, n, 65536):
        size = min(65536, n - bstart)
        if size < 5:
            continue
        lim = bstart + size - 4
        i = bstart
        while True:
            m = search(buf, i, lim)
            if m is None:
                break
            i = m.start() + 1
            hb = buf[i + 3]
            if hb == 0 or hb == 0xFF:
                addr = (i + 4) & 0xFFFFFF
                rel = (buf[i] | (buf[i + 1] << 8) | (buf[i + 2] << 16)) - addr
                if rel & 0x800000:
                    buf[i + 3] = hb ^ 0xFF
                buf[i] = rel & 0xFF
                buf[i + 1] = (rel >> 8) & 0xFF
                buf[i + 2] = (rel >> 16) & 0xFF
            i += 4
    return bytes(buf)


def dest_path(out_dir: str, dest: str):
    m = re.match(r"\{([^}]+)\}\\?(.*)$", dest)
    if m and m.group(1).lower() == "app":
        rel = m.group(2).replace("\\", "/")
        return os.path.join(out_dir, "app", *rel.split("/")), "app", rel
    const = m.group(1) if m else "_noconst"
    rest = m.group(2) if m else dest
    rel = rest.replace("\\", "/")
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", const)
    return os.path.join(out_dir, "_other", safe, *rel.split("/")), const, rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("setup")
    ap.add_argument("out_dir")
    ap.add_argument("--list", action="store_true", help="parse + list only, do not extract")
    ap.add_argument("--json", help="write parsed entries to this json")
    ap.add_argument("--manifest", help="write extracted-file manifest (path,size,sha256) to this json")
    args = ap.parse_args()

    exe = open(args.setup, "rb").read()
    setup_sha = hashlib.sha256(exe).hexdigest()
    tbl = read_ldr_table(exe)
    header, tasks, dirs, files, icons, regs, runs, locs, meta = parse_setup0(exe, tbl["offset0"])
    method = header["compress_method"]
    print(f"installer {os.path.basename(args.setup)} {len(exe)} bytes sha256 {setup_sha}")
    print(f"  {meta['setup_id']}  AppName={header['AppName']!r} AppVersion={header['AppVersion']!r} "
          f"AppId={header['AppId']!r}")
    print(f"  offset0={tbl['offset0']} offset1={tbl['offset1']} compress={method} "
          f"slices_per_disk={header['slices_per_disk']}")
    print(f"  counts: " + ", ".join(f"{k}={v}" for k, v in header["counts"].items() if v))
    print(f"  block1 {meta['block1_size']} bytes, unparsed tail (wizard images etc.) {meta['block1_unparsed_tail']}")
    if header["slices_per_disk"] != 1 or any(l["first_slice"] != 0 or l["last_slice"] != 0 for l in locs):
        raise Corrupt("disk spanning not supported")
    if any("ChunkEncrypted" in l["flags"] for l in locs):
        raise Corrupt("encrypted chunks not supported")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(dict(installer=os.path.basename(args.setup), installer_sha256=setup_sha,
                           ldr_table=tbl, meta=meta, header=header, tasks=tasks, dirs=dirs,
                           files=files, icons=icons, registry=regs, run=runs, locations=locs),
                      fh, ensure_ascii=False, indent=1)
    if args.list:
        for fe in files:
            print(f"  [{fe['location']:5d}] {fe['DestName']}  tasks={fe['Tasks']!r} check={fe['Check']!r}")
        return 0

    # map location -> destinations
    by_loc: dict[int, list[dict]] = {}
    for fe in files:
        if fe["location"] >= 0:
            by_loc.setdefault(fe["location"], []).append(fe)
    unused = [l["index"] for l in locs if l["index"] not in by_loc]

    # group into chunks
    chunks: dict[tuple, list[dict]] = {}
    for l in locs:
        chunks.setdefault((l["start_offset"], l["chunk_compressed_size"]), []).append(l)
    starts = sorted(chunks)
    print(f"  {len(locs)} data locations in {len(chunks)} chunk(s); {len(files)} file entries; "
          f"{len(unused)} unreferenced locations")

    written: dict[str, dict] = {}
    verified = 0
    total = 0
    with open(args.setup, "rb") as f:
        for key in starts:
            start, csize = key
            members = sorted(chunks[key], key=lambda l: l["chunk_suboffset"])
            comp = {("ChunkCompressed" in l["flags"]) for l in members}
            if len(comp) != 1:
                raise Corrupt("mixed compression flags inside one chunk")
            pos = tbl["offset1"] + start
            if comp.pop():
                cur = Cursor(chunk_stream(f, pos, csize, method))
            else:
                f.seek(pos)
                if f.read(4) != ZLB_MAGIC:
                    raise Corrupt(f"missing chunk magic at {pos}")
                stored = f.read(csize)
                cur = Cursor(iter([stored]))
            for l in members:
                data = cur.read_at(l["chunk_suboffset"], l["size"])
                if "CallInstructionOptimized" in l["flags"]:
                    data = call_untransform(data)
                h = hashlib.sha256(data).hexdigest()
                if len(data) != l["size"] or h != l["sha256"]:
                    print(f"SELF-VERIFY FAILED: location {l['index']} size {len(data)}/{l['size']} "
                          f"sha256 {h} != {l['sha256']} flags={l['flags']} "
                          f"dest={[x['DestName'] for x in by_loc.get(l['index'], [])]}", file=sys.stderr)
                    return 2
                verified += 1
                total += len(data)
                for fe in by_loc.get(l["index"], []):
                    path, const, rel = dest_path(args.out_dir, fe["DestName"])
                    key2 = f"{{{const}}}/{rel}"
                    if key2 in written:
                        if written[key2]["sha256"] != h:
                            print(f"  NOTE duplicate destination with different content: {key2} "
                                  f"(entry {fe['index']}, tasks={fe['Tasks']!r} check={fe['Check']!r}) "
                                  f"-> kept first, wrote alternative as .alt{fe['index']}")
                            path = path + f".alt{fe['index']}"
                        else:
                            continue
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as out:
                        out.write(data)
                    if key2 not in written:
                        written[key2] = dict(const=const, path=rel, size=len(data), sha256=h,
                                             location=l["index"], entry=fe["index"],
                                             tasks=fe["Tasks"], check=fe["Check"],
                                             components=fe["Components"], languages=fe["Languages"],
                                             options=fe["options"])
    print(f"  SELF-VERIFY OK: {verified}/{len(locs)} locations, {total} bytes, every SHA-256 matched")
    print(f"  wrote {len(written)} destination files")
    if args.manifest:
        app = sorted((w for w in written.values() if w["const"].lower() == "app"), key=lambda w: w["path"])
        other = sorted((w for w in written.values() if w["const"].lower() != "app"),
                       key=lambda w: (w["const"], w["path"]))
        with open(args.manifest, "w", encoding="utf-8") as fh:
            json.dump(dict(format=1, installer=os.path.basename(args.setup), installer_sha256=setup_sha,
                           installer_size=len(exe), setup_id=meta["setup_id"],
                           app_name=header["AppName"], app_version=header["AppVersion"],
                           app_id=header["AppId"], self_verified_locations=verified,
                           total_files=len(app), total_bytes=sum(w["size"] for w in app),
                           files=[dict(path=w["path"], size=w["size"], sha256=w["sha256"]) for w in app],
                           other_destinations=[dict(const=w["const"], path=w["path"], size=w["size"],
                                                    sha256=w["sha256"], tasks=w["tasks"],
                                                    check=w["check"], options=w["options"]) for w in other],
                           conditional_app_files=[dict(path=w["path"], tasks=w["tasks"], check=w["check"],
                                                       components=w["components"])
                                                  for w in app if w["tasks"] or w["check"] or w["components"]]),
                      fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Corrupt as e:
        print(f"ABORT: {e}", file=sys.stderr)
        sys.exit(3)
