from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

from mineswooper.board import Board
from mineswooper.game import Game, Status

DEFAULT_ROWS = 9
DEFAULT_COLS = 9
DEFAULT_MINES = 10

FLAG_SYMBOL = "F"

REVEAL = "reveal"
FLAG = "flag"
CHORD = "chord"

# Prefixes the player can type in front of a `row col` move. A bare move reveals.
_PREFIXES = {"f": FLAG, "c": CHORD}


class Command(NamedTuple):
    action: str
    row: int
    col: int


def _prompt_dimension(label: str, default: int) -> int:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if value <= 0:
            print("Please enter a positive number.")
            continue
        return value


def _prompt_setup() -> Game:
    rows = _prompt_dimension("Rows", DEFAULT_ROWS)
    cols = _prompt_dimension("Columns", DEFAULT_COLS)
    while True:
        mines = _prompt_dimension("Mines", DEFAULT_MINES)
        try:
            return Game(rows, cols, mines)
        except ValueError as exc:
            print(exc)


def _render_board(
    board: Board, reveal_all: bool = False, flags: Iterable[tuple[int, int]] = ()
) -> str:
    header = " ".join(str((col + 1) % 10) for col in range(board.cols))
    row_label_width = len(str(board.rows))
    rendered = [list(line) for line in board.render(reveal_all=reveal_all).split("\n")]
    for row, col in flags:
        cell = board.grid[row][col]
        # A revealed cell cannot be flagged, and a full reveal outranks a flag.
        if cell.revealed or (cell.is_mine and reveal_all):
            continue
        # render() emits one character per cell, space separated, so column `col` sits at 2 * col.
        rendered[row][2 * col] = FLAG_SYMBOL
    lines = [" " * (row_label_width + 1) + header]
    for row_index, symbols in enumerate(rendered):
        label = str(row_index + 1).rjust(row_label_width)
        lines.append(f"{label} {''.join(symbols)}")
    return "\n".join(lines)


def _render_game(game: Game, reveal_all: bool = False) -> str:
    """Render a game's board, marking the flags the Game is tracking."""
    flags = [
        (row, col)
        for row in range(game.rows)
        for col in range(game.cols)
        if game.is_flagged(row, col)
    ]
    return _render_board(game.board, reveal_all=reveal_all, flags=flags)


def _parse_move(raw: str, rows: int, cols: int) -> tuple[int, int] | None:
    parts = raw.split()
    if len(parts) != 2:
        return None
    try:
        row, col = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (1 <= row <= rows and 1 <= col <= cols):
        return None
    return row - 1, col - 1


def _parse_command(raw: str, rows: int, cols: int) -> Command | None:
    """Parse an optional action prefix plus a `row col` move, e.g. 'f 3 4' or '3 4'."""
    parts = raw.split()
    action = REVEAL
    if parts and parts[0].lower() in _PREFIXES:
        action = _PREFIXES[parts[0].lower()]
        parts = parts[1:]
    move = _parse_move(" ".join(parts), rows, cols)
    if move is None:
        return None
    return Command(action, *move)


def _state_signature(game: Game) -> tuple:
    """A cheap snapshot of everything a legal move could change."""
    cells = tuple(
        (game.board.grid[row][col].revealed, game.is_flagged(row, col))
        for row in range(game.rows)
        for col in range(game.cols)
    )
    return game.status, cells


def _rejection_message(game: Game, command: Command) -> str:
    """Explain why a syntactically valid command changed nothing.

    `Game` treats every illegal move as a silent no-op, so the reason is reconstructed here for
    the player's benefit. It is only ever used to pick wording, never to decide behavior.
    """
    position = f"({command.row + 1}, {command.col + 1})"
    cell = game.board.grid[command.row][command.col]

    if command.action == FLAG:
        return f"{position} is already revealed, so it cannot be flagged."
    if command.action == CHORD:
        if not cell.revealed:
            return f"Chording needs a revealed number, and {position} is still covered."
        if cell.adjacent_mines == 0:
            return f"Chording needs a numbered cell, and {position} has no adjacent mines."
        flagged = sum(
            1 for neighbor in game.board.neighbors(command.row, command.col)
            if game.is_flagged(*neighbor)
        )
        if flagged == cell.adjacent_mines:
            return f"Chording {position} found nothing left to reveal."
        return (
            f"Chording {position} needs exactly {cell.adjacent_mines} "
            f"flag(s) around it, but there are {flagged}."
        )
    if game.is_flagged(command.row, command.col):
        return f"{position} is flagged. Unflag it with 'f {command.row + 1} {command.col + 1}'."
    return f"{position} is already revealed."


def play() -> None:
    game = _prompt_setup()
    print(_render_game(game))

    while True:
        command = _parse_command(input("Enter row col: ").strip(), game.rows, game.cols)
        if command is None:
            print(
                f"Enter two numbers between 1 and {game.rows}/{game.cols}, e.g. '3 4', "
                "optionally prefixed with 'f' to flag or 'c' to chord."
            )
            continue

        before = _state_signature(game)
        if command.action == FLAG:
            game.toggle_flag(command.row, command.col)
        elif command.action == CHORD:
            game.chord(command.row, command.col)
        else:
            game.reveal(command.row, command.col)

        print(_render_game(game, reveal_all=game.status is Status.LOST))
        if _state_signature(game) == before:
            print(_rejection_message(game, command))

        if game.status is Status.LOST:
            print("You hit a mine! Game over.")
            return
        if game.status is Status.WON:
            print("You win! All safe cells revealed.")
            return


def main() -> None:
    try:
        play()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
