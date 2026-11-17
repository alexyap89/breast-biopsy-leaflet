# breast-biopsy-leaflet

Two editions ship from this repo:

| File | Edition | Build |
|---|---|---|
| `index.html` | **media edition** — graded stills, motion clips, print sheet | `python3 tools/build2.py --out index.html` |
| `index3d.html` | 3D edition — three.js scene | `python3 tools/build.py --out index3d.html` |

Both read the same `src/` fragments, `audio/`, and `assets/`. Media assets are versioned with `?v=` / `?av=` query tags so a rebuilt frame is never masked by the browser cache.

# Understanding Your Breast Biopsy — patient leaflet

Interactive patient leaflet for ultrasound-guided breast core biopsy at a Singapore
public hospital. One self-contained `index.html`: an interactive 3D walkthrough
(three.js, GLB inlined), step narration in six locales (en, zh, yue, ms, ta, nan),
display-size / high-contrast / print support.

**Live copy:** https://alexyap89.github.io/breast-biopsy-leaflet/
(serve state is live-measured, never remembered — see `CHANGELOG.md` "Deploy state".)

## Build — two stages, do not confuse them

| Stage | Command | Output |
|---|---|---|
| 1. Generate the 3D model (rarely needed) | `python3 build_breast.py` | `model/breast_scene.glb` (needs trimesh/numpy/shapely venv) |
| 2. Assemble the page (the normal build) | `python3 tools/build.py` | `index.html` from `src/` fragments + GLB + audio tables |

```
python3 tools/build.py            # rebuild index.html (all narration lazy)
python3 tools/build.py --check    # verify index.html matches src/ byte-exact
python3 tools/build.py --standalone  # also inline English clips for offline single-file use
```

`build_breast.py` does **not** produce the page — it only regenerates the GLB.
Hand-edited source is `src/` (`head_top.html`, `style.css`, `head_body.html`,
`app_glb.js`, `app_scene.js`, `app_app.js`, `tail.html`, `i18n/*.json`);
`index.html` is generated and must never be edited directly.

## Preview locally

```
python3 -m http.server 8055     # from this directory, then http://127.0.0.1:8055/
```

Narration mp3s (`audio/<locale>/leaflet/stepNN.mp3`) are fetched lazily by the page,
so they must be served beside `index.html` (any static server works).

## Deploy

GitHub Pages via `.github/workflows/pages.yml`: a push to `main` publishes the repo
root, so the committed, built `index.html` at the root is exactly what goes live.
Deploying is `git push origin main` — Alex's call only; overnight cycles never push.

## Conventions

- Display prefs persist in `localStorage` under `breast.size` / `breast.contrast` / `breast.lang`.
- All UI strings live in `src/i18n/<code>.json`; never hardcode step copy in JS.
- Version tags are annotated and local-first (`git tag -l`); deploy state is measured
  with `curl` against the live URL, not remembered.
