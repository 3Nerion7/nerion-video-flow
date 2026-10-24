"""Negative checks for download integrity and preservation of previous output."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ci import bootstrap, verify_demo

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

if __name__ == '__main__':
    unittest.main()
