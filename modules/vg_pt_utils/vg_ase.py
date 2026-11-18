##########################################################################
#
# Copyright 2010-2024 Vincent GAULT - Adobe
# All Rights Reserved.
#
##########################################################################

"""
Reader for Adobe Swatch Exchange (.ase) files, as exported by Adobe Color.
Pure Python (no Painter / Qt dependency): returns plain sRGB tuples.
"""
__author__ = "Vincent GAULT - Adobe"

import struct

_VALUES_PER_MODEL = {"RGB ": 3, "CMYK": 4, "LAB ": 3, "GRAY": 1}
_BLOCK_COLOR = 0x0001


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _lab_to_srgb(l, a, b):
    """CIE Lab (D65) → sRGB floats in [0, 1]."""
    fy = (l + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def finv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16.0 / 116.0) / 7.787

    x, y, z = finv(fx) * 0.95047, finv(fy), finv(fz) * 1.08883
    r = 3.2406 * x - 1.5372 * y - 0.4986 * z
    g = -0.9689 * x + 1.8758 * y + 0.0415 * z
    bl = 0.0557 * x - 0.2040 * y + 1.0570 * z

    def gamma(c):
        c = _clamp01(c)
        return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055

    return gamma(r), gamma(g), gamma(bl)


def _to_srgb(model, vals):
    if model == "RGB ":
        return tuple(_clamp01(v) for v in vals)
    if model == "GRAY":
        g = _clamp01(vals[0])
        return g, g, g
    if model == "CMYK":
        c, m, y, k = (_clamp01(v) for v in vals)
        return (1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)
    if model == "LAB ":
        # ASE stores L as 0-1; a and b are already in their natural range
        return _lab_to_srgb(vals[0] * 100.0, vals[1], vals[2])
    return None


def parse_ase(path):
    """Return [(name, (r, g, b))] with sRGB floats in [0, 1], in file order. Raises ValueError."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 12 or data[:4] != b"ASEF":
        raise ValueError("Not an Adobe Swatch Exchange (.ase) file")

    block_count = struct.unpack_from(">I", data, 8)[0]
    pos = 12
    colors = []
    for _ in range(block_count):
        if pos + 6 > len(data):
            break
        block_type, length = struct.unpack_from(">HI", data, pos)
        pos += 6
        end = pos + length
        if block_type == _BLOCK_COLOR:
            try:
                name_len = struct.unpack_from(">H", data, pos)[0]
                p = pos + 2
                name = data[p:p + name_len * 2].decode("utf-16-be", errors="replace").rstrip("\x00")
                p += name_len * 2
                model = data[p:p + 4].decode("ascii", errors="replace").upper()
                p += 4
                count = _VALUES_PER_MODEL.get(model)
                if count:
                    rgb = _to_srgb(model, struct.unpack_from(">" + "f" * count, data, p))
                    if rgb:
                        colors.append((name, rgb))
            except struct.error:
                pass
        pos = end
    return colors
