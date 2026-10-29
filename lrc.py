"""LRC parsing and stateless lyric lookup, with no GUI dependency."""
from bisect import bisect_right
from dataclasses import dataclass, replace
from pathlib import Path
import re

STAMP = re.compile(r"\[(\d+):(\d{2})(?:[.:](\d{1,3}))?\]")
OFFSET = re.compile(r"\[offset\s*:\s*([+-]?\d+)\]", re.I)
META = re.compile(r"^\[(?:ar|al|ti|au|by|re|ve|length|offset)\s*:", re.I)
INSTRUMENTAL_MARKERS = {"纯音乐请欣赏", "纯音乐请您欣赏", "此歌曲为没有填词的纯音乐"}
CREDIT = re.compile(
    r"^(?:作曲|曲|编曲|作词|词|词曲|制作人|制作|演奏|乐器|混音|混音师|母带|母带处理|"
    r"录音|录音师|录音室|出品|出品人|发行|发行公司|版权|监制|统筹|策划|封面|"
    r"Composer|Composed\s+by|Arranger|Arranged\s+by|Producer|Produced\s+by|"
    r"Lyrics|Lyricist|Mixed\s+by|Mastered\s+by|Copyright)\s*[:：]\s*\S", re.I)


@dataclass(frozen=True)
class TimedWord:
    start_ms: int
    end_ms: int
    text_start: int
    text_end: int


@dataclass(frozen=True)
class LyricLine:
    start_ms: int
    text: str
    words: tuple[TimedWord, ...] = ()
    translation: str = ""
    secondary_start: int = -1
    end_ms: int | None = None


@dataclass
class LyricDocument:
    lines: list[LyricLine]
    warnings: list[str]
    offset_ms: int = 0
    instrumental: bool = False


def chinese_translation(text):
    """Only genuine Chinese text is eligible; optional bad data is harmless."""
    return (isinstance(text, str) and len(text) <= 2048 and not any(c in text for c in "\x00\r")
            and any('\u3400' <= c <= '\u9fff' or '\U00020000' <= c <= '\U0003134f' for c in text))


def instrumental_document(document):
    if document is None:
        return False
    if document.instrumental:
        return True
    marker = False
    for line in document.lines:
        # Equal-time LRC records are combined with newlines by the parser.
        for text in line.text.splitlines():
            text = text.strip()
            if not text:
                continue
            if re.sub(r"[\s，,。.!！:：]", "", text) in INSTRUMENTAL_MARKERS:
                marker = True
            elif not CREDIT.match(text):
                return False
    # Credits alone are insufficient evidence; genuine lyrics remain untouched.
    return marker


def display_document(document, prefer_translation=False, mode=None, hide_instrumental=False):
    if hide_instrumental and instrumental_document(document):
        return None
    mode = mode or ("translation" if prefer_translation else "original")
    if document is None or mode == "original":
        return document
    lines = []
    for line in document.lines:
        if not line.text.strip() or not chinese_translation(line.translation) or line.text.strip() == line.translation.strip():
            lines.append(line)
            continue
        translation = line.translation.strip()
        if mode == "translation":
            lines.append(replace(line, text=translation, words=()))
        else:
            primary, secondary = (translation, line.text) if mode == "bilingual_translation" else (line.text, translation)
            start = len(primary) + 1
            words = tuple(replace(word, text_start=word.text_start+start, text_end=word.text_end+start)
                          for word in line.words) if mode == "bilingual_translation" else line.words
            lines.append(replace(line, text=primary + "\n" + secondary, words=words, secondary_start=start))
    return LyricDocument(lines, list(document.warnings), document.offset_ms, document.instrumental)


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
    entry_end_ms: float = 0
    exit_start_ms: float = 0
    words: tuple[TimedWord, ...] = ()
    secondary_start: int = -1


def limit_display_window(item, maximum_ms, exit_duration):
    """Finish the exit before a user deadline, without changing the song clock."""
    if not maximum_ms or item.end_ms <= item.start_ms + maximum_ms:
        return item
    end = item.start_ms + maximum_ms
    return replace(item, end_ms=end,
                   entry_end_ms=min(item.entry_end_ms, item.start_ms + maximum_ms * .35),
                   exit_start_ms=min(item.exit_start_ms, end - min(exit_duration, maximum_ms * .3)))


def extended_display_window(index, line, end, entry_duration, exit_duration):
    """One finite lifetime, including entry/exit; new cues do not end this line."""
    life = max(0, end - line.start_ms)
    return ActiveLine(index, line.text, line.start_ms, end, 1,
                      line.start_ms + min(entry_duration, life * .35),
                      end - min(exit_duration, life * .3), line.words, line.secondary_start)


class LyricTimeline:
    """Position is authoritative: pause and seek need no event replay."""
    def __init__(self, document: LyricDocument, delay_ms: int = 0, animation_style: str = "classic",
                 entry_speed: int = 100, exit_speed: int = 100, scramble_exit: bool = False,
                 max_display_ms: int | None = None, extended_display_ms: int = 0):
        # A positive LRC offset advances timestamps; a positive UI delay postpones them.
        shift = delay_ms - document.offset_ms
        self.lines = [replace(line, start_ms=line.start_ms + shift,
                              end_ms=line.end_ms + shift if line.end_ms is not None else None,
                              words=tuple(replace(word, start_ms=word.start_ms + shift, end_ms=word.end_ms + shift)
                                          for word in line.words)) for line in document.lines]
        self.starts = [line.start_ms for line in self.lines]
        self.animation_style = animation_style
        self.scramble_exit = scramble_exit
        self.entry_duration = 700 * 100 / entry_speed
        self.exit_duration = 600 * 100 / exit_speed
        self.classic_entry = 300 * 100 / entry_speed
        self.max_display_ms = max_display_ms
        self.extended_display_ms = extended_display_ms
        self._nonblank = [i for i, line in enumerate(self.lines) if line.text.strip()]
        self._nonblank_starts = [self.lines[i].start_ms for i in self._nonblank]
        self._extended_ends = {}
        if extended_display_ms:
            next_blank = float("inf")
            blank_limits = {}
            for i in range(len(self.lines) - 1, -1, -1):
                if not self.lines[i].text.strip():
                    next_blank = self.lines[i].start_ms
                else:
                    blank_limits[i] = next_blank
            for rank, i in enumerate(self._nonblank):
                # Retire the oldest before a fifth block arrives, including its exit.
                capacity_limit = (self._nonblank_starts[rank + 4]
                                  if rank + 4 < len(self._nonblank) else float("inf"))
                self._extended_ends[i] = min(self.lines[i].start_ms + extended_display_ms,
                                              blank_limits[i], capacity_limit)

    def _extended_visible(self, position, duration):
        rank = bisect_right(self._nonblank_starts, position)
        active = []
        for i in self._nonblank[max(0, rank - 4):rank]:
            end = self._extended_ends[i]
            if duration > 0:
                end = min(end, duration)
            line = self.lines[i]
            if not line.start_ms <= position < end:
                continue
            item = extended_display_window(i, line, end,
                self.classic_entry if self.animation_style == "classic" else self.entry_duration,
                self.exit_duration)
            if self.animation_style == "classic" and not self.scramble_exit:
                item = replace(item, opacity=max(0., min(1.,
                    (position - item.start_ms) / max(1, item.entry_end_ms - item.start_ms),
                    (end - position) / max(1, end - item.exit_start_ms))))
            active.append(item)
        return active

    def _animated_window(self, index, duration):
        line = self.lines[index]
        following = self.lines[index + 1] if index + 1 < len(self.lines) else None
        boundary = following.start_ms if following else (duration or line.start_ms + 6000)
        if duration > 0:
            boundary = min(boundary, duration)
        if line.end_ms is not None and line.end_ms > line.start_ms:
            vocal_end = min(line.end_ms, boundary)
            end = vocal_end + self.exit_duration
            if following:
                end = min(end, boundary + (self.exit_duration if following.text else 0))
            if duration > 0:
                end = min(end, duration)
            entry = self.classic_entry if self.animation_style == "classic" else self.entry_duration
            entry_end = line.start_ms + min(entry, max(0, vocal_end - line.start_ms) * .35)
            return ActiveLine(index, line.text, line.start_ms, end, 1, entry_end, vocal_end, line.words, line.secondary_start)
        interval = max(0, boundary - line.start_ms)
        entry_end = line.start_ms + min(self.classic_entry if self.animation_style == "classic" else self.entry_duration, interval * .35)
        if following and following.text and boundary < (duration or float("inf")):
            next_boundary = (self.lines[index + 2].start_ms if index + 2 < len(self.lines)
                             else duration or following.start_ms + 6000)
            if duration > 0:
                next_boundary = min(next_boundary, duration)
            tail = min(self.exit_duration, max(0, next_boundary - boundary) * .45)
            exit_start, end = boundary, boundary + tail
        else:
            end = boundary
            exit_start = end - min(self.exit_duration, interval * .3)
        return ActiveLine(index, line.text, line.start_ms, end, 1, entry_end, exit_start, line.words, line.secondary_start)

    def visible(self, position_ms: float, duration_ms: int = 0) -> list[ActiveLine]:
        if self.extended_display_ms:
            return self._extended_visible(position_ms, duration_ms)
        index = bisect_right(self.starts, position_ms) - 1
        active = []
        for i in range(max(0, index - 1), index + 1):
            line = self.lines[i]
            if not line.text:
                continue
            if line.end_ms is not None and line.end_ms > line.start_ms:
                item = limit_display_window(self._animated_window(i, duration_ms), self.max_display_ms, self.exit_duration)
                if item.start_ms <= position_ms < item.end_ms:
                    if self.animation_style == "classic" and not self.scramble_exit:
                        opacity = min(1., (position_ms - item.start_ms) / max(1, item.entry_end_ms - item.start_ms),
                                      (item.end_ms - position_ms) / max(1, item.end_ms - item.exit_start_ms))
                        item = replace(item, opacity=max(0., opacity))
                    active.append(item)
                continue
            if self.animation_style != "classic" or self.scramble_exit:
                item = limit_display_window(self._animated_window(i, duration_ms), self.max_display_ms, self.exit_duration)
                if item.start_ms <= position_ms < item.end_ms and item.end_ms > item.start_ms:
                    active.append(item)
                continue
            # None preserves the legacy programmatic default. The UI passes an
            # explicit cap (6 s by default); zero disables that extra deadline.
            end = line.start_ms + 6000 if self.max_display_ms is None else float("inf")
            if self.max_display_ms:
                end = line.start_ms + self.max_display_ms
            if i + 1 < len(self.lines):
                following = self.lines[i + 1]
                end = min(end, following.start_ms + (self.exit_duration if following.text else 0))
            if duration_ms > 0:
                end = min(end, duration_ms)
            elif i + 1 == len(self.lines):
                end = min(end, line.start_ms + 6000)
            age, life = position_ms - line.start_ms, end - line.start_ms
            if life <= 0 or age < 0 or position_ms >= end:
                continue
            fade_in = min(self.classic_entry, life / 2)
            fade_out = min(self.exit_duration, life / 2)
            opacity = max(0.0, min(1.0, age / fade_in, (end - position_ms) / fade_out))
            active.append(ActiveLine(i, line.text, line.start_ms, end, opacity, words=line.words, secondary_start=line.secondary_start))
        return active


def word_timing_status(document, waiting=False):
    if waiting:
        return "等待歌词"
    lines = [line for line in document.lines if line.text.strip()] if document else []
    timed = sum(bool(line.words) for line in lines)
    if not timed:
        return "本曲无逐字时间"
    complete = all(all(char.isspace() or any(word.text_start <= index < word.text_end for word in line.words)
                       for index, char in enumerate(line.text)) for line in lines)
    return "逐字时间可用" if complete else "部分歌词可用"
