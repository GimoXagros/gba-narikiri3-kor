#!/usr/bin/env python3
"""Local, frame-stepped libretro diagnostic host (not a product build).

Uses the documented libretro ABI. ROM is loaded from an immutable byte copy;
input saves are copied into core memory, never opened for writing. All evidence
is confined to a new run directory. A single-threaded localhost API serializes
operations; there is no real-time background guest execution.
"""
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from PIL import Image


BUTTONS = {"b": 0, "select": 2, "start": 3, "up": 4, "down": 5,
           "left": 6, "right": 7, "a": 8, "l": 10, "r": 11}


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


class SystemInfo(C.Structure):
    _fields_ = [("name", C.c_char_p), ("version", C.c_char_p), ("extensions", C.c_char_p),
                ("need_fullpath", C.c_bool), ("block_extract", C.c_bool)]


class Variable(C.Structure):
    _fields_ = [("key", C.c_char_p), ("value", C.c_char_p)]


class MemoryDescriptor(C.Structure):
    _fields_ = [("flags", C.c_uint64), ("ptr", C.c_void_p), ("offset", C.c_size_t),
                ("start", C.c_size_t), ("select", C.c_size_t), ("disconnect", C.c_size_t),
                ("len", C.c_size_t), ("addrspace", C.c_char_p)]


class MemoryMap(C.Structure):
    _fields_ = [("descriptors", C.POINTER(MemoryDescriptor)), ("num_descriptors", C.c_uint)]


ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
BATCH = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL = C.CFUNCTYPE(None)
INPUT = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


class Probe:
    def __init__(self, dll: Path, rom_path: Path, run_dir: Path, save_path: Path | None):
        if run_dir.exists():
            raise ValueError("Run directory must be new: no prior evidence or save is overwritten")
        run_dir.mkdir(parents=True)
        self.root = run_dir.resolve()
        self.frame = 0
        self.pixel_format = 0
        self.video = None
        self.keys = set()
        self.maps = []
        self.options = {}
        self.ram_interventions = 0
        self.closed = False
        self.option_overrides = {b"mgba_use_bios": b"OFF", b"mgba_skip_bios": b"ON",
                                 b"mgba_frameskip": b"disabled", b"mgba_frameskip_interval": b"0"}
        self.directory = str(self.root).encode("utf-8")
        self.rom = rom_path.read_bytes()
        self.rom_hash = hashlib.sha256(self.rom).hexdigest()
        self.dll_hash = hashlib.sha256(dll.read_bytes()).hexdigest()
        self.lib = C.CDLL(str(dll.resolve()))
        self.callbacks = [ENV(self.environment), VIDEO(self.receive_video), AUDIO(lambda *_: None),
                          BATCH(lambda _, n: n), POLL(lambda: None), INPUT(self.input)]
        for name, callback in zip(("environment", "video_refresh", "audio_sample", "audio_sample_batch",
                                   "input_poll", "input_state"), self.callbacks):
            fn = getattr(self.lib, "retro_set_" + name)
            fn.argtypes = [type(callback)]
            fn.restype = None
            fn(callback)
        for name in ("retro_init", "retro_deinit", "retro_run", "retro_reset", "retro_unload_game"):
            getattr(self.lib, name).argtypes = []
            getattr(self.lib, name).restype = None
        self.lib.retro_get_system_info.argtypes = [C.POINTER(SystemInfo)]
        self.lib.retro_load_game.argtypes = [C.POINTER(GameInfo)]
        self.lib.retro_load_game.restype = C.c_bool
        self.lib.retro_get_memory_data.argtypes = [C.c_uint]
        self.lib.retro_get_memory_data.restype = C.c_void_p
        self.lib.retro_get_memory_size.argtypes = [C.c_uint]
        self.lib.retro_get_memory_size.restype = C.c_size_t
        self.lib.retro_serialize_size.argtypes = []
        self.lib.retro_serialize_size.restype = C.c_size_t
        for name in ("retro_serialize", "retro_unserialize"):
            getattr(self.lib, name).argtypes = [C.c_void_p, C.c_size_t]
            getattr(self.lib, name).restype = C.c_bool
        self.lib.retro_init()
        info = SystemInfo()
        self.lib.retro_get_system_info(C.byref(info))
        if info.need_fullpath:
            raise ValueError("This diagnostic requires memory-loaded content")
        self.core_name = info.name.decode()
        self.core_version = info.version.decode()
        self.rom_buffer = C.create_string_buffer(self.rom)
        game = GameInfo(b"diagnostic.gba", C.cast(self.rom_buffer, C.c_void_p), len(self.rom), None)
        if not self.lib.retro_load_game(C.byref(game)):
            raise RuntimeError("Core rejected ROM")
        self.input_save_hash = None
        if save_path:
            savedata = save_path.read_bytes()
            if len(savedata) != 8192:
                raise ValueError("Only an explicit 8192-byte EEPROM save is accepted")
            pointer = self.lib.retro_get_memory_data(0)
            size = self.lib.retro_get_memory_size(0)
            if not pointer or size < len(savedata):
                raise ValueError("Save memory is not available")
            offset = self.eeprom_offset(size)
            C.memmove(pointer + offset, savedata, len(savedata))
            self.input_save_buffer_offset = offset
            self.input_save_hash = hashlib.sha256(savedata).hexdigest()
        self.log({"op": "initialize", **self.status()})

    def log(self, entry):
        with (self.root / "operations.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps({"frame": self.frame, **entry}, ensure_ascii=False) + "\n")

    def eeprom_offset(self, size):
        if size == 139264 and self.dll_hash == 'd44bac8b74eef4e61e1e5cba7678f7ce78e949d44becd3b2a5d813b79c8c6372':
            # This core's adjust_save_ram runs in retro_init, before the host
            # supplies a save. Its combined buffer therefore remains active:
            # memory.c places eepromData after the 128 KiB Flash area.
            # Source: libretro/vba-next@788192f215ad0a1413f1625b40ebba3423fa0ade.
            return 0x20000
        if size in (8192, 131072) and self.core_name == 'mGBA':
            return 0  # mGBA switches its exposed size after EEPROM detection.
        raise ValueError(f'Unsupported EEPROM buffer layout: {self.core_name}, {size}')

    def environment(self, command, data):
        command &= 0xFFFF
        if command in (9, 31):
            C.cast(data, C.POINTER(C.c_char_p))[0] = self.directory
            return True
        if command == 3:
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        if command == 10:
            self.pixel_format = C.cast(data, C.POINTER(C.c_uint))[0]
            return self.pixel_format in (0, 1, 2)
        if command == 16:
            values = C.cast(data, C.POINTER(Variable))
            n = 0
            while values[n].key:
                definition = values[n].value.decode()
                self.options[values[n].key] = definition.split(";", 1)[1].strip().split("|")[0].encode()
                n += 1
            return True
        if command == 15:
            var = C.cast(data, C.POINTER(Variable)).contents
            value = self.option_overrides.get(var.key, self.options.get(var.key))
            if value is None:
                return False
            var.value = value
            return True
        if command == 17:
            C.cast(data, C.POINTER(C.c_bool))[0] = False
            return True
        if command == 36:
            value = C.cast(data, C.POINTER(MemoryMap)).contents
            self.maps = [{name: getattr(value.descriptors[i], name) for name, _ in MemoryDescriptor._fields_}
                         for i in range(value.num_descriptors)]
            return True
        if command in (39, 52):
            C.cast(data, C.POINTER(C.c_uint))[0] = 0
            return True
        if command == 47:
            C.cast(data, C.POINTER(C.c_int))[0] = 3
            return True
        if command == 50:
            C.cast(data, C.POINTER(C.c_float))[0] = 59.7275
            return True
        if command in (1, 11, 18, 32, 35, 37):
            return True
        return False

    def input(self, port, device, index, button):
        return int(port == 0 and device == 1 and index == 0 and button in self.keys)

    def receive_video(self, pointer, width, height, pitch):
        if pointer and pointer != C.c_void_p(-1).value:
            self.video = (C.string_at(pointer, pitch * height), width, height, pitch)

    def status(self):
        return {"core": self.core_name, "core_version": self.core_version,
                "core_sha256": self.dll_hash, "rom_sha256": self.rom_hash,
                "input_save_sha256": self.input_save_hash, "frame": self.frame,
                "ram_interventions": self.ram_interventions,
                "pixel_format": self.pixel_format, "save_size": self.lib.retro_get_memory_size(0),
                "memory_maps": [{k: v for k, v in d.items() if k not in ("ptr", "addrspace")}
                                for d in self.maps], "options": {k.decode(): v.decode() for k, v in self.options.items()},
                "option_overrides": {k.decode(): v.decode() for k, v in self.option_overrides.items()}}

    def output_path(self, name):
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Evidence path outside run directory")
        if path.exists():
            raise ValueError("Evidence already exists; use a new name")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def read_memory(self, address, length):
        if not 0 < length <= 0x20000:
            raise ValueError("Memory read must be 1..131072 bytes")
        for d in self.maps:
            if d["ptr"] and d["start"] <= address and address + length <= d["start"] + d["len"]:
                return C.string_at(d["ptr"] + d["offset"] + address - d["start"], length)
        raise ValueError("Read outside a core-reported direct memory extent")

    def execute(self, request):
        op = request["op"]
        result = {}
        if op == "status":
            return self.status()
        if op == "frames":
            count = request.get("count", 1)
            if type(count) is not int or not 1 <= count <= 3600:
                raise ValueError("Frame count must be 1..3600")
            self.keys = {BUTTONS[b] for b in request.get("buttons", [])}
            try:
                for _ in range(count):
                    self.lib.retro_run()
                    self.frame += 1
            finally:
                self.keys = set()
        elif op == "screenshot":
            if self.video is None:
                raise ValueError("No frame has been rendered")
            data, width, height, pitch = self.video
            if self.pixel_format == 1:
                im = Image.frombytes("RGB", (width, height), data, "raw", "BGRX", pitch)
            else:
                pixels = []
                for y in range(height):
                    for x in range(width):
                        v = int.from_bytes(data[y*pitch+x*2:y*pitch+x*2+2], "little")
                        if self.pixel_format == 2:
                            pixels.append((((v >> 11) & 31)*255//31, ((v >> 5) & 63)*255//63, (v & 31)*255//31))
                        else:
                            pixels.append((((v >> 10) & 31)*255//31, ((v >> 5) & 31)*255//31, (v & 31)*255//31))
                im = Image.new("RGB", (width, height))
                im.putdata(pixels)
            path = self.output_path(request["name"])
            im.save(path)
            im.resize((width*4, height*4), Image.Resampling.NEAREST).save(path.with_name(path.stem + "_4x.png"))
            result = {"path": str(path), "size": [width, height], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        elif op in ("read", "dump"):
            address = int(str(request["address"]), 0)
            memory = self.read_memory(address, int(request["length"]))
            if op == "read":
                result = {"hex": memory.hex(), "address": address}
            else:
                path = self.output_path(request["name"])
                path.write_bytes(memory)
                result = {"path": str(path), "sha256": hashlib.sha256(memory).hexdigest()}
        elif op == "write_ram":
            # Controlled test-fixture construction, never a ROM/IO/VRAM write.
            address = int(str(request["address"]), 0)
            expected = bytes.fromhex(request["expected_hex"])
            final = bytes.fromhex(request["final_hex"])
            if not 0 < len(final) <= 2048 or len(expected) != len(final):
                raise ValueError("RAM compare-and-set must be equal-length, 1..2048 bytes")
            if not any(start <= address and address+len(final) <= end for start,end in
                       ((0x02000000,0x02040000),(0x03000000,0x03008000))):
                raise ValueError("Fixture writes are restricted to direct work RAM")
            if len(request.get("reason", "")) < 10 or request.get("test_fixture_only") is not True:
                raise ValueError("An explicit fixture-only reason is required")
            if self.read_memory(address, len(expected)) != expected:
                raise ValueError("RAM expected bytes do not match; no write performed")
            for d in self.maps:
                if d["ptr"] and d["start"] <= address and address+len(final) <= d["start"]+d["len"]:
                    C.memmove(d["ptr"]+d["offset"]+address-d["start"], final, len(final))
                    break
            else:
                raise ValueError("No direct core memory extent")
            self.ram_interventions += 1
            result = {"address":address,"length":len(final),"fixture_modified":True,
                      "limitation":"NOT natural progression or save-compatibility evidence"}
        elif op == "state_save":
            size = self.lib.retro_serialize_size()
            buffer = C.create_string_buffer(size)
            if not self.lib.retro_serialize(buffer, size):
                raise ValueError("Serialize failed")
            path = self.output_path(request["name"])
            path.write_bytes(buffer.raw)
            record = {"rom_sha256": self.rom_hash, "core_sha256": self.dll_hash, "frame": self.frame,
                      "state_sha256": hashlib.sha256(buffer.raw).hexdigest()}
            path.with_suffix(path.suffix + ".json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            result = {"path": str(path), **record}
        elif op == "state_load":
            path = Path(request["path"]).resolve()
            record = json.loads(path.with_suffix(path.suffix + ".json").read_text(encoding="utf-8"))
            data = path.read_bytes()
            if record["rom_sha256"] != self.rom_hash or record["core_sha256"] != self.dll_hash or record["state_sha256"] != hashlib.sha256(data).hexdigest():
                raise ValueError("State is not bound to this exact ROM/core")
            buffer = C.create_string_buffer(data)
            if not self.lib.retro_unserialize(buffer, len(data)):
                raise ValueError("Unserialize failed")
            self.frame = record["frame"]
            self.video = None
        elif op == "save_export":
            size = self.lib.retro_get_memory_size(0)
            offset = self.eeprom_offset(size)
            if size != 8192 and offset == 0:
                raise ValueError(f"EEPROM not identified as 8 KiB: {size}")
            data = C.string_at(self.lib.retro_get_memory_data(0) + offset, 8192)
            path = self.output_path(request["name"])
            path.write_bytes(data)
            result = {"path": str(path), "size": len(data), "core_buffer_size": size, "core_buffer_offset": offset, "sha256": hashlib.sha256(data).hexdigest(),
                      "fixture_modified": self.ram_interventions > 0}
        elif op == "close":
            self.closed = True
        else:
            raise ValueError("Unknown operation")
        self.log({"request": request, "result": result})
        return {"ok": True, "frame": self.frame, **result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--trace", type=Path, help="Replay recorded controller inputs before serving")
    args = parser.parse_args()
    probe = Probe(args.core, args.rom, args.run_dir, args.save)
    if args.trace:
        for line in args.trace.read_text(encoding="utf-8").splitlines():
            request = json.loads(line).get("request", {})
            if request.get("op") == "frames":
                probe.execute(request)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                length = int(self.headers["Content-Length"])
                if not 0 < length <= 16384:
                    raise ValueError("Invalid request length")
                result = probe.execute(json.loads(self.rfile.read(length)))
                code = 200
            except Exception as error:
                result, code = {"ok": False, "error": str(error)}, 400
            data = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    (probe.root / "endpoint.json").write_text(json.dumps({"port": server.server_port, **probe.status()}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"port": server.server_port, **probe.status()}, ensure_ascii=False), flush=True)
    try:
        while not probe.closed:
            server.handle_request()
    finally:
        server.server_close()
        probe.lib.retro_unload_game()
        probe.lib.retro_deinit()


if __name__ == "__main__":
    main()
