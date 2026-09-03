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

