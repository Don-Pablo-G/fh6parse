"""Optional STEP → stacked opposite-isometric PNG for 80 mm tickets."""

from __future__ import annotations

from pathlib import Path
import hashlib
import tempfile

# Printable width on 80 mm ESC/POS at 203 dpi, multiple of 8.
THERMAL_DOTS = 512
VIEW_HEIGHT = 360
STACK_GAP = 8

# (1,1,1) and 180° around Z — both from above, opposite sides.
_ISO_A = (1.0, 1.0, 1.0)
_ISO_B = (-1.0, -1.0, 1.0)


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
    key = f"{step_path.resolve()}|{mtime}|{size}|{THERMAL_DOTS}|{VIEW_HEIGHT}"
    digest = hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:20]
    return cache_dir() / f"{digest}.png"


def render_step_stack(step_path: Path, dest: Path) -> Path | None:
    """Two opposite isometric views, stacked, white background. None on failure."""
    try:
        from PIL import Image
        import numpy as np
        import trimesh
    except ImportError:
        return None
    try:
        mesh = trimesh.load(str(step_path), force="mesh", skip_materials=True)
        if isinstance(mesh, trimesh.Scene):
            geom = mesh.dump(concatenate=True)
            mesh = geom
        if mesh is None or getattr(mesh, "vertices", None) is None:
            return None
        if len(mesh.vertices) < 3 or len(mesh.faces) < 1:
            return None
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        if len(faces) > 80000:
            faces = faces[:: max(1, len(faces) // 80000)]
        view_a = _raster_view(vertices, faces, _ISO_A, THERMAL_DOTS, VIEW_HEIGHT)
        view_b = _raster_view(vertices, faces, _ISO_B, THERMAL_DOTS, VIEW_HEIGHT)
        gap = STACK_GAP
        stacked = Image.new("L", (THERMAL_DOTS, VIEW_HEIGHT * 2 + gap), 255)
        stacked.paste(Image.fromarray(view_a, mode="L"), (0, 0))
        stacked.paste(Image.fromarray(view_b, mode="L"), (0, VIEW_HEIGHT + gap))
        dest.parent.mkdir(parents=True, exist_ok=True)
        stacked.save(dest, format="PNG")
        return dest
    except Exception:
        return None


def _raster_view(vertices, faces, direction, width: int, height: int):
    import numpy as np

    zaxis = np.asarray(direction, dtype=np.float64)
    zaxis = zaxis / (np.linalg.norm(zaxis) or 1.0)
    up = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(up, zaxis))) > 0.92:
        up = np.array([0.0, 1.0, 0.0])
    xaxis = np.cross(up, zaxis)
    n = np.linalg.norm(xaxis)
    if n < 1e-9:
        xaxis = np.array([1.0, 0.0, 0.0])
    else:
        xaxis = xaxis / n
    yaxis = np.cross(zaxis, xaxis)
    basis = np.stack([xaxis, yaxis, zaxis], axis=1)
    center = vertices.mean(axis=0)
    pts = (vertices - center) @ basis
    xy = pts[:, :2]
    depth = pts[:, 2]
    lo = xy.min(axis=0)
    hi = xy.max(axis=0)
    span = float(max(hi[0] - lo[0], hi[1] - lo[1], 1e-9))
    margin = 0.06 * span
    scale = (min(width, height) - 2) / (span + 2 * margin)
    origin = (lo + hi) / 2.0
    screen = np.empty_like(xy)
    screen[:, 0] = (xy[:, 0] - origin[0]) * scale + width / 2.0
    screen[:, 1] = height / 2.0 - (xy[:, 1] - origin[1]) * scale

    img = np.full((height, width), 255, dtype=np.uint8)
    zbuf = np.full((height, width), -1e30, dtype=np.float64)

    tri = screen[faces]
    ztri = depth[faces]
    # Face lighting: view-facing faces are darker on the ticket.
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    normals = np.cross(v1 - v0, v2 - v0)
    nlen = np.linalg.norm(normals, axis=1)
    nlen = np.where(nlen < 1e-12, 1.0, nlen)
    lambert = np.abs((normals @ zaxis) / nlen)
    shades = (40.0 + 170.0 * lambert).astype(np.uint8)

    for (a, b, c), (za, zb, zc), shade in zip(tri, ztri, shades):
        _fill_triangle(img, zbuf, a, b, c, za, zb, zc, int(shade))
    return img


def _fill_triangle(img, zbuf, a, b, c, za, zb, zc, shade: int) -> None:
    import numpy as np

    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    if abs(area) < 1e-8:
        return
    h, w = img.shape
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
        row_i = img[y, minx : maxx + 1]
        closer = inside & (z >= row_z)
        row_z[closer] = z[closer]
        row_i[closer] = shade
