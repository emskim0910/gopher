# GOPHER

Source for the GOPHER project site: a self-propelled, tethered unmanned underground vehicle by
Ethan M. Kim. Patent pending.

All rights reserved. The text, images and drawings here are published for viewing only. Nothing
in this repository is licensed for reuse.

## What ships

| Path | Contents |
| --- | --- |
| `index.html` | The whole page: overview, motion, architecture, missions, status, contact. Plain text, edit by hand. |
| `assets/style.css` | Colors, type and layout. |
| `assets/app.js` | The hero: draws a sequence of flat images as the page scrolls. |
| `assets/hero/f00.webp` to `f27.webp` | The vehicle exploded, then assembling, as 28 pre-rendered pictures from one fixed view. Exterior only, hidden lines removed, no perspective. |
| `assets/side-view.webp` | Side view of the assembled vehicle in true proportion, exterior only. |
| `assets/figures/*.webp` | Two schematic sheets of the filed patent drawings (advance cycle, mission plan) as raster line art. |
| `tools/check_protected.py`, `.githooks/pre-commit`, `.github/workflows/protect.yml` | The file-protection check (below). |

No build step and no bundler. To preview:

```bash
python -m http.server 8140
```

then open http://localhost:8140/.

## File protection

This repository is public, and so is every past version of it. The rule is simple: **pictures and
page text only, never design data.**

- No CAD, mesh, STEP, drawing-exchange, PDF, spreadsheet or archive file is here, and none may be added.
- The hero is not a 3D model. It is 28 flat images from one fixed view, with no scale and no
  coordinates, so there is no model file to download. Only outside surfaces are drawn; nothing
  inside the vehicle is shown. Like any picture, it still shows exterior proportions. The pictures
  are rendered offline; the model and the renderer are kept outside this repository.
- The two figures are raster copies of schematic drawings in the filed patent application. The
  detailed section and component drawings are not published.
- `.gitignore` denies everything except the files listed in it.
- `tools/check_protected.py` rejects forbidden file types (by name and by content), any file over
  400 KB, and any text containing a patent application number or a local disk path. It runs before
  every commit and again on GitHub for every push.

After cloning, turn the commit hook on once:

```bash
git config core.hooksPath .githooks
```

## Editing the text

Open `index.html`, change the words, save. Keep every statement to what the filed patent
specification and drawings say.
