"""Read KuGou KRC/LRC lyrics with bounded decoding and conservative matching."""
from dataclasses import dataclass
import base64
import configparser
import json
import math
import os
from pathlib import Path
import re
import unicodedata
import urllib.parse
import urllib.request
import zlib

from lrc import LyricDocument, LyricLine, TimedWord, parse_lrc, chinese_translation
from kugou_identity import title_keys, titles_match, track_artists_match

LIMIT = 2 * 1024 * 1024
KRC_KEY = bytes((64, 71, 97, 119, 94, 50, 116, 71, 81, 54, 49, 45, 206, 210, 110, 105))


@dataclass(frozen=True)
class LyricResult:
    document: LyricDocument | None
    message: str
    source: str = ""


def normalized(text):
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", str(text)).casefold())


def decode_krc(raw):
    if not isinstance(raw, bytes) or len(raw) > LIMIT or not raw.startswith(b"krc1"):
        raise ValueError("KRC 文件头无效或文件过大")
    encrypted = raw[4:]
    compressed = bytes(value ^ KRC_KEY[i % len(KRC_KEY)] for i, value in enumerate(encrypted))
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(compressed, LIMIT + 1)
    if len(decoded) > LIMIT or not decoder.eof or decoder.unused_data:
        raise ValueError("KRC 解压内容无效或过大")
    return decoded.decode("utf-8-sig")


def parse_krc(text):
    if len(text.encode("utf-8")) > LIMIT:
        raise ValueError("歌词过大")
    rows = []
    offset_match = re.search(r"\[offset:([+-]?\d+)\]", text, re.I)
    offset = int(offset_match[1]) if offset_match else 0
    for raw in text.splitlines():
        match = re.match(r"\[(\d+),(\d+)\](.*)", raw)
        if not match:
            continue
        start, duration, body = int(match[1]), int(match[2]), match[3]
        if not 0 <= start < 86400000 or not 0 <= duration <= 86400000 or len(body) > 16384:
            raise ValueError("KRC 时间或行长度无效")
        tokens = list(re.finditer(r"<(\d+),(\d+),\d+>", body))
        line, words = "", []
        if tokens:
            line = body[:tokens[0].start()]
            for i, token in enumerate(tokens):
                part = body[token.end():tokens[i + 1].start() if i + 1 < len(tokens) else len(body)]
                begin = start + int(token[1]); end = begin + int(token[2])
                index = len(line)
                line += part
                if part.strip() and 0 <= begin < end <= 86400000:
                    words.append(TimedWord(begin, end, index, len(line)))
        else:
            line = body
        if len(line) > 2048 or len(rows) >= 5000:
            raise ValueError("歌词行数或文本长度过大")
        if start + duration > 86400000:
            raise ValueError("KRC 结束时间无效")
        rows.append(LyricLine(start, line, tuple(words), end_ms=start + duration))
    if not rows:
        raise ValueError("未找到 KRC 歌词")
    # KuGou's language tag stores translation rows by original line index.
    language = re.search(r"\[language:([A-Za-z0-9+/=]+)\]", text)
    if language:
        try:
            data = json.loads(base64.b64decode(language[1], validate=True))
            for item in data.get("content", []):
                if item.get("type") != 1:
                    continue
                translated = item.get("lyricContent", [])
                if len(translated) != len(rows):
                    continue
                from dataclasses import replace
                for i, parts in enumerate(translated):
                    if isinstance(parts, list) and all(isinstance(x, str) for x in parts):
                        value = " ".join(parts).strip()
                        if chinese_translation(value):
                            rows[i] = replace(rows[i], translation=value)
                break
        except (ValueError, TypeError, AttributeError):
            pass
    return LyricDocument(sorted(rows, key=lambda row: row.start_ms), [], offset)


def lyric_directories():
    roots = []
    appdata = Path(os.environ.get("APPDATA", str(Path.home())))
    for folder in (appdata / "KuGou8", appdata / "KuGou", Path.home() / "Music" / "KuGou"):
        for ini in (folder / "KuGou.ini", folder / "kugou.ini"):
            if not ini.is_file() or ini.stat().st_size > LIMIT:
                continue
            for encoding in ("utf-8-sig", "utf-16", "gb18030"):
                try:
                    parser = configparser.ConfigParser(strict=False, interpolation=None)
                    parser.read_string(ini.read_text(encoding=encoding))
                    for section in parser.sections():
                        for key, value in parser.items(section):
                            if key in ("lyricpath", "lrcpath"):
                                roots.append(Path(value.strip().strip('"')))
                    break
                except (UnicodeError, configparser.Error):
                    continue
        roots.append(folder / "Lyric")
    roots.extend((Path.home() / "Music" / "KuGou" / "Lyric",))
    return tuple(dict.fromkeys(p for p in roots if p.is_dir()))


def local_lyrics(snapshot, directories=None, cancelled=lambda: False):
    title = normalized(snapshot.title)
    artist = normalized(snapshot.artist)
    expected_hash = getattr(snapshot, "lyric_hash", "").casefold()
    titles = title_keys(snapshot.title)
    if getattr(snapshot, "native_title", ""):
        titles |= title_keys(snapshot.native_title)
    matches, hash_matches = [], set()
    for folder in directories if directories is not None else lyric_directories():
        try:
            for index, path in enumerate(Path(folder).iterdir()):
                if cancelled() or index >= 6000:
                    break
                if path.suffix.casefold() not in (".krc", ".lrc") or not path.is_file():
                    continue
                stem = re.sub(r"[-_][0-9a-f]{32}(?:-\d+-[0-9a-f]+)?$", "", path.stem, flags=re.I)
                valid_names = set(titles)
                if artist:
                    valid_names = {artist + value for value in titles} | {value + artist for value in titles}
                parts = stem.split(" - ", 1)
                alias_match = (len(parts) == 2 and bool(artist) and track_artists_match(
                                   parts[0], snapshot.artist, parts[1], snapshot.title)
                               and bool(title_keys(parts[1]) & titles))
                hash_named = bool(expected_hash) and bool(re.search(
                    r"(?<![0-9a-f])" + re.escape(expected_hash) + r"(?![0-9a-f])", path.stem, re.I))
                if (normalized(stem) in valid_names or alias_match or hash_named) and 0 < path.stat().st_size <= LIMIT:
                    matches.append(path)
                    if hash_named:
                        hash_matches.add(path)
        except OSError:
            continue
    # Never attach an arbitrary recent cache file to the currently playing song.
    for path in sorted(matches, key=lambda p: (p not in hash_matches, p.suffix.casefold() != ".krc", -p.stat().st_mtime))[:8]:
        if cancelled():
            return None
        try:
            raw = path.read_bytes()
            text = decode_krc(raw) if path.suffix.casefold() == ".krc" else raw.decode("utf-8-sig")
            if expected_hash:
                match = re.search(r"\[hash:([0-9a-f]{32})\]", text, re.I)
                if match is None or match[1].casefold() != expected_hash:
                    continue
            doc = parse_krc(text) if path.suffix.casefold() == ".krc" else parse_lrc(text)
            return LyricResult(doc, "已同步酷狗本地歌词", "cache")
        except (OSError, UnicodeError, ValueError, zlib.error):
            continue
    return None


def request_json(path, params, opener=None):
    url = "https://lyrics.kugou.com" + path + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "KuGou2012", "Accept": "application/json"})
    with (opener or urllib.request.urlopen)(request, timeout=4) as response:
        raw = response.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("歌词响应过大")
    return json.loads(raw)


def choose_candidate(candidates, snapshot, *, diagnostics=None):
    matches = []
    counts = dict(title=0, artist=0, duration=0, identity=0)
    def failed(reason):
        if diagnostics is not None:
            diagnostics.update(reason=reason, **counts)
        return None
    if not isinstance(candidates, list):
        return failed("invalid")
    if not candidates:
        return failed("empty")
    for row in candidates[:100]:
        if not isinstance(row, dict) or not titles_match(row.get("song", ""), snapshot.title):
            continue
        counts["title"] += 1
        if not snapshot.artist or not track_artists_match(
                row.get("singer", ""), snapshot.artist, row.get("song", ""), snapshot.title):
            continue
        counts["artist"] += 1
        duration = row.get("duration")
        if (isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration)
                or not 0 < duration <= 86400000 or abs(duration - snapshot.duration_ms) > 2500):
            continue
        counts["duration"] += 1
        if not re.fullmatch(r"\d{1,32}", str(row.get("id", ""))) or not re.fullmatch(r"[a-zA-Z0-9]{8,128}", str(row.get("accesskey", ""))):
            continue
        matches.append(row)
        counts["identity"] += 1
    if not matches:
        return failed("title" if not counts["title"] else "artist" if not counts["artist"] else
                      "duration" if not counts["duration"] else "invalid")
    matches.sort(key=lambda row: abs(row["duration"] - snapshot.duration_ms))
    if len(matches) > 1 and matches[0]["id"] != matches[1]["id"] and matches[0]["duration"] == matches[1]["duration"]:
        return failed("ambiguous")
    return matches[0]


def load_song_lyrics(snapshot, cancelled=lambda: False, request=request_json, directories=None):
    local = local_lyrics(snapshot, directories=directories, cancelled=cancelled)
    if local:
        return local
    if cancelled():
        return LyricResult(None, "已取消歌词读取")
    if not snapshot.artist:
        return LyricResult(None, "未能可靠读取歌手，等待酷狗显示完整歌曲信息；暂不猜配联网歌词。")
    params = dict(ver=1, client="pc", man="yes", keyword=snapshot.artist + " " + snapshot.title,
                  duration=snapshot.duration_ms)
    data = request("/search", params)
    if cancelled():
        return LyricResult(None, "已取消歌词读取")
    diagnostics = {}
    candidate = choose_candidate(data.get("candidates"), snapshot, diagnostics=diagnostics)
    if candidate is None:
        # The client may finish writing its own cache during the HTTP request.
        # Recheck once before reporting failure; do not wait or guess a candidate.
        local = local_lyrics(snapshot, directories=directories, cancelled=cancelled)
        if local:
            return local
        if cancelled():
            return LyricResult(None, "已取消歌词读取")
        reason = diagnostics["reason"]
        messages = {
            "empty": "酷狗官方接口未返回歌词候选，等待本地缓存；可选择歌词缓存目录后重新获取。",
            "title": "歌词候选的歌名不匹配，暂不使用；请检查当前歌曲信息或选择歌词缓存目录。",
            "artist": "歌词候选的歌手不匹配，暂不使用；请检查歌手信息或选择歌词缓存目录。",
            "duration": "歌词候选与读取时长不符，暂不使用；" +
                        ("当前时长来自原生歌词范围，可尝试读取本地缓存。" if snapshot.mode == "native" else
                         "请等待完整歌曲信息或选择歌词缓存目录。"),
            "ambiguous": "存在多个无法区分的歌词版本，等待对应本地缓存；可稍后重新获取。",
            "invalid": "酷狗歌词接口数据不完整，暂不使用；可稍后重新获取。",
        }
        return LyricResult(None, messages[reason])
    result = request("/download", dict(ver=1, client="pc", id=candidate["id"], accesskey=candidate["accesskey"], fmt="krc", charset="utf8"))
    encoded = result.get("content", "")
    if not isinstance(encoded, str) or len(encoded) > LIMIT:
        raise ValueError("酷狗歌词内容无效")
    raw = base64.b64decode(encoded, validate=True)
    text = decode_krc(raw)
    expected_hash = getattr(snapshot, "lyric_hash", "")
    if expected_hash:
        match = re.search(r"\[hash:([0-9a-f]{32})\]", text, re.I)
        if match is None or match[1].casefold() != expected_hash:
            return LyricResult(None, "搜索结果与酷狗当前选用的歌词版本不同，等待对应缓存。")
    doc = parse_krc(text)
    return LyricResult(doc, "已同步酷狗逐字歌词", "network")
