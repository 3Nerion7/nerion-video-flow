NERION VIDEO FLOW

A working Python/FFmpeg portfolio example for repetitive video preparation:
trim and join local clips, normalize their frame size/rate, add a separate
narration and quiet generated music, transcribe the narration locally, and
export burned-in captions. No account or paid API is used by the renderer.

The supplied example is entirely synthetic. It is a technical demonstration,
not client work or a claim of prior production results. Code and review were
prepared with AI assistance. The voice is Flite KAL, not Nerion's own voice.

SEE THE RESULT

example-output/reviewed.mp4 shows the version with agent-reviewed captions.
example-output/raw.mp4 preserves the automatic model output for comparison.
Both are 16 seconds, 1280x720, 30 fps. Visible source-frame counters demonstrate
that source A starts at frame 60 (2 seconds) and source B at frame 30 (1 second).
Each 12-second source contributes 8 seconds to the joined result.

The tiny.en ASR model misrecognized two words in the supplied 18-word script:
"trim" became "bring", and "captions" became "caption". The raw SRT is retained
unchanged. The reviewed SRT corrects those words and punctuation against the
original synthetic script, and merges a 0.35-second cue for readability.
This was agent review, not a claim that a person performed the review.
Review captions before using them in a delivery. No general accuracy or
monthly-volume benchmark follows from this single English synthetic example.

RUN ON WINDOWS

Tested with Python 3.13.16 and the installed FFmpeg build
2026-04-09-git-d3d0b7a5ee-full_build-www.gyan.dev. Python uses only its standard
library. FFmpeg and ffprobe must be on PATH. This requires an FFmpeg build
with whisper, subtitles/libass, drawtext and libx264. Flite is needed only to
regenerate the synthetic example inputs. GPU execution is not used.

Download ggml-tiny.en.bin from the pinned official whisper.cpp model repository:
https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-tiny.en.bin

Expected SHA256:
921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f

The renderer verifies that hash. The model is not included in this package.
With the downloaded file in a local models directory, run from this folder:

python video_flow.py --job demo-job-reviewed.json --model models/ggml-tiny.en.bin --font C:/Windows/Fonts/arial.ttf --out new-reviewed-result

For raw automatic captions, use demo-job.json and a different --out directory.
An existing output directory is refused. Inputs must be relative files under
the job directory; URLs, UNC paths, parent traversal and linked inputs are
unsupported. Each clip has path, start and duration fields. Narration must fit
the assembled duration. Source audio is discarded; the job supplies narration
and music explicitly. Output is fixed at 1280x720/30 fps in this example tool.
This does not claim CapCut project export, multilingual validation or a general
secure upload service. Linux was not executed for this portfolio sample and
would require an equivalent FFmpeg build and installed font.

python -m unittest -v test_video_flow.py

To regenerate the original visuals, voice and music into a NEW directory:
python make_demo_inputs.py --font C:/Windows/Fonts/arial.ttf --out regenerated-inputs

Adjust a copy of the example job if using that new directory. The manually
reviewed caption file remains a separate, explicitly identified input.

EVIDENCE AND LIMITS

example-output/*-run.json records the actual jobs, model/input/output hashes,
stage return codes, dimensions and full decode result. The completed runs
decoded all video and audio with -xerror and no decode error output.
Durations in receipts cover one local render with inputs/model already
available; they exclude downloads, asset generation and caption review.
They are observations on this PC, not a delivery-time promise or a benchmark
for real footage, noisy speech, other languages or 30-100 monthly videos.

No sample video, voice, music, personal file, logo or business data came from
a client or employer. The Windows font, FFmpeg binaries and model weights are
not redistributed. See THIRD-PARTY.txt for component sources and conditions.

For a paid job, scope, rights to source material, price, revisions, acceptance
checks and an actually funded first milestone must be agreed before work.
