"""Generate original shapes, sine-wave music and explicitly synthetic Flite KAL speech."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

def make(font: Path, out: Path):
    if any(str(p).replace('\\','/').startswith('//') for p in (font,out)):
        raise ValueError('UNC paths unsupported')
    out=out.resolve()
    if out.exists():raise FileExistsError('Destination exists; not overwriting')
    if not font.is_file():raise ValueError('Supply an installed TrueType font')
    out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='.work-',dir=out) as name:
        work=Path(name).resolve()
        assert work.parent==out and work.name.startswith('.work-')
        shutil.copyfile(font,work/'font.ttf')
        def ff(args,output):
            assert not (work/output).exists()
            r=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n',*args],cwd=work,capture_output=True,timeout=120)
            if r.returncode or not (work/output).is_file() or not (work/output).stat().st_size:
                raise RuntimeError('Synthetic asset generation failed: '+r.stderr.decode('utf-8',errors='replace'))
        for output,color,label in [('source-a-v2.mp4','0x101c35','SOURCE A'),('source-b-v2.mp4','0x113a34','SOURCE B')]:
            vf=f"drawgrid=width=80:height=80:thickness=1:color=white@0.08,drawbox=x=100:y=220:w=520:h=220:color=0x729aff@0.5:t=fill,drawtext=fontfile=font.ttf:text='{label} - Generated shapes':fontcolor=white:fontsize=34:x=60:y=100,drawtext=fontfile=font.ttf:text='Source frame %{{n}}':fontcolor=white:fontsize=32:x=60:y=170,drawtext=fontfile=font.ttf:text='FICTIONAL PORTFOLIO INPUT':fontcolor=white@0.8:fontsize=22:x=60:y=640"
            ff(['-f','lavfi','-i',f'color=c={color}:s=1280x720:r=30:d=12','-vf',vf,'-an','-c:v','libx264','-threads','2','-preset','fast','-pix_fmt','yuv420p','-map_metadata','-1',output],output)
        script='First, trim the clips. Next, add clear captions. Finally, export a consistent video. This is a synthetic demonstration.\n'
        (work/'narration-script.txt').write_bytes(script.encode('utf-8'))
        ff(['-f','lavfi','-i','aevalsrc=0.04*sin(2*PI*220*t)+0.025*sin(2*PI*330*t)+0.02*sin(2*PI*440*t):s=48000:d=20','-c:a','pcm_s16le','-map_metadata','-1','generated-music.wav'],'generated-music.wav')
        ff(['-f','lavfi','-i','flite=textfile=narration-script.txt:voice=kal','-c:a','pcm_s16le','-map_metadata','-1','synthetic-voice.wav'],'synthetic-voice.wav')
        for file in ['source-a-v2.mp4','source-b-v2.mp4','narration-script.txt','generated-music.wav','synthetic-voice.wav']:
            shutil.copyfile(work/file,out/file)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();make(a.font,a.out)
    print('Five original synthetic assets generated; no font, model or engine redistributed.')
