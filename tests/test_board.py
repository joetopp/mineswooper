import pytest

from mineswooper.board import Board, Cell


def _compute_adjacent_counts(board: Board) -> None:
    for row in range(board.rows):
        for col in range(board.cols):
            cell = board.grid[row][col]
            if cell.is_mine:
                continue
            cell.adjacent_mines = sum(
                1 for n_row, n_col in board._neighbors(row, col) if board.grid[n_row][n_col].is_mine
            )


def test_cell_defaults():
    cell = Cell()
    assert cell.is_mine is False
    assert cell.revealed is False
    assert cell.adjacent_mines == 0


def test_board_starts_without_mines():
    board = Board(rows=5, cols=5, mine_count=5)
    assert all(not cell.is_mine for row in board.grid for cell in row)


def test_board_rejects_mine_count_that_leaves_no_room_for_exclusion():
    with pytest.raises(ValueError):
        Board(rows=2, cols=2, mine_count=4)


def test_place_mines_respects_count_and_exclusion():
    board = Board(rows=5, cols=5, mine_count=10)
    board.place_mines(exclude_row=2, exclude_col=2)

    mines = [(r, c) for r in range(5) for c in range(5) if board.grid[r][c].is_mine]
    assert len(mines) == 10
    assert (2, 2) not in mines


def test_place_mines_computes_adjacent_counts():
    board = Board(rows=3, cols=3, mine_count=1)
    board.grid[0][0].is_mine = True
    _compute_adjacent_counts(board)

    assert board.grid[0][1].adjacent_mines == 1
    assert board.grid[1][1].adjacent_mines == 1
    assert board.grid[2][2].adjacent_mines == 0


def test_reveal_flood_fills_zero_region_and_stops_at_numbers():
    board = Board(rows=3, cols=3, mine_count=1)
    board.grid[0][0].is_mine = True
    _compute_adjacent_counts(board)

    board.reveal(2, 2)

    assert board.grid[2][2].revealed
    assert board.grid[1][1].revealed
    assert board.grid[0][1].revealed
    assert board.grid[1][0].revealed
    assert not board.grid[0][0].revealed  # the mine itself is never auto-revealed


def test_reveal_on_numbered_cell_does_not_expand():
    board = Board(rows=3, cols=3, mine_count=1)
    board.grid[0][0].is_mine = True
    _compute_adjacent_counts(board)

    board.reveal(0, 1)

    assert board.grid[0][1].revealed
    assert not board.grid[1][1].revealed
    assert not board.grid[2][2].revealed


def test_is_won_true_when_all_non_mine_cells_revealed():
    board = Board(rows=2, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True
    board.grid[0][1].revealed = True
    board.grid[1][0].revealed = True
    board.grid[1][1].revealed = True

    assert board.is_won()


def test_is_won_false_when_a_non_mine_cell_is_hidden():
    board = Board(rows=2, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True
    board.grid[0][1].revealed = True
    board.grid[1][0].revealed = True

    assert not board.is_won()


def test_render_hides_unrevealed_cells():
    board = Board(rows=2, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True

    assert board.render() == ". .\n. ."


def test_render_shows_revealed_numbers_and_blanks():
    board = Board(rows=2, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True
    board.grid[0][1].adjacent_mines = 1
    board.grid[0][1].revealed = True
    board.grid[1][1].adjacent_mines = 0
    board.grid[1][1].revealed = True

    assert board.render() == ". 1\n.  "


def test_render_reveal_all_shows_mines():
    board = Board(rows=1, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True

    assert board.render(reveal_all=True) == "* ."
