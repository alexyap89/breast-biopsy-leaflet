#!/usr/bin/env python3
"""Generate the leaflet's spoken steps, one MP3 per step.

The narration text is PARSED out of src/app_app.js, never hand-copied, so the
audio can never drift from what the page displays. Step N is spoken as
"Step N. {title}. {note}".

Two engines, both writing the same files:

    python3 tools/make_audio_leaflet.py                # gTTS (en-GB), offline fallback
    python3 tools/make_audio_leaflet.py --engine say   # macOS say, fully offline
    python3 tools/make_audio_leaflet.py --engine gtts  # require the network engine
    python3 tools/make_audio_leaflet.py --engine omnivoice   # neural, cloned reference voice

`say` and gTTS are formant synthesisers - intelligible and completely flat. `omnivoice`
runs the OmniVoice neural TTS in the sibling project's venv and clones one reference voice
for every step, which is what makes the narration sound like a person rather than a reader.
It is the slowest by far (a CPU model load, then one render per clip) and needs no network.

Files land in audio/en/leaflet/stepNN.mp3. `say` and gTTS write mono 48 kbps 44.1 kHz; the neural
engine writes mono 48 kbps 32 kHz, which is what the clip set it replaces already measured at and
keeps the inlined total inside the budget below. tools/build.py inlines them as a base64 `AUDIO`
table keyed by 1-based step number, so the names matter. A previously generated set is preserved as
stepNN.<engine>.mp3 first.

Duration is checked against a naive 150 words-per-minute estimate; a clip more
than 45% off that is a truncation and fails the run.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "app_app.js")
OUTDIR = os.path.join(ROOT, "audio", "en", "leaflet")
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
SAY = "/usr/bin/say"
SAY_VOICE = "Daniel"          # en_GB register, right for this audience
# `say -r` is COARSE for the installed voices: 110-141 all render identically, so
# 100 is the only usable slow setting. Daniel at 100 measures ~160 wpm, so a light
# 5% stretch lands the pace near 150 - far less time-stretch artefact than slowing
# a fast take by 14%, and the stretch is what makes a synthetic voice sound wrong.
SAY_RATE = 100
GTTS_TLD = "co.uk"            # en-GB
ATEMPO = 0.95                 # light on purpose: stretching also lengthens the gaps
WPM_ESTIMATE = 150.0
# The gate above is a TRUNCATION check: a clip far shorter than its text implies has lost words.
# It is not a tempo prescription, and the neural engine reads at its own natural pace: measured
# 12.9 s for a 42-word step = 195 wpm, against 150 for the `say` take of the same text. Both are
# ordinary speaking rates, so the band has to admit both, or a good neural render fails the run
# for being human. Anything faster than ~220 wpm really is a clipped reading.
TOLERANCE = 0.45

# ---- neural engine (OmniVoice) -------------------------------------------------
# The two engines above are formant synthesisers: `say` and gTTS are intelligible and
# completely flat, which is what "the voice does not sound natural" means. OmniVoice is a
# neural TTS that clones a reference voice, so every step is read by the same speaker.
#
# The renderer and its reference voice live in the sibling project, which already had to
# solve two things this file must not re-solve: the model's auto mode picks a FRESH
# SPEAKER on every call (so clips rendered one at a time change voice between steps - every
# clip is generated against one reference), and a failed neural render is not an error but
# a rumble of the right length and level (so each render is gated for speech-likeness).
#
# It runs on CPU: the OmniVoice family hangs indefinitely inside `from_pretrained` on MPS.
NEURAL_VENV = "/Users/alexyap/models/meralion-hokkien-tts/venv/bin/python"
NEURAL_SCRIPT = "/Users/alexyap/Documents/Priming MRI VR/webxr_mri_simulation_v3/scripts/neural_tts.py"
NEURAL_MODEL = "k2-fsa/OmniVoice"
NEURAL_REF = "/Users/alexyap/Documents/Priming MRI VR/webxr_mri_simulation_v3/scripts/voices/en.wav"
# Exact transcript of NEURAL_REF. A wrong transcript poisons the clone for every clip - it does
# not fail loudly, it produces speech-shaped noise that passes a spectral gate. Measured, not
# guessed: transcribing the reference itself gives
#   "Breath hold practice. For abdominal scans, you hold your breath for short periods. We will
#    practice that gently here so it feels familiar on the day."
# which is the clip it actually contains. An earlier version of this file used a different
# narration's text here; every rendered clip came back as nonsense (word recall 3-30% against the
# page's text) while still passing the speech-likeness gate.
NEURAL_REF_TEXT = ("Breath hold practice. For abdominal scans, you hold your breath for short "
                   "periods. We will practice that gently here so it feels familiar on the day.")
# -19, the sibling project's value. Raising it to -16 was tried to match the -19.5 dBFS RMS of the
# clips being replaced and changed NOTHING: the gain is capped by the true-peak limit, so the neural
# set sits at -22.4 dBFS RMS with peaks at -1.5 dBTP. That gap is crest factor, not a level error -
# the `say` clips were squashed to about 14 dB, natural speech runs nearer 21 dB. Compressing these
# to close it would undo the thing that made them sound human, so the level is left where the peak
# ceiling puts it.
NEURAL_LUFS = -19.0
NEURAL_TRUE_PEAK = -1.5
NEURAL_BITRATE = "48k"        # matches the density of the clips it replaces (784,930 B for 130 s)


def parse_steps():
    """Pull the STEPS array out of the page's own source."""
    src = open(SRC, encoding="utf-8").read()
    m = re.search(r"const STEPS\s*=\s*\[(.*?)\n  \];", src, re.S)
    if not m:
        raise SystemExit("could not find the STEPS array in src/app_app.js")
    body = m.group(1)
    pairs = re.findall(r'\{t:"((?:[^"\\]|\\.)*)",\s*\n\s*n:"((?:[^"\\]|\\.)*)"', body)
    if not pairs:
        raise SystemExit("STEPS found but no {t, n} entries parsed")
    out = []
    for title, note in pairs:
        title = title.encode().decode("unicode_escape")
        note = note.encode().decode("unicode_escape")
        out.append((title, note))
    return out


def spoken(i, title, note):
    return speakable(f"Step {i}. {title}. {note}")


def speakable(text):
    """Make the text safe for a TTS engine.

    Measured cause of the pauses the user hears: the notes contain 5 em dashes
    and 1 en dash, and the engine reads an em dash as a long break, so the clips
    came out with 5-6 silences each against only 1-2 commas of real punctuation.
    Rewriting the dashes as ordinary punctuation removes the invented pauses
    without changing a single word. The sentence-ending periods are left alone:
    a pause at the end of a sentence is wanted.
    """
    t = text

    # Dashes are the problem. A TTS engine reads an em dash as an arbitrary
    # long pause, which is what "the dash is not well dictated" is. Where the
    # dash is parenthetical - two of them in one sentence - a comma is right.
    # Where it separates two clauses, a full stop is: the engine then produces a
    # normal, expected sentence break instead of a hole in the middle of a line.
    def _sentences(x):
        out, cur = [], ""
        for ch in x:
            cur += ch
            if ch in ".!?":
                out.append(cur)
                cur = ""
        if cur:
            out.append(cur)
        return out

    rebuilt = []
    for sent in _sentences(t):
        if sent.count("\u2014") >= 2:
            sent = sent.replace("\u2014", ", ")
        elif "\u2014" in sent:
            head, _sep, tail = sent.partition("\u2014")
            tail = tail.lstrip()
            if tail:
                tail = tail[0].upper() + tail[1:]
            sent = head.rstrip() + ". " + tail
        rebuilt.append(sent)
    t = "".join(rebuilt)

    # En dashes are ranges: "1-2 weeks" must be read as "1 to 2 weeks".
    t = re.sub(r"(\d)\s*\u2013\s*(\d)", r"\1 to \2", t)
    t = t.replace("\u2013", ", ")
    t = t.replace("\u2019", "'").replace("\u201c", "").replace("\u201d", "")
    t = re.sub(r"\s+", " ", t)           # collapse runs of whitespace
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)   # never a space before punctuation
    t = re.sub(r",\s*,+", ",", t)        # collapse doubled commas
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def synth_gtts(text, path):
    from gtts import gTTS
    gTTS(text=text, lang="en", tld=GTTS_TLD, slow=False).save(path)
    return "gtts"


def synth_say(text, path):
    aiff = path + ".aiff"
    if os.path.exists(aiff):
        os.remove(aiff)
    subprocess.run([SAY, "-v", SAY_VOICE, "-r", str(SAY_RATE), "-o", aiff, text], check=True)
    if not os.path.exists(aiff) or os.path.getsize(aiff) < 8192:
        raise SystemExit(f"say produced nothing usable for {os.path.basename(path)}")
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", aiff,
                    "-filter:a", f"atempo={ATEMPO}",
                    "-ac", "1", "-ar", "44100", "-b:a", "48k",
                    "-map_metadata", "-1", path], check=True)
    os.remove(aiff)
    return "say"


def encode_mp3(src, path):
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src,
                    "-filter:a", f"atempo={ATEMPO}",
                    "-ac", "1", "-ar", "44100", "-b:a", "48k",
                    "-map_metadata", "-1", path], check=True)


def duration(path):
    """Seconds of audio, from ffmpeg's own report.

    Raises instead of returning 0.0 on failure. It used to swallow a broken probe and hand back
    0.0 for every clip, so a broken tool was reported as nine suspect clips, which is a much
    worse failure than an error message.
    """
    out = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path, "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", out)
    if not m:
        raise SystemExit(f"could not read the duration of {os.path.basename(path)}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def ffmpeg_exe():
    """A WORKING ffmpeg, system first.

    The homebrew build on this machine is broken: it wants libx265.216.dylib and the installed
    x265 is 4.3, which ships .217, so every call dies with a dyld error before it reads a byte.
    That took down the whole tool, not just the neural path - `duration()` returned 0.0 for every
    clip (silently, because it swallowed the failure) and the pace check then failed a good run.
    The venv's self-contained copy reports libmp3lame and needs no homebrew, so use it when the
    system one is unusable.
    """
    try:
        if subprocess.run([FFMPEG, "-hide_banner", "-version"],
                          capture_output=True).returncode == 0:
            return FFMPEG
    except OSError:
        pass
    return subprocess.run([NEURAL_VENV, "-c",
                           "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                          capture_output=True, text=True, check=True).stdout.strip()


def neural_render(clips, outdir):
    """Render every clip against ONE reference voice. Returns the wav dir.

    Rendered as a batch, not per step: the model is loaded once, and - the reason this
    cannot be per-step - `create_voice_clone_prompt` pins the speaker for the whole set.
    The model's auto mode picks a new speaker on every call, which is what made an earlier
    attempt at this change voice between tour steps in the sibling project.

    A wav that already exists is kept, so re-encoding does not re-render; delete the
    directory to force a fresh take.
    """
    os.makedirs(outdir, exist_ok=True)

    def stale(clip_id):
        """Is this clip missing, or was it rendered from different words?

        Keyed on the text, not just the filename. Filename alone would silently reuse a take
        rendered from older copy - which is exactly what happened when step 7's wording changed
        from "two or three times" and the cache still held the previous recording.
        """
        wav = os.path.join(outdir, clip_id + ".wav")
        tag = os.path.join(outdir, clip_id + ".txt")
        if not os.path.exists(wav):
            return True
        if not os.path.exists(tag):
            return True
        with open(tag, encoding="utf-8") as fh:
            return fh.read() != clips[clip_id]

    missing = [k for k in clips if stale(k)]
    if not missing:
        print(f"  reusing {len(clips)} rendered clips in {outdir}")
        return outdir
    clips_json = os.path.join(outdir, "clips.json")
    with open(clips_json, "w", encoding="utf-8") as fh:
        json.dump(clips, fh, indent=1)
    cmd = [NEURAL_VENV, NEURAL_SCRIPT, "--clips", clips_json, "--out", outdir,
           "--model", NEURAL_MODEL, "--language", "en",
           "--ref-audio", NEURAL_REF, "--ref-text", NEURAL_REF_TEXT]
    print(f"  rendering {len(missing)} clip(s) on CPU - the model load alone takes a minute")
    proc = subprocess.run(cmd, env=dict(os.environ, NEURAL_TTS_DEVICE="cpu"),
                          capture_output=True, text=True)
    for line in (proc.stdout or "").splitlines():
        if line.startswith(("loading", "loaded", "cloning", "ok ", "fail", "rendered")):
            print("  " + line)
    if proc.returncode != 0:
        raise RuntimeError("neural render failed:\n" + (proc.stderr or "")[-1500:])
    for clip_id, text in clips.items():
        if os.path.exists(os.path.join(outdir, clip_id + ".wav")):
            with open(os.path.join(outdir, clip_id + ".txt"), "w", encoding="utf-8") as fh:
                fh.write(text)
    return outdir


def neural_mp3(wav, path):
    """Level one rendered wav and encode it to mp3. Returns the gain applied.

    Two passes, not one: neural clips come out at very different levels - the sibling
    project measured 8.7 LU between two locales, and a quiet clip cannot be lifted by
    anything downstream - so the gain is computed from ffmpeg's own loudness analysis and
    capped by the true-peak limit. A single `loudnorm` pass overshoots.
    """
    ff = ffmpeg_exe()
    analysis = subprocess.run(
        [ff, "-hide_banner", "-i", wav, "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", analysis, re.S)
    if not m:
        raise RuntimeError("could not measure loudness of " + wav)
    meas = json.loads(m.group(0))
    gain = min(NEURAL_LUFS - float(meas["input_i"]), NEURAL_TRUE_PEAK - float(meas["input_tp"]))
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", wav, "-af", f"volume={gain:.2f}dB",
                    "-codec:a", "libmp3lame", "-b:a", NEURAL_BITRATE, "-ac", "1", "-ar", "32000", path],
                   check=True)
    return gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=("auto", "gtts", "say", "omnivoice"), default="say")
    args = ap.parse_args()

    steps = parse_steps()
    os.makedirs(OUTDIR, exist_ok=True)

    # The neural engine renders the whole set in one go, before the per-step loop: the model
    # is loaded once, and one reference voice is cloned for every clip. The loop below only
    # levels and encodes what it produced. Kept under OUTDIR so a re-encode does not re-render.
    wav_dir = None
    if args.engine == "omnivoice":
        wav_dir = neural_render(
            {f"step{i:02d}": spoken(i, title, note) for i, (title, note) in enumerate(steps, 1)},
            os.path.join(OUTDIR, "_neural_wav"))

    # preserve whatever is already there under the engine that made it
    for p in sorted(glob.glob(os.path.join(OUTDIR, "step*.mp3"))):
        if not re.search(r"\.\w+\.mp3$", p):
            shutil.copy2(p, p[:-4] + ".previous.mp3")

    rows, total, engine_used = [], 0, None
    for i, (title, note) in enumerate(steps, 1):
        text = spoken(i, title, note)
        words = len(text.split())
        path = os.path.join(OUTDIR, f"step{i:02d}.mp3")
        raw = path + ".src"
        engine = None
        if args.engine == "omnivoice":
            wav = os.path.join(wav_dir, f"step{i:02d}.wav")
            if not os.path.exists(wav):
                raise SystemExit(f"no neural render for step {i}: {wav}")
            gain = neural_mp3(wav, path)
            engine = "omnivoice"
        if args.engine in ("auto", "gtts"):
            try:
                synth_gtts(text, raw)
                encode_mp3(raw, path)
                engine = "gtts"
            except Exception as exc:
                if args.engine == "gtts":
                    raise
                print(f"  gtts unavailable ({type(exc).__name__}: {str(exc)[:60]}); falling back to say")
        if engine is None:
            # `say` writes AIFF; ffmpeg does the MP3 encode
            synth_say(text, path)
            engine = "say"
        if os.path.exists(raw):
            os.remove(raw)
        engine_used = engine_used or engine
        dur = duration(path)
        size = os.path.getsize(path)
        expect = words / WPM_ESTIMATE * 60.0
        dev = abs(dur - expect) / max(expect, 1e-6)
        flag = "" if dur > 2.0 and dev <= TOLERANCE else "  <-- SUSPECT"
        rows.append({"step": i, "title": title, "characters": len(text), "words": words,
                     "duration_s": round(dur, 3), "bytes": size,
                     "wpm": round(words / dur * 60, 1) if dur else 0, "engine": engine})
        total += size
        print(f"  {i:>2}  {dur:6.2f}s  {size:>8} B  {words:>3}w  {rows[-1]['wpm']:>5} wpm  {title[:34]}{flag}")

    bad = [r for r in rows if r["duration_s"] <= 2.0
           or abs(r["duration_s"] - r["words"] / WPM_ESTIMATE * 60) / (r["words"] / WPM_ESTIMATE * 60) > TOLERANCE]
    manifest = {
        "engine": engine_used,
        "voice": (f"macOS say {SAY_VOICE} at {SAY_RATE} wpm" if engine_used == "say"
                  else f"gTTS en tld={GTTS_TLD}" if engine_used == "gtts"
                  else f"OmniVoice {NEURAL_MODEL}, one cloned reference voice for every step"),
        "files": [f"audio/en/leaflet/step{i:02d}.mp3" for i in range(1, len(rows) + 1)],
        "steps": {f"step{r['step']:02d}": r for r in rows},
        "total": {"duration_s": round(sum(r["duration_s"] for r in rows), 2),
                  "bytes": total, "steps": len(rows)},
    }
    with open(os.path.join(OUTDIR, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")

    print(f"\nengine={engine_used}  total {total/1e6:.2f} MB  "
          f"{manifest['total']['duration_s']:.1f} s  ({total*4/3/1e6:.2f} MB once inlined)")
    if bad:
        print(f"FAIL: {len(bad)} clip(s) empty or off pace: "
              + ", ".join(str(r['step']) for r in bad))
        return 1
    if total > 1_500_000:
        print(f"FAIL: {total/1e6:.2f} MB exceeds the 1.5 MB budget (it is base64 inlined)")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
