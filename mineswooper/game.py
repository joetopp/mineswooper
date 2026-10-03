from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum
from typing import Any, NamedTuple

from mineswooper.board import Board

# Opaque per-cell tokens used by to_dict(). A covered cell is always reported as COVERED or
# FLAGGED, so a serialized snapshot of a game in progress can never leak where the mines are.
COVERED = "covered"
FLAGGED = "flagged"
MINE = "mine"
EXPLODED = "exploded"


class Status(Enum):
    READY = "ready"
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"


class Preset(NamedTuple):
    rows: int
    cols: int
    mine_count: int


class Difficulty(Enum):
    BEGINNER = Preset(9, 9, 10)
    INTERMEDIATE = Preset(16, 16, 40)
    EXPERT = Preset(16, 30, 99)

    @property
    def rows(self) -> int:
        return self.value.rows

    @property
    def cols(self) -> int:
        return self.value.cols

    @property
    def mine_count(self) -> int:
        return self.value.mine_count


class Game:
    """Game state for a single round: status, flags, timing, and serialization.

    Out-of-bounds coordinates raise ValueError, because only a buggy caller can produce them.
    Every other illegal move (revealing a flag, flagging a revealed cell, playing on a finished
    board, chording an unsatisfied number) is a silent no-op: those are benign UI races, such as
    a click already in flight when the game ended.
    """

    def __init__(
        self,
        rows: int,
        cols: int,
        mine_count: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.board = Board(rows, cols, mine_count)
        self.clock = clock
        self.status = Status.READY
        self.exploded: tuple[int, int] | None = None
        self._flags: set[tuple[int, int]] = set()
        self._mines_placed = False
        self._started_at: float | None = None
        self._ended_at: float | None = None

    @classmethod
    def from_difficulty(
        cls, difficulty: Difficulty, *, clock: Callable[[], float] = time.monotonic
    ) -> Game:
        return cls(difficulty.rows, difficulty.cols, difficulty.mine_count, clock=clock)

    @property
    def rows(self) -> int:
        return self.board.rows

    @property
    def cols(self) -> int:
        return self.board.cols

    @property
    def mine_count(self) -> int:
        return self.board.mine_count

    @property
    def mines_remaining(self) -> int:
        """Mines minus flags. Goes negative when the player over-flags; that is the point."""
        return self.board.mine_count - len(self._flags)

    @property
    def is_over(self) -> bool:
        return self.status in (Status.WON, Status.LOST)

    @property
    def elapsed(self) -> float:
        """Seconds since the first reveal: 0 before the game starts, frozen once it ends."""
        if self._started_at is None:
            return 0.0
        end = self._ended_at if self._ended_at is not None else self.clock()
        return end - self._started_at

    def is_flagged(self, row: int, col: int) -> bool:
        self._require_in_bounds(row, col)
        return (row, col) in self._flags

    def reveal(self, row: int, col: int) -> None:
        self._require_in_bounds(row, col)
        if self.is_over or (row, col) in self._flags:
            return
        if self.board.grid[row][col].revealed:
            return

        self._start(row, col)
        hit_mine = self.board.grid[row][col].is_mine
        self.board.reveal(row, col)
        self._drop_flags_on_revealed_cells()

        if hit_mine:
            self._lose(row, col)
        elif self.board.is_won():
            self._win()

    def toggle_flag(self, row: int, col: int) -> None:
        self._require_in_bounds(row, col)
        if self.is_over or self.board.grid[row][col].revealed:
            return
        if (row, col) in self._flags:
            self._flags.remove((row, col))
        else:
            self._flags.add((row, col))

    def chord(self, row: int, col: int) -> None:
        """Reveal the unflagged neighbors of a revealed number whose flag count already matches it.

        A wrong flag therefore uncovers a mine and loses the game. Neighbors are visited in
        row-major order, so the recorded explosion is the topmost-leftmost mine that was hit.
        """
        self._require_in_bounds(row, col)
        if self.status is not Status.PLAYING:
            return

        cell = self.board.grid[row][col]
        if not cell.revealed or cell.adjacent_mines == 0:
            return
        neighbors = sorted(self.board._neighbors(row, col))
        if sum(1 for neighbor in neighbors if neighbor in self._flags) != cell.adjacent_mines:
            return

        first_hit: tuple[int, int] | None = None
        for n_row, n_col in neighbors:
            if (n_row, n_col) in self._flags:
                continue
            if self.board.grid[n_row][n_col].is_mine and first_hit is None:
                first_hit = (n_row, n_col)
            self.board.reveal(n_row, n_col)
        self._drop_flags_on_revealed_cells()

        if first_hit is not None:
            self._lose(*first_hit)
        elif self.board.is_won():
            self._win()

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready snapshot. While the game is ready or playing, the grid is anti-cheat:
        covered mines and covered blanks are indistinguishable."""
        return {
            "status": self.status.value,
            "rows": self.rows,
            "cols": self.cols,
            "mine_count": self.mine_count,
            "mines_remaining": self.mines_remaining,
            "elapsed": self.elapsed,
            "exploded": list(self.exploded) if self.exploded is not None else None,
            "grid": [
                [self._token(row, col) for col in range(self.cols)] for row in range(self.rows)
            ],
        }

    def _require_in_bounds(self, row: int, col: int) -> None:
        if not (0 <= row < self.board.rows and 0 <= col < self.board.cols):
            raise ValueError(f"({row}, {col}) is outside a {self.rows}x{self.cols} board")

    def _start(self, row: int, col: int) -> None:
        """Place the mines around the very first reveal, exactly once, and start the clock."""
        if self._mines_placed:
            return
        self.board.place_mines(row, col)
        self._mines_placed = True
        self.status = Status.PLAYING
        self._started_at = self.clock()

    def _drop_flags_on_revealed_cells(self) -> None:
        """A flood fill can run through a wrongly flagged blank; that flag has been disproved."""
        self._flags = {
            (row, col) for row, col in self._flags if not self.board.grid[row][col].revealed
        }

    def _lose(self, row: int, col: int) -> None:
        self.exploded = (row, col)
        for r, c in self._cells():
            cell = self.board.grid[r][c]
            if cell.is_mine and (r, c) not in self._flags:
                cell.revealed = True
        self.status = Status.LOST
        self._ended_at = self.clock()

    def _win(self) -> None:
        self._flags = {(r, c) for r, c in self._cells() if self.board.grid[r][c].is_mine}
        self.status = Status.WON
        self._ended_at = self.clock()

    def _cells(self):
        for row in range(self.rows):
            for col in range(self.cols):
                yield row, col

    def _token(self, row: int, col: int) -> str:
        cell = self.board.grid[row][col]
        if not cell.revealed:
            return FLAGGED if (row, col) in self._flags else COVERED
        if cell.is_mine:
            return EXPLODED if (row, col) == self.exploded else MINE
        return str(cell.adjacent_mines)
