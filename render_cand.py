"""Render a candidate AM5 mount mesh (mount only, no scope) for visual comparison.

Usage on host:  PYTHONPATH=src python -B render_cand.py <code.py> <out.png> [az] [el]
The candidate file must define build_part(C) (or build_mount(C)) using the same
primitives exposed by asiairbridge.mount_render.
"""
import math
import os
import sys

import numpy as np

from asiairbridge import mount_render as M

code_path, out_path = sys.argv[1], sys.argv[2]
if len(sys.argv) > 3:
    os.environ["MV_AZ"] = sys.argv[3]
if len(sys.argv) > 4:
    os.environ["MV_EL"] = sys.argv[4]

ns = {
    "np": np, "math": math,
    "cylinder": M.cylinder, "box": M.box, "disk": M.disk, "tube": M.tube,
    "rotmat": M.rotmat, "transform": M.transform, "_arr": M._arr,
}
exec(open(code_path, encoding="utf-8").read(), ns)
build_mount = ns.get("build_part") or ns.get("build_mount")

parts = []
apex = np.array([0, 0, 22.0])
for az in (90, 210, 330):
    foot = np.array([24 * math.cos(math.radians(az)), 24 * math.sin(math.radians(az)), 0.0])
    d = apex - foot
    L = float(np.linalg.norm(d))
    R = M._align_z(d / L)
    p, n = M.cylinder(1.3, 0.9, L, seg=14)
    parts.append((*M.transform(p, n, R, foot), (0.55, 0.57, 0.60)))
p, n = M.cylinder(4.6, 4.6, 2.2, seg=36)
parts.append((*M.transform(p, n, None, apex), (0.12, 0.13, 0.14)))

R_polar = M.rotmat("x", 40 - 90)
head_base = apex + np.array([0, 0, 2.2])
for P, N, col in build_mount(M.PALETTE):
    parts.append((*M.transform(P, N, R_polar, head_base), col))

png = M.render_png(parts, size=int(os.environ.get("MV_SIZE", "820")))
with open(out_path, "wb") as fh:
    fh.write(png)
print("rendered", out_path, len(png), "bytes")
