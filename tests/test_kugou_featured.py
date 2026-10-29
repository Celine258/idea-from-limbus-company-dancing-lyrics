"""Guests explicitly credited in the title can be missing from SMTC artist."""
import asyncio
import json
from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch
from kugou_identity import artists_match, track_artists_match
from kugou_native import NativeLyricsReader
from kugou_reader import sample_channels
from kugou_lyrics import local_lyrics, choose_candidate
from test_kugou import krc, song

TITLE = "Song (feat. Guest)"


class FeaturedArtistTests(unittest.TestCase):
    def test_real_source_evidence_retains_initial_failure_and_does_not_claim_same_song_live(self):
        root=Path(__file__).resolve().parents[1]
        record=json.loads((root/'docs/research/kugou-featured-20261030.json').read_text(encoding='utf-8'))
        self.assertFalse(record['initial_packaged_probe']['passed'])
        self.assertTrue(record['source_regression']['passed'])
        self.assertTrue(all(record['source_regression']['checks'].values()))
        self.assertTrue(record['captured_metadata_replay']['native_identity_accepted'])
        self.assertTrue(record['captured_metadata_replay']['real_cache_received'])
        self.assertFalse(record['captured_metadata_replay']['dynamic_playback_verified'])
        self.assertFalse(record['same_previously_failed_song_verified'] or record['synthetic_live_data'])
        self.assertEqual(record['music_playback_commands'],0)

    def test_explicit_guest_matches_symmetrically_without_weakening_plain_artists(self):
        self.assertFalse(artists_match("Main", "Main、Guest"))
        for main, full, title in (("Main", "Main、Guest", TITLE),
                                  ("Main", "Main & Guest", "Song (featuring Guest)"),
                                  ("Main", "Main;Guest", "Song（ft. Guest）"),
                                  ("Main (メイン)", "Main、Guest", TITLE),
                                  ("Main", "Main、Guest、Other", "Song (feat. Guest & Other)"),
                                  ("AC/DC", "AC/DC、Guest", TITLE)):
            self.assertTrue(track_artists_match(main, full, title, title), (main,full))
            self.assertTrue(track_artists_match(full, main, title, title))

    def test_missing_evidence_wrong_guest_main_or_version_are_rejected(self):
        for first, second, a, b in (("Main", "Main、Guest", "Song", "Song"),
                                   ("Main", "Main、Other", TITLE, TITLE),
                                   ("Other", "Main、Guest", TITLE, TITLE),
                                   ("Main", "Main、Guest、Other", TITLE, TITLE),
                                   ("Main", "Main、Guest", TITLE, "Song (Live) (feat. Guest)"),
                                   ("Main", "Guest", TITLE, TITLE),
                                   ("", "Main、Guest", TITLE, TITLE),
                                   ("Main", "Main、Guest、Guest", TITLE, TITLE),
                                   ("Main", "Main、Guest", "Song (with Guest)", "Song (with Guest)")):
            self.assertFalse(track_artists_match(first, second, a, b), (first,second,a,b))

    def test_matching_native_guest_view_keeps_advancing_without_ocr(self):
        tick = [10.]
        reader = NativeLyricsReader(lambda: tick[0])
        reader.process = NS(pid=42)
        reader.objects, reader.retry_at = [(100,None)], 100
        media = dict(title=TITLE,artist="Main",album="",duration_ms=0,playing=True)
        row = dict(title=TITLE,artist="Main、Guest",album="Album",duration_ms=60000,
                   position_ms=1000,document=200,lyric_hash="a"*32)
        with patch("kugou_native.read_object",side_effect=lambda *_:dict(row)), patch(
                "kugou_reader.smtc_snapshot",new=AsyncMock(return_value=media)), patch("kugou_reader.WindowReader") as ocr:
            first = asyncio.run(sample_channels(None,reader,NS(pid=lambda:42)))[0]
            tick[0] += .2; row['position_ms'] += 200
            second = asyncio.run(sample_channels(None,reader,NS(pid=lambda:42)))[0]
            self.assertEqual((first['mode'],second['mode']),('native','native'))
            self.assertGreater(second['position_ms'], first['position_ms'])
            self.assertTrue(second['playing'])
            self.assertEqual(second['lyric_hash'],'a'*32)
            self.assertEqual(second['artist'],'Main')
            ocr.assert_not_called()

    def test_late_media_accepts_credited_guest_and_rejects_different_guest(self):
        packet=dict(title=TITLE,artist="Main、Guest",album="",duration_ms=60000,position_ms=1000,playing=True,mode="native")
        for artist,accepted in (("Main",True),("Other",False),("Main、Other",False)):
            native=NS(read=Mock(return_value=dict(packet)))
            media=dict(title=TITLE,artist=artist,playing=True,rate=1)
            with patch("kugou_reader.smtc_snapshot",new=AsyncMock(side_effect=[None,media])):
                self.assertEqual(asyncio.run(sample_channels(None,native,NS(pid=lambda:42)))[0] is not None, accepted)

    def test_full_credit_cache_and_network_match_but_hash_stays_mandatory(self):
        snapshot=replace(song(title=TITLE),artist="Main",lyric_hash="a"*32)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/f'Main、Guest - {TITLE}-{"a"*32}-12-00000000.krc'
            path.write_bytes(krc('[hash:'+"a"*32+']\n[1000,2000]Test'))
            self.assertEqual(local_lyrics(snapshot,[directory]).source,'cache')
            path.write_bytes(krc('[hash:'+"b"*32+']\n[1000,2000]Wrong'))
            self.assertIsNone(local_lyrics(snapshot,[directory]))
            snapshot=replace(snapshot,lyric_hash="")
            self.assertEqual(local_lyrics(snapshot,[directory]).source,'cache')
            self.assertIsNone(local_lyrics(replace(snapshot,title='Song (Live) (feat. Guest)'),[directory]))
        row=dict(song=TITLE,singer="Main、Guest",duration=snapshot.duration_ms,id="12",accesskey="a"*32)
        self.assertIs(choose_candidate([row],snapshot),row)
        self.assertIsNone(choose_candidate([{**row,'singer':'Main、Other'}],snapshot))
        self.assertIsNone(choose_candidate([{**row,'duration':snapshot.duration_ms+4000}],snapshot))
