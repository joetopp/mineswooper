from __future__ import annotations

from mineswooper.board import Board

DEFAULT_ROWS = 9
DEFAULT_COLS = 9
DEFAULT_MINES = 10


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


def _prompt_setup() -> Board:
    rows = _prompt_dimension("Rows", DEFAULT_ROWS)
    cols = _prompt_dimension("Columns", DEFAULT_COLS)
    while True:
        mines = _prompt_dimension("Mines", DEFAULT_MINES)
        try:
            return Board(rows, cols, mines)
        except ValueError as exc:
            print(exc)


def _render_board(board: Board, reveal_all: bool = False) -> str:
    header = " ".join(str((col + 1) % 10) for col in range(board.cols))
    row_label_width = len(str(board.rows))
    lines = [" " * (row_label_width + 1) + header]
    for row_index, line in enumerate(board.render(reveal_all=reveal_all).split("\n")):
        label = str(row_index + 1).rjust(row_label_width)
        lines.append(f"{label} {line}")
    return "\n".join(lines)


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


def play() -> None:
    board = _prompt_setup()
    print(_render_board(board))

    first_move = True
    while True:
        move = _parse_move(input("Enter row col: ").strip(), board.rows, board.cols)
        if move is None:
            print(f"Enter two numbers between 1 and {board.rows}/{board.cols}, e.g. '3 4'.")
            continue

        row, col = move
        if first_move:
            board.place_mines(row, col)
            first_move = False

        if board.grid[row][col].is_mine:
            board.reveal(row, col)
            print(_render_board(board, reveal_all=True))
            print("You hit a mine! Game over.")
            return

        board.reveal(row, col)
        print(_render_board(board))

        if board.is_won():
            print("You win! All safe cells revealed.")
            return


def main() -> None:
    try:
        play()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
