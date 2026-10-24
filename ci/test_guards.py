"""Negative checks for download integrity and preservation of previous output."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from ci import bootstrap, verify_demo
import video_flow

class IntegrityGuards(unittest.TestCase):
    def test_corrupt_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch('urllib.request.urlopen', return_value=io.BytesIO(b'wrong')):
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                bootstrap.download(bootstrap.MODEL_URL, Path(temp) / 'model.bin', 5, '0' * 64)

    def test_oversized_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch('urllib.request.urlopen', return_value=io.BytesIO(b'too long')):
            with self.assertRaisesRegex(ValueError, 'exceeded'):
                bootstrap.download(bootstrap.MODEL_URL, Path(temp) / 'model.bin', 3, '0' * 64)

    def test_existing_tools_are_preserved_without_download(self):
        with tempfile.TemporaryDirectory() as temp, patch('urllib.request.urlopen') as download:
            out = Path(temp)
            sentinel = out / 'sentinel.txt'
            sentinel.write_text('preserve me', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                bootstrap.bootstrap(out)
            download.assert_not_called()
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'preserve me')

    def test_existing_results_cannot_be_passed_off_as_a_fresh_run(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            sentinel = out / 'sentinel.txt'
            sentinel.write_text('preserve me', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                verify_demo.verify(Path('not-used-model'), Path('not-used-font'), out)
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'preserve me')

    def test_native_failure_code_is_retained_without_a_success_receipt(self):
        # Simulated process failure control, not a real media/CPU test.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for name in ['job.json', 'model.bin', 'font.ttf', 'voice.wav', 'music.wav']:
                (base / name).write_bytes(b'test')
            job = ({}, [], base / 'voice.wav', base / 'music.wav', 1.0)
            failure = SimpleNamespace(returncode=3221225501, stdout='', stderr='simulated native failure')
            out = base / 'new-result'
            with patch('video_flow.load_job', return_value=job), patch('video_flow.sha', return_value=video_flow.MODEL_SHA256), patch('video_flow.subprocess.run', return_value=failure):
                with self.assertRaisesRegex(RuntimeError, r'join failed.*3221225501.*c000001d'):
                    video_flow.render(base / 'job.json', base / 'model.bin', base / 'font.ttf', out)
            log = (out / 'join.log').read_text(encoding='utf-8')
            self.assertIn('Native process exit code: 3221225501 (0xc000001d)', log)
            self.assertIn('simulated native failure', log)
            self.assertFalse((out / 'run.json').exists())

if __name__ == '__main__':
    unittest.main()
