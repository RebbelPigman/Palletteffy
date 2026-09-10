#!/usr/bin/env python3
"""Palletteffy — map every pixel of an image to the nearest colour in a palette."""

import math
import os
import re
import sys

from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Default 16-colour palette, shown as hex in the editor.
DEFAULT_PALETTE_TEXT = """\
#11111b
#1e1e2e
#cdd6f4
#b38465
#f38ba8
#d16c89
#fab387
#d89468
#f9e2af
#d8c190
#a6e3a1
#87c282
#89dceb
#89b4fa
#cba6f7
#ab87d5
"""

PICTURES_DIR = os.path.expanduser("~/Pictures")

_HEX = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
_RGB = re.compile(
    r"(?:rgb\s*\(\s*)?(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*\)?",
    re.IGNORECASE,
)


def parse_palette(text):
    """Parse hex (#rgb / #rrggbb) or R,G,B triples from free-form text."""
    colours = []
    seen = set()
    for raw in text.splitlines():
        candidate = raw.split("//", 1)[0].strip()
        if not candidate:
            continue

        hex_match = _HEX.search(candidate)
        if hex_match:
            h = hex_match.group(1)
            if len(h) == 3:
                h = "".join(ch * 2 for ch in h)
            rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        else:
            rgb_match = _RGB.search(candidate)
            if not rgb_match:
                continue
            rgb = tuple(int(x) for x in rgb_match.groups())
            if any(c > 255 for c in rgb):
                continue

        if rgb not in seen:
            seen.add(rgb)
            colours.append(rgb)
    return colours


def _srgb_to_oklab(rgb):
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = lin(rgb[0]), lin(rgb[1]), lin(rgb[2])
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = l ** (1.0 / 3.0), m ** (1.0 / 3.0), s ** (1.0 / 3.0)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    b = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, a, b


def _oklch(rgb):
    L, a, b = _srgb_to_oklab(rgb)
    C = math.hypot(a, b)
    H = math.atan2(b, a)
    return L, C, H


def _colour_distance(src_ok, pal_ok):
    """Hue-preserving OKLCH distance.

    RGB Euclidean (and even raw OKLab) maps pastel purple onto grey-lilac
    because lightness is closer. Penalise dropping chroma and weight hue
    for colourful pixels so flats stay in the same colour family.
    """
    L, C, H = src_ok
    Lp, Cp, Hp = pal_ok
    dL = L - Lp
    dC = C - Cp
    dH = abs(H - Hp)
    dH = min(dH, 2.0 * math.pi - dH)
    gray_pen = 0.0
    if C > 0.035 and Cp < C * 0.6:
        gray_pen = (C - Cp) * 3.0
    hue_w = min(8.0, 3.0 + 40.0 * C)
    return (
        dL * dL
        + 0.8 * dC * dC
        + hue_w * (dH * dH) * max(C, 0.01)
        + gray_pen
    )


def closest_colour(pixel, palette, palette_oklch=None):
    src_ok = _oklch(pixel[:3])
    if palette_oklch is None:
        palette_oklch = [_oklch(c) for c in palette]
    best = palette[0]
    best_d = None
    for colour, pal_ok in zip(palette, palette_oklch):
        d = _colour_distance(src_ok, pal_ok)
        if best_d is None or d < best_d:
            best_d = d
            best = colour
    return best


def palettize(im, palette):
    im = im.convert("RGB")
    palette_oklch = [_oklch(c) for c in palette]
    cache = {}
    pixels = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            src = pixels[x, y]
            mapped = cache.get(src)
            if mapped is None:
                mapped = closest_colour(src, palette, palette_oklch)
                cache[src] = mapped
            pixels[x, y] = mapped
    return im


def pil_to_pixmap(im):
    if im.mode != "RGB":
        im = im.convert("RGB")
    data = im.tobytes("raw", "RGB")
    qim = QImage(data, im.width, im.height, QImage.Format_RGB888)
    return QPixmap.fromImage(qim)


class SwatchBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self.setMinimumHeight(22)

    def set_colours(self, palette):
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for r, g, b in palette:
            chip = QFrame()
            chip.setFixedHeight(18)
            chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            chip.setToolTip("#{:02x}{:02x}{:02x}  ({}, {}, {})".format(r, g, b, r, g, b))
            chip.setStyleSheet(
                "background-color: rgb({},{},{}); border: 1px solid rgba(0,0,0,80);".format(
                    r, g, b
                )
            )
            self._layout.addWidget(chip)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Palletteffy")
        self.original = None
        self.result = None
        self._orig_pix = None
        self._res_pix = None

        self.lbl_orig = QLabel("Original")
        self.lbl_orig.setAlignment(Qt.AlignCenter)
        self.lbl_orig.setMinimumSize(320, 240)
        self.lbl_res = QLabel("Palettized")
        self.lbl_res.setAlignment(Qt.AlignCenter)
        self.lbl_res.setMinimumSize(320, 240)

        self.palette_edit = QPlainTextEdit()
        self.palette_edit.setPlainText(DEFAULT_PALETTE_TEXT)
        self.palette_edit.setPlaceholderText(
            "One colour per line: #rrggbb, #rgb, or R,G,B"
        )
        self.palette_edit.setTabChangesFocus(True)
        self.palette_edit.setMinimumHeight(160)
        self.palette_edit.textChanged.connect(self._on_palette_text_changed)

        self.swatches = SwatchBar()
        self.palette_status = QLabel()

        pal_label = QLabel("Palette")
        pal_hint = QLabel("#rrggbb  ·  #rgb  ·  R,G,B  —  one colour per line")
        pal_hint.setStyleSheet("color: palette(mid);")

        self.btn_load = QPushButton("Load image")
        self.btn_go = QPushButton("Palettize")
        self.btn_save = QPushButton("Save result")
        self.btn_reset_pal = QPushButton("Reset palette")
        self.btn_go.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.btn_load.clicked.connect(self.load)
        self.btn_go.clicked.connect(self.process)
        self.btn_save.clicked.connect(self.save)
        self.btn_reset_pal.clicked.connect(self._reset_palette)

        images = QHBoxLayout()
        images.addWidget(self.lbl_orig)
        images.addWidget(self.lbl_res)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_load)
        buttons.addWidget(self.btn_go)
        buttons.addWidget(self.btn_save)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_reset_pal)

        pal_col = QVBoxLayout()
        pal_col.setSpacing(4)
        pal_col.addWidget(pal_label)
        pal_col.addWidget(pal_hint)
        pal_col.addWidget(self.palette_edit)
        pal_col.addWidget(self.swatches)
        pal_col.addWidget(self.palette_status)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(images, 1)
        layout.addLayout(pal_col)
        layout.addLayout(buttons)
        self.setCentralWidget(central)

        self._on_palette_text_changed()

    def _reset_palette(self):
        self.palette_edit.setPlainText(DEFAULT_PALETTE_TEXT)

    def _on_palette_text_changed(self):
        palette = parse_palette(self.palette_edit.toPlainText())
        self.swatches.set_colours(palette)
        n = len(palette)
        if n == 0:
            self.palette_status.setText("No valid colours — add #rrggbb or R,G,B values.")
        elif n == 1:
            self.palette_status.setText("1 colour")
        else:
            self.palette_status.setText("{} colours".format(n))

    def current_palette(self):
        return parse_palette(self.palette_edit.toPlainText())

    def _fit(self, pix, label):
        label.setPixmap(
            pix.scaled(
                label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._orig_pix is not None:
            self._fit(self._orig_pix, self.lbl_orig)
        if self._res_pix is not None:
            self._fit(self._res_pix, self.lbl_res)

    def load(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open image",
            PICTURES_DIR,
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.tif *.tiff)",
        )
        if not path:
            return
        self.original = Image.open(path)
        self._orig_pix = pil_to_pixmap(self.original)
        self._fit(self._orig_pix, self.lbl_orig)
        self.lbl_res.clear()
        self.lbl_res.setText("Palettized")
        self._res_pix = None
        self.result = None
        self.btn_go.setEnabled(True)
        self.btn_save.setEnabled(False)

    def process(self):
        if self.original is None:
            return
        palette = self.current_palette()
        if not palette:
            QMessageBox.warning(
                self,
                "Empty palette",
                "The palette has no valid colours.\n"
                "Enter #rrggbb, #rgb, or R,G,B values, one per line.",
            )
            return
        self.btn_go.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            self.result = palettize(self.original.copy(), palette)
            self._res_pix = pil_to_pixmap(self.result)
            self._fit(self._res_pix, self.lbl_res)
            self.btn_save.setEnabled(True)
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_go.setEnabled(True)

    def save(self):
        if self.result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save palettized image",
            os.path.join(PICTURES_DIR, "palettized.png"),
            "PNG (*.png)",
        )
        if path:
            self.result.save(path)


if __name__ == "__main__":
    # Honour the desktop's Qt5 style, fonts, and colour scheme
    # (qt5ct, KDE, GTK platform theme, etc.). Do not force a style.
    QApplication.setDesktopSettingsAware(True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Palletteffy")
    w = Window()
    w.resize(960, 720)
    w.show()
    sys.exit(app.exec_())
