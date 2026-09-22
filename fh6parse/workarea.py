"""Machine travel vs programmed work: allowed work-offset origin box in G53 mm."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import math
import tempfile

from .machtime import MachineProfile, to_mm

Vec3 = tuple[float, float, float]
Plane = tuple[Vec3, float]
PoseBC = tuple[float, float]


@dataclass
class WorkBBox:
    """Programmed work-coordinate extents (program units)."""

    min_x: float | None = None
    max_x: float | None = None
    min_y: float | None = None
    max_y: float | None = None
    min_z: float | None = None
    max_z: float | None = None

    def add(
        self,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> None:
        if x is not None:
            self.min_x = x if self.min_x is None else min(self.min_x, x)
            self.max_x = x if self.max_x is None else max(self.max_x, x)
        if y is not None:
            self.min_y = y if self.min_y is None else min(self.min_y, y)
            self.max_y = y if self.max_y is None else max(self.max_y, y)
        if z is not None:
            self.min_z = z if self.min_z is None else min(self.min_z, z)
            self.max_z = z if self.max_z is None else max(self.max_z, z)

    def has_xy(self) -> bool:
        return None not in (self.min_x, self.max_x, self.min_y, self.max_y)

    def union(self, other: WorkBBox) -> WorkBBox:
        out = WorkBBox(
            self.min_x, self.max_x, self.min_y, self.max_y, self.min_z, self.max_z
        )
        out.add(other.min_x, other.min_y, other.min_z)
        out.add(other.max_x, other.max_y, other.max_z)
        return out


@dataclass(frozen=True)
class G54Window:
    """Where work offset origin may sit in G53 mm so the work AABB stays in travel."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float | None = None
    z_max: float | None = None
    fits: bool = True
    g54_inside: bool | None = None
    leftover_x: float = 0.0
    leftover_y: float = 0.0
    dwo: bool = False
    poses: tuple[PoseBC, ...] = ()

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0)

    @property
    def center_xyz(self) -> tuple[float, float, float] | None:
        if self.z_min is None or self.z_max is None:
            return None
        cx, cy = self.center
        return (cx, cy, (self.z_min + self.z_max) / 2.0)

    @property
    def max_tool_dia_mm(self) -> float | None:
        """Largest Ø whose tool axis still fits if the work AABB is centred.

        Outside G41/G42: leftover on +X and −X is one diameter. Skip when the
        uncompensated box already exceeds travel. Skip under DWO: leftover is
        the origin cube, not planar compensation at B0 C0.
        """
        if self.dwo:
            return None
        if self.leftover_x < -1e-9 or self.leftover_y < -1e-9:
            return None
        return min(self.leftover_x, self.leftover_y)

    @property
    def corners(self) -> tuple[tuple[float, float], ...]:
        """SW, SE, NE, NW in G53 (Y up)."""
        return (
            (self.x_min, self.y_min),
            (self.x_max, self.y_min),
            (self.x_max, self.y_max),
            (self.x_min, self.y_max),
        )

    @property
    def corners_xyz(self) -> tuple[Vec3, ...]:
        """Zmin SW/SE/NE/NW then Zmax SW/SE/NE/NW. Z=0 when the window has no Z."""
        z0 = 0.0 if self.z_min is None else self.z_min
        z1 = z0 if self.z_max is None else self.z_max
        return tuple((x, y, z) for z in (z0, z1) for x, y in self.corners)


def _ordered(a: float, b: float) -> tuple[float, float]:
    return (a, b) if a <= b else (b, a)


def _work_mm(bbox: WorkBBox, *, inch: bool) -> tuple[float, float, float, float, float, float]:
    wx0 = to_mm(bbox.min_x or 0.0, inch=inch)
    wx1 = to_mm(bbox.max_x or 0.0, inch=inch)
    wy0 = to_mm(bbox.min_y or 0.0, inch=inch)
    wy1 = to_mm(bbox.max_y or 0.0, inch=inch)
    wz0 = to_mm(bbox.min_z or 0.0, inch=inch)
    wz1 = to_mm(bbox.max_z or 0.0, inch=inch)
    if wx0 > wx1:
        wx0, wx1 = wx1, wx0
    if wy0 > wy1:
        wy0, wy1 = wy1, wy0
    if wz0 > wz1:
        wz0, wz1 = wz1, wz0
    return wx0, wx1, wy0, wy1, wz0, wz1


def _linear_window(
    mill: MachineProfile,
    bbox: WorkBBox,
    *,
    inch: bool = False,
) -> G54Window | None:
    if not mill.has_xy_travel() or not bbox.has_xy():
        return None
    wx0, wx1, wy0, wy1, wz0, wz1 = _work_mm(bbox, inch=inch)
    tx0, tx1 = _ordered(mill.x_min or 0.0, mill.x_max or 0.0)
    ty0, ty1 = _ordered(mill.y_min or 0.0, mill.y_max or 0.0)
    x_min = tx0 - wx0
    x_max = tx1 - wx1
    y_min = ty0 - wy0
    y_max = ty1 - wy1
    leftover_x = x_max - x_min
    leftover_y = y_max - y_min
    fits_x = leftover_x >= -1e-9
    fits_y = leftover_y >= -1e-9
    fits = fits_x and fits_y
    if not fits_x:
        x_min, x_max = x_max, x_min
    if not fits_y:
        y_min, y_max = y_max, y_min
    z_min = z_max = None
    if mill.has_z_travel() and bbox.min_z is not None and bbox.max_z is not None:
        tz0, tz1 = _ordered(mill.z_min or 0.0, mill.z_max or 0.0)
        length = mill.tool_length_mm
        z_min = tz0 - wz0 - length
        z_max = tz1 - wz1 - length
        if z_min > z_max:
            fits = False
            z_min, z_max = z_max, z_min
    inside = _origin_inside(
        mill, x_min, x_max, y_min, y_max, z_min, z_max, fits
    )
    return G54Window(
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
        z_min=z_min,
        z_max=z_max,
        fits=fits,
        g54_inside=inside,
        leftover_x=leftover_x,
        leftover_y=leftover_y,
    )


def _origin_inside(
    mill: MachineProfile,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    z_min: float | None,
    z_max: float | None,
    fits: bool,
) -> bool | None:
    if mill.offset_x is None or mill.offset_y is None or not fits:
        return None
    inside = (
        x_min - 1e-6 <= mill.offset_x <= x_max + 1e-6
        and y_min - 1e-6 <= mill.offset_y <= y_max + 1e-6
    )
    if inside and z_min is not None and mill.offset_z is not None:
        inside = z_min - 1e-6 <= mill.offset_z <= (z_max or z_min) + 1e-6
    return inside


def _tilted_poses(poses: tuple[PoseBC, ...]) -> tuple[PoseBC, ...]:
    out: list[PoseBC] = []
    seen: set[PoseBC] = set()
    for b, c in poses:
        key = (round(float(b), 2), round(float(c), 2))
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return tuple(out)


def _uses_dwo(mill: MachineProfile, poses: tuple[PoseBC, ...]) -> bool:
    if not mill.has_mrzp():
        return False
    for b, c in poses:
        if abs(b) > 1e-6 or abs(c) > 1e-6:
            return True
    return False


def umc_rotation(b_deg: float, c_deg: float) -> tuple[Vec3, Vec3, Vec3]:
    """UMC table-table: R = Ry(B) Rz(C). Part origin stays on the part."""
    b = math.radians(b_deg)
    c = math.radians(c_deg)
    cb, sb = math.cos(b), math.sin(b)
    cc, sc = math.cos(c), math.sin(c)
    return (
        (cb * cc, -cb * sc, sb),
        (sc, cc, 0.0),
        (-sb * cc, sb * sc, cb),
    )


def _mul_R(r: tuple[Vec3, Vec3, Vec3], v: Vec3) -> Vec3:
    return (
        r[0][0] * v[0] + r[0][1] * v[1] + r[0][2] * v[2],
        r[1][0] * v[0] + r[1][1] * v[1] + r[1][2] * v[2],
        r[2][0] * v[0] + r[2][1] * v[1] + r[2][2] * v[2],
    )


def dwo_g53_xyz(
    origin: Vec3,
    work: Vec3,
    b_deg: float,
    c_deg: float,
    mrzp: Vec3,
    *,
    tool_length_mm: float = 0.0,
) -> Vec3:
    """Machine XYZ of a part point. Origin is G54 in G53 at B0 C0. Limits only."""
    r = umc_rotation(b_deg, c_deg)
    rel = (
        origin[0] - mrzp[0] + work[0],
        origin[1] - mrzp[1] + work[1],
        origin[2] - mrzp[2] + work[2],
    )
    rotated = _mul_R(r, rel)
    return (
        mrzp[0] + rotated[0],
        mrzp[1] + rotated[1],
        mrzp[2] + rotated[2] + tool_length_mm,
    )


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Vec3) -> Vec3:
    length = math.sqrt(_dot(a, a))
    if length < 1e-15:
        return (0.0, 0.0, 1.0)
    return (a[0] / length, a[1] / length, a[2] / length)


def _unique_pts(pts: list[Vec3], eps: float = 1e-6) -> list[Vec3]:
    out: list[Vec3] = []
    for p in pts:
        if any(math.dist(p, q) < eps for q in out):
            continue
        out.append(p)
    return out


def _plane_hit(p: Vec3, q: Vec3, a: Vec3, b: float) -> Vec3:
    dp = _dot(a, p)
    dq = _dot(a, q)
    den = dq - dp
    if abs(den) < 1e-15:
        return p
    t = (b - dp) / den
    t = min(1.0, max(0.0, t))
    return _add(p, _scale(_sub(q, p), t))


def _clip_polygon(poly: list[Vec3], a: Vec3, b: float, eps: float = 1e-9) -> list[Vec3]:
    if not poly:
        return []
    out: list[Vec3] = []
    prev = poly[-1]
    prev_in = _dot(a, prev) <= b + eps
    for cur in poly:
        cur_in = _dot(a, cur) <= b + eps
        if cur_in:
            if not prev_in:
                out.append(_plane_hit(prev, cur, a, b))
            out.append(cur)
        elif prev_in:
            out.append(_plane_hit(prev, cur, a, b))
        prev = cur
        prev_in = cur_in
    return _unique_pts(out)


def _order_plane_points(pts: list[Vec3], a: Vec3) -> list[Vec3]:
    pts = _unique_pts(pts)
    if len(pts) < 3:
        return pts
    n = _norm(a)
    ax = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _norm(_cross(n, ax))
    v = _cross(n, u)
    ox = sum(p[0] for p in pts) / len(pts)
    oy = sum(p[1] for p in pts) / len(pts)
    oz = sum(p[2] for p in pts) / len(pts)
    origin = (ox, oy, oz)

    def angle(p: Vec3) -> float:
        d = _sub(p, origin)
        return math.atan2(_dot(d, v), _dot(d, u))

    return sorted(pts, key=angle)


def _aabb_faces(lo: Vec3, hi: Vec3) -> list[list[Vec3]]:
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    return [
        [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
        [(x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1)],
        [(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)],
        [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
        [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
        [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)],
    ]


def _clip_polyhedron(faces: list[list[Vec3]], a: Vec3, b: float) -> list[list[Vec3]]:
    if not faces:
        return []
    new_faces: list[list[Vec3]] = []
    cap: list[Vec3] = []
    for face in faces:
        clipped = _clip_polygon(face, a, b)
        if len(clipped) >= 3:
            new_faces.append(clipped)
        for p, q in zip(face, face[1:] + face[:1]):
            pin = _dot(a, p) <= b + 1e-9
            qin = _dot(a, q) <= b + 1e-9
            if pin != qin:
                cap.append(_plane_hit(p, q, a, b))
    cap_face = _order_plane_points(cap, a)
    if len(cap_face) >= 3:
        new_faces.append(cap_face)
    return new_faces


def _poly_vertices(faces: list[list[Vec3]]) -> list[Vec3]:
    pts: list[Vec3] = []
    for face in faces:
        pts.extend(face)
    return _unique_pts(pts)


def _inv3_mul(rows: tuple[Vec3, Vec3, Vec3], rhs: Vec3) -> Vec3 | None:
    a00, a01, a02 = rows[0]
    a10, a11, a12 = rows[1]
    a20, a21, a22 = rows[2]
    det = (
        a00 * (a11 * a22 - a12 * a21)
        - a01 * (a10 * a22 - a12 * a20)
        + a02 * (a10 * a21 - a11 * a20)
    )
    if abs(det) < 1e-14:
        return None
    i00 = (a11 * a22 - a12 * a21) / det
    i01 = (a02 * a21 - a01 * a22) / det
    i02 = (a01 * a12 - a02 * a11) / det
    i10 = (a12 * a20 - a10 * a22) / det
    i11 = (a00 * a22 - a02 * a20) / det
    i12 = (a02 * a10 - a00 * a12) / det
    i20 = (a10 * a21 - a11 * a20) / det
    i21 = (a01 * a20 - a00 * a21) / det
    i22 = (a00 * a11 - a01 * a10) / det
    return (
        i00 * rhs[0] + i01 * rhs[1] + i02 * rhs[2],
        i10 * rhs[0] + i11 * rhs[1] + i12 * rhs[2],
        i20 * rhs[0] + i21 * rhs[1] + i22 * rhs[2],
    )


def _polyhedron_vertices(planes: list[Plane], lo: Vec3, hi: Vec3) -> list[Vec3]:
    faces = _aabb_faces(lo, hi)
    for a, b in planes:
        faces = _clip_polyhedron(faces, a, b)
        if not faces:
            return []
    return _poly_vertices(faces)


def _max_centered_extents(
    planes: list[Plane], center: Vec3, cap: Vec3
) -> Vec3 | None:
    ineq: list[Plane] = []
    for a, b in planes:
        slack = b - _dot(a, center)
        if slack < -1e-6:
            return None
        ineq.append(((abs(a[0]), abs(a[1]), abs(a[2])), max(0.0, slack)))
    ineq.extend(
        [
            ((-1.0, 0.0, 0.0), 0.0),
            ((0.0, -1.0, 0.0), 0.0),
            ((0.0, 0.0, -1.0), 0.0),
            ((1.0, 0.0, 0.0), cap[0]),
            ((0.0, 1.0, 0.0), cap[1]),
            ((0.0, 0.0, 1.0), cap[2]),
        ]
    )
    best = (0.0, 0.0, 0.0)
    best_sum = -1.0
    n = len(ineq)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                rows = (ineq[i][0], ineq[j][0], ineq[k][0])
                rhs = (ineq[i][1], ineq[j][1], ineq[k][1])
                h = _inv3_mul(rows, rhs)
                if h is None:
                    continue
                if h[0] < -1e-7 or h[1] < -1e-7 or h[2] < -1e-7:
                    continue
                ok = True
                for a, b in ineq:
                    if _dot(a, h) > b + 1e-5:
                        ok = False
                        break
                if not ok:
                    continue
                total = h[0] + h[1] + h[2]
                if total > best_sum:
                    best = h
                    best_sum = total
    if best_sum < 0:
        return None
    return best


def _dwo_planes(
    mill: MachineProfile,
    bbox: WorkBBox,
    poses: tuple[PoseBC, ...],
    *,
    inch: bool,
) -> list[Plane] | None:
    wx0, wx1, wy0, wy1, wz0, wz1 = _work_mm(bbox, inch=inch)
    mrzp = (mill.mrzp_x or 0.0, mill.mrzp_y or 0.0, mill.mrzp_z or 0.0)
    pc = ((wx0 + wx1) / 2.0, (wy0 + wy1) / 2.0, (wz0 + wz1) / 2.0)
    half = ((wx1 - wx0) / 2.0, (wy1 - wy0) / 2.0, (wz1 - wz0) / 2.0)
    tx0, tx1 = _ordered(mill.x_min or 0.0, mill.x_max or 0.0)
    ty0, ty1 = _ordered(mill.y_min or 0.0, mill.y_max or 0.0)
    travel: list[tuple[float, float] | None] = [(tx0, tx1), (ty0, ty1), None]
    if mill.has_z_travel():
        travel[2] = _ordered(mill.z_min or 0.0, mill.z_max or 0.0)
    length = mill.tool_length_mm
    planes: list[Plane] = []
    for b_deg, c_deg in poses:
        r = umc_rotation(b_deg, c_deg)
        rpc = _mul_R(r, (pc[0] - mrzp[0], pc[1] - mrzp[1], pc[2] - mrzp[2]))
        shift = (mrzp[0], mrzp[1], mrzp[2] + length)
        for i in range(3):
            lim = travel[i]
            if lim is None:
                continue
            t0, t1 = lim
            infl = abs(r[i][0]) * half[0] + abs(r[i][1]) * half[1] + abs(r[i][2]) * half[2]
            if t1 - t0 < 2.0 * infl - 1e-9:
                return None
            row = r[i]
            hi = t1 - shift[i] - infl - rpc[i]
            lo = t0 - shift[i] + infl - rpc[i]
            planes.append((row, hi))
            planes.append(((-row[0], -row[1], -row[2]), -lo))
    return planes


def _point_in_planes(point: Vec3, planes: list[Plane], eps: float = 1e-6) -> bool:
    return all(_dot(a, point) <= b + eps for a, b in planes)


def _dwo_window(
    mill: MachineProfile,
    bbox: WorkBBox,
    poses: tuple[PoseBC, ...],
    *,
    inch: bool,
) -> G54Window | None:
    linear = _linear_window(mill, bbox, inch=inch)
    if linear is None:
        return None
    used = _tilted_poses(poses)
    planes = _dwo_planes(mill, bbox, used, inch=inch)
    if planes is None:
        return G54Window(
            x_min=linear.x_min,
            x_max=linear.x_max,
            y_min=linear.y_min,
            y_max=linear.y_max,
            z_min=linear.z_min,
            z_max=linear.z_max,
            fits=False,
            g54_inside=False if linear.g54_inside is not None else None,
            leftover_x=linear.leftover_x,
            leftover_y=linear.leftover_y,
            dwo=True,
            poses=used,
        )
    pad = 2000.0
    mrzp = (mill.mrzp_x or 0.0, mill.mrzp_y or 0.0, mill.mrzp_z or 0.0)
    lo = (mrzp[0] - pad, mrzp[1] - pad, mrzp[2] - pad)
    hi = (mrzp[0] + pad, mrzp[1] + pad, mrzp[2] + pad)
    verts = _polyhedron_vertices(planes, lo, hi)
    if not verts:
        return G54Window(
            x_min=linear.x_min,
            x_max=linear.x_max,
            y_min=linear.y_min,
            y_max=linear.y_max,
            z_min=linear.z_min,
            z_max=linear.z_max,
            fits=False,
            g54_inside=False if linear.g54_inside is not None else None,
            leftover_x=linear.leftover_x,
            leftover_y=linear.leftover_y,
            dwo=True,
            poses=used,
        )
    n = len(verts)
    center = (
        sum(v[0] for v in verts) / n,
        sum(v[1] for v in verts) / n,
        sum(v[2] for v in verts) / n,
    )
    cap = (
        max(abs(v[0] - center[0]) for v in verts) + 1.0,
        max(abs(v[1] - center[1]) for v in verts) + 1.0,
        max(abs(v[2] - center[2]) for v in verts) + 1.0,
    )
    extents = _max_centered_extents(planes, center, cap)
    if extents is None:
        return G54Window(
            x_min=linear.x_min,
            x_max=linear.x_max,
            y_min=linear.y_min,
            y_max=linear.y_max,
            z_min=linear.z_min,
            z_max=linear.z_max,
            fits=False,
            g54_inside=False if linear.g54_inside is not None else None,
            leftover_x=linear.leftover_x,
            leftover_y=linear.leftover_y,
            dwo=True,
            poses=used,
        )
    hx, hy, hz = extents
    x_min, x_max = center[0] - hx, center[0] + hx
    y_min, y_max = center[1] - hy, center[1] + hy
    leftover_x = x_max - x_min
    leftover_y = y_max - y_min
    fits = leftover_x >= -1e-9 and leftover_y >= -1e-9 and hz >= -1e-9
    z_min = z_max = None
    if mill.has_z_travel() or any(abs(b) > 1e-6 for b, _c in used):
        z_min = center[2] - hz
        z_max = center[2] + hz
        if z_min > z_max:
            fits = False
            z_min, z_max = z_max, z_min
    inside: bool | None = None
    if mill.offset_x is not None and mill.offset_y is not None:
        oz = 0.0 if mill.offset_z is None else mill.offset_z
        pt = (mill.offset_x, mill.offset_y, oz)
        inside = _point_in_planes(pt, planes)
        if inside and mill.offset_z is None and z_min is not None:
            inside = z_min - 1e-6 <= oz <= (z_max or z_min) + 1e-6
    return G54Window(
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
        z_min=z_min,
        z_max=z_max,
        fits=fits,
        g54_inside=inside if fits else False if inside is not None else None,
        leftover_x=leftover_x,
        leftover_y=leftover_y,
        dwo=True,
        poses=used,
    )


def g54_window(
    mill: MachineProfile,
    bbox: WorkBBox,
    *,
    inch: bool = False,
    rotary_poses: tuple[PoseBC, ...] | list[PoseBC] | None = None,
) -> G54Window | None:
    poses = _tilted_poses(tuple(rotary_poses or ()))
    if _uses_dwo(mill, poses):
        return _dwo_window(mill, bbox, poses, inch=inch)
    return _linear_window(mill, bbox, inch=inch)


def fmt_mm(v: float) -> str:
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.1f}"


def fmt_xy(x: float, y: float) -> str:
    return f"{fmt_mm(x)},{fmt_mm(y)}"


def fmt_xyz(x: float, y: float, z: float) -> str:
    return f"{fmt_mm(x)},{fmt_mm(y)},{fmt_mm(z)}"


def _fmt_xy(x: float, y: float) -> str:
    return fmt_xy(x, y)


def render_g54_window_png(
    mill: MachineProfile,
    window: G54Window,
    *,
    dest: Path | None = None,
) -> Path | None:
    """Labeled XY rectangle of allowed work-offset origin. Needs Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    width, height = 512, 360
    margin = 56
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    tx0, tx1 = _ordered(mill.x_min or 0.0, mill.x_max or 0.0)
    ty0, ty1 = _ordered(mill.y_min or 0.0, mill.y_max or 0.0)
    span_x = max(tx1 - tx0, abs(window.x_max - window.x_min), 1.0)
    span_y = max(ty1 - ty0, abs(window.y_max - window.y_min), 1.0)
    pad = 0.08
    gx0 = min(tx0, window.x_min) - span_x * pad
    gx1 = max(tx1, window.x_max) + span_x * pad
    gy0 = min(ty0, window.y_min) - span_y * pad
    gy1 = max(ty1, window.y_max) + span_y * pad
    if gx1 - gx0 < 1:
        gx1 = gx0 + 1
    if gy1 - gy0 < 1:
        gy1 = gy0 + 1

    def to_px(x: float, y: float) -> tuple[int, int]:
        px = margin + (x - gx0) / (gx1 - gx0) * (width - 2 * margin)
        py = height - margin - (y - gy0) / (gy1 - gy0) * (height - 2 * margin)
        return int(round(px)), int(round(py))

    draw.rectangle([to_px(tx0, ty1), to_px(tx1, ty0)], outline=80, width=1)
    w0 = to_px(window.x_min, window.y_max)
    w1 = to_px(window.x_max, window.y_min)
    draw.rectangle([w0, w1], outline=0, width=3)
    cx, cy = window.center
    pc = to_px(cx, cy)
    draw.line([(pc[0] - 6, pc[1]), (pc[0] + 6, pc[1])], fill=0, width=2)
    draw.line([(pc[0], pc[1] - 6), (pc[0], pc[1] + 6)], fill=0, width=2)
    labels = [
        (window.corners[0], (0, 12)),
        (window.corners[1], (-48, 12)),
        (window.corners[2], (-48, -14)),
        (window.corners[3], (0, -14)),
    ]
    for (x, y), (dx, dy) in labels:
        px, py = to_px(x, y)
        draw.text((px + dx, py + dy), _fmt_xy(x, y), fill=0, font=font)
    draw.text((pc[0] - 28, pc[1] + 10), _fmt_xy(cx, cy), fill=0, font=font)
    if mill.offset_x is not None and mill.offset_y is not None:
        gx, gy = to_px(mill.offset_x, mill.offset_y)
        r = 4
        draw.ellipse([gx - r, gy - r, gx + r, gy + r], outline=0, width=2)
    title = "Offset origin G53 mm"
    if window.dwo:
        title = "Offset origin G53 mm (DWO)"
    if not window.fits:
        title += "  TOO BIG"
    elif window.g54_inside is False:
        title += "  OFFSET OUT"
    draw.text((8, 6), title, fill=0, font=font)
    dia = window.max_tool_dia_mm
    if dia is not None:
        draw.text(
            (8, height - 18),
            f"Omax {fmt_mm(dia)} mm  centred G41/G42",
            fill=0,
            font=font,
        )
    path = dest or _cache_png_path(mill, window)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    img.save(tmp, format="PNG")
    tmp.replace(path)
    return path


def _cache_png_path(mill: MachineProfile, window: G54Window) -> Path:
    key = (
        f"{mill.id}|{mill.x_min}|{mill.x_max}|{mill.y_min}|{mill.y_max}|"
        f"{mill.z_min}|{mill.z_max}|{mill.mrzp_x}|{mill.mrzp_y}|{mill.mrzp_z}|"
        f"{window.x_min}|{window.x_max}|{window.y_min}|{window.y_max}|"
        f"{window.z_min}|{window.z_max}|{window.dwo}|{window.poses}|"
        f"{mill.offset_x}|{mill.offset_y}|{window.fits}|{window.g54_inside}|"
        f"{window.leftover_x}|{window.leftover_y}|v4"
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    root = Path(tempfile.gettempdir()) / "fh6parse-models"
    return root / f"g54-{digest}.png"


def window_for_result(result: object) -> G54Window | None:
    mill = getattr(result, "machine", None)
    bbox = getattr(result, "work_bbox", None)
    if mill is None or bbox is None:
        return None
    inch = getattr(result, "units", "") == "inch"
    poses = tuple(getattr(result, "rotary_poses", ()) or ())
    return g54_window(mill, bbox, inch=inch, rotary_poses=poses)


def g54_png_for_result(result: object) -> Path | None:
    mill = getattr(result, "machine", None)
    window = window_for_result(result)
    if mill is None or window is None:
        return None
    return render_g54_window_png(mill, window)


def append_g54_png(result: object, images: list[Path] | None = None) -> list[Path]:
    """STEP views first (isometric), then the labeled work-offset origin rectangle."""
    out = list(images or [])
    png = g54_png_for_result(result)
    if png is not None and png not in out:
        out.append(png)
    return out
