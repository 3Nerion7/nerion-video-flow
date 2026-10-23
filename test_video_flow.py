"""Boundary tests plus the separate recorded end-to-end media test."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import video_flow as flow

class InputBoundaries(unittest.TestCase):
    def test_network_path_rejected_without_probe(self):
        with patch.object(flow,'probe',side_effect=AssertionError('must not reach ffprobe')):
            with self.assertRaises(ValueError):
                flow.local_input(Path.cwd(),'https://example.test/video.mp4')

    def test_parent_escape_rejected(self):
        parent=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='.test-',dir=parent) as name:
            base=Path(name);(base/'job').mkdir();(base/'outside.mp4').write_bytes(b'x')
            self.assertEqual(base.resolve().parent,parent)
            with self.assertRaises(ValueError):flow.local_input(base/'job','../outside.mp4')

    def test_unc_and_absolute_rejected_before_resolution(self):
        for path in ('//server.invalid/share/clip.mp4','/absolute/clip.mp4'):
            with self.subTest(path=path),patch.object(Path,'resolve',side_effect=AssertionError('must reject before filesystem resolution')):
                with self.assertRaises(ValueError):flow.local_input(Path.cwd(),path)

    def test_existing_output_preserved_before_input_processing(self):
        parent=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='.test-',dir=parent) as name:
            base=Path(name)
            self.assertEqual(base.resolve().parent,parent)
            sentinel=base/'keep.txt';sentinel.write_text('preserve',encoding='utf-8')
            with patch.object(flow,'load_job',side_effect=AssertionError('must stop early')):
                with self.assertRaises(FileExistsError):flow.render(Path('absent.json'),Path('absent.bin'),Path('absent.ttf'),base)
            self.assertEqual(sentinel.read_text(encoding='utf-8'),'preserve')

    def test_trim_beyond_real_clip_rejected_before_render(self):
        source=Path(__file__).parent/'demo-job.json'
        job=json.loads(source.read_text(encoding='utf-8'));job['clips'][0]['duration']=100
        # Keep the job root stable so this reaches the actual 12-second source.
        temp=source.parent/'negative-trim-test.json'
        self.assertFalse(temp.exists())
        try:
            with temp.open('x',encoding='utf-8') as f:json.dump(job,f)
            with self.assertRaisesRegex(ValueError,'outside'):flow.load_job(temp)
        finally:
            if temp.exists():temp.unlink()

    def test_subtitle_must_fit_output(self):
        text='1\n00:00:00,000 --> 00:00:20,000\nToo late\n'
        with self.assertRaises(ValueError):flow.parse_srt(text,16)

    def test_empty_asr_has_no_manual_fallback(self):
        with self.assertRaises(ValueError):flow.parse_srt('',16)

    def test_subtitle_markup_rejected(self):
        text='1\n00:00:00,000 --> 00:00:01,000\n{\\pos(1,2)}caption\n'
        with self.assertRaises(ValueError):flow.parse_srt(text,16)

    def test_nonfinite_or_boolean_time_rejected(self):
        for value in (float('nan'),float('inf'),True):
            with self.subTest(value=value),self.assertRaises(ValueError):flow.number(value,'time')

if __name__=='__main__':unittest.main()
