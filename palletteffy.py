#!/usr/bin/env python3
"""Palletteffy — map every pixel of an image to the nearest colour in a palette."""

import math
import os
import re
import sys

from PIL import Image, ImageFilter
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Default palette: Catppuccin Mocha (official names as comments).
DEFAULT_PALETTE_TEXT = """\
#11111b // crust
#181825 // mantle
#1e1e2e // base
#313244 // surface0
#45475a // surface1
#585b70 // surface2
#6c7086 // overlay0
#7f849c // overlay1
#9399b2 // overlay2
#a6adc8 // subtext0
#bac2de // subtext1
#cdd6f4 // text
#f5e0dc // rosewater
#f2cdcd // flamingo
#f5c2e7 // pink
#cba6f7 // mauve
#f38ba8 // red
#eba0ac // maroon
#fab387 // peach
#f9e2af // yellow
#a6e3a1 // green
#94e2d5 // teal
#89dceb // sky
#74c7ec // sapphire
#89b4fa // blue
#b4befe // lavender
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


def _line_has_colour(line):
    candidate = line.split("//", 1)[0].strip()
    if not candidate:
        return False
    if _HEX.search(candidate):
        return True
    m = _RGB.search(candidate)
    return bool(m) and all(int(x) <= 255 for x in m.groups())


def rewrite_palette_colour(text, index, new_rgb=None):
    """Replace or delete the index-th colour line. None deletes it."""
    lines = text.splitlines(True)
    found = 0
    out = []
    for line in lines:
        if not _line_has_colour(line):
            out.append(line)
            continue
        if found != index:
            out.append(line)
            found += 1
            continue
        found += 1
        if new_rgb is None:
            continue
        hex_ = "#{:02x}{:02x}{:02x}".format(*new_rgb)
        nl = "\n" if line.endswith("\n") else ""
        if "//" in line:
            comment = line.split("//", 1)[1]
            if comment.endswith("\n"):
                comment = comment[:-1]
                nl = "\n"
            out.append("{} //{}\n".format(hex_, comment) if nl else "{} //{}".format(hex_, comment))
        else:
            out.append(hex_ + nl)
    return "".join(out)


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


def closest_colour(pixel, palette, palette_oklch=None, used=None):
    src_ok = _oklch(pixel[:3])
    if palette_oklch is None:
        palette_oklch = [_oklch(c) for c in palette]
    best = palette[0]
    best_d = None
    for i, (colour, pal_ok) in enumerate(zip(palette, palette_oklch)):
        if used is not None and used[i]:
            continue
        d = _colour_distance(src_ok, pal_ok)
        if best_d is None or d < best_d:
            best_d = d
            best = colour
    if best_d is None and used is not None:
        return closest_colour(pixel, palette, palette_oklch, used=None)
    return best


# Merge source colours closer than this into one in-picture group.
_CLUSTER_MERGE = 0.012
# A small group keeps its own slot if it is farther than this from every major.
_CLUSTER_DISTINCT = 0.045
# Groups below this share of pixels fold into a nearby major, unless distinct.
_CLUSTER_MINOR = 0.002


def _cluster_image_colours(im):
    """Group the picture's own colours: near-duplicates merge, real flats stay apart."""
    w, h = im.size
    total = w * h
    listed = im.getcolors(total)
    if not listed:
        return [], total
    items = sorted(((n, rgb) for n, rgb in listed), reverse=True)
    clusters = []
    for n, rgb in items:
        rgb = rgb[:3]
        ok = _oklch(rgb)
        best_i = None
        best_d = None
        for i, cl in enumerate(clusters):
            d = _colour_distance(ok, cl["ok"])
            if best_d is None or d < best_d:
                best_d = d
                best_i = i
        if best_d is not None and best_d < _CLUSTER_MERGE:
            cl = clusters[best_i]
            cl["count"] += n
            cl["members"][rgb] = cl["members"].get(rgb, 0) + n
        else:
            clusters.append(
                {"rep": rgb, "ok": ok, "count": n, "members": {rgb: n}}
            )

    floor = max(32, int(_CLUSTER_MINOR * total))
    majors = [cl for cl in clusters if cl["count"] >= floor]
    minors = [cl for cl in clusters if cl["count"] < floor]
    if not majors:
        majors, minors = clusters, []

    kept = []
    absorbed = []
    for cl in minors:
        dmin = min(_colour_distance(cl["ok"], m["ok"]) for m in majors)
        if dmin > _CLUSTER_DISTINCT:
            kept.append(cl)
        else:
            absorbed.append(cl)
    majors.extend(kept)
    for cl in absorbed:
        nearest = min(majors, key=lambda m: _colour_distance(cl["ok"], m["ok"]))
        nearest["count"] += cl["count"]
        for rgb, n in cl["members"].items():
            nearest["members"][rgb] = nearest["members"].get(rgb, 0) + n
    majors.sort(key=lambda cl: -cl["count"])
    return majors, total


def _assign_groups_to_palette(groups, palette, palette_oklch):
    """Give each in-picture group its own palette slot while slots last.

    Larger flats choose first, so one popular palette colour cannot take
    every group that happens to be nearest to it.
    """
    used = [False] * len(palette)
    for cl in groups:
        best_i = None
        best_d = None
        for i, pal_ok in enumerate(palette_oklch):
            if used[i]:
                continue
            d = _colour_distance(cl["ok"], pal_ok)
            if best_d is None or d < best_d:
                best_d = d
                best_i = i
        if best_i is None:
            best_i = min(
                range(len(palette)),
                key=lambda i: _colour_distance(cl["ok"], palette_oklch[i]),
            )
        else:
            used[best_i] = True
        cl["pal"] = palette[best_i]


def _resnap_to_palette(im, palette, palette_oklch):
    pixels = im.load()
    w, h = im.size
    cache = {}
    for y in range(h):
        for x in range(w):
            src = pixels[x, y]
            mapped = cache.get(src)
            if mapped is None:
                mapped = closest_colour(src, palette, palette_oklch)
                cache[src] = mapped
            pixels[x, y] = mapped
    return im


def _soften_in_palette(im, palette, palette_oklch):
    """Knock out speckles and round jagged flats, then snap back to the palette."""
    im = im.filter(ImageFilter.MedianFilter(size=3))
    im = _resnap_to_palette(im, palette, palette_oklch)
    im = im.filter(ImageFilter.GaussianBlur(radius=0.7))
    return _resnap_to_palette(im, palette, palette_oklch)


def palettize(im, palette, smooth=True):
    im = im.convert("RGB")
    if smooth:
        im = im.filter(ImageFilter.GaussianBlur(radius=0.55))
    palette_oklch = [_oklch(c) for c in palette]
    groups, _total = _cluster_image_colours(im)
    lut = {}
    if groups:
        _assign_groups_to_palette(groups, palette, palette_oklch)
        for cl in groups:
            dest = cl["pal"]
            for rgb in cl["members"]:
                lut[rgb] = dest

    pixels = im.load()
    w, h = im.size
    cache = dict(lut)
    for y in range(h):
        for x in range(w):
            src = pixels[x, y]
            mapped = cache.get(src)
            if mapped is None:
                mapped = closest_colour(src, palette, palette_oklch)
                cache[src] = mapped
            pixels[x, y] = mapped
    if smooth:
        im = _soften_in_palette(im, palette, palette_oklch)
    return im


def pil_to_pixmap(im):
    if im.mode != "RGB":
        im = im.convert("RGB")
    data = im.tobytes("raw", "RGB")
    qim = QImage(data, im.width, im.height, QImage.Format_RGB888)
    return QPixmap.fromImage(qim)


class SwatchChip(QFrame):
    edit_requested = pyqtSignal(int)
    remove_requested = pyqtSignal(int)

    def __init__(self, index, rgb, parent=None):
        super().__init__(parent)
        self._index = index
        r, g, b = rgb
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setToolTip(
            "#{:02x}{:02x}{:02x}  ({}, {}, {})\n"
            "Left-click to edit · right-click to remove".format(r, g, b, r, g, b)
        )
        self.setStyleSheet(
            "background-color: rgb({},{},{}); border: 1px solid rgba(0,0,0,80);".format(
                r, g, b
            )
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.edit_requested.emit(self._index)
            event.accept()
            return
        if event.button() == Qt.RightButton:
            menu = QMenu(self)
            act_edit = menu.addAction("Edit colour…")
            act_remove = menu.addAction("Remove colour")
            chosen = menu.exec_(event.globalPos())
            if chosen is act_edit:
                self.edit_requested.emit(self._index)
            elif chosen is act_remove:
                self.remove_requested.emit(self._index)
            event.accept()
            return
        super().mousePressEvent(event)


class SwatchBar(QWidget):
    edit_requested = pyqtSignal(int)
    remove_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self.setMinimumHeight(24)

    def set_colours(self, palette):
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for i, rgb in enumerate(palette):
            chip = SwatchChip(i, rgb)
            chip.edit_requested.connect(self.edit_requested)
            chip.remove_requested.connect(self.remove_requested)
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
        self.swatches.edit_requested.connect(self._edit_swatch)
        self.swatches.remove_requested.connect(self._remove_swatch)
        self.palette_status = QLabel()

        pal_label = QLabel("Palette")
        pal_hint = QLabel(
            "#rrggbb  ·  #rgb  ·  R,G,B  —  click a swatch to edit, right-click to remove"
        )
        pal_hint.setStyleSheet("color: palette(mid);")

        self.btn_load = QPushButton("Load image")
        self.btn_go = QPushButton("Palettize")
        self.btn_save = QPushButton("Save result")
        self.btn_reset_pal = QPushButton("Reset palette")
        self.chk_smooth = QCheckBox("Smooth edges")
        self.chk_smooth.setChecked(True)
        self.chk_smooth.setToolTip(
            "Median + slight blur, then snap back to the palette. "
            "Cuts speckles and crunchy outlines. Uncheck for a hard posterized look."
        )
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
        buttons.addWidget(self.chk_smooth)
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

    def _set_palette_text(self, text):
        cursor_pos = self.palette_edit.textCursor().position()
        self.palette_edit.blockSignals(True)
        self.palette_edit.setPlainText(text)
        self.palette_edit.blockSignals(False)
        cursor = self.palette_edit.textCursor()
        cursor.setPosition(min(cursor_pos, len(text)))
        self.palette_edit.setTextCursor(cursor)
        self._on_palette_text_changed()

    def _edit_swatch(self, index):
        palette = self.current_palette()
        if index < 0 or index >= len(palette):
            return
        r, g, b = palette[index]
        colour = QColorDialog.getColor(
            QColor(r, g, b),
            self,
            "Edit palette colour",
        )
        if not colour.isValid():
            return
        new_rgb = (colour.red(), colour.green(), colour.blue())
        if new_rgb == (r, g, b):
            return
        text = rewrite_palette_colour(
            self.palette_edit.toPlainText(), index, new_rgb
        )
        self._set_palette_text(text)

    def _remove_swatch(self, index):
        palette = self.current_palette()
        if index < 0 or index >= len(palette):
            return
        text = rewrite_palette_colour(
            self.palette_edit.toPlainText(), index, None
        )
        self._set_palette_text(text)

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
            self.result = palettize(
                self.original.copy(),
                palette,
                smooth=self.chk_smooth.isChecked(),
            )
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
