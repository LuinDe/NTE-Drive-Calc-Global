"""Exercise the real Windows native.inventory.page RPC with an isolated capture provider.

python build_tools/verify_elyms_native.py <original-2.3.1-nte-core.exe> <updated-nte-core.exe>

Requires pywin32. Both executables receive only synthetic records through a named pipe
owned by the test process. No game, DLL deployment, account or network access is needed.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import multiprocessing
import os
from pathlib import Path
from queue import Queue
import struct
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread

import win32file
import win32pipe


DRIVE = "cell2_style1_1_Orange"
CORE = "Attack_orange"
PROVIDER = "toolkit.combat.v1"
TIMEOUT = 10


def uid(slot: int, serial: int) -> dict:
    # 'solt' is the capture plugin's spelling on the wire.
    return {"solt": slot, "serial": serial, "key": f"{slot}:{serial}"}


def make_snapshot(character_id: int) -> tuple[dict, list]:
    owner, other = uid(20001, 900001), uid(20002, 900002)
    drive, core = uid(10001, 700001), uid(10002, 700002)
    empty = uid(0, 0)
    slots = []
    for index in range(49):
        row, column = divmod(index, 7)
        occupied = index in (8, 9)
        slots.append({
            "slotIndex": index, "Row": row, "Column": column, "State": int(occupied),
            "EquipmentID": DRIVE if occupied else "None",
            "EquipNetID": drive if occupied else empty, "bFirstStep": index == 8,
        })
    holder = {
        "kind": "HTCharacterItem", "ItemID": str(character_id), "UniqueID": owner,
        "source": "InventoryItemsMap.CARD", "bIsTemporary": False, "bUnSaved": False,
        "EquipCoreSlots": [{"slotIndex": 0, "Row": 0, "Column": 0, "State": 1,
                           "EquipmentID": CORE, "EquipNetID": core, "bFirstStep": True}],
        "EquipmentSlots": [{"groupIndex": 0, "SlotList": slots}],
    }
    other_holder = dict(holder, ItemID="1057", UniqueID=other, EquipCoreSlots=[], EquipmentSlots=[])
    records = []
    for item_id, instance, base_properties in [(DRIVE, drive, ["AtkAdd", "HPMaxAdd"]),
                                                (CORE, core, ["AtkUp"])]:
        records.append({
            "kind": "HTEquipmentItem", "UniqueID": instance, "mapUniqueID": instance,
            "ItemID": item_id, "CharacterNetID": owner, "source": "InventoryItemsMap",
            "containerType": 1, "mapUidMatchesItem": True, "duplicateMapUidObserved": False,
            "StrengthenLevel": 20, "IsLocked": True, "IsDiscarded": False, "IsEquiped": True,
            "bIsTemporary": False, "bUnSaved": False, "Amount": 1,
            "RandomBaseModifyData": base_properties,
            "RandomModifyData": [{"PropName": name, "PropValue": value} for name, value in (
                ("AtkUp", 0.05), ("CritBase", 0.06), ("CritDamageBase", 0.12), ("DefAdd", 18.0))],
        })
    header = {
        "providerId": PROVIDER, "domain": "inventory", "domainKey": "fixture-inventory",
        "snapshotId": "10", "generation": "7", "observedUnixUs": "1700000000000000",
        "observedMonotonicMs": "1000", "enabled": True, "ready": True, "state": "ready",
        "recordCount": len(records), "sourceRecordCount": len(records), "complete": False,
        "enumerationComplete": True, "collectionComplete": True, "collectionScope": "EQUIP",
        "characterRefs": [other_holder, holder], "characterRefsComplete": True,
        "sourceCoverage": "unknown", "changeCoverage": "unknown",
        "missing": [], "failed": False, "truncated": False,
    }
    return header, records


def read_exact(pipe, count: int) -> bytes:
    buf = bytearray()
    while len(buf) < count:
        _, chunk = win32file.ReadFile(pipe, count - len(buf))
        if not chunk:
            raise EOFError("native pipe closed")
        buf.extend(chunk)
    return bytes(buf)


def serve_fixture(character_id: int, ready) -> None:
    times = [wintypes.FILETIME() for _ in range(4)]
    if not ctypes.windll.kernel32.GetProcessTimes(wintypes.HANDLE(-1), *(ctypes.byref(t) for t in times)):
        raise ctypes.WinError()
    created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    pipe_name = rf"\\.\pipe\nte.capture.v1.{os.getpid()}.{created}"
    header, records = make_snapshot(character_id)
    pipe = win32pipe.CreateNamedPipe(pipe_name, win32pipe.PIPE_ACCESS_DUPLEX, win32pipe.PIPE_TYPE_BYTE,
                                     1, 65536, 65536, 1000, None)
    try:
        ready.send(True)
        ready.close()
        try:
            win32pipe.ConnectNamedPipe(pipe, None)
        except OSError as err:
            if err.winerror != 535:  # Client connected between creation and ConnectNamedPipe.
                raise
        while True:
            size, = struct.unpack("<I", read_exact(pipe, 4))
            if not 0 < size <= 65536:
                raise ValueError("unexpected native request size")
            request = json.loads(read_exact(pipe, size))
            method = request["method"]
            if method == "hello":
                result = {"protocolVersion": 1, "providerId": PROVIDER, "gamePid": os.getpid(),
                          "ready": True, "capabilities": ["combat.context.v1", "inventory.snapshot.v1"]}
            elif method == "snapshot.refresh":
                assert request["params"]["domain"] == "inventory"
                result = header
            elif method == "snapshot.page":
                params = request["params"]
                assert params["domain"] == "inventory" and params["snapshotId"] == header["snapshotId"]
                assert params["offset"] == 0 and params["limit"] >= len(records)
                result = dict(header, offset=0, nextOffset=None, records=records)
            else:
                raise ValueError(f"unexpected native method: {method}")
            message = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}).encode()
            win32file.WriteFile(pipe, struct.pack("<I", len(message)) + message)
    except OSError as err:
        if err.winerror != 109:  # Normal disconnect on Core shutdown.
            raise
    finally:
        pipe.Close()


def read_stdout(stream, replies: Queue) -> None:
    for line in stream:
        replies.put(json.loads(line))
    replies.put(None)


def page_reply(executable: Path, character_id: int) -> dict:
    with TemporaryDirectory(prefix="nte-elyms-verify-") as data:
        context = multiprocessing.get_context("spawn")
        ready, signal = context.Pipe(duplex=False)
        peer = context.Process(target=serve_fixture, args=(character_id, signal), daemon=True)
        peer.start()
        signal.close()
        try:
            if not ready.poll(TIMEOUT) or not ready.recv():
                raise TimeoutError("fixture pipe did not start")
            cmd = [str(executable), "serve-native", "--stdio", "--game-pid", str(peer.pid), "--data-dir", data]
            with subprocess.Popen(cmd, cwd=data, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  creationflags=subprocess.CREATE_NO_WINDOW) as core:
                try:
                    replies = Queue()
                    reader = Thread(target=read_stdout, args=(core.stdout, replies), daemon=True)
                    reader.start()
                    def rpc(method: str, params: dict) -> dict:
                        core.stdin.write((json.dumps({"jsonrpc": "2.0", "method": method,
                                                      "id": method, "params": params}) + "\n").encode())
                        core.stdin.flush()
                        while True:
                            reply = replies.get(timeout=TIMEOUT)
                            if reply is None:
                                raise RuntimeError(f"Core exited while handling {method}")
                            if reply.get("id") == method:
                                return reply
                    hello = rpc("core.hello", {"client_name": "fixture", "client_version": "2.3.1",
                                              "protocol_min": 1, "protocol_max": 1})["result"]
                    assert "native_inventory_dto_v1" in hello["capabilities"]
                    header = rpc("native.snapshot.refresh", {"domain": "inventory"})["result"]
                    assert header["ready"] and header["recordCount"] == 2
                    return rpc("native.inventory.page", {"snapshotId": header["snapshotId"], "offset": 0, "limit": 64})
                finally:
                    core.terminate()
                    core.wait(timeout=TIMEOUT)
        finally:
            ready.close()
            peer.terminate()
            peer.join(timeout=TIMEOUT)


def verify_page(core: Path, owner: int) -> dict:
    page = page_reply(core, owner)["result"]
    assert page["projectionComplete"] and not page["projectionMissing"]
    assert sorted(row["character_id"] for row in page["characters"]) == sorted([1057, owner])
    items = {item["item_id"]: item for item in page["items"]}
    assert set(items) == {DRIVE, CORE}
    assert all(item["equipped_character_id"] == owner and item["equipped"] for item in items.values())
    assert all(item["equipped_character_uid"] == {"slot": 20001, "serial": 900001} for item in items.values())
    assert items[DRIVE]["equipped_placement"] == {"row": 1, "column": 1}
    assert items[CORE]["equipped_placement"] is None
    return page


def verify_unsupported(core: Path, character_id: int) -> None:
    reply = page_reply(core, character_id)
    assert "result" not in reply
    assert reply["error"]["code"] == -32000
    assert reply["error"]["data"]["domain_code"] == "NATIVE_MAPPING_UNSUPPORTED"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("updated", type=Path)
    args = parser.parse_args()
    previous, updated = args.baseline.resolve(strict=True), args.updated.resolve(strict=True)
    assert verify_page(previous, 1003) == verify_page(updated, 1003), "known mapping changed"
    verify_unsupported(previous, 1090)
    verify_page(updated, 1090)
    verify_unsupported(updated, 999999)
    print("PASS: known pair unchanged; old Core rejects Elyms; new Core preserves both owners and both equipped items; unknown ID rejected.")
