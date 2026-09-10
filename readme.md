# Palletteffy

A small PyQt5 app that remaps every pixel of an image to the nearest colour in a user-defined palette. The default set is a 16-colour dark theme palette.

The UI follows system Qt5 settings: widget style, fonts, and colours come from the desktop (qt5ct, KDE, or the GTK platform theme). No Fusion/style override is applied.

## Requirements

- Nix (for `shell.nix`), or Python 3 with `PyQt5` and `Pillow`
- A display (Wayland or X11). On Wayland compositors such as Niri, `qtwayland` is included in the Nix shell.

## Run with Nix

From this directory:

```bash
nix-shell
python palletteffy.py
```

Or in one shot:

```bash
nix-shell --run "python palletteffy.py"
```

The Nix shell sets `QT_QPA_PLATFORMTHEME=qt5ct` when that variable is not already set, so existing qt5ct / KDE configuration is used.

## Run without Nix

```bash
pip install PyQt5 Pillow
python palletteffy.py
```

Leave `QT_STYLE_OVERRIDE` unset so the desktop theme applies.

## Usage

1. **Load image** — PNG, JPEG, BMP, WebP, GIF, TIFF.
2. Edit the **Palette** box if you do not want the default set.
3. **Palettize** — the picture’s own colours are grouped first, then each group claims a different palette slot (largest flats first, OKLCH hue/chroma distance). That stops one palette colour from swallowing every nearby region.
4. **Save result** — writes a PNG.

Large images are processed in a nested Python loop, so expect a wait on big photos. The cursor switches to a wait cursor while that runs.

## Palette input

Colours go in the text area, one per line. Accepted forms:

- `#rrggbb` — e.g. `#aa5500`
- `#rgb` — e.g. `#f80` → `#ff8800`
- `R,G,B` or `rgb(R, G, B)` — components 0–255

`// comments` on a line are ignored. Duplicates are dropped. The swatch row under the editor shows the parsed colours. **Reset palette** restores the default set.

Default set:

| # | Hex     | RGB             | Group          |
|---|---------|-----------------|----------------|
| 1 | #11111b | 17, 17, 27      | dark           |
| 2 | #1e1e2e | 30, 30, 46      | dark           |
| 3 | #cdd6f4 | 205, 214, 244   | paper          |
| 4 | #b38465 | 179, 132, 101   | brown          |
| 5 | #f38ba8 | 243, 139, 168   | pink           |
| 6 | #d16c89 | 209, 108, 137   | pink (dark)    |
| 7 | #fab387 | 250, 179, 135   | peach          |
| 8 | #d89468 | 216, 148, 104   | peach (dark)   |
| 9 | #f9e2af | 249, 226, 175   | yellow         |
| 10 | #d8c190 | 216, 193, 144  | yellow (dark)  |
| 11 | #a6e3a1 | 166, 227, 161  | green          |
| 12 | #87c282 | 135, 194, 130  | green (dark)   |
| 13 | #89dceb | 137, 220, 235  | sky            |
| 14 | #89b4fa | 137, 180, 250  | blue           |
| 15 | #cba6f7 | 203, 166, 247  | mauve          |
| 16 | #ab87d5 | 171, 135, 213  | mauve (dark)   |

## Files

- `palletteffy.py` — the application
- `shell.nix` — Nix development shell (Python 3, PyQt5, Pillow, Qt5 Wayland, qt5ct)
- `readme.md` — this file
