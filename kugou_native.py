"""Bounded read-only adapter for the running KuGou native lyric animation.

Layouts come from named exports and strictly recognized getter instructions in
the installed ui.dll, never a version number or persisted process address. No
native code is loaded or invoked. An unknown layout is an unavailable channel.
"""
import ctypes as c
from ctypes import wintypes as w
from dataclasses import dataclass
from pathlib import Path
import re
import struct
import time
import unicodedata
from kugou_identity import titles_match, track_artists_match


LIMIT_MS = 86400000


def normalized(value):
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", value).casefold())


def member_getter(code, kind="int"):
    """Accept only a complete, side-effect-free field getter ending in ret."""
    prefixes = {"int": (b"\x8b\x81", b"\x8b\x41"),
                "address": (b"\x48\x8d\x81", b"\x48\x8d\x41"),
                "pointer": (b"\x48\x8b\x81", b"\x48\x8b\x41"),
                "float": (b"\xf3\x0f\x10\x81", b"\xf3\x0f\x10\x41")}
    for prefix, size in zip(prefixes[kind], (4, 1)):
        end = len(prefix) + size
        if code.startswith(prefix) and code[end:end + 1] == b"\xc3":
            offset = int.from_bytes(code[len(prefix):end], "little", signed=True)
            if 0 <= offset <= 16384:
                return offset
    raise ValueError("Unrecognized native lyric getter")


def dispatch_getter(code):
    # mov rcx,[rcx+member]; mov rax,[rcx]; jmp qword ptr [rax+slot]
    if code[:3] != b"\x48\x8b\x89" or code[7:10] != b"\x48\x8b\x01":
        raise ValueError("Unrecognized lyric dispatch")
    member = struct.unpack_from("<I", code, 3)[0]
    jump = 11 if code[10:11] == b"\x48" else 10
    if code[jump:jump + 2] == b"\xff\x60":
        slot = code[jump + 2]
    elif code[jump:jump + 2] == b"\xff\xa0":
        slot = struct.unpack_from("<I", code, jump + 2)[0]
    else:
        raise ValueError("Unrecognized lyric dispatch slot")
    if not 8 <= member <= 16384 or not 8 <= slot <= 1024 or slot % 8:
        raise ValueError("Invalid lyric dispatch layout")
    return member, slot


def read_msvc_string(read, address, *, wide=True):
    raw = read(address, 32)
    if len(raw) != 32:
        raise ValueError("Missing lyric metadata")
    size, capacity = struct.unpack_from("<QQ", raw, 16)
    if size > 1024 or capacity < size or capacity > 1048576:
        raise ValueError("Invalid lyric metadata string")
    unit, inline = (2, 8) if wide else (1, 16)
    data = raw[:size * unit] if capacity < inline else read(struct.unpack_from("<Q", raw)[0], size * unit)
    if len(data) != size * unit:
        raise ValueError("Truncated lyric metadata")
    text = data.decode("utf-16le" if wide else "utf-8")
    if any(char in text for char in "\x00\r\n"):
        raise ValueError("Invalid lyric metadata text")
    return text


@dataclass(frozen=True)
class Layout:
    vtable: int
    position: int
    lyric: int
    title: int
    artist: int
    album: int
    length: int
    duration: int
    lyric_hash: int | None = None


class NativeUnavailable(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def discover_layouts(path, base, read=None):
    """Infer supported layouts from exports and code in a PE file, not offsets."""
    import pefile
    pe = pefile.PE(str(path), fast_load=True)
    try:
        if pe.FILE_HEADER.Machine == 0x14c:
            raise NativeUnavailable("client_x86_unsupported")
        if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.SizeOfImage > 64 * 1024 * 1024:
            raise NativeUnavailable("module_unsupported")
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
        exports = {symbol.name.decode("ascii"): symbol.address for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols
                   if symbol.name}
        def exported(prefix):
            matches = [rva for name, rva in exports.items() if name.startswith(prefix)]
            if len(matches) != 1:
                raise ValueError("Native lyric export unavailable")
            return matches[0]
        def code(rva, size=64):
            if not 0 <= rva < pe.OPTIONAL_HEADER.SizeOfImage:
                return b""
            return pe.get_data(rva, size)
        if read is not None:
            for prefix in ("?GetPlaybackPosition@LyricViewForPlaying@", "?GetLyricText@LyricViewForPlaying@",
                           "?GetTitle@LyricText@", "?GetLength@LyricText@"):
                rva = exported(prefix)
                if read(base + rva, 24) != code(rva, 24):
                    raise ValueError("Installed lyric module differs from running module")
        owner, position_slot = dispatch_getter(code(exported("?GetPlaybackPosition@LyricViewForPlaying@")))
        highlight_owner, highlight_slot = dispatch_getter(code(exported("?GetCurrentLineHighlinePercent@LyricViewForPlaying@")))
        if owner != highlight_owner:
            raise ValueError("Inconsistent lyric implementation")
        outer_rva = exported("?GetLyricText@LyricViewForPlaying@")
        outer = code(outer_rva)
        # sub rsp,28; mov rcx,[rcx+owner]; call shared_ptr accessor
        if outer[:7] != b"\x48\x83\xec\x28\x48\x8b\x89" or outer[11:12] != b"\xe8":
            raise ValueError("Unrecognized lyric document accessor")
        if struct.unpack_from("<I", outer, 7)[0] != owner:
            raise ValueError("Inconsistent lyric document owner")
        target = outer_rva + 16 + struct.unpack_from("<i", outer, 12)[0]
        shared = code(target)
        # The managed shared_ptr accessor copies [rcx+lyric] into [rdx].
        copies = re.findall(rb"\x48\x8b\x41(.)\x48\x89\x02", shared, re.DOTALL)
        if len(copies) != 1:
            raise ValueError("Unrecognized lyric document pointer")
        lyric = copies[0][0]
        fields = {name: member_getter(code(exported("?Get" + name.capitalize() + "@LyricText@")),
                                      "address" if name in ("title", "artist", "album") else "int")
                  for name in ("title", "artist", "album", "length", "duration")}
        hashes = [rva for name, rva in exports.items() if name.startswith("?GetHash@LyricText@")]
        fields["lyric_hash"] = member_getter(code(hashes[0]), "address") if len(hashes) == 1 else None
        # Find complete integer field getters in executable sections, then find
        # their vtable references. Highlight must independently be a float getter.
        getters = {}
        for section in pe.sections:
            if not section.Characteristics & 0x20000000:
                continue
            raw = section.get_data()
            for match in re.finditer(rb"\x8b(?:\x81.{4}|\x41.)\xc3", raw, re.DOTALL):
                try:
                    getters[pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress + match.start()] = member_getter(match.group())
                except ValueError:
                    pass
        layouts = {}
        for section in pe.sections:
            if not section.Characteristics & 0x40000000 or section.Characteristics & (0x20000000 | 0x80000000):
                continue
            raw = section.get_data()
            for function, position in getters.items():
                at = raw.find(struct.pack("<Q", function))
                while at >= 0:
                    start = at - position_slot
                    if start >= 0 and start % 8 == 0 and start + highlight_slot + 8 <= len(raw):
                        high = struct.unpack_from("<Q", raw, start + highlight_slot)[0] - pe.OPTIONAL_HEADER.ImageBase
                        try:
                            member_getter(code(high), "float")
                            rva = section.VirtualAddress + start
                            layouts[rva] = Layout(base + rva, position, lyric, **fields)
                        except (ValueError, IndexError, struct.error):
                            pass
                    at = raw.find(struct.pack("<Q", function), at + 8)
        if not 1 <= len(layouts) <= 16:
            raise ValueError("Native lyric tables unavailable or ambiguous")
        return list(layouts.values())
    finally:
        pe.close()


class MemoryInfo(c.Structure):
    _fields_ = [("base", c.c_void_p), ("allocation_base", c.c_void_p), ("allocation_protect", w.DWORD),
                ("partition", w.WORD), ("size", c.c_size_t), ("state", w.DWORD),
                ("protect", w.DWORD), ("type", w.DWORD)]


class ReadOnlyProcess:
    def __init__(self, pid):
        self.pid, self.handle = pid, None
        self.kernel = k = c.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenProcess.restype = w.HANDLE
        k.CloseHandle.argtypes = [w.HANDLE]
        k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
        k.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
        k.VirtualQueryEx.argtypes = [w.HANDLE, c.c_void_p, c.POINTER(MemoryInfo), c.c_size_t]
        k.VirtualQueryEx.restype = c.c_size_t
        k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        self.handle = k.OpenProcess(0x10 | 0x400, False, pid)
        try:
            if not self.handle:
                raise OSError("KuGou read access unavailable")
            path, size = c.create_unicode_buffer(32768), w.DWORD(32768)
            if not k.QueryFullProcessImageNameW(self.handle, 0, path, c.byref(size)):
                raise OSError("KuGou identity unavailable")
            self.path = Path(path.value)
            if self.path.name.casefold() != "kugou.exe":
                raise ValueError("Read target is not KuGou")
        except Exception:
            self.close()
            raise

    def read(self, address, size):
        if not self.handle or not 65536 <= address < 0x7fffffffffff or not 0 <= size <= 2 * 1024 * 1024:
            return b""
        raw, count = c.create_string_buffer(size), c.c_size_t()
        if not self.kernel.ReadProcessMemory(self.handle, address, raw, size, c.byref(count)):
            return b""
        return raw.raw[:count.value]

    def pointer(self, address):
        raw = self.read(address, 8)
        return struct.unpack("<Q", raw)[0] if len(raw) == 8 else 0

    def ui_module(self):
        ps = c.WinDLL("psapi", use_last_error=True)
        ps.EnumProcessModulesEx.argtypes = [w.HANDLE, c.POINTER(w.HMODULE), w.DWORD, c.POINTER(w.DWORD), w.DWORD]
        ps.GetModuleFileNameExW.argtypes = [w.HANDLE, w.HMODULE, w.LPWSTR, w.DWORD]
        items, needed = (w.HMODULE * 2048)(), w.DWORD()
        if not ps.EnumProcessModulesEx(self.handle, items, c.sizeof(items), c.byref(needed), 3) or needed.value > c.sizeof(items):
            raise OSError("KuGou modules unavailable")
        modules = {}
        for base in items[:needed.value // c.sizeof(w.HMODULE)]:
            path = c.create_unicode_buffer(32768)
            if ps.GetModuleFileNameExW(self.handle, base, path, len(path)):
                modules[Path(path.value).name.casefold()] = (base, Path(path.value))
        base, path = modules["ui.dll"]
        if path.parent != modules["kugou.dll"][1].parent:
            raise ValueError("Lyric module is outside KuGou")
        return base, path

    def objects(self, layouts, max_bytes=768 * 1024 * 1024, max_seconds=4):
        patterns = [(struct.pack("<Q", layout.vtable), layout) for layout in layouts]
        found, address, scanned, started = [], 0, 0, time.monotonic()
        while scanned < max_bytes and time.monotonic() - started < max_seconds:
            info = MemoryInfo()
            if not self.kernel.VirtualQueryEx(self.handle, address, c.byref(info), c.sizeof(info)):
                break
            region = info.base or 0
            end = region + info.size
            if end <= address:
                break
            if info.state == 0x1000 and info.type == 0x20000 and info.protect in (4, 8):
                for offset in range(0, info.size, 1024 * 1024):
                    raw = self.read(region + offset, min(1024 * 1024, info.size - offset, max_bytes - scanned))
                    scanned += len(raw)
                    for pattern, layout in patterns:
                        at = raw.find(pattern)
                        while at >= 0:
                            obj = region + offset + at
                            if obj % 8 == 0:
                                found.append((obj, layout))
                                if len(found) >= 128:
                                    return found
                            at = raw.find(pattern, at + 1)
                    if scanned >= max_bytes or time.monotonic() - started >= max_seconds:
                        break
            address = end
        return found

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def read_object(memory, obj, layout):
    if memory.pointer(obj) != layout.vtable:
        raise ValueError("Lyric object was replaced")
    lyric = memory.pointer(obj + layout.lyric)
    fields = {name: read_msvc_string(memory.read, lyric + getattr(layout, name)) for name in ("title", "artist", "album")}
    def integer(address):
        raw = memory.read(address, 4)
        if len(raw) != 4:
            raise ValueError("Missing lyric time")
        return struct.unpack("<i", raw)[0]
    duration = max(integer(lyric + layout.duration), integer(lyric + layout.length))
    position = integer(obj + layout.position)
    if not fields["title"].strip() or not 0 < duration <= LIMIT_MS or not 0 <= position <= LIMIT_MS:
        raise ValueError("Invalid lyric timeline")
    if memory.pointer(obj) != layout.vtable or memory.pointer(obj + layout.lyric) != lyric:
        raise ValueError("Lyric document changed while reading")
    lyric_hash = read_msvc_string(memory.read, lyric + layout.lyric_hash, wide=False) if layout.lyric_hash is not None else ""
    if lyric_hash and not re.fullmatch(r"[0-9a-fA-F]{32}", lyric_hash):
        lyric_hash = ""
    return dict(**fields, duration_ms=duration, position_ms=position, document=lyric, lyric_hash=lyric_hash.casefold())


class NativeLyricsReader:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.process = None
        self.objects = []
        self.retry_at = 0
        self.previous = {}
        self.status = "waiting"
        self.module_version = ""

    def close(self):
        if self.process:
            self.process.close()
        self.process = None
        self.objects = []
        self.previous.clear()

    def read(self, pid, media=None):
        now = self.clock()
        if self.process and self.process.pid != pid:
            self.close()
            self.retry_at = 0
        if self.process is None:
            if now < self.retry_at:
                return None
            self.retry_at = now + 10
            try:
                self.process = ReadOnlyProcess(pid)
            except OSError:
                self.status = "read_access_unavailable"
                raise
            try:
                base, path = self.process.ui_module()
                self.module_version = path.parent.name if re.fullmatch(r"\d+(?:\.\d+){1,4}", path.parent.name) else ""
                self.layouts = discover_layouts(path, base, self.process.read)
            except Exception as error:
                self.status = (error.code if isinstance(error, NativeUnavailable) else
                               "module_unavailable" if isinstance(error, (KeyError, OSError)) else "layout_unrecognized")
                self.close()
                raise ValueError("Native lyric layout unavailable") from error
            self.objects = self.process.objects(self.layouts)
            self.retry_at = self.clock() + 5
        rows = []
        for obj, layout in self.objects:
            try:
                row = read_object(self.process, obj, layout)
                if media and (not titles_match(row["title"], media["title"]) or
                              media["artist"] and not track_artists_match(
                                  row["artist"], media["artist"], row["title"], media["title"])):
                    continue
                key = obj, row["document"]
                previous = self.previous.get(key)
                changed_at = now if previous is None or previous[0] != row["position_ms"] else previous[1]
                moved = bool(previous and (previous[2] or previous[0] != row["position_ms"]))
                self.previous[key] = row["position_ms"], changed_at, moved
                if len(self.previous) > 512:
                    self.previous = dict(list(self.previous.items())[-128:])
                # A valid object can stop advancing while audio buffers. Keep
                # its lyrics and freeze transport instead of falling back to OCR
                # and clearing a minimized window. A changing sibling wins below.
                row["playing"] = (media["playing"] and (previous is None or now - changed_at < .6)
                                  if media else moved and now - changed_at < .7)
                row["fresh"] = changed_at
                rows.append(row)
            except (ValueError, UnicodeError, struct.error):
                continue
        if not rows:
            self.status = "no_matching_lyric_object"
            if now >= self.retry_at:
                self.objects = self.process.objects(self.layouts)
                self.retry_at = self.clock() + 5
            return None
        # The desktop lyric view can be created after the first scan. A valid
        # main-window object may remain frozen after minimizing, so successful
        # reads alone must not prevent rediscovery of a newly running view.
        if now >= self.retry_at and not any(row["playing"] for row in rows) and (not media or media["playing"]):
            self.objects = self.process.objects(self.layouts)
            self.retry_at = self.clock() + 5
        self.status = "ready" if any(row["playing"] for row in rows) or media and not media["playing"] else "timeline_stalled"
        rows.sort(key=lambda row: row["fresh"], reverse=True)
        selected = rows[0]
        # Multiple views may include a frozen main-window copy; prefer views
        # that actually changed most recently, never average stale positions.
        result = {key: selected[key] for key in ("title", "artist", "album", "duration_ms", "position_ms", "playing")}
        result["native_title"] = selected["title"]
        result["lyric_hash"] = selected.get("lyric_hash", "")
        if media:
            for key in ("title", "artist", "album"):
                result[key] = media[key]
        result.update(source="kugou", rate=media.get("rate", 1.0) if media else 1.0, mode="native")
        return result
