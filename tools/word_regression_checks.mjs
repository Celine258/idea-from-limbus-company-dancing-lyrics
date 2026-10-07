// The native decoder seeks to nearby audio frames rather than an exact millisecond.
export function seekFinishes(samples, target) {
    const last = samples.at(-1);
    return !!last && last.seekLoading === 0 && Math.abs(last.position - target) <= .75;
}

export function regressionChecks(cases, nextSongs) {
    return {
        realEnglishWords: cases[0]?.timedLines > 0,
        realChineseWords: cases[1]?.timedLines > 0,
        realPauseFreezes: cases.length >= 2 && cases.slice(0, 2).every(s => s.freeze),
        realSeekFinishes: cases.length >= 2 && cases.slice(0, 2).every(s => s.seekFinishes),
        sentenceOnlyFallback: cases[2]?.timedLines === 0 && cases[2]?.lyricCount > 0,
        pureMusicUnchanged: cases[3]?.displayType === 'pure' && cases[3]?.timedLines === 0,
        allSelectedSongsProgress: cases.length === 4 && cases.every(s => s.progresses),
        threeNextCommandsStaySelected: nextSongs.length === 3 && nextSongs.every(s => s.staysSelected),
        threeNextSongsProgress: nextSongs.length === 3 && nextSongs.every(s => s.progresses),
        switchedLyricsBelongToSong: nextSongs.length === 3 && nextSongs.every(s => s.lyricMatches)
    };
}
