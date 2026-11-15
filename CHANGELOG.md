# Changelog — breast-biopsy-leaflet

Newest first. Each entry: what changed, how verified, and how to roll it back.
Rollback of any single entry: `git revert <commit>` then rebuild
(`python3 tools/build.py`). Rollback of everything: `git checkout <previous tag>`.
Nothing below is live until Alex pushes `main` and GitHub Pages redeploys.

## [v0.9.1] — 2026-11-16 (media edition; local only, not pushed)

### M3 — Motion beats for the two cold steps (this commit)
- Steps 4 and 6 were stills that didn't show the action Alex asked for (LA = gauze;
  needle step = bare probe). Both are now local **image-to-video clips** (LTX-2.5,
  49f @24fps, 768×480, faststart, ~160 KB each) generated from the graded stills:
  `m4_lido.mp4` (needle advances, skin dimples) and `m6_needle.mp4` (needle enters
  in one straight line beside the sheathed probe). Stills remain as posters.
- v10 stills were attempted first and **rejected**: seed 137 drifted to an abdomen
  with a navel; seed 401 gave ambiguous anatomy; the b6 v10 take grew the needle
  out of the probe. Adopted v9/v8 stills instead — same recipe as FNAC (still
  poises, clip carries the entry).
- Verified: four video elements in the built page (m2/m3/m4/m6), posters set,
  `paused=false`, no media error, zero 4xx on the resource timeline; clips
  frame-checked (first/last) and structure-checked (moov before mdat).
- Known: nan.json still duplicates zh.json (Carried from C6).

### M2 — Generated stills replace the hand-drawn SVGs and wrong beats
- Adopted graded renders over SVGs: `b1_anatomy.jpg` (breast cross-section
  illustration with lump) and `b7_clip.jpg` (marker clip + magnified inset).
- Replaced wrong-beat stills: b4 LA injection (was a clinician holding gauze),
  b5 scalpel nick (was a marking pen on the drape), b6 biopsy device at entry
  beside the probe (was a bare probe). Alt text rewritten to match; stale
  `b1_anatomy.svg`, `b7_clip.svg`, `b5_mark.jpg`, `b6_probe.jpg` removed.
- Rollback: `git revert` this range; rebuild with `python3 tools/build2.py`.

### M1 — Media edition restored
- `src2/app_media.js`, `src2/style_media.css`, `tools/build2.py`, `assets/*` and
  built `index2.html` were evicted by a C-cycle `git clean` and recovered
  byte-identical from Google Drive trash; now committed to the repo.
- Fix: stage media now eager-loads (`loading='lazy'` starved below-fold step
  swaps; video `preload='auto'`).
- Media edition builds against the current `src/` (inherits C1–C8: k80 locales,
  lazy EN audio, favicon).

## [v0.9.0] — 2026-11-15 (C1–C8 overnight cycles; local only, not pushed)

### C8 — Deploy hygiene (this commit)
- Added `README.md` (build/serve/deploy contract; corrects the long-running confusion
  where `build_breast.py`, the GLB generator, was documented as the page build —
  the assembler is `tools/build.py`) and `CHANGELOG.md` (this file).
- Added `favicon.svg` + `<link rel="icon">` in `src/head_top.html` — kills the
  `/favicon.ico` 404 noted in C4.
- Verified: `tools/build.py --check` reproduces `index.html` byte-exact after the
  edit; local static serve returns 200 for `/`, `/favicon.svg` (image/svg+xml) and
  `audio/en/leaflet/step01.mp3`; `.github/workflows/pages.yml` parses and publishes
  repo root (built `index.html` included), same shape as the shipped FNAC workflow.
- Annotated tag `v0.9.0` created **locally** (C9 final gate not yet run, hence 0.9).
- Rollback: `git revert` this commit; `git tag -d v0.9.0`.

### C6 — Locale integrity — `5647dc4`
- `k80` step-prefix pattern was referenced by the language switcher but absent from
  all six locales, so every language showed English "Step N of M". Added `k80` to
  all six; both render paths route through one `stepPrefix()`. Key parity 105/105.
- Known issue left open: `nan.json` byte-identical to `zh.json` (Hokkien is Mandarin)
  — needs a native translator; do not ship a "Hokkien" claim until replaced.
- Rollback: `git revert 5647dc4`.

### C5 — 3D scene correctness — `e2e53c4`
- Probe foot was buried ~2.6 cm inside the breast (min-z face seating); `seatProbe`
  now seats the max-z face at the most anterior point within 2 cm of the lesion,
  tilted onto the local surface normal. Needle path/depth, dressing, clip and
  faceless-bust checks all PASS by raycast + screenshots.
- Rollback: `git revert e2e53c4`.

### C4 — Performance — `094cdde`
- English narration de-inlined to lazy `audio/en/leaflet/*.mp3` like other locales.
  Document 2,625,654 → 1,767,782 B raw; gzip wire 1,260,645 → 628,442 B (−50.2 %);
  DCL 130 → 52 ms. `--standalone` still produces the old inline single-file build.
- Rollback: `git revert 094cdde` (restores inlined English audio).

### C3 — Accessibility + print — `be83449`
- Size/contrast prefs now persist (previously never saved); size-button labels
  translated (k259/k260 × 6 locales); fake tablist → group; full print stylesheet
  (black-on-white, outlined tick boxes, chrome hidden); 19/19 tap targets ≥ 44 px;
  contrast min 5.69 normal / 8.88 high-contrast.
- Rollback: `git revert be83449`.

### C2 — Copy pass — `8d92c30`
- Redundant k55 disclaimer trimmed in all 6 locales; ~30 Malay typo fixes +
  step-04 title; en k179 grammar. Clinical claims untouched; 10 flagged for Alex
  (see `~/AI-OS/docs/breast-overnight/C2-COPY-AUDIT-2026-11-15.md`).
- Rollback: `git revert 8d92c30`.

## Baseline — `53d8645` (2026-11-10, currently LIVE)
- Probe centred over lesion and seated on curved skin; mirrored intact torso,
  conforming dressing, standardised views. This commit (pre-C2) is what
  https://alexyap89.github.io/breast-biopsy-leaflet/ serves as of 2026-11-15.

## Deploy state (measured 2026-11-15, C8 run)
- `origin/main` = `53d8645`; local `main` = **5 ahead / 0 behind**; live HTTP 200
  serving the pre-C2 build (2,622,776 B; no `stepPrefix`/`k259` in served HTML).
- To ship: Alex runs `git push origin main --follow-tags`; Pages deploys automatically
  from `pages.yml`. To unship: revert on `main`, push, Pages redeploys.
