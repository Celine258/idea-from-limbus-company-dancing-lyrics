"""LRC parsing and stateless lyric lookup, with no GUI dependency."""
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
import re

STAMP = re.compile(r"\[(\d+):(\d{2})(?:[.:](\d{1,3}))?\]")
OFFSET = re.compile(r"\[offset\s*:\s*([+-]?\d+)\]", re.I)
META = re.compile(r"^\[(?:ar|al|ti|au|by|re|ve|length|offset)\s*:", re.I)


@dataclass(frozen=True)
class LyricLine:
    start_ms: int
    text: str


@dataclass
class LyricDocument:
    lines: list[LyricLine]
    warnings: list[str]
    offset_ms: int = 0


def parse_lrc(text: str) -> LyricDocument:
    grouped: dict[int, list[str]] = {}
    warnings = []
    offset = 0
    for number, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        match = OFFSET.search(raw)
        if match:
            offset = int(match[1])
            continue
        stamps = list(STAMP.finditer(raw))
        if not stamps:
            if not META.match(raw):
                warnings.append(f"第 {number} 行没有有效时间标签，已跳过")
            continue
        lyric = STAMP.sub("", raw).strip()
        for stamp in stamps:
            minute, second = int(stamp[1]), int(stamp[2])
            if second >= 60:
                warnings.append(f"第 {number} 行秒数应小于 60，已跳过该时间标签")
                continue
            fraction = int((stamp[3] or "0").ljust(3, "0"))
            start = (minute * 60 + second) * 1000 + fraction
            texts = grouped.setdefault(start, [])
            if lyric and lyric not in texts:
                texts.append(lyric)
    lines = [LyricLine(t, "\n".join(words)) for t, words in sorted(grouped.items())]
    if not any(line.text for line in lines):
        raise ValueError("没有找到有效歌词。请使用含 [00:12.50] 这类时间标签的 LRC 文件。")
    return LyricDocument(lines, warnings, offset)


def load_lrc(path: str | Path) -> LyricDocument:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return parse_lrc(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise ValueError("歌词编码无法识别，请将文件另存为 UTF-8 后重试。")


@dataclass(frozen=True)
class ActiveLine:
    index: int
    text: str
    start_ms: int
    end_ms: int
    opacity: float


class LyricTimeline:
    """Position is authoritative: pause and seek need no event replay."""
    def __init__(self, document: LyricDocument, delay_ms: int = 0):
        # A positive LRC offset advances timestamps; a positive UI delay postpones them.
        shift = delay_ms - document.offset_ms
        self.lines = [LyricLine(line.start_ms + shift, line.text) for line in document.lines]
        self.starts = [line.start_ms for line in self.lines]

    def visible(self, position_ms: float, duration_ms: int = 0) -> list[ActiveLine]:
        index = bisect_right(self.starts, position_ms) - 1
        active = []
        for i in range(max(0, index - 1), index + 1):
            line = self.lines[i]
            if not line.text:
                continue
            end = line.start_ms + 6000
            if i + 1 < len(self.lines):
                following = self.lines[i + 1]
                end = min(end, following.start_ms + (600 if following.text else 0))
            if duration_ms > 0:
                end = min(end, duration_ms)
            age, life = position_ms - line.start_ms, end - line.start_ms
            if life <= 0 or age < 0 or position_ms >= end:
                continue
            fade_in = min(300, life / 2)
            fade_out = min(600, life / 2)
            opacity = max(0.0, min(1.0, age / fade_in, (end - position_ms) / fade_out))
            active.append(ActiveLine(i, line.text, line.start_ms, end, opacity))
        return active
