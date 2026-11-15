# Changelog — breast-biopsy-leaflet

Newest first. Each entry: what changed, how verified, and how to roll it back.
Rollback of any single entry: `git revert <commit>` then rebuild
(`python3 tools/build.py`). Rollback of everything: `git checkout <previous tag>`.
Nothing below is live until Alex pushes `main` and GitHub Pages redeploys.

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
