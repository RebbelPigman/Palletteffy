# Palletteffy

A small PyQt5 app that remaps every pixel of an image to the nearest colour in a user-defined palette. The default set is the classic 16-colour CGA/EGA palette.

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
2. Edit the **Palette** box if you do not want the default CGA/EGA set.
3. **Palettize** — each pixel is replaced by the closest RGB colour in the current palette (squared Euclidean distance).
4. **Save result** — writes a PNG.

Large images are processed in a nested Python loop, so expect a wait on big photos. The cursor switches to a wait cursor while that runs.

## Palette input

Colours go in the text area, one per line. Accepted forms:

- `#rrggbb` — e.g. `#aa5500`
- `#rgb` — e.g. `#f80` → `#ff8800`
- `R,G,B` or `rgb(R, G, B)` — components 0–255

`// comments` on a line are ignored. Duplicates are dropped. The swatch row under the editor shows the parsed colours. **Reset palette** restores the default CGA/EGA set.

Default set (CGA / EGA):

| Colour        | Hex     | RGB            |
|---------------|---------|----------------|
| black         | #000000 | 0, 0, 0        |
| blue          | #0000aa | 0, 0, 170      |
| green         | #00aa00 | 0, 170, 0      |
| cyan          | #00aaaa | 0, 170, 170    |
| red           | #aa0000 | 170, 0, 0      |
| magenta       | #aa00aa | 170, 0, 170    |
| brown         | #aa5500 | 170, 85, 0     |
| light gray    | #aaaaaa | 170, 170, 170  |
| dark gray     | #555555 | 85, 85, 85     |
| light blue    | #5555ff | 85, 85, 255    |
| light green   | #55ff55 | 85, 255, 85    |
| light cyan    | #55ffff | 85, 255, 255   |
| light red     | #ff5555 | 255, 85, 85    |
| light magenta | #ff55ff | 255, 85, 255   |
| yellow        | #ffff55 | 255, 255, 85   |
| white         | #ffffff | 255, 255, 255  |

## Files

- `palletteffy.py` — the application
- `shell.nix` — Nix development shell (Python 3, PyQt5, Pillow, Qt5 Wayland, qt5ct)
- `readme.md` — this file
