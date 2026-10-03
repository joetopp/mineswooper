import pytest

from mineswooper import minesweeper
from mineswooper.board import Board


def _feed_input(monkeypatch, lines):
    responses = iter(lines)
    monkeypatch.setattr("builtins.input", lambda *_: next(responses))


def test_prompt_dimension_returns_default_on_blank(monkeypatch):
    _feed_input(monkeypatch, [""])
    assert minesweeper._prompt_dimension("Rows", 9) == 9


def test_prompt_dimension_reprompts_on_invalid_input(monkeypatch):
    _feed_input(monkeypatch, ["abc", "-1", "0", "5"])
    assert minesweeper._prompt_dimension("Rows", 9) == 5


def test_prompt_setup_uses_defaults_on_blank_input(monkeypatch):
    _feed_input(monkeypatch, ["", "", ""])
    board = minesweeper._prompt_setup()
    assert (board.rows, board.cols, board.mine_count) == (
        minesweeper.DEFAULT_ROWS,
        minesweeper.DEFAULT_COLS,
        minesweeper.DEFAULT_MINES,
    )


def test_prompt_setup_reprompts_when_mine_count_invalid(monkeypatch):
    _feed_input(monkeypatch, ["2", "2", "4", "1"])
    board = minesweeper._prompt_setup()
    assert (board.rows, board.cols, board.mine_count) == (2, 2, 1)


def test_render_board_includes_row_and_column_headers():
    board = Board(rows=2, cols=3, mine_count=1)
    lines = minesweeper._render_board(board).split("\n")
    assert lines[0] == "  1 2 3"
    assert lines[1] == "1 . . ."
    assert lines[2] == "2 . . ."


def test_render_board_marks_flagged_cells():
    board = Board(rows=2, cols=3, mine_count=1)
    lines = minesweeper._render_board(board, flags=[(0, 1)]).split("\n")
    assert lines[1] == "1 . F ."
    assert lines[2] == "2 . . ."


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1 1", (0, 0)),
        ("3 4", (2, 3)),
        ("1", None),
        ("1 2 3", None),
        ("abc def", None),
        ("0 1", None),
        ("10 1", None),
    ],
)
def test_parse_move(raw, expected):
    assert minesweeper._parse_move(raw, rows=9, cols=9) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1 1", (minesweeper.REVEAL, 0, 0)),
        ("3 4", (minesweeper.REVEAL, 2, 3)),
        ("f 1 1", (minesweeper.FLAG, 0, 0)),
        ("F 3 4", (minesweeper.FLAG, 2, 3)),
        ("c 3 4", (minesweeper.CHORD, 2, 3)),
        ("f", None),
        ("f 1", None),
        ("f 1 2 3", None),
        ("c 0 1", None),
        ("c 10 1", None),
        ("x 1 1", None),
    ],
)
def test_parse_command(raw, expected):
    assert minesweeper._parse_command(raw, rows=9, cols=9) == expected


def test_play_wins_when_last_safe_cell_is_revealed(monkeypatch, capsys):
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: [(0, 1)])
    _feed_input(monkeypatch, ["1", "2", "1", "1 1"])

    minesweeper.play()

    assert "You win!" in capsys.readouterr().out


def test_play_reprompt_on_invalid_move_does_not_consume_a_turn(monkeypatch, capsys):
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: [(0, 1)])
    _feed_input(monkeypatch, ["1", "2", "1", "bad input", "9 9", "1 1"])

    minesweeper.play()

    output = capsys.readouterr().out
    assert output.count("Enter two numbers") == 2
    assert "You win!" in output


def test_play_flag_command_marks_the_cell_without_revealing_it(monkeypatch, capsys):
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: [(0, 1)])
    _feed_input(monkeypatch, ["1", "2", "1", "f 1 2", "1 1"])

    minesweeper.play()

    output = capsys.readouterr().out
    assert "1 . F" in output
    assert "You win!" in output


def test_play_chord_command_reveals_unflagged_neighbors_and_wins(monkeypatch, capsys):
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: [(1, 1)])
    _feed_input(monkeypatch, ["2", "2", "1", "1 1", "f 2 2", "c 1 1"])

    minesweeper.play()

    output = capsys.readouterr().out
    assert "1 1 1" in output
    assert "2 1 F" in output
    assert "You win!" in output


def test_play_hits_mine_and_reveals_full_board(monkeypatch, capsys):
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: [(1, 1)])
    _feed_input(monkeypatch, ["2", "2", "1", "1 1", "2 2"])

    minesweeper.play()

    output = capsys.readouterr().out
    assert "You hit a mine! Game over." in output
    assert "*" in output


def test_main_handles_eof_gracefully(monkeypatch, capsys):
    def _raise_eof(*_):
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)

    minesweeper.main()

    assert "Goodbye" in capsys.readouterr().out



def test_play_reports_why_a_chord_was_rejected(monkeypatch, capsys):
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: [(1, 1)])
    _feed_input(monkeypatch, ["2", "2", "1", "1 1", "c 1 1", "f 2 2", "c 1 1"])

    minesweeper.play()

    output = capsys.readouterr().out
    assert "needs exactly 1 flag(s) around it, but there are 0" in output
    assert "You win!" in output


def test_play_reports_why_a_flag_was_rejected(monkeypatch, capsys):
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: [(1, 1)])
    _feed_input(monkeypatch, ["2", "2", "1", "1 1", "f 1 1", "f 2 2", "c 1 1"])

    minesweeper.play()

    output = capsys.readouterr().out
    assert "(1, 1) is already revealed, so it cannot be flagged." in output
    assert "You win!" in output


def test_play_reports_why_revealing_a_flagged_cell_was_rejected(monkeypatch, capsys):
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: [(1, 1)])
    _feed_input(monkeypatch, ["2", "2", "1", "1 1", "f 2 2", "2 2", "c 1 1"])

    minesweeper.play()

    output = capsys.readouterr().out
    assert "(2, 2) is flagged. Unflag it with 'f 2 2'." in output
    assert "You win!" in output


def test_play_stays_quiet_when_a_move_is_legal(monkeypatch, capsys):
    monkeypatch.setattr("mineswooper.board.random.sample", lambda population, k: [(1, 1)])
    _feed_input(monkeypatch, ["2", "2", "1", "1 1", "f 2 2", "c 1 1"])

    minesweeper.play()

    output = capsys.readouterr().out
    assert "already revealed" not in output
    assert "needs exactly" not in output
    assert "is flagged." not in output
    assert "You win!" in output


def test_play_reports_a_satisfied_chord_that_has_nothing_left_to_reveal(monkeypatch, capsys):
    monkeypatch.setattr(
        "mineswooper.board.random.sample", lambda population, k: [(0, 0), (0, 2)]
    )
    # (1, 2) is a 2 with both its mines flagged; the second chord is legal but finds
    # every unflagged neighbor already uncovered.
    _feed_input(monkeypatch, ["5", "5", "2", "1 2", "f 1 1", "f 1 3", "c 1 2", "c 1 2", "3 3"])

    minesweeper.play()

    output = capsys.readouterr().out
    assert "Chording (1, 2) found nothing left to reveal." in output
    assert "needs exactly" not in output
