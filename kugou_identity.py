"""Conservative title equivalence for KuGou's translated display aliases."""
import re
import unicodedata


def normalized(value):
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", str(value)).casefold())


def title_keys(value):
    text = unicodedata.normalize("NFKC", str(value)).strip()
    keys = {normalized(text)}
    match = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", text)
    if match:
        base, alias = match.groups()
        # The client adds Chinese translations to foreign titles. Version and
        # performance qualifiers remain part of the identity, including live,
        # remixes and Chinese version labels; do not use general fuzzy matching.
        foreign = re.search(r"[A-Za-z\u3040-\u30ff\uac00-\ud7af]", base)
        chinese = re.search(r"[\u3400-\u9fff]", alias)
        qualifier = re.search(r"版|现场|伴奏|翻唱|混音|原唱|录音|合唱|铃声|剪辑|串烧|live|remix|cover|instrumental|acoustic", alias, re.I)
        if foreign and chinese and not qualifier and not re.search(r"[\u3040-\u30ff\uac00-\ud7af]", alias):
            keys.add(normalized(base))
    return keys - {""}


def titles_match(first, second):
    return bool(title_keys(first) & title_keys(second))


def artist_keys(value):
    """Allow an explicit cross-script name alias, never drop collaborators."""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    keys = {normalized(text)}
    match = re.fullmatch(r"([^()]+?)\s*\(([^()]+)\)", text)
    if match:
        base, alias = match.groups()
        qualifier = re.search(r"\b(?:feat|ft|featuring|with|vs|live|remix|cover|instrumental|acoustic|piano)\b|版|现场|伴奏|翻唱|混音|合唱|合作|原唱|录音", alias, re.I)
        def scripts(name):
            return {label for label, pattern in (
                ("latin", r"[A-Za-z]"), ("han", r"[\u3400-\u9fff]"),
                ("kana", r"[\u3040-\u30ff]"), ("hangul", r"[\uac00-\ud7af]")) if re.search(pattern, name)}
        original, translated = scripts(base), scripts(alias)
        if (not qualifier and original and translated and original.isdisjoint(translated)
                and not re.search(r"[&+/、,;\d]", alias)):
            keys.add(normalized(base))
    return keys - {""}


def artists_match(first, second):
    return bool(artist_keys(first) & artist_keys(second))


def _credit_parts(value):
    # KuGou uses an ideographic comma. Only split other separators when spaced,
    # so band names such as AC/DC and Earth, Wind & Fire are not truncated.
    text = unicodedata.normalize("NFKC", str(value)).strip()
    parts = re.split(r"\s*[、;]\s*|\s+[&+/]\s+", text)
    if not 1 <= len(parts) <= 8 or any(not part or len(part) > 256 for part in parts):
        return []
    if any(artists_match(part, earlier) for i, part in enumerate(parts) for earlier in parts[:i]):
        return []
    return parts


def _featured_parts(title):
    text = unicodedata.normalize("NFKC", str(title)).strip()
    match = re.fullmatch(r".+?\s*\(\s*(?:feat\.?|ft\.?|featuring)\s+([^()]+)\)", text, re.I)
    return _credit_parts(match[1]) if match else []


def track_artists_match(first, second, first_title, second_title):
    """Permit an omitted guest only when both full titles explicitly credit it.

    SMTC can expose just the main artist while the native/cache record exposes
    all artists. Do not relax ordinary artist matching or remove version labels.
    """
    if artists_match(first, second):
        return True
    if not titles_match(first_title, second_title):
        return False
    guests, other_guests = _featured_parts(first_title), _featured_parts(second_title)
    if not guests or len(guests) != len(other_guests):
        return False
    if not all(any(artists_match(guest, other) for other in other_guests) for guest in guests):
        return False
    remaining, removals = [], []
    for credit in (first, second):
        parts = _credit_parts(credit)
        removed = 0
        for guest in guests:
            matches = [i for i, part in enumerate(parts) if artists_match(part, guest)]
            if len(matches) == 1:
                parts.pop(matches[0])
                removed += 1
        if not parts:
            return False
        remaining.append(parts)
        removals.append(removed)
    # One record must really contain every guest, and the remaining main
    # artists must match exactly. An uncredited collaborator never disappears.
    return (max(removals) == len(guests) and len(remaining[0]) == len(remaining[1])
            and all(any(artists_match(part, other) for other in remaining[1]) for part in remaining[0]))
