Fresh Windows integration check
==============================

The workflow tests the checked-out source, not example-output/*.mp4. It runs
the nine renderer boundary tests and five integrity/preservation tests, then
two fresh 16-second renders (raw captions and separately agent-reviewed
captions). Both runs execute tiny.en on the CPU through FFmpeg's whisper
filter, normalize the voice to 16 kHz mono, render, and decode the complete
video/audio output. The verification script checks fixture hashes, stages,
input/output provenance, subtitle source, 720p/30fps, duration, and AAC audio.
The raw ASR transcript is retained; this remains one synthetic English case.

No new input generation is claimed by this check. It uses the committed
synthetic shapes, frame counters, Flite KAL narration and generated music.
It does not accept client files, make a production claim, or validate Linux.
The ordinary Ubuntu FFmpeg checked during preparation lacked whisper.

Fresh local run (PowerShell, Python 3.13, Windows):

  python ci/bootstrap.py
  $env:PATH = (Join-Path (Get-Location) '_ci-tools/bin') + ';' + $env:PATH
  python -m unittest -v test_video_flow.py ci/test_guards.py
  python ci/verify_demo.py --model _ci-tools/ggml-tiny.en.bin --font C:/Windows/Fonts/arial.ttf --out _ci-results

Both _ci-tools and _ci-results must be new directories. A failed attempt is
retained for inspection; use a different fresh path for a later attempt.
The bootstrap accepts --out and the verifier accepts --model/--font/--out.
The tools occupy about 775 MB including the retained archive and model;
about 326.5 MB is downloaded. Nothing is installed system-wide.

Dependency provenance:
- Gyan's third-party Windows FFmpeg full build, release 2026-04-09-git-d3d0b7a5ee:
  https://github.com/GyanD/codexffmpeg/releases/tag/2026-04-09-git-d3d0b7a5ee
  The ZIP byte count and SHA256, both executable byte counts and SHA256s,
  and exact ZIP member names are fixed in bootstrap.py. A mismatch fails.
  FFmpeg itself publishes source; this is not an FFmpeg-authored binary or
  a claim that we reproduced its compilation. See THIRD-PARTY.txt.
- The public tiny.en GGML checkpoint is fixed to Hugging Face revision
  5359861c739e955e79d9a303bcbc70fb988958b1, with length and SHA256 verified.
- Arial is used from the Windows installation; no font file is distributed.
- GitHub checkout and setup-python actions are pinned by full commit hash.
  Python is selected from the 3.13 series; the Windows runner image and
  installed font can change. The run reports actual versions and output
  hashes; no cross-machine bit-identical result is promised.

On GitHub the workflow uses the standard windows-2022 runner in this public
repository. It requests read-only contents access and disables persisted
checkout credentials. There are no secrets, scheduled jobs, paid/larger
runners, uploaded artifacts or dependency caches. Results are printed to
the job log and step summary. On failure, the last 80 lines of the fixed
synthetic raw ASR stage log are printed for diagnosis. Each stage log and
native-process exception retain its decimal and hexadecimal exit code;
this does not turn a failed render into a success. This is not a file
upload facility for arbitrary inputs or client material.
Public standard-runner compute is free under
GitHub's published pricing; this workflow does not enable paid services.

This is portfolio evidence, not a client delivery, accuracy benchmark,
funded assignment or promise of contest winnings. Review captions before
any real delivery. Development and these checks were AI-assisted.
