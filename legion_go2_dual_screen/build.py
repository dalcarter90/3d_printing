"""Build the Legion Go 2 version of davolesh's "Lenovo Legion Go Dual Screen".

Inputs (source/):
  thingiverse_7291595/Legion_Go_Monitor_Holder_-_REV_2.stl  monitor holder (Go 1)
  legion_go2_protective_case/Legion Model REV4 PETG.stl     Go 2 case

Outputs (stl/):
  Legion_Go_2_Case_with_Hinge.stl     Go 2 case with the three hinge tabs added
  Legion_Go_2_Monitor_Holder.stl      holder with its outer knuckles moved in

Every dimension below was measured from the original REV 2 STLs, which share
one assembly frame: X along the long edge, Y up toward the top edge, Z toward
the back of the device. The original pivot axis is at Y=146.5, Z=-18.7.

Run:  python3 build.py   (needs trimesh, manifold3d, shapely, numpy)
"""
import os

import numpy as np
import shapely.geometry as sg
import shapely.ops as so
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_HOLDER = os.path.join(HERE, "source/thingiverse_7291595/Legion_Go_Monitor_Holder_-_REV_2.stl")
SRC_CASE = os.path.join(HERE, "source/legion_go2_protective_case/Legion Model REV4 PETG.stl")
OUT_CASE = os.path.join(HERE, "stl/Legion_Go_2_Case_with_Hinge.stl")
OUT_HOLDER = os.path.join(HERE, "stl/Legion_Go_2_Monitor_Holder.stl")

# --- Original (Go 1) REV 2 case -------------------------------------------
GO1_CASE_X = (-105.09, 105.75)    # case is flush with the 210 mm tablet
GO1_TOP_OUTER_Y = 137.542         # outer face of the top wall
GO1_FRONT_Z = -12.602             # front (screen side) lip
GO1_PIVOT = (146.5, -18.7)        # (Y, Z) of the hinge bolt axis
# Tabs as (x_min, x_max); each sits in a 4.4 / 3.8 mm gap between knuckles.
GO1_TABS = {"left": (-103.06, -99.06), "middle": (-4.06, -0.65), "right": (99.74, 103.74)}
TAB_BOSS_R = 7.35                 # outer radius of the round boss at the pivot
TAB_HOLE_D = 4.0                  # bolt hole in the case tabs (M4)

# --- Go 2 case (MakerWorld "Legion Go 2 Protective Case", REV4 PETG) ------
GO2_CASE_X = (0.0, 206.0)         # flush with the 206 mm Go 2 tablet
GO2_TOP_OUTER_Y = 139.033
GO2_FRONT_Z = -2.778
GO2_BACK_Z = 25.596

# Keep the hinge centred on the tablet ...
DX = sum(GO2_CASE_X) / 2 - sum(GO1_CASE_X) / 2
# ... and keep the outer hinges the same distance in from the tablet edges.
EDGE_SHIFT = ((GO1_CASE_X[1] - GO1_CASE_X[0]) - (GO2_CASE_X[1] - GO2_CASE_X[0])) / 2
# Pivot keeps the same offset from the case's top-front corner as on the Go 1.
PIVOT = (GO2_TOP_OUTER_Y + (GO1_PIVOT[0] - GO1_TOP_OUTER_Y),
         GO2_FRONT_Z + (GO1_PIVOT[1] - GO1_FRONT_Z))
DY = PIVOT[0] - GO1_PIVOT[0]
DZ = PIVOT[1] - GO1_PIVOT[1]

TAB_X = {
    "left": tuple(x + DX + EDGE_SHIFT for x in GO1_TABS["left"]),
    "middle": tuple(x + DX for x in GO1_TABS["middle"]),
    "right": tuple(x + DX - EDGE_SHIFT for x in GO1_TABS["right"]),
}


def tab_profile():
    """Side profile (Y, Z) of one hinge tab, the same shape as the original:
    a fin hugging the top wall from the back plate to the front lip that
    tapers out to a round boss around the pivot."""
    wall_overlap = 1.0   # sink into the 2 mm top wall so the union fuses
    top_width = 2.0      # fin thickness beyond the wall at the back plate
    y0 = GO2_TOP_OUTER_Y - wall_overlap
    wall_strip = sg.box(y0, GO2_FRONT_Z, GO2_TOP_OUTER_Y, GO2_BACK_Z)
    back_corner = sg.box(y0, GO2_BACK_Z - top_width, GO2_TOP_OUTER_Y + top_width, GO2_BACK_Z)
    boss = sg.Point(PIVOT).buffer(TAB_BOSS_R, quad_segs=32)
    fin = so.unary_union([wall_strip, back_corner, boss]).convex_hull
    fin = fin.difference(sg.Point(PIVOT).buffer(TAB_HOLE_D / 2, quad_segs=24))
    # Never reach into the tablet pocket or stick out behind the back plate.
    return fin.intersection(sg.box(y0, -100, 300, GO2_BACK_Z))


def make_tab(x_range, profile):
    # Extrude the (Y, Z) profile along +Z, then rotate so extrusion runs along X.
    m = trimesh.creation.extrude_polygon(profile, height=x_range[1] - x_range[0])
    # (y, z, w) -> (w, y, z) is a cyclic axis swap, so face winding stays valid.
    m.vertices = m.vertices[:, [2, 0, 1]]
    m.apply_translation([x_range[0], 0, 0])
    return m


def build_case():
    case = trimesh.load(SRC_CASE)
    profile = tab_profile()
    tabs = [make_tab(TAB_X[k], profile) for k in ("left", "middle", "right")]
    out = trimesh.boolean.union([case] + tabs, engine="manifold")
    return out, tabs


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def build_holder():
    """Move the outer knuckle pairs EDGE_SHIFT mm toward the centre.

    The forks (|x| > 94, y > 126) move rigidly. The weight fades to zero by
    |x| = 45 and y = 60, so the four monitor mounting holes at x = -32 / 44,
    y = 19 / 95 (and the middle knuckles) do not move."""
    h = trimesh.load(SRC_HOLDER)
    v = h.vertices.copy()
    cx = sum(GO1_CASE_X) / 2
    rel = v[:, 0] - cx
    w = smoothstep((np.abs(rel) - 45.0) / (90.0 - 45.0)) * smoothstep((v[:, 1] - 60.0) / (126.0 - 60.0))
    v[:, 0] -= np.sign(rel) * EDGE_SHIFT * w
    h.vertices = v
    return h


def to_assembly(holder):
    """Holder moved into the Go 2 case's frame (closed position)."""
    m = holder.copy()
    m.apply_translation([DX, DY, DZ])
    return m


def print_ready(mesh, flip):
    """Copy of `mesh` sitting on the bed at the origin. `flip` turns it over
    about X so the back plate is on the bed and the hinge tabs point up."""
    m = mesh.copy()
    if flip:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    m.apply_translation(-m.bounds[0])
    return m


def main():
    os.makedirs(os.path.dirname(OUT_CASE), exist_ok=True)
    case, _ = build_case()
    holder = build_holder()
    assert case.is_watertight and holder.is_watertight
    # Export in print orientation: case back-plate down, holder plate down.
    case = print_ready(case, flip=True)
    holder = print_ready(holder, flip=False)
    case.export(OUT_CASE)
    holder.export(OUT_HOLDER)
    print(f"pivot (Y,Z) = ({PIVOT[0]:.3f}, {PIVOT[1]:.3f}); DX={DX:.3f} DY={DY:.3f} DZ={DZ:.3f} edge shift={EDGE_SHIFT:.3f}")
    for k, (a, b) in TAB_X.items():
        print(f"tab {k:6s}: x {a:.2f} .. {b:.2f}")
    print(f"case:   {OUT_CASE}  extents {np.round(case.extents, 2)}  volume {case.volume / 1000:.1f} cm^3")
    print(f"holder: {OUT_HOLDER}  extents {np.round(holder.extents, 2)}  volume {holder.volume / 1000:.1f} cm^3")


if __name__ == "__main__":
    main()
