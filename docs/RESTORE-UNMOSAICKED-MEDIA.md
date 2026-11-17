# Un-mosaicked media — archive and revert

Alex's instruction (2026-11-16): keep the version **without** the nipple mosaic in case we
want to revert.

## Where the un-mosaicked set lives

```
~/AI-OS/workspace/breast-media/archive_nomosaic/assets/
    b4_lido.jpg  b5_nick.jpg  b6_needle.jpg  b8_dressing.jpg
    m4_lido.mp4  m6_needle.mp4  m8_dressing.mp4
```

Kept **outside** the published site folder on purpose — the GitHub Pages deploy publishes the
repo root, so an `assets-nomosaic/` folder inside the project would be served publicly. The
canonical copy is also git history: commit **50996ba** (the last build before the mosaic).

## How to revert

1. Copy the files back over the live ones:
   ```
   cp ~/AI-OS/workspace/breast-media/archive_nomosaic/assets/* \
      "/Users/agents/My Drive/20_Projects/Radiology/01-Active/Breast Biopsy/assets/"
   ```
2. Bump the media version in `src2/app_media.js` (`?v=15` → `?v=16`) so no browser serves
   the mosaicked frames from cache.
3. `python3 tools/build2.py` and commit.

Equivalently, restore from git: `git checkout 50996ba -- assets/b4_lido.jpg …` then steps 2–3.

## Mosaic spec (if you want to re-apply)

`~/AI-OS/workspace/breast-media/apply_mosaic.py` — blocky pixelation, feather 6 px, centred on
the standardised areola point (60 %, 58 %), radius 6.2 % of width, block 1.4 % of width.
Applied to the four stills and the three clips; areola stays readable, instruments untouched.
