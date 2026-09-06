from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Cell:
    is_mine: bool = False
    revealed: bool = False
    adjacent_mines: int = 0
    flagged: bool = False


class Board:
    def __init__(self, rows: int, cols: int, mine_count: int) -> None:
        if not 0 <= mine_count <= rows * cols - 1:
            raise ValueError(
                f"mine_count must be between 0 and {rows * cols - 1} for a {rows}x{cols} board, "
                "leaving room for the first-click exclusion"
            )
        self.rows = rows
        self.cols = cols
        self.mine_count = mine_count
        self.grid: list[list[Cell]] = [[Cell() for _ in range(cols)] for _ in range(rows)]
        self.mines_placed = False

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def _neighbors(self, row: int, col: int):
        for d_row in (-1, 0, 1):
            for d_col in (-1, 0, 1):
                if d_row == 0 and d_col == 0:
                    continue
                n_row, n_col = row + d_row, col + d_col
                if self.in_bounds(n_row, n_col):
                    yield n_row, n_col

    def compute_adjacent_counts(self) -> None:
        for row in range(self.rows):
            for col in range(self.cols):
                cell = self.grid[row][col]
                if cell.is_mine:
                    continue
                cell.adjacent_mines = sum(
                    1 for n_row, n_col in self._neighbors(row, col) if self.grid[n_row][n_col].is_mine
                )

    def place_mines(self, exclude_row: int, exclude_col: int) -> None:
        if self.mines_placed:
            return
        candidates = [
            (row, col)
            for row in range(self.rows)
            for col in range(self.cols)
            if (row, col) != (exclude_row, exclude_col)
        ]
        for row, col in random.sample(candidates, self.mine_count):
            self.grid[row][col].is_mine = True

        self.mines_placed = True
        self.compute_adjacent_counts()

    def reveal(self, row: int, col: int) -> bool:
        if not self.in_bounds(row, col):
            raise ValueError(f"({row}, {col}) is outside a {self.rows}x{self.cols} board")

        hit_mine = False
        stack = [(row, col)]
        while stack:
            r, c = stack.pop()
            cell = self.grid[r][c]
            if cell.revealed or cell.flagged:
                continue
            cell.revealed = True
            if cell.is_mine:
                hit_mine = True
                continue
            if cell.adjacent_mines == 0:
                for n_row, n_col in self._neighbors(r, c):
                    if not self.grid[n_row][n_col].revealed:
                        stack.append((n_row, n_col))
        return hit_mine

    def is_won(self) -> bool:
        return all(cell.revealed for row in self.grid for cell in row if not cell.is_mine)

    def render(self, reveal_all: bool = False) -> str:
        lines = []
        for row in self.grid:
            symbols = []
            for cell in row:
                if cell.is_mine and (reveal_all or cell.revealed):
                    symbols.append("*")
                elif cell.flagged:
                    symbols.append("F")
                elif cell.revealed:
                    symbols.append(" " if cell.adjacent_mines == 0 else str(cell.adjacent_mines))
                else:
                    symbols.append(".")
            lines.append(" ".join(symbols))
        return "\n".join(lines)
