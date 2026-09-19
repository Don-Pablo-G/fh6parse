"""Optional STEP → stacked opposite-isometric line drawings for 80 mm tickets."""

from __future__ import annotations

from pathlib import Path
import hashlib
import shutil
import tempfile

# Printable width on 80 mm ESC/POS at 203 dpi, multiple of 8.
THERMAL_DOTS = 512
# Hard cap per view so a bulky part cannot run down the roll (~30 mm at 203 dpi).
MAX_VIEW_HEIGHT = 240
# A 2 m × 20 mm shaft becomes a few pixels; keep a sliver so it is not 1 px.
MIN_VIEW_HEIGHT = 12
STACK_GAP = 4
# Feature edges: dihedral steeper than this (smooth tessellation stays hidden).
CREASE_DEG = 30.0


def render_available() -> bool:
    try:
        import cascadio  # noqa: F401
        import numpy  # noqa: F401
        import trimesh  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return True


def cache_dir() -> Path:
    root = Path(tempfile.gettempdir()) / "fh6parse-models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def cache_png_path(step_path: Path, mtime: float, size: int) -> Path:
    key = (
        f"{step_path.resolve()}|{mtime}|{size}|ticket-v3-edges|"
        f"{THERMAL_DOTS}|{MAX_VIEW_HEIGHT}|{MIN_VIEW_HEIGHT}|{CREASE_DEG}"
    )
    digest = hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:20]
    return cache_dir() / f"{digest}.png"


def ensure_cache_path(dest: Path) -> Path:
    """Bitmaps are only allowed under the temp cache, never on a company share."""
    root = cache_dir().resolve()
    dest = Path(dest)
    if not dest.is_absolute():
        dest = root / dest.name
    dest = dest.resolve()
    try:
        dest.relative_to(root)
    except ValueError as exc:
        raise PermissionError(f"refusing to write outside cache: {dest}") from exc
    return dest


def staged_step_copy(step_path: Path) -> Path:
    """Read-only copy in the temp cache so CAD libraries cannot touch the share."""
    src = Path(step_path)
    st = src.stat()
    key = f"{src.resolve()}|{st.st_mtime}|{st.st_size}|src-v1"
    digest = hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:20]
    dest = cache_dir() / f"{digest}{src.suffix.lower() or '.stp'}"
    if dest.is_file() and dest.stat().st_size == st.st_size:
        return dest
    tmp = dest.with_name(dest.name + ".tmp")
    with src.open("rb") as incoming, tmp.open("wb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    tmp.replace(dest)
    return dest


def ticket_view_pixels(vertices) -> tuple[int, int]:
    """Pixel size of one view: width is the 80 mm axis; height follows the part."""
    import numpy as np

    verts = np.asarray(vertices, dtype=np.float64)
    basis = _ticket_basis(verts, opposite=False)
    return _fit_pixels(verts, basis)


def render_step_stack(step_path: Path, dest: Path) -> Path | None:
    """Two opposite views, stacked. Canvas is cropped to the part (no empty roll)."""
    try:
        from PIL import Image
        import numpy as np
        import trimesh
    except ImportError:
        return None
    try:
        dest = ensure_cache_path(dest)
        staged = staged_step_copy(step_path)
        mesh = trimesh.load(str(staged), force="mesh", skip_materials=True)
        if isinstance(mesh, trimesh.Scene):
            geom = mesh.dump(concatenate=True)
            mesh = geom
        if mesh is None or getattr(mesh, "vertices", None) is None:
            return None
        if len(mesh.vertices) < 3 or len(mesh.faces) < 1:
            return None
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        view_a = _raster_view(vertices, faces, opposite=False)
        view_b = _raster_view(vertices, faces, opposite=True)
        gap = STACK_GAP
        height = view_a.shape[0] + gap + view_b.shape[0]
        stacked = Image.new("L", (THERMAL_DOTS, height), 255)
        stacked.paste(Image.fromarray(view_a, mode="L"), (0, 0))
        stacked.paste(Image.fromarray(view_b, mode="L"), (0, view_a.shape[0] + gap))
        dest.parent.mkdir(parents=True, exist_ok=True)
        stacked.save(dest, format="PNG")
        return dest
    except Exception:
        return None


def _ticket_basis(vertices, *, opposite: bool):
    """True isometric camera; longest AABB axis stays across the 80 mm width.

    Sequential shop rotations are 45° about vertical then arctan(1/√2)≈35.264°
    about the screen-horizontal axis — same as looking along (1,1,1). The old
    view only did the 45° (look in the plane of the two short axes), so the
    long axis stayed face-on.
    """
    import numpy as np

    size = vertices.max(axis=0) - vertices.min(axis=0)
    long_i = int(np.argmax(size))
    axes = np.eye(3, dtype=np.float64)
    look = axes[0] + axes[1] + axes[2]
    n = np.linalg.norm(look)
    look = look / n if n > 1e-12 else axes[2]
    if opposite:
        look = -look
    xaxis = axes[long_i]
    xaxis = xaxis - look * float(np.dot(xaxis, look))
    xn = np.linalg.norm(xaxis)
    xaxis = xaxis / xn if xn > 1e-12 else axes[(long_i + 1) % 3]
    yaxis = np.cross(look, xaxis)
    yn = np.linalg.norm(yaxis)
    yaxis = yaxis / yn if yn > 1e-12 else axes[(long_i + 2) % 3]
    up_i = 2 if long_i != 2 else 1
    if float(np.dot(yaxis, axes[up_i])) < 0:
        yaxis = -yaxis
        xaxis = -xaxis
    return np.stack([xaxis, yaxis, look], axis=1)


def _fit_pixels(vertices, basis) -> tuple[int, int]:
    import numpy as np

    center = vertices.mean(axis=0)
    pts = (vertices - center) @ basis
    span_x = float(max(pts[:, 0].max() - pts[:, 0].min(), 1e-9))
    span_y = float(max(pts[:, 1].max() - pts[:, 1].min(), 1e-9))
    pad = 0.04
    scale = (THERMAL_DOTS - 8) / (span_x * (1.0 + 2 * pad))
    height = int(round(span_y * scale * (1.0 + 2 * pad))) + 2
    if height > MAX_VIEW_HEIGHT:
        scale *= MAX_VIEW_HEIGHT / height
        height = MAX_VIEW_HEIGHT
    height = max(MIN_VIEW_HEIGHT, min(MAX_VIEW_HEIGHT, height))
    if height % 2:
        height += 1
    return THERMAL_DOTS, height


def _raster_view(vertices, faces, *, opposite: bool):
    """Z-buffer the solid, then stroke silhouette + crease edges in black."""
    import numpy as np

    basis = _ticket_basis(vertices, opposite=opposite)
    width, height = _fit_pixels(vertices, basis)
    look = basis[:, 2]
    center = vertices.mean(axis=0)
    pts = (vertices - center) @ basis
    xy = pts[:, :2]
    depth = pts[:, 2]
    lo = xy.min(axis=0)
    hi = xy.max(axis=0)
    span_x = float(max(hi[0] - lo[0], 1e-9))
    span_y = float(max(hi[1] - lo[1], 1e-9))
    origin = (lo + hi) / 2.0
    scale = (width - 8) / (span_x * 1.08)
    used_h = span_y * scale * 1.08
    if used_h > height - 2:
        scale *= (height - 2) / used_h
    screen = np.empty_like(xy)
    screen[:, 0] = (xy[:, 0] - origin[0]) * scale + width / 2.0
    screen[:, 1] = height / 2.0 - (xy[:, 1] - origin[1]) * scale

    img = np.full((height, width), 255, dtype=np.uint8)
    zbuf = np.full((height, width), -1e30, dtype=np.float64)

    tri = screen[faces]
    ztri = depth[faces]
    for (a, b, c), (za, zb, zc) in zip(tri, ztri):
        _fill_z(zbuf, a, b, c, za, zb, zc)

    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    normals = np.cross(v1 - v0, v2 - v0)
    nlen = np.linalg.norm(normals, axis=1, keepdims=True)
    nlen = np.where(nlen < 1e-12, 1.0, nlen)
    normals = normals / nlen
    facing = normals @ look
    depth_span = float(max(depth.max() - depth.min(), 1e-9))
    bias = 0.004 * depth_span
    crease_cos = float(np.cos(np.deg2rad(CREASE_DEG)))
    for (i, j), fis in _edge_faces(faces).items():
        if not _is_visible_edge(fis, facing, normals, crease_cos):
            continue
        _draw_line(
            img,
            zbuf,
            screen[i],
            screen[j],
            float(depth[i]),
            float(depth[j]),
            bias,
        )
    return img


def _edge_faces(faces) -> dict[tuple[int, int], list[int]]:
    edges: dict[tuple[int, int], list[int]] = {}
    for fi, (a, b, c) in enumerate(faces):
        a, b, c = int(a), int(b), int(c)
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            edges.setdefault(key, []).append(fi)
    return edges


def _is_visible_edge(
    fis: list[int],
    facing,
    normals,
    crease_cos: float,
) -> bool:
    if len(fis) == 1:
        return bool(facing[fis[0]] > 0)
    f0, f1 = fis[0], fis[1]
    front0 = facing[f0] > 0
    front1 = facing[f1] > 0
    if front0 != front1:
        return True
    if not (front0 or front1):
        return False
    return float(normals[f0] @ normals[f1]) < crease_cos


def _fill_z(zbuf, a, b, c, za, zb, zc) -> None:
    import numpy as np

    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    if abs(area) < 1e-8:
        return
    h, w = zbuf.shape
    minx = max(int(min(ax, bx, cx)), 0)
    maxx = min(int(max(ax, bx, cx)) + 1, w - 1)
    miny = max(int(min(ay, by, cy)), 0)
    maxy = min(int(max(ay, by, cy)) + 1, h - 1)
    if minx > maxx or miny > maxy:
        return
    xs = np.arange(minx, maxx + 1) + 0.5
    for y in range(miny, maxy + 1):
        py = y + 0.5
        w0 = (bx - xs) * (cy - py) - (by - py) * (cx - xs)
        w1 = (cx - xs) * (ay - py) - (cy - py) * (ax - xs)
        w2 = (ax - xs) * (by - py) - (ay - py) * (bx - xs)
        if area < 0:
            inside = (w0 <= 0) & (w1 <= 0) & (w2 <= 0)
        else:
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not np.any(inside):
            continue
        bary = np.stack([w0, w1, w2], axis=1) / area
        z = bary[:, 0] * za + bary[:, 1] * zb + bary[:, 2] * zc
        row_z = zbuf[y, minx : maxx + 1]
        closer = inside & (z >= row_z)
        row_z[closer] = z[closer]


def _draw_line(img, zbuf, p0, p1, z0: float, z1: float, bias: float) -> None:
    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    dx = x1 - x0
    dy = y1 - y0
    steps = int(max(abs(dx), abs(dy))) + 1
    h, w = img.shape
    for i in range(steps + 1):
        t = i / steps if steps else 0.0
        x = x0 + t * dx
        y = y0 + t * dy
        z = z0 + t * (z1 - z0) + bias
        xi = int(round(x))
        yi = int(round(y))
        for px, py in ((xi, yi), (xi + 1, yi), (xi, yi + 1)):
            if 0 <= px < w and 0 <= py < h and z >= zbuf[py, px]:
                img[py, px] = 0
