"""Build src/i18n/en.json from the hand-authored markup and the step array.

English is authored in two places: the page copy lives in `src/head_body.html` with a
`data-i18n` hook on each element, and the nine step titles/notes live in the `STEPS`
array in `src/app_app.js`. This reads both so the catalogue can never drift from what
the page actually shows.

    python3 tools/extract_i18n.py
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "src/head_body.html")
APP = os.path.join(ROOT, "src/app_app.js")
OUT = os.path.join(ROOT, "src/i18n/en.json")

html = open(BODY, encoding="utf-8").read()

def text_of(s, start):
    """Text content of the element starting at `start`, skipping child elements."""
    depth, i, out = 1, start, []
    tag = re.match(r"<([a-zA-Z0-9]+)", s[s.rfind("<", 0, start):start]).group(1)
    while depth and i < len(s):
        nxt = s.find("<", i)
        if nxt < 0:
            break
        out.append(s[i:nxt])
        m = re.match(r"</?([a-zA-Z0-9]+)", s[nxt:])
        if not m:
            i = nxt + 1
            continue
        name = m.group(1)
        closing = s[nxt + 1] == "/"
        if name == tag:
            if closing:
                depth -= 1
                if depth == 0:
                    break
            elif not s[nxt:].startswith("/>"):
                depth += 1
        i = s.find(">", nxt) + 1
    return re.sub(r"\s+", " ", "".join(out)).strip()

keys, order = {}, []
for m in re.finditer(r'data-i18n="(k\d+)"[^>]*>', html):
    key, start = m.group(1), m.end()
    if key in keys:
        continue
    txt = text_of(html, start)
    # A heading carries its number in a decorative <span class="num">N</span>; the badge is
    # markup, not copy, so strip it or every translation would repeat the digit.
    if 'class="num"' in html[m.start():m.end() + 200]:
        txt = re.sub(r"^\d+\s+", "", txt)
    keys[key] = txt
    order.append(key)

app = open(APP, encoding="utf-8").read()
steps = {}
for i, m in enumerate(re.finditer(r'\{t:"((?:[^"\\]|\\.)*)",\s*\n\s*n:"((?:[^"\\]|\\.)*)"', app), start=1):
    steps[f"step{i:02d}"] = {"t": m.group(1).replace('\\"', '"'), "n": m.group(2).replace('\\"', '"')}

missing = [k for k, v in keys.items() if not v]
if missing:
    print("WARNING empty text for:", missing)
print(f"html keys {len(keys)}, steps {len(steps)}")

out = {"html": {k: keys[k] for k in sorted(keys, key=lambda x: int(x[1:]))}, "steps": steps}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", OUT, os.path.getsize(OUT), "bytes")
