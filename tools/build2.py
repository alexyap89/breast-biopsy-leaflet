#!/usr/bin/env python3
"""Assemble index2.html — the MEDIA edition of the breast-biopsy leaflet.

Reuses tools/build.py's injection literals (AUDIO, AUDIO_LOCALES, I18N) but
swaps the three.js stage for a media stage (stills + SVG diagrams + clips).

    python3 tools/build2.py            -> index2.html
    python3 tools/build2.py --out P    -> write to P

Never touches index.html or src/. Media files are expected in assets/ beside
the page (assets/b*.jpg, assets/b*.svg, future *.mp4).
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build as B  # reuse read(), audio_literal(), locale_audio_literal(), i18n_literal(), constants

STAGE_NEW = b"""    <div class="stage media-stage" id="mediaStage" role="img" tabindex="0"
      aria-label="Illustration of the breast core biopsy step by step. A text description of every step is given underneath."></div>
"""

META_NEW = b"""    <div class="stage-meta">
      <div class="badge" data-i18n="k71b">Tap a step above, or press play</div>
    </div>
"""

def patch_head_body(html: bytes) -> bytes:
    html, n = re.subn(rb'    <div class="stage">\n(?:.*?\n)*?    </div>\n', STAGE_NEW, html, count=1)
    if n != 1:
        raise SystemExit("stage block not found in head_body.html")
    html, n = re.subn(rb'    <div class="stage-meta">\n(?:.*?\n)*?    </div>\n', META_NEW, html, count=1)
    if n != 1:
        raise SystemExit("stage-meta block not found in head_body.html")
    # The 3D instruction (k125) tells the reader to drag and rotate — meaningless on a
    # media stage, and every locale carries it. Swap to k125b, a media-specific key, so
    # the 3D page keeps its own correct wording.
    html, n = re.subn(
        rb'<p data-i18n="k125">(?:.*?\n)*?.*?</p>',
        ("<p data-i18n=\"k125b\">Tap any step below, or press play, to see what happens "
         "at each step. The pictures are illustrations, not photographs.</p>").encode(),
        html, count=1)
    if n != 1:
        raise SystemExit("k125 paragraph not found in head_body.html")
    return html

def main():
    manifest = json.load(open(os.path.join(ROOT, "src", "manifest.json")))
    standalone = "--standalone" in sys.argv
    target = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "index2.html")

    head_top = B.read(manifest["files"]["head_top"])
    css = B.read(manifest["files"]["css"])
    head_body = patch_head_body(B.read(manifest["files"]["head_body"]))
    app = open(os.path.join(ROOT, "src2", "app_media.js"), "rb").read()
    media_css = open(os.path.join(ROOT, "src2", "style_media.css"), "rb").read()
    tail = B.read(manifest["files"]["tail"])

    # Match the 3D page's C4 contract: narration ships as audio/<locale>/leaflet/stepNN.mp3
    # beside the page and is fetched on demand. Inlining EN cost ~0.9 MB of base64 on every
    # visit for a 9-step leaflet most patients open once. --standalone inlines it again for
    # a single-file hand-out build.
    if standalone:
        audio, audio_bytes = B.audio_literal(manifest)
    else:
        audio, audio_bytes = b"", 0
    locales = B.locale_audio_literal(manifest, standalone=standalone)
    i18n = B.i18n_literal(manifest)

    parts = [head_top, B.STYLE_OPEN.encode(), css + b"\n" + media_css, B.STYLE_CLOSE.encode(),
             head_body, B.SCRIPT_OPEN.encode(), B.BANNER.encode(),
             audio, locales, i18n, app, tail]
    out = b"".join(p for p in parts if p)
    open(target, "wb").write(out)
    print(f"wrote {target}  {len(out)} bytes  (audio {audio_bytes/1e6:.2f} MB)")

if __name__ == "__main__":
    main()
