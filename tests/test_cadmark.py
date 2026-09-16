"""Wireframe isometric cube used as the STEP-ready mark."""

from __future__ import annotations

import unittest

from fh6parse.cadmark import cube_pixels


class TestCadMark(unittest.TestCase):
    def test_cube_is_outline_not_filled_square(self) -> None:
        bg = (0x1A, 0x1A, 0x1A)
        edge = (0xFF, 0xD5, 0x4A)
        grid = cube_pixels(24, bg=bg, edge=edge, width=2)
        self.assertEqual(len(grid), 24)
        self.assertEqual(len(grid[0]), 24)
        colors = {px for row in grid for px in row}
        self.assertEqual(colors, {bg, edge})
        self.assertEqual(grid[0][0], bg)
        self.assertEqual(grid[0][-1], bg)
        self.assertEqual(grid[-1][0], bg)
        self.assertEqual(grid[-1][-1], bg)
        inked = sum(1 for row in grid for px in row if px == edge)
        self.assertGreater(inked, 40)
        self.assertLess(inked, 24 * 24 // 2)
        self.assertEqual(grid[3][12], edge)
        self.assertEqual(grid[7][12], bg)

    def test_gif_is_transparent_ready_mark(self) -> None:
        from fh6parse.cadmark import CUBE_YELLOW, gif89a

        bg = (0x11, 0x11, 0x11)
        grid = cube_pixels(24, bg=bg, edge=CUBE_YELLOW, width=2)
        data = gif89a(grid)
        self.assertTrue(data.startswith(b"GIF89a"))
        self.assertEqual(data[-1], 0x3B)
        self.assertGreater(len(data), 800)

    def test_empty_gif_is_window_colour(self) -> None:
        from fh6parse.cadmark import gif89a

        size = 20
        bg = (0x11, 0x11, 0x11)
        grid = [[bg for _ in range(size)] for _ in range(size)]
        data = gif89a(grid)
        self.assertTrue(data.startswith(b"GIF89a"))

    def test_empty_corners_stay_background(self) -> None:
        bg = (0xF0, 0xF0, 0xF0)
        grid = cube_pixels(20, bg=bg, edge=(1, 2, 3), width=2)
        self.assertEqual(grid[0][0], bg)
        self.assertEqual(grid[-1][0], bg)
        self.assertEqual(grid[0][-1], bg)
        self.assertEqual(grid[-1][-1], bg)
