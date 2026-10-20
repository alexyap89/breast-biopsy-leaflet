"""Render the five non-English narration sets and their manifests.

Same contract as the English set: nine clips per locale at audio/<code>/leaflet/stepNN.mp3,
mono 48 kbps 32 kHz, one cloned reference voice per locale, gated for speech-likeness by
the renderer itself.
"""
import json, os, subprocess

ROOT = "/Users/alexyap/My Drive/20_Projects/Radiology/01-Active/Breast Biopsy"
PRIME = os.path.expanduser("~/Documents/Priming MRI VR/webxr_mri_simulation_v3")
PY = os.path.expanduser("~/models/meralion-hokkien-tts/venv/bin/python")
TTS = os.path.join(PRIME, "scripts/neural_tts.py")
REFS = "/tmp/fnac_ref_texts.json"
PREFIX = {"ms": "Langkah %d.", "ta": "படி %d.", "zh": "第%d步。", "yue": "第%d步。", "nan": "第%d步。"}
SEP = {"ms": ". ", "ta": ". ", "zh": "。", "yue": "。", "nan": "。"}
VOICE = {"nan": "MERaLiON Hokkien, cloned from the clinically approved Hokkien clip"}
DEFAULT_VOICE = "OmniVoice k2-fsa/OmniVoice, one cloned reference voice for every step"

reftexts = json.load(open(REFS, encoding="utf-8"))

for code in ("ms", "ta", "zh", "yue", "nan"):
    cat = json.load(open(os.path.join(ROOT, f"src/i18n/{code}.json"), encoding="utf-8"))
    steps = sorted(cat["steps"].items())
    clips = {k: (PREFIX[code] % (i + 1)) + " " + v["t"] + SEP[code] + v["n"] for i, (k, v) in enumerate(steps)}

    outdir = os.path.join(ROOT, "audio", code, "leaflet")
    wavdir = os.path.join(outdir, "_neural_wav")
    os.makedirs(wavdir, exist_ok=True)
    clipsfile = f"/tmp/clips_{code}.json"
    json.dump(clips, open(clipsfile, "w", encoding="utf-8"), ensure_ascii=False)

    if code == "nan":
        model = "MERaLiON/MERaLiON-OmniVoice-Hokkien-TTS"
        ref = os.path.join(PRIME, "public/audio/vo/nan/hotspot.scanner.narration.mp3")
        reftxt = reftexts["nan"]["hotspot.scanner.narration"]
    else:
        model = "k2-fsa/OmniVoice"
        ref = os.path.join(PRIME, "scripts/voices", f"{code}.wav")
        reftxt = reftexts[code]["hotspot.breath-hold.narration"]

    cmd = [PY, TTS, "--clips", clipsfile, "--out", wavdir, "--model", model,
           "--ref-audio", ref, "--ref-text", reftxt]
    if code == "ms":
        cmd += ["--language", "id"]          # the ms tag renders as a rumble; id is stable
    print(f"=== {code} ===", flush=True)
    subprocess.run(cmd, check=True)

    files, meta, total_s, total_b = [], {}, 0.0, 0
    for i in range(1, 10):
        key = f"step{i:02d}"
        wav = os.path.join(wavdir, key + ".wav")
        mp3 = os.path.join(outdir, key + ".mp3")
        subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-i", wav, "-ac", "1", "-ar", "32000",
                        "-b:a", "48k", mp3], check=True)
        d = float(subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", mp3], capture_output=True, text=True).stdout.strip())
        b = os.path.getsize(mp3)
        text = clips[key]
        files.append(f"audio/{code}/leaflet/{key}.mp3")
        meta[key] = {"step": i, "title": cat["steps"][key]["t"], "characters": len(text),
                     "words": len(text.split()), "duration_s": round(d, 2), "bytes": b,
                     "wpm": round(len(text.split()) / d * 60, 1), "engine": "omnivoice"}
        total_s += d; total_b += b
    json.dump({"engine": "omnivoice", "voice": VOICE.get(code, DEFAULT_VOICE), "files": files,
               "steps": meta, "total": {"duration_s": round(total_s, 2), "bytes": total_b, "steps": 9}},
              open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"{code}: 9 clips {total_s:.1f}s", flush=True)
print("ALL DONE")
