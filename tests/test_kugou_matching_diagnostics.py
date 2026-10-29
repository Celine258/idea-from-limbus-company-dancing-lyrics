from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from kugou_lyrics import choose_candidate, load_song_lyrics, local_lyrics
from test_kugou import song, krc


class KugouMatchingDiagnosticsTests(unittest.TestCase):
    def test_exact_hash_cache_accepts_renamed_file_only_with_matching_content(self):
        fingerprint = "abcdef0123456789" * 2
        snapshot = replace(song(), lyric_hash=fingerprint)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / (fingerprint.upper() + "-123-00000000.krc")
            path.write_bytes(krc("[hash:" + fingerprint + "]\n[1000,1000]Hello"))
            self.assertEqual(local_lyrics(snapshot, [folder]).source, "cache")
            path.write_bytes(krc("[hash:" + "b" * 32 + "]\n[1000,1000]Wrong"))
            self.assertIsNone(local_lyrics(snapshot, [folder]))
            path.write_bytes(krc("[1000,1000]Missing identity"))
            self.assertIsNone(local_lyrics(snapshot, [folder]))

    def test_hash_cache_does_not_guess_without_a_native_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / ("a" * 32 + ".krc")).write_bytes(krc())
            self.assertIsNone(local_lyrics(song(), [folder]))

    def test_empty_results_and_each_rejection_have_specific_diagnostics(self):
        good = dict(song="Example", singer="Singer", duration=6000, id="12", accesskey="a"*32)
        for candidates, reason in (([], "empty"), (None, "invalid"),
                                   ([{**good, "song":"Other"}], "title"),
                                   ([{**good, "singer":"Other"}], "artist"),
                                   ([{**good, "duration":12000}], "duration"),
                                   ([{**good, "id":"bad"}], "invalid"),
                                   ([good, {**good, "id":"13"}], "ambiguous")):
            details = {}
            self.assertIsNone(choose_candidate(candidates, song(), diagnostics=details))
            self.assertEqual(details["reason"], reason)
        for value in (float("nan"),float("inf"),-1,True):
            self.assertIsNone(choose_candidate([{**good, "duration":value}], song()))

    def test_empty_official_result_is_not_reported_as_metadata_mismatch(self):
        result = load_song_lyrics(song(), directories=[], request=lambda *_: {"candidates":[]})
        self.assertIsNone(result.document)
        self.assertIn("未返回歌词候选", result.message)
        self.assertNotIn("时长不符", result.message)

    def test_native_duration_rejection_explains_lyric_range_without_relaxing_match(self):
        candidate = dict(song="Example", singer="Singer", duration=20000, id="12", accesskey="a"*32)
        result = load_song_lyrics(replace(song(),mode="native"), directories=[],
                                  request=lambda *_: {"candidates":[candidate]})
        self.assertIsNone(result.document)
        self.assertIn("原生歌词范围", result.message)

    def test_cache_written_during_empty_network_request_is_used_immediately(self):
        with tempfile.TemporaryDirectory() as folder:
            def request(*_):
                (Path(folder) / 'Singer - Example.krc').write_bytes(krc())
                return {"candidates": []}
            result = load_song_lyrics(song(), directories=[folder], request=request)
            self.assertIsNotNone(result.document)
            self.assertEqual(result.source, 'cache')
