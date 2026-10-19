"""Per-picture pixel diff of two folders of screenshots that share file names.

usage: pixel_diff.py BEFORE AFTER [--mask x0,y0,x1,y1 ...]

Masks are boxes ignored in every picture (real-time animations you cannot freeze).
Prints, per picture: pixels differing by more than 24 and by more than 60, the largest
difference, and the 40px cells holding differences above 120 as (x, y, count).
"""
import glob
import os
import sys

import numpy as np
from PIL import Image


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    before, after = argv[0], argv[1]
    masks = []
    rest = argv[2:]
    i = 0
    while i < len(rest):
        if rest[i] != '--mask' or i + 1 >= len(rest):
            sys.exit(f'unknown or incomplete argument: {rest[i]}')
        masks.append(tuple(int(v) for v in rest[i + 1].split(',')))
        i += 2
    for a in sorted(glob.glob(os.path.join(before, '*.png'))):
        name = os.path.basename(a)
        b = os.path.join(after, name)
        if not os.path.exists(b):
            print(name, 'missing in AFTER')
            continue
        x = np.asarray(Image.open(a).convert('RGB')).astype(int)
        y = np.asarray(Image.open(b).convert('RGB')).astype(int)
        if x.shape != y.shape:
            print(name, 'size differs', x.shape, y.shape)
            continue
        d = np.abs(x - y).max(axis=2)
        for x0, y0, x1, y1 in masks:
            d[y0:y1, x0:x1] = 0
        cells = {}
        ys, xs = np.nonzero(d > 120)
        for yy, xx in zip(ys, xs):
            key = (int(yy) // 40, int(xx) // 40)
            cells[key] = cells.get(key, 0) + 1
        hot = [(c[1] * 40, c[0] * 40, n) for c, n in sorted(cells.items())][:12]
        print(f'{name}  >24: {int((d > 24).sum())}  >60: {int((d > 60).sum())}  max {int(d.max())}  cells>120: {hot}')


if __name__ == '__main__':
    main(sys.argv[1:])
