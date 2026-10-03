import json

import pytest

from mineswooper.game import (
    COVERED,
    EXPLODED,
    FLAGGED,
    MINE,
    Difficulty,
    Game,
    Status,
)


class _Clock:
    """A hand-cranked stand-in for time.monotonic()."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _game(rows, cols, mines, *, monkeypatch, clock=None):
    """A Game whose first reveal lays exactly `mines`, wherever the player clicks."""
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: list(mines))
    return Game(rows, cols, len(mines), clock=clock or _Clock())


# A 5x5 layout whose every neighbor of (1, 1) is a mine or a number, so that revealing them
# never flood-fills and the far corner of the board stays covered:
#
#   * 2 * 0 0
#   1 2 1 0 0
#   1 1 1 0 0
#   1 * 1 0 0
#   1 1 1 0 0
CORNER_MINES = [(0, 0), (0, 2), (3, 1)]


def _corner_game(monkeypatch, clock=None):
    """The layout above, started by revealing the 2 at (1, 1)."""
    game = _game(5, 5, CORNER_MINES, monkeypatch=monkeypatch, clock=clock)
    game.reveal(1, 1)
    return game


def test_status_values():
    assert [status.value for status in Status] == ["ready", "playing", "won", "lost"]


@pytest.mark.parametrize(
    "difficulty, rows, cols, mine_count",
    [
        (Difficulty.BEGINNER, 9, 9, 10),
        (Difficulty.INTERMEDIATE, 16, 16, 40),
        (Difficulty.EXPERT, 16, 30, 99),
    ],
)
def test_difficulty_presets(difficulty, rows, cols, mine_count):
    assert (difficulty.rows, difficulty.cols, difficulty.mine_count) == (rows, cols, mine_count)


def test_from_difficulty_builds_a_matching_board():
    game = Game.from_difficulty(Difficulty.EXPERT)
    assert (game.rows, game.cols, game.mine_count) == (16, 30, 99)
    assert game.status is Status.READY


def test_new_game_is_ready_with_no_mines_and_a_full_mine_counter():
    game = Game(9, 9, 10)
    assert game.status is Status.READY
    assert game.mines_remaining == 10
    assert all(not cell.is_mine for row in game.board.grid for cell in row)


@pytest.mark.parametrize("method", ["reveal", "toggle_flag", "chord", "is_flagged"])
@pytest.mark.parametrize("coord", [(-1, 0), (0, -1), (5, 0), (0, 5)])
def test_out_of_bounds_coordinates_raise(method, coord):
    game = Game(5, 5, 3)
    with pytest.raises(ValueError):
        getattr(game, method)(*coord)


def test_first_reveal_places_mines_exactly_once(monkeypatch):
    game = _game(5, 5, CORNER_MINES, monkeypatch=monkeypatch)
    calls = []
    place_mines = game.board.place_mines

    def spy(exclude_row, exclude_col):
        calls.append((exclude_row, exclude_col))
        place_mines(exclude_row, exclude_col)

    monkeypatch.setattr(game.board, "place_mines", spy)

    game.reveal(1, 1)
    game.reveal(4, 4)

    assert calls == [(1, 1)]
    mines = [(r, c) for r in range(5) for c in range(5) if game.board.grid[r][c].is_mine]
    assert sorted(mines) == sorted(CORNER_MINES)


def test_first_reveal_starts_the_game_and_is_never_a_mine():
    game = Game(4, 4, 15)  # every cell but the first click holds a mine
    game.reveal(1, 1)

    assert game.board.grid[1][1].is_mine is False
    assert game.status is not Status.LOST


def test_reveal_is_a_no_op_on_a_flagged_cell(monkeypatch):
    game = _corner_game(monkeypatch)
    game.toggle_flag(2, 2)

    game.reveal(2, 2)

    assert game.board.grid[2][2].revealed is False
    assert game.is_flagged(2, 2) is True


def test_reveal_is_a_no_op_once_the_game_is_over(monkeypatch):
    game = _corner_game(monkeypatch)
    game.reveal(0, 2)  # a mine
    assert game.status is Status.LOST

    game.reveal(4, 4)

    assert game.board.grid[4][4].revealed is False


def test_toggle_flag_flips_and_tracks_mines_remaining(monkeypatch):
    game = _corner_game(monkeypatch)

    game.toggle_flag(0, 0)
    assert game.is_flagged(0, 0) is True
    assert game.mines_remaining == 2

    game.toggle_flag(0, 0)
    assert game.is_flagged(0, 0) is False
    assert game.mines_remaining == 3


def test_mines_remaining_goes_negative_when_over_flagged(monkeypatch):
    game = _corner_game(monkeypatch)
    for coord in [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]:
        game.toggle_flag(*coord)

    assert game.mines_remaining == -2


def test_toggle_flag_is_a_no_op_on_a_revealed_cell(monkeypatch):
    game = _corner_game(monkeypatch)

    game.toggle_flag(1, 1)

    assert game.is_flagged(1, 1) is False
    assert game.mines_remaining == 3


def test_toggle_flag_is_a_no_op_once_the_game_is_over(monkeypatch):
    game = _corner_game(monkeypatch)
    game.reveal(0, 2)
    remaining = game.mines_remaining

    game.toggle_flag(4, 4)

    assert game.is_flagged(4, 4) is False
    assert game.mines_remaining == remaining


def test_toggle_flag_before_the_first_reveal_does_not_start_the_game(monkeypatch):
    clock = _Clock()
    game = _game(5, 5, CORNER_MINES, monkeypatch=monkeypatch, clock=clock)

    clock.advance(10)
    game.toggle_flag(0, 0)

    assert game.status is Status.READY
    assert game.elapsed == 0
    assert game.mines_remaining == 2
    assert all(not cell.is_mine for row in game.board.grid for cell in row)


def test_chord_reveals_the_unflagged_neighbors_of_a_satisfied_number(monkeypatch):
    game = _corner_game(monkeypatch)
    game.toggle_flag(0, 0)
    game.toggle_flag(0, 2)

    game.chord(1, 1)

    for coord in [(0, 1), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)]:
        assert game.board.grid[coord[0]][coord[1]].revealed is True
    assert game.board.grid[0][0].revealed is False
    assert game.board.grid[0][2].revealed is False
    assert game.board.grid[4][4].revealed is False
    assert game.status is Status.PLAYING


def test_chord_does_nothing_when_the_flag_count_does_not_match(monkeypatch):
    game = _corner_game(monkeypatch)
    game.toggle_flag(0, 0)  # (1, 1) is a 2, so one flag is not enough

    game.chord(1, 1)

    assert game.board.grid[1][0].revealed is False
    assert game.board.grid[2][2].revealed is False
    assert game.status is Status.PLAYING


def test_chord_is_a_no_op_on_a_covered_cell(monkeypatch):
    game = _corner_game(monkeypatch)

    game.chord(2, 2)

    assert game.board.grid[2][1].revealed is False


def test_chord_is_a_no_op_before_and_after_the_game(monkeypatch):
    ready = _game(5, 5, CORNER_MINES, monkeypatch=monkeypatch)
    ready.chord(1, 1)
    assert ready.status is Status.READY
    assert all(not cell.revealed for row in ready.board.grid for cell in row)

    finished = _corner_game(monkeypatch)
    finished.reveal(0, 2)
    finished.chord(1, 1)
    assert finished.exploded == (0, 2)


def test_chord_on_a_wrong_flag_loses_and_records_the_first_mine_hit(monkeypatch):
    game = _corner_game(monkeypatch)
    game.toggle_flag(1, 0)  # both flags are wrong, so chording uncovers two mines
    game.toggle_flag(1, 2)

    game.chord(1, 1)

    assert game.status is Status.LOST
    assert game.exploded == (0, 0)  # row-major: the first mine the chord hit
    assert game.board.grid[0][0].revealed is True
    assert game.board.grid[0][2].revealed is True


def test_chord_can_win_the_game(monkeypatch):
    game = _game(3, 3, [(0, 0)], monkeypatch=monkeypatch)
    game.reveal(0, 1)
    game.toggle_flag(0, 0)

    game.chord(0, 1)

    assert game.status is Status.WON


def test_losing_reveals_every_unflagged_mine_and_leaves_flagged_ones_covered(monkeypatch):
    game = _corner_game(monkeypatch)
    game.toggle_flag(0, 0)

    game.reveal(0, 2)

    assert game.status is Status.LOST
    assert game.is_over is True
    assert game.exploded == (0, 2)
    assert game.board.grid[0][2].revealed is True
    assert game.board.grid[3][1].revealed is True
    assert game.board.grid[0][0].revealed is False
    assert game.is_flagged(0, 0) is True


def test_winning_auto_flags_every_mine(monkeypatch):
    game = _game(3, 3, [(0, 0)], monkeypatch=monkeypatch)

    game.reveal(2, 2)  # flood-fills every safe cell

    assert game.status is Status.WON
    assert game.is_over is True
    assert game.mines_remaining == 0
    assert game.is_flagged(0, 0) is True
    assert game.board.grid[0][0].revealed is False


def test_elapsed_is_zero_before_the_first_reveal(monkeypatch):
    clock = _Clock()
    game = _game(3, 3, [(0, 0)], monkeypatch=monkeypatch, clock=clock)

    clock.advance(42)

    assert game.elapsed == 0


def test_elapsed_tracks_the_clock_while_playing(monkeypatch):
    clock = _Clock()
    game = _game(5, 5, CORNER_MINES, monkeypatch=monkeypatch, clock=clock)

    clock.advance(3)
    game.reveal(1, 1)
    assert game.elapsed == 0

    clock.advance(7)
    assert game.elapsed == 7


def test_elapsed_freezes_when_the_game_is_lost(monkeypatch):
    clock = _Clock()
    game = _corner_game(monkeypatch, clock=clock)

    clock.advance(4)
    game.reveal(0, 2)
    clock.advance(100)

    assert game.elapsed == 4


def test_elapsed_freezes_when_the_game_is_won(monkeypatch):
    clock = _Clock()
    game = _game(3, 3, [(0, 0)], monkeypatch=monkeypatch, clock=clock)

    game.reveal(2, 2)
    clock.advance(100)

    assert game.elapsed == 0


def test_to_dict_reports_the_scoreboard(monkeypatch):
    clock = _Clock()
    game = _corner_game(monkeypatch, clock=clock)
    game.toggle_flag(0, 0)
    clock.advance(5)

    snapshot = game.to_dict()

    assert snapshot["status"] == "playing"
    assert snapshot["rows"] == 5
    assert snapshot["cols"] == 5
    assert snapshot["mine_count"] == 3
    assert snapshot["mines_remaining"] == 2
    assert snapshot["elapsed"] == 5
    assert snapshot["exploded"] is None
    assert snapshot["grid"][1][1] == "2"
    assert snapshot["grid"][0][0] == FLAGGED


def test_to_dict_never_distinguishes_a_covered_mine_from_a_covered_blank(monkeypatch):
    game = _corner_game(monkeypatch)
    game.toggle_flag(0, 0)

    grid = game.to_dict()["grid"]

    for row in range(game.rows):
        for col in range(game.cols):
            if not game.board.grid[row][col].revealed:
                assert grid[row][col] in (COVERED, FLAGGED)


@pytest.mark.parametrize("status", [Status.READY, Status.PLAYING])
def test_to_dict_is_unchanged_when_the_hidden_mines_move(monkeypatch, status):
    game = _game(5, 5, CORNER_MINES, monkeypatch=monkeypatch)
    if status is Status.PLAYING:
        game.reveal(1, 1)
        game.toggle_flag(0, 0)
    assert game.status is status

    before = game.to_dict()["grid"]
    for row in range(game.rows):
        for col in range(game.cols):
            cell = game.board.grid[row][col]
            if not cell.revealed:
                cell.is_mine = not cell.is_mine

    assert game.to_dict()["grid"] == before


def test_to_dict_shows_the_mines_and_the_explosion_after_a_loss(monkeypatch):
    game = _corner_game(monkeypatch)
    game.toggle_flag(0, 0)

    game.reveal(0, 2)
    snapshot = game.to_dict()

    assert snapshot["status"] == "lost"
    assert snapshot["exploded"] == [0, 2]
    assert snapshot["grid"][0][2] == EXPLODED
    assert snapshot["grid"][3][1] == MINE
    assert snapshot["grid"][0][0] == FLAGGED
    assert snapshot["grid"][4][4] == COVERED


def test_to_dict_is_json_serializable(monkeypatch):
    game = _corner_game(monkeypatch)

    assert json.loads(json.dumps(game.to_dict()))["status"] == "playing"


def test_a_flag_a_flood_fill_runs_over_is_dropped(monkeypatch):
    game = _corner_game(monkeypatch)
    game.toggle_flag(4, 4)  # a wrong flag, sitting inside a blank region
    assert game.mines_remaining == 2

    game.reveal(2, 4)

    assert game.board.grid[4][4].revealed is True
    assert game.is_flagged(4, 4) is False
    assert game.mines_remaining == 3
    assert game.status is Status.PLAYING


def test_chord_stops_revealing_at_the_first_mine_it_hits(monkeypatch):
    game = _corner_game(monkeypatch)
    # (1, 1) is a 2, so two flags satisfy it -- but both of these are wrong.
    game.toggle_flag(1, 0)
    game.toggle_flag(2, 0)

    game.chord(1, 1)

    assert game.status is Status.LOST
    assert game.exploded == (0, 0)
    assert game.board.grid[0][0].revealed is True
    # Neighbors after (0, 0) in row-major order must stay covered rather than being
    # flood-filled by a chord that has already lost.
    for coord in [(0, 1), (1, 2), (2, 1), (2, 2)]:
        assert game.board.grid[coord[0]][coord[1]].revealed is False, coord
