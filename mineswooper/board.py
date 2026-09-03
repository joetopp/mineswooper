from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Cell:
    is_mine: bool = False
    revealed: bool = False
    adjacent_mines: int = 0


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

    def _neighbors(self, row: int, col: int):
        for d_row in (-1, 0, 1):
            for d_col in (-1, 0, 1):
                if d_row == 0 and d_col == 0:
                    continue
                n_row, n_col = row + d_row, col + d_col
                if 0 <= n_row < self.rows and 0 <= n_col < self.cols:
                    yield n_row, n_col

    def place_mines(self, exclude_row: int, exclude_col: int) -> None:
        candidates = [
            (row, col)
            for row in range(self.rows)
            for col in range(self.cols)
            if (row, col) != (exclude_row, exclude_col)
        ]
        for row, col in random.sample(candidates, self.mine_count):
            self.grid[row][col].is_mine = True

        for row in range(self.rows):
            for col in range(self.cols):
                cell = self.grid[row][col]
                if cell.is_mine:
                    continue
                cell.adjacent_mines = sum(
                    1 for n_row, n_col in self._neighbors(row, col) if self.grid[n_row][n_col].is_mine
                )

    def reveal(self, row: int, col: int) -> None:
        stack = [(row, col)]
        while stack:
            r, c = stack.pop()
            cell = self.grid[r][c]
            if cell.revealed:
                continue
            cell.revealed = True
            if not cell.is_mine and cell.adjacent_mines == 0:
                for n_row, n_col in self._neighbors(r, c):
                    if not self.grid[n_row][n_col].revealed:
                        stack.append((n_row, n_col))

    def is_won(self) -> bool:
        return all(cell.revealed for row in self.grid for cell in row if not cell.is_mine)

    def render(self, reveal_all: bool = False) -> str:
        lines = []
        for row in self.grid:
            symbols = []
            for cell in row:
                if cell.is_mine and (reveal_all or cell.revealed):
                    symbols.append("*")
                elif cell.revealed:
                    symbols.append(" " if cell.adjacent_mines == 0 else str(cell.adjacent_mines))
                else:
                    symbols.append(".")
            lines.append(" ".join(symbols))
        return "\n".join(lines)
