#!/usr/bin/env python3
"""Assemble index.html from src/ fragments, inlining the model and the audio.

    python3 tools/build.py            rebuild index.html
    python3 tools/build.py --check    rebuild and diff against the current file
    python3 tools/build.py --out P    write to P instead of index.html

Fragments (src/, produced by tools/split.py):
    head.html     markup + CSS
    lib/three.min.js
    app_glb.js    GLB parser + ROLE_COL
    app_scene.js  buildThreeScene()
    app_app.js    UI, step machine, render loop
    tail.html     </script></body></html>

Line 448 `<script>` and line 449 (the app banner) are constants here so the
join is byte-exact against the file split.py read.

Injected, never hand-edited:
    const GLB_B64='...'      from manifest["model"]
    const AUDIO={...}        from manifest["audio_glob"], only if files match

GLB_B64 is written into the fragment slot that split.py extracted by replacing
the existing `const GLB_B64='...'` assignment in app_glb.js. AUDIO is inserted
right after the three.js blob, so app_app.js can read it as a const.
"""
import base64, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

STYLE_OPEN = "<style>\n"
STYLE_CLOSE = "</style>\n"
SCRIPT_OPEN = "<script>\n"
BANNER = ("/* ============================================================="
          "= GEOMETRY == */\n")


def read(name):
    with open(os.path.join(SRC, name), "rb") as fh:
        return fh.read()


def glb_literal(path):
    with open(os.path.join(ROOT, path), "rb") as fh:
        data = fh.read()
    if data[:4] != b"glTF":
        raise SystemExit(f"{path}: not a GLB (magic {data[:4]!r})")
    return b"const GLB_B64='" + base64.b64encode(data) + b"';"


def audio_literal(manifest):
    """Build the AUDIO table from the real mp3 files. Empty means no clip.

    The name must be exactly `stepNN.mp3` (two digits). A looser glob picks up
    work-in-progress files such as `step01_s1.mp3` from a sentence-by-sentence
    synthesis run, which would collide on the step key and inline fragments.
    """
    entries, total = [], 0
    pat = re.compile(r"^step(\d{2})\.mp3$")
    for path in sorted(glob.glob(os.path.join(ROOT, manifest["audio_glob"]))):
        m = pat.match(os.path.basename(path))
        if not m:
            print(f"  skipping {os.path.relpath(path, ROOT)}: not a stepNN.mp3")
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        if not data:
            print(f"  skipping {os.path.relpath(path, ROOT)}: empty")
            continue
        total += len(data)
        entries.append(" %d:{b64:'%s'}" % (int(m.group(1)),
                                          base64.b64encode(data).decode()))
    if not entries:
        return b"", 0
    body = (b"const AUDIO={mime:'audio/mpeg',bytes:" + str(total).encode()
            + b",\n" + ",\n".join(entries).encode() + b"};\n")
    return body, total


def locale_audio_literal(manifest):
    """List each non-English locale's clips as file paths instead of inlining them.

    English stays inlined in AUDIO so a downloaded single file still speaks. Six locales
    inlined would add roughly 10 MB of base64 to a 3.3 MB page, so the rest ship as
    `audio/<locale>/leaflet/stepNN.mp3` beside the page and are fetched on demand.
    """
    pat = re.compile(r"^step(\d{2})\.mp3$")
    table = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "audio", "*", "leaflet", "*.mp3"))):
        code = os.path.relpath(path, ROOT).split(os.sep)[1]
        if code == "en":
            continue
        m = pat.match(os.path.basename(path))
        if not m or os.path.getsize(path) == 0:
            continue
        table.setdefault(code, {})[str(int(m.group(1)))] = \
            os.path.relpath(path, ROOT).replace(os.sep, "/")
    if not table:
        return b""
    payload = json.dumps(table, separators=(",", ":")).encode()
    return b"const AUDIO_LOCALES=" + payload + b";\n"


def i18n_literal(manifest):
    """Inline every locale catalogue as one I18N table.

    Each file is `src/i18n/<code>.json` shaped `{"html": {key: text}, "steps": {stepNN: {t, n}}}`.
    The table is a payload rather than a fragment because it is generated from the translation
    files, so the fragments stay the hand-edited source and `--check` strips it like AUDIO.
    """
    folder = os.path.join(ROOT, manifest.get("i18n_dir", "src/i18n"))
    table = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        code = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as fh:
            table[code] = json.load(fh)
    if not table:
        return b""
    payload = json.dumps(table, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return b"const I18N=" + payload + b";\n"


def assemble(manifest, with_audio=True):
    head_top = read(manifest["files"]["head_top"])
    css = read(manifest["files"]["css"])
    head_body = read(manifest["files"]["head_body"])
    lib = read(manifest["files"]["lib"])
    glb = read(manifest["files"]["glb"])
    scene = read(manifest["files"]["scene"])
    app = read(manifest["files"]["app"])
    tail = read(manifest["files"]["tail"])

    literal = glb_literal(manifest["model"])
    glb_new, n = re.subn(rb"const GLB_B64='[A-Za-z0-9+/=]*';", literal, glb)
    if n != 1:
        raise SystemExit(f"app_glb.js: found {n} GLB_B64 assignments, expected 1")
    glb = glb_new

    audio, audio_bytes = audio_literal(manifest) if with_audio else (b"", 0)
    locales = locale_audio_literal(manifest) if with_audio else b""
    i18n = i18n_literal(manifest)

    parts = [head_top, STYLE_OPEN.encode(), css, STYLE_CLOSE.encode(),
             head_body, SCRIPT_OPEN.encode(), BANNER.encode(), lib,
             b"" if lib.endswith(b"\n") else b"\n", audio, locales, i18n, glb, scene, app, tail]
    out = b"".join(p for p in parts if p)
    return out, audio_bytes


def strip_injected(data):
    """Remove the build-injected GLB_B64 / AUDIO payloads so fragments alone
    can be compared against a shipped file."""
    data = re.sub(rb"const AUDIO=\{.*?\};\n", b"", data, flags=re.S)
    data = re.sub(rb"const AUDIO_LOCALES=\{.*?\};\n", b"", data, flags=re.S)
    data = re.sub(rb"const I18N=\{.*?\};\n", b"", data, flags=re.S)
    return re.sub(rb"const GLB_B64='[A-Za-z0-9+/=]*';", b"const GLB_B64='';", data)


def main():
    manifest = json.load(open(os.path.join(SRC, "manifest.json")))
    check = "--check" in sys.argv
    target = os.path.join(ROOT, "index.html")

    if "--out" in sys.argv:
        target = sys.argv[sys.argv.index("--out") + 1]
        out, audio_bytes = assemble(manifest)
        with open(target, "wb") as fh:
            fh.write(out)
        print(f"wrote {target}  {len(out)} bytes  (audio {audio_bytes / 1e6:.2f} MB)")
        return 0

    if check:
        out, _ = assemble(manifest, with_audio=False)
        cur = strip_injected(open(target, "rb").read())
        out = strip_injected(out)
        if cur == out:
            print(f"OK  src/ fragments reproduce index.html exactly "
                  f"({len(out)} bytes, injected payloads ignored)")
            return 0
        print(f"DIFF  on disk {len(cur)} bytes, built from fragments {len(out)} bytes")
        import difflib
        a = cur.decode("utf-8", "replace").splitlines()
        b = out.decode("utf-8", "replace").splitlines()
        shown = 0
        for line in difflib.unified_diff(a, b, "index.html", "built", n=0):
            if line.startswith(("+++", "---")):
                continue
            print("  " + line[:160])
            shown += 1
            if shown > 40:
                print("  … more")
                break
        return 1

    out, audio_bytes = assemble(manifest)
    with open(target, "wb") as fh:
        fh.write(out)
    print(f"wrote index.html  {len(out)} bytes  (audio inlined "
          f"{audio_bytes / 1e6:.2f} MB, model {manifest['model']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
