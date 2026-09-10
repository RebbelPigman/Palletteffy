# Palletteffy

A small PyQt5 app that remaps an image onto a user-defined palette. The default set is **Catppuccin Mocha** (26 official colours).

The UI follows system Qt5 settings: widget style, fonts, and colours come from the desktop (qt5ct, KDE, or the GTK platform theme). No Fusion or style override is applied.

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

Load and save dialogs open in `~/Pictures`.

1. **Load image** — PNG, JPEG, BMP, WebP, GIF, TIFF.
2. Edit the palette if you do not want the default Mocha set (see below).
3. **Palettize** — colours that belong together in the picture are grouped, then each group claims a different palette slot.
4. **Smooth edges** (on by default) — cleans speckles and crunchy outlines, then snaps every pixel back onto the palette. Uncheck for a hard posterized look.
5. **Save result** — writes a PNG (default name `~/Pictures/palettized.png`).

The cursor switches to a wait cursor while processing. Large photos take a while: mapping still walks every pixel in Python.

## Palette editor

Colours go in the text area, one per line. Accepted forms:

- `#rrggbb` — e.g. `#fab387`
- `#rgb` — e.g. `#f80` → `#ff8800`
- `R,G,B` or `rgb(R, G, B)` — components 0–255

`// comments` after a colour are ignored (the default list uses them for Mocha names). Duplicates are dropped.

The swatch row under the editor shows the parsed colours:

- **Left-click** a swatch to pick a new colour
- **Right-click** for Edit / Remove

**Reset palette** restores Catppuccin Mocha.

## How colours are chosen

Not raw RGB nearest-neighbour. That mapped pastel purple onto grey because the lightness was closer.

1. Convert each colour to **OKLCH** (lightness, chroma, hue).
2. Cluster the picture’s own colours: near-duplicates merge, distinct flats stay apart. A small region (a nose, a highlight) keeps its own group only if it is clearly different from every large flat.
3. Assign groups to palette slots with **one slot per group** while slots last. Larger flats choose first, so one popular palette colour cannot take every nearby region.
4. Distance used for those choices weights hue and chroma on colourful pixels and penalises dropping a colourful pixel onto a grey.

## Smooth edges

When the checkbox is on:

1. A very light blur on the source so noisy antialiased edges join their parent flat.
2. Palette mapping as above.
3. A 3×3 median filter to remove isolated pixels.
4. A slight Gaussian blur, then every pixel is snapped back to the nearest palette colour.

The saved image still contains only palette colours.

## Default palette (Catppuccin Mocha)

Official hex values, neutrals first, then accents from rosewater to lavender.

| # | Hex     | RGB             | Name       |
|---|---------|-----------------|------------|
| 1 | #11111b | 17, 17, 27      | crust      |
| 2 | #181825 | 24, 24, 37      | mantle     |
| 3 | #1e1e2e | 30, 30, 46      | base       |
| 4 | #313244 | 49, 50, 68      | surface0   |
| 5 | #45475a | 69, 71, 90      | surface1   |
| 6 | #585b70 | 88, 91, 112     | surface2   |
| 7 | #6c7086 | 108, 112, 134   | overlay0   |
| 8 | #7f849c | 127, 132, 156   | overlay1   |
| 9 | #9399b2 | 147, 153, 178   | overlay2   |
| 10 | #a6adc8 | 166, 173, 200  | subtext0   |
| 11 | #bac2de | 186, 194, 222  | subtext1   |
| 12 | #cdd6f4 | 205, 214, 244  | text       |
| 13 | #f5e0dc | 245, 224, 220  | rosewater  |
| 14 | #f2cdcd | 242, 205, 205  | flamingo   |
| 15 | #f5c2e7 | 245, 194, 231  | pink       |
| 16 | #cba6f7 | 203, 166, 247  | mauve      |
| 17 | #f38ba8 | 243, 139, 168  | red        |
| 18 | #eba0ac | 235, 160, 172  | maroon     |
| 19 | #fab387 | 250, 179, 135  | peach      |
| 20 | #f9e2af | 249, 226, 175  | yellow     |
| 21 | #a6e3a1 | 166, 227, 161  | green      |
| 22 | #94e2d5 | 148, 226, 213  | teal       |
| 23 | #89dceb | 137, 220, 235  | sky        |
| 24 | #74c7ec | 116, 199, 236  | sapphire   |
| 25 | #89b4fa | 137, 180, 250  | blue       |
| 26 | #b4befe | 180, 190, 254  | lavender   |

## Files

- `palletteffy.py` — the application
- `shell.nix` — Nix development shell (Python 3, PyQt5, Pillow, Qt5 Wayland, qt5ct)
- `readme.md` — this file
