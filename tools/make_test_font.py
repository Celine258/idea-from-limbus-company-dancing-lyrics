"""Rebuild our CC0 synthetic test font. Requires fontTools only for this tool."""
from pathlib import Path
from copy import deepcopy
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTCollection

ROOT = Path(__file__).resolve().parents[1]
characters = sorted(set("A中给今天一点节奏陪你写下一行代码Hello music123 ·"))
order = [".notdef"] + [f"char{ord(char):04x}" for char in characters]
builder = FontBuilder(1000, isTTF=True)
builder.setupGlyphOrder(order)
builder.setupCharacterMap({ord(char): f"char{ord(char):04x}" for char in characters})
glyphs = {}
for name in order:
    pen = TTGlyphPen(None)
    if name != "char0020":
        # Deliberate overhang: real ink extends beyond the advance and ascender.
        pen.moveTo((-140, -260))
        pen.lineTo((1080, -260))
        pen.lineTo((1080, 940))
        pen.lineTo((-140, 940))
        pen.closePath()
    glyphs[name] = pen.glyph()
builder.setupGlyf(glyphs)
builder.setupHorizontalMetrics({name: (600, -140) for name in order})
builder.setupHorizontalHeader(ascent=800, descent=-200)
builder.setupNameTable({"familyName": "Floating Lyrics Test", "styleName": "Regular",
                        "uniqueFontIdentifier": "FloatingLyricsTest-Regular-1", "fullName": "Floating Lyrics Test Regular",
                        "psName": "FloatingLyricsTest-Regular", "version": "Version 1.0"})
builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=940, usWinDescent=260)
builder.setupPost()
builder.setupMaxp()
builder.font["head"].created = builder.font["head"].modified = 2082844800
builder.font.recalcTimestamp = False
target = ROOT / "tests/fixtures/lyrics-test.ttf"
target.parent.mkdir(parents=True, exist_ok=True)
builder.save(target)
print(target)
second = deepcopy(builder.font)
replacements = {1: "Floating Lyrics Second", 3: "FloatingLyricsSecond-Regular-1",
                4: "Floating Lyrics Second Regular", 6: "FloatingLyricsSecond-Regular"}
for record in second["name"].names:
    if record.nameID in replacements:
        record.string = replacements[record.nameID].encode(record.getEncoding())
collection = TTCollection()
collection.fonts = [builder.font, second]
collection.save(target.with_suffix(".ttc"))

opentype = FontBuilder(1000, isTTF=False)
opentype.setupGlyphOrder(order)
opentype.setupCharacterMap({ord(char): f"char{ord(char):04x}" for char in characters})
charstrings = {}
for name in order:
    pen = T2CharStringPen(600, None)
    if name != "char0020":
        pen.moveTo((-140, -260))
        pen.lineTo((1080, -260))
        pen.lineTo((1080, 940))
        pen.lineTo((-140, 940))
        pen.closePath()
    charstrings[name] = pen.getCharString()
opentype.setupCFF("FloatingLyricsOpenType-Regular", {"FullName": "Floating Lyrics OpenType Regular",
                   "FamilyName": "Floating Lyrics OpenType", "Weight": "Regular"}, charstrings, {})
opentype.setupHorizontalMetrics({name: (600, -140) for name in order})
opentype.setupHorizontalHeader(ascent=800, descent=-200)
opentype.setupNameTable({"familyName": "Floating Lyrics OpenType", "styleName": "Regular",
                        "uniqueFontIdentifier": "FloatingLyricsOpenType-Regular-1", "fullName": "Floating Lyrics OpenType Regular",
                        "psName": "FloatingLyricsOpenType-Regular", "version": "Version 1.0"})
opentype.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=940, usWinDescent=260)
opentype.setupPost()
opentype.font["head"].created = opentype.font["head"].modified = 2082844800
opentype.font.recalcTimestamp = False
opentype.save(target.with_suffix(".otf"))
