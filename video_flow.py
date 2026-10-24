"""Local, explicit-job video automation. No network, account or paid API calls."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

MODEL_SHA256 = '921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f'

def sha(path: Path) -> str:
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def local_input(base: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or ':' in value or '\\' in value:
        raise ValueError('Inputs must be relative local paths using forward slashes')
    relative=Path(value)
    if relative.is_absolute() or relative.anchor or '..' in relative.parts:
        raise ValueError('Input must be a relative path without parent traversal')
    p = base
    for part in relative.parts:
        p /= part
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):
            raise ValueError('Symlink or junction inputs are unsupported')
    resolved = p.resolve(strict=True)
    if not resolved.is_relative_to(base):
        raise ValueError('Input escapes the job directory')
    if not resolved.is_file():
        raise ValueError('Input is not a regular file')
    return resolved

def number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)

def probe(path: Path) -> dict:
    r = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-show_streams', '-show_format', '-of', 'json', str(path)],
        capture_output=True, check=True, timeout=30)
    return json.loads(r.stdout)

def load_job(path: Path) -> tuple[dict, list, Path, Path, float]:
    job = json.loads(path.read_text(encoding='utf-8'))
    clips = job.get('clips')
    if not isinstance(clips, list) or not 1 <= len(clips) <= 20:
        raise ValueError('Job requires 1 to 20 clips')
    base = path.resolve().parent
    checked = []
    for clip in clips:
        p = local_input(base, clip['path'])
        if p.suffix.lower() not in {'.mp4', '.mov', '.mkv', '.webm'}:
            raise ValueError('Unsupported video container')
        start, duration = number(clip['start'], 'start'), number(clip['duration'], 'duration')
        data = probe(p)
        if not any(s['codec_type'] == 'video' for s in data['streams']):
            raise ValueError('Clip has no video stream')
        available = float(data['format']['duration'])
        if start < 0 or duration <= 0 or start + duration > available + 0.02:
            raise ValueError('Trim lies outside its source clip')
        checked.append((p, start, duration))
    total = sum(x[2] for x in checked)
    if total > 600:
        raise ValueError('This bounded portfolio tool supports at most 10 minutes')
    voice, music = local_input(base, job['narration']), local_input(base, job['music'])
    for p in (voice, music):
        if p.suffix.lower() not in {'.wav', '.mp3', '.m4a', '.flac'}:
            raise ValueError('Unsupported audio container')
        data = probe(p)
        if not any(s['codec_type'] == 'audio' for s in data['streams']):
            raise ValueError('Input has no audio stream')
        if float(data['format']['duration']) <= 0:
            raise ValueError('Empty audio input')
    if float(probe(voice)['format']['duration']) > total + 0.02:
        raise ValueError('Narration would be truncated by the video')
    return job, checked, voice, music, total

def parse_srt(text: str, duration: float) -> list[dict]:
    def seconds(stamp):
        h, m, s, ms = map(int, re.split('[:,]', stamp))
        if m > 59 or s > 59:
            raise ValueError('Invalid subtitle timestamp')
        return h * 3600 + m * 60 + s + ms / 1000
    cues = []
    previous = 0.0
    for block in re.split(r'\n\s*\n', text.replace('\r\n', '\n').strip()):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError('Unexpected ASR subtitle format')
        match = re.fullmatch(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', lines[1])
        if not match:
            raise ValueError('Unexpected ASR time range')
        start, end = map(seconds, match.groups())
        caption = ' '.join(lines[2:]).strip()
        if not caption or any(x in caption for x in '{}<>\\'):
            raise ValueError('Unsupported subtitle markup')
        if not 0 <= start < end <= duration + 0.25 or start < previous:
            raise ValueError('ASR time range outside the output or out of order')
        cues.append({'start': start, 'end': end, 'text': caption})
        previous = end
    if not cues:
        raise ValueError('ASR produced no subtitles; no manual fallback is used')
    return cues

def render(job_path: Path, model: Path, font: Path, out: Path) -> dict:
    for p in (job_path,model,font,out):
        if str(p).replace('\\','/').startswith('//'):
            raise ValueError('UNC or device paths are unsupported')
    out = out.resolve()
    if out.exists():
        raise FileExistsError('Output directory already exists; nothing was overwritten')
    job, clips, voice, music, total = load_job(job_path)
    if sha(model) != MODEL_SHA256:
        raise ValueError('Model hash differs from the documented tiny.en checkpoint')
    if not font.is_file():
        raise ValueError('Provide an installed TrueType font')
    out.mkdir(parents=True, exist_ok=False)
    events = []
    input_clips=[]
    began = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='.work-', dir=out) as temp:
        work = Path(temp).resolve()
        assert work.parent == out and work.name.startswith('.work-')
        shutil.copyfile(model, work/'model.bin')
        shutil.copyfile(font, work/'font.ttf')
        (work/'fonts.conf').write_text('<fontconfig><dir>.</dir><cachedir>font-cache</cachedir></fontconfig>', encoding='utf-8')
        env = os.environ.copy()
        env['FONTCONFIG_FILE'] = str(work/'fonts.conf')
        def ff(stage, args, expected_output):
            expected = work/expected_output
            if expected.exists():
                raise FileExistsError(f'{stage} would overwrite an existing stage output')
            command = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-nostdin', '-n', *args]
            t = time.perf_counter()
            r = subprocess.run(command, cwd=work, env=env, capture_output=True,
                text=True, encoding='utf-8', errors='replace', timeout=240)
            event = {'stage': stage, 'seconds': round(time.perf_counter()-t, 3), 'exit_code': r.returncode}
            events.append(event)
            native_code = f'{r.returncode} (0x{r.returncode & 0xffffffff:08x})'
            (out/f'{stage}.log').write_text(f'Native process exit code: {native_code}\n'+r.stdout+r.stderr, encoding='utf-8')
            if r.returncode:
                raise RuntimeError(f'{stage} failed with native exit code {native_code}; inspect its local log')
            if not expected.is_file() or not expected.stat().st_size:
                raise RuntimeError(f'{stage} reported success without a new nonempty output')
        for i, (p, start, duration) in enumerate(clips):
            name=f'input-{i}{p.suffix.lower()}'
            shutil.copyfile(p, work/name)
            input_clips.append({'file':p.name,'sha256':sha(work/name),'start':start,'duration':duration})
            ff(f'normalize-{i}', ['-protocol_whitelist','file,pipe','-ss',str(start),'-i',name,
                '-t',str(duration),'-an','-vf','scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p',
                '-c:v','libx264','-threads','2','-preset','fast','-crf','20','-map_metadata','-1',f'clip-{i}.mp4'],f'clip-{i}.mp4')
        args=[]
        for i in range(len(clips)):
            args += ['-protocol_whitelist','file,pipe','-i',f'clip-{i}.mp4']
        concat=''.join(f'[{i}:v]' for i in range(len(clips)))+f'concat=n={len(clips)}:v=1:a=0[v]'
        ff('join', [*args,'-filter_complex',concat,'-map','[v]','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','20','-map_metadata','-1','joined.mp4'],'joined.mp4')
        shutil.copyfile(voice, work/f'voice-input{voice.suffix.lower()}')
        ff('voice', ['-protocol_whitelist','file,pipe','-i',f'voice-input{voice.suffix.lower()}',
            '-ar','16000','-ac','1','-c:a','pcm_s16le','-map_metadata','-1','voice.wav'],'voice.wav')
        normalized_voice=probe(work/'voice.wav')
        if normalized_voice['streams'][0]['sample_rate']!='16000' or normalized_voice['streams'][0]['channels']!=1:
            raise RuntimeError('Narration normalization did not produce 16 kHz mono')
        normalized_voice_sha256=sha(work/'voice.wav')
        assert not (work/'raw.srt').exists()
        ff('asr', ['-protocol_whitelist','file,pipe','-i','voice.wav','-af',
            'whisper=model=model.bin:language=en:use_gpu=false:queue=20:max_len=42:destination=raw.srt:format=srt',
            '-f','null','-'],'raw.srt')
        srt=(work/'raw.srt').read_text(encoding='utf-8')
        cues=parse_srt(srt,total)
        caption_file='raw.srt'
        reviewed=job.get('reviewed_captions')
        if reviewed is not None:
            reviewed_path=local_input(job_path.resolve().parent,reviewed)
            reviewed_text=reviewed_path.read_text(encoding='utf-8')
            parse_srt(reviewed_text,total)
            (work/'reviewed.srt').write_text(reviewed_text,encoding='utf-8',newline='\n')
            caption_file='reviewed.srt'
        shutil.copyfile(music, work/f'music{music.suffix.lower()}')
        music_sha256=sha(work/f'music{music.suffix.lower()}')
        audio=f'[1:a]apad,atrim=duration={total}[voice];[2:a]atrim=duration={total},volume=0.12[music];[voice][music]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]'
        label='CAPTIONS - AGENT REVIEWED' if reviewed else 'RAW AUTOMATIC CAPTIONS - REVIEW REQUIRED'
        video=f"subtitles=filename={caption_file}:fontsdir=.:force_style='FontName=Arial,FontSize=26,Outline=2,MarginV=70',drawtext=fontfile=font.ttf:text='NERION DEV - SYNTHETIC PORTFOLIO DEMO':fontsize=20:fontcolor=white:x=30:y=25,drawtext=fontfile=font.ttf:text='{label}':fontsize=18:fontcolor=white:x=30:y=55"
        ff('export', ['-protocol_whitelist','file,pipe','-i','joined.mp4','-protocol_whitelist','file,pipe','-i','voice.wav',
            '-stream_loop','-1','-protocol_whitelist','file,pipe','-i',f'music{music.suffix.lower()}',
            '-filter_complex',audio,'-map','0:v','-map','[a]','-vf',video,'-t',str(total),
            '-c:v','libx264','-threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p',
            '-c:a','aac','-ar','48000','-b:a','128k','-movflags','+faststart','-map_metadata','-1','-map_chapters','-1','final.mp4'],'final.mp4')
        shutil.copyfile(work/'final.mp4',out/'demo.mp4')
        shutil.copyfile(work/'raw.srt',out/'raw-asr.srt')
        shutil.copyfile(work/caption_file,out/'burned-captions.srt')
    result=probe(out/'demo.mp4')
    stream=next(x for x in result['streams'] if x['codec_type']=='video')
    if (stream['width'],stream['height']) != (1280,720) or abs(float(result['format']['duration'])-total)>0.1:
        raise RuntimeError('Output geometry or duration verification failed')
    decoded=subprocess.run(['ffmpeg','-v','error','-xerror','-err_detect','explode','-nostdin','-protocol_whitelist','file,pipe','-i',str(out/'demo.mp4'),'-f','null','-'],capture_output=True,timeout=120)
    (out/'decode.log').write_bytes(decoded.stdout+decoded.stderr)
    if decoded.returncode or decoded.stderr.strip():
        raise RuntimeError('Full decode reported an error')
    receipt={'utc':datetime.now(timezone.utc).isoformat(),'status':'RENDERED_AND_FULLY_DECODED',
        'elapsed_seconds':round(time.perf_counter()-began,3),'width':1280,'height':720,'fps':stream['avg_frame_rate'],
        'duration_seconds':float(result['format']['duration']),'clip_count':len(clips),
        'source_sha256':sha(Path(__file__)),'python_version':sys.version.split()[0],
        'input_clips':input_clips,'music_sha256':music_sha256,
        'normalized_voice_sha256':normalized_voice_sha256,
        'model_sha256':MODEL_SHA256,'job_sha256':sha(job_path),'voice_sha256':sha(voice),
        'video_sha256':sha(out/'demo.mp4'),'raw_srt_sha256':sha(out/'raw-asr.srt'),
        'asr_cues':cues,'events':events,'raw_asr_modified':False,
        'burned_caption_source':'reviewed local file' if reviewed else 'raw ASR',
        'burned_caption_sha256':sha(out/'burned-captions.srt'),
        'caption_review_note':job.get('caption_review_note','No editorial correction'),
        'normalized_voice_sample_rate':16000,
        'full_decode_exit_code':decoded.returncode,'full_decode_error_bytes':len(decoded.stderr),
        'voice':'Synthetic Flite KAL in the supplied demo; not the account owner',
        'limits':'One synthetic English Windows case, tiny.en CPU. No real-client, multilingual, CapCut or monthly-volume benchmark. Review captions before delivery.'}
    (out/'run.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--job',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--font',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    try:
        print(json.dumps(render(a.job,a.model,a.font,a.out),ensure_ascii=True))
    except (OSError,ValueError,KeyError,subprocess.SubprocessError,RuntimeError) as e:
        p.exit(1,f'{type(e).__name__}: {e}\n')

if __name__=='__main__':main()
