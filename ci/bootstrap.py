"""Download pinned public Windows demo dependencies into a new local directory."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile

BUILD = 'ffmpeg-2026-04-09-git-d3d0b7a5ee-full_build'
ARCHIVE_URL = f'https://github.com/GyanD/codexffmpeg/releases/download/2026-04-09-git-d3d0b7a5ee/{BUILD}.zip'
ARCHIVE_BYTES = 248796609
ARCHIVE_SHA = 'ce1a20075ea765b2dcc61967f7523753ec8dfe37ad48d24370d5ea95d904b80e'
MODEL_URL = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-tiny.en.bin'
MODEL_BYTES = 77704715
MODEL_SHA = '921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f'
BINARIES = {
    'ffmpeg.exe': (223936512, '9683f30191441e6820df781cc2493aed7e4d78f15cb1e74a2f59b4d6c3d441c9'),
    'ffprobe.exe': (223730176, '4a2b4c72aaea35eb2ea2c37ba5a3ee68f54f9a9a6d1adb8506f9ef9f47d3ae58'),
}

def check(path: Path, size: int, digest: str) -> None:
    if path.stat().st_size != size:
        raise ValueError(f'Unexpected byte count for {path.name}')
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != digest:
        raise ValueError(f'Unexpected SHA256 for {path.name}')

def download(url: str, path: Path, size: int, digest: str) -> None:
    # Default TLS verification stays enabled. No account or credential is used.
    with urllib.request.urlopen(url, timeout=90) as response, path.open('xb') as target:
        received = 0
        while chunk := response.read(1024 * 1024):
            received += len(chunk)
            if received > size:
                raise ValueError(f'Download exceeded the pinned size for {path.name}')
            target.write(chunk)
    check(path, size, digest)

def bootstrap(out: Path) -> None:
    if sys.platform != 'win32':
        raise RuntimeError('This pinned binary setup is for Windows only')
    # Never merge into an old directory or overwrite an existing download.
    out.mkdir(parents=True, exist_ok=False)
    archive = out / 'ffmpeg.zip'
    download(ARCHIVE_URL, archive, ARCHIVE_BYTES, ARCHIVE_SHA)
    binary_dir = out / 'bin'
    binary_dir.mkdir()
    with zipfile.ZipFile(archive) as package:
        for name, (size, digest) in BINARIES.items():
            # Exact members only; no extractall, paths from ZIP, or bundled fonts.
            member = package.getinfo(f'{BUILD}/bin/{name}')
            if member.file_size != size:
                raise ValueError(f'Unexpected uncompressed size for {name}')
            destination = binary_dir / name
            with package.open(member) as source, destination.open('xb') as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            check(destination, size, digest)
    download(MODEL_URL, out / 'ggml-tiny.en.bin', MODEL_BYTES, MODEL_SHA)
    print('Pinned archive, both Windows executables, and tiny.en verified.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('_ci-tools'))
    args = parser.parse_args()
    bootstrap(args.out)
