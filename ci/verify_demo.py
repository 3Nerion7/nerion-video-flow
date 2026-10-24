"""Run fresh raw and reviewed synthetic demos; never reuse example-output videos."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from video_flow import MODEL_SHA256, probe, render, sha  # noqa: E402

def capabilities() -> dict:
    def command(*args):
        return subprocess.run(args, check=True, capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=30).stdout
    filters = {line.split()[1] for line in command('ffmpeg', '-hide_banner', '-filters').splitlines()
               if len(line.split()) >= 3 and line.strip() and line.split()[0] != '--'}
    missing = {'whisper', 'subtitles', 'drawtext'} - filters
    encoders = {line.split()[1] for line in command('ffmpeg', '-hide_banner', '-encoders').splitlines()
                if len(line.split()) >= 3}
    if missing or 'libx264' not in encoders:
        raise RuntimeError(f'Required FFmpeg capabilities unavailable: {sorted(missing)}, libx264={"libx264" in encoders}')
    return {'ffmpeg': command('ffmpeg', '-version').splitlines()[0],
            'ffprobe': command('ffprobe', '-version').splitlines()[0]}

def verify_receipt(receipt: dict, out: Path, reviewed: bool) -> None:
    if receipt['status'] != 'RENDERED_AND_FULLY_DECODED' or receipt['full_decode_exit_code'] != 0 or receipt['full_decode_error_bytes'] != 0:
        raise ValueError('Full output decode did not pass')
    if receipt['raw_asr_modified'] is not False or not receipt['asr_cues']:
        raise ValueError('Raw ASR must be retained with nonempty cues')
    if receipt['model_sha256'] != MODEL_SHA256 or receipt['source_sha256'] != sha(ROOT / 'video_flow.py'):
        raise ValueError('Model or renderer provenance differs')
    events = receipt['events']
    if [e['stage'] for e in events] != ['normalize-0', 'normalize-1', 'join', 'voice', 'asr', 'export'] or any(e['exit_code'] != 0 for e in events):
        raise ValueError('Fresh complete render stages are required')
    for name, key in [('demo.mp4', 'video_sha256'), ('raw-asr.srt', 'raw_srt_sha256'), ('burned-captions.srt', 'burned_caption_sha256')]:
        if sha(out / name) != receipt[key]:
            raise ValueError(f'Output differs from its receipt: {name}')
    expected_caption = ROOT / 'demo-inputs/reviewed-captions.srt' if reviewed else out / 'raw-asr.srt'
    if sha(out / 'burned-captions.srt') != sha(expected_caption):
        raise ValueError('Wrong caption source was burned')
    if receipt['burned_caption_source'] != ('reviewed local file' if reviewed else 'raw ASR'):
        raise ValueError('Caption source label is misleading')
    if [(c['start'], c['duration']) for c in receipt['input_clips']] != [(2.0, 8.0), (1.0, 8.0)]:
        raise ValueError('Expected synthetic trim inputs were not used')
    expected_clips = ['source-a-v2.mp4', 'source-b-v2.mp4']
    if [(c['file'], c['sha256']) for c in receipt['input_clips']] != [(name, sha(ROOT / 'demo-inputs' / name)) for name in expected_clips]:
        raise ValueError('Rendered clips differ from the synthetic fixtures')
    if receipt['voice_sha256'] != sha(ROOT / 'demo-inputs/synthetic-voice.wav') or receipt['music_sha256'] != sha(ROOT / 'demo-inputs/generated-music.wav'):
        raise ValueError('Rendered audio differs from the synthetic fixtures')
    expected_job = ROOT / ('demo-job-reviewed.json' if reviewed else 'demo-job.json')
    if receipt['job_sha256'] != sha(expected_job):
        raise ValueError('A different job was rendered')
    streams = probe(out / 'demo.mp4')['streams']
    videos = [s for s in streams if s['codec_type'] == 'video']
    audios = [s for s in streams if s['codec_type'] == 'audio']
    if len(videos) != 1 or len(audios) != 1:
        raise ValueError('Exactly one video and one audio stream are required')
    video, audio = videos[0], audios[0]
    if (video['width'], video['height'], video['avg_frame_rate']) != (1280, 720, '30/1') or abs(receipt['duration_seconds'] - 16) > 0.1:
        raise ValueError('Output is not the expected 16-second 720p30 demo')
    if audio['codec_name'] != 'aac' or audio['sample_rate'] != '48000':
        raise ValueError('Expected AAC 48 kHz audio is missing')

def verify(model: Path, font: Path, out: Path) -> dict:
    if sys.platform != 'win32':
        raise RuntimeError('This integration recipe currently covers Windows only')
    if out.exists():
        raise FileExistsError('Use a fresh results directory; no cached render is accepted')
    locked = json.loads((ROOT / 'ci/fixture-lock.json').read_text(encoding='utf-8'))
    for relative, expected in locked.items():
        if sha(ROOT / relative) != expected:
            raise ValueError(f'Synthetic fixture differs from the pinned sample: {relative}')
    versions = capabilities()
    out.mkdir(parents=True, exist_ok=False)
    results = {}
    for name, reviewed in [('raw', False), ('reviewed', True)]:
        job = ROOT / ('demo-job-reviewed.json' if reviewed else 'demo-job.json')
        target = out / name
        receipt = render(job, model, font, target)
        verify_receipt(receipt, target, reviewed)
        results[name] = receipt
    summary = {'status': 'TWO_FRESH_RENDERS_AND_FULL_DECODES_PASSED',
               'platform': platform.system(), 'python': platform.python_version(),
               **versions, 'fixture_sha256': locked,
               'verification_source_sha256': sha(Path(__file__)),
               'raw': results['raw'], 'reviewed': results['reviewed'],
               'limits': 'One synthetic English case on Windows CPU; not a client benchmark or Linux validation. Captions still need editorial review.'}
    text = json.dumps(summary, ensure_ascii=True, indent=2) + '\n'
    (out / 'verification.json').write_text(text, encoding='utf-8', newline='\n')
    print(text)
    step_summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if step_summary:
        with Path(step_summary).open('a', encoding='utf-8', newline='\n') as stream:
            stream.write('## VideoFlow integration result\n\nTwo fresh Windows CPU renders passed, including real local Whisper ASR and complete video/audio decode.\n\n```json\n' + text + '```\n')
    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--font', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    verify(args.model, args.font, args.out)
