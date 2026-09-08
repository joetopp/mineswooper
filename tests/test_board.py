import pytest

from mineswooper.board import Board, Cell


def test_cell_defaults():
    cell = Cell()
    assert cell.is_mine is False
    assert cell.revealed is False
    assert cell.adjacent_mines == 0
    assert cell.flagged is False


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
    board.compute_adjacent_counts()

    assert board.grid[0][1].adjacent_mines == 1
    assert board.grid[1][1].adjacent_mines == 1
    assert board.grid[2][2].adjacent_mines == 0


def test_reveal_flood_fills_zero_region_and_stops_at_numbers():
    board = Board(rows=3, cols=3, mine_count=1)
    board.grid[0][0].is_mine = True
    board.compute_adjacent_counts()

    board.reveal(2, 2)

    assert board.grid[2][2].revealed
    assert board.grid[1][1].revealed
    assert board.grid[0][1].revealed
    assert board.grid[1][0].revealed
    assert not board.grid[0][0].revealed  # the mine itself is never auto-revealed


def test_reveal_on_numbered_cell_does_not_expand():
    board = Board(rows=3, cols=3, mine_count=1)
    board.grid[0][0].is_mine = True
    board.compute_adjacent_counts()

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


def test_render_shows_flagged_cells():
    board = Board(rows=1, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True
    board.grid[0][0].flagged = True
    board.grid[0][1].flagged = True

    assert board.render() == "F F"


def test_render_reveal_all_shows_flagged_mine_as_mine_not_flag():
    board = Board(rows=1, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True
    board.grid[0][0].flagged = True

    assert board.render(reveal_all=True) == "* ."


def test_place_mines_is_idempotent():
    board = Board(rows=5, cols=5, mine_count=10)
    board.place_mines(exclude_row=2, exclude_col=2)
    board.place_mines(exclude_row=0, exclude_col=0)

    mines = [(r, c) for r in range(5) for c in range(5) if board.grid[r][c].is_mine]
    assert len(mines) == 10


def test_place_mines_sets_mines_placed_flag():
    board = Board(rows=5, cols=5, mine_count=10)
    assert board.mines_placed is False

    board.place_mines(exclude_row=2, exclude_col=2)

    assert board.mines_placed is True


def test_reveal_returns_true_when_hitting_a_mine():
    board = Board(rows=2, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True
    board.compute_adjacent_counts()

    assert board.reveal(0, 0) is True


def test_reveal_returns_false_when_not_hitting_a_mine():
    board = Board(rows=2, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True
    board.compute_adjacent_counts()

    assert board.reveal(1, 1) is False


def test_reveal_skips_flagged_cells():
    board = Board(rows=1, cols=2, mine_count=1)
    board.grid[0][0].is_mine = True
    board.grid[0][0].flagged = True
    board.compute_adjacent_counts()

    result = board.reveal(0, 0)

    assert result is False
    assert not board.grid[0][0].revealed


def test_reveal_flood_fill_stops_at_flagged_cells():
    board = Board(rows=1, cols=3, mine_count=0)
    board.compute_adjacent_counts()
    board.grid[0][1].flagged = True

    board.reveal(0, 0)

    assert board.grid[0][0].revealed
    assert not board.grid[0][1].revealed
    assert not board.grid[0][2].revealed


def test_reveal_raises_value_error_out_of_bounds():
    board = Board(rows=3, cols=3, mine_count=1)

    with pytest.raises(ValueError):
        board.reveal(3, 0)

    with pytest.raises(ValueError):
        board.reveal(0, -1)


def test_in_bounds():
    board = Board(rows=3, cols=3, mine_count=1)

    assert board.in_bounds(0, 0)
    assert board.in_bounds(2, 2)
    assert not board.in_bounds(3, 0)
    assert not board.in_bounds(0, -1)
