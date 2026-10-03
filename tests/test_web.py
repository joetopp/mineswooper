import json

import pytest
from fastapi.testclient import TestClient

from mineswooper.game import COVERED, EXPLODED, FLAGGED, MINE, Difficulty, Game
from mineswooper.web import api, server

STATE_KEYS = {
    "status",
    "rows",
    "cols",
    "mine_count",
    "mines_remaining",
    "elapsed",
    "exploded",
    "grid",
}

# The 5x5 layout from test_game: every neighbor of (1, 1) is a mine or a number, so revealing
# (1, 1) never flood-fills and most of the board stays covered.
#
#   * 2 * 0 0
#   1 2 1 0 0
#   1 1 1 0 0
#   1 * 1 0 0
#   1 1 1 0 0
CORNER_MINES = [(0, 0), (0, 2), (3, 1)]


@pytest.fixture
def client():
    """A client over a fresh beginner game, so tests never inherit each other's board."""
    api.set_game(Game.from_difficulty(api.DEFAULT_DIFFICULTY))
    yield TestClient(api.app)
    api.set_game(Game.from_difficulty(api.DEFAULT_DIFFICULTY))


def _install_corner_game(monkeypatch):
    """Install a game whose first reveal lays CORNER_MINES, wherever the player clicks."""
    monkeypatch.setattr(
        "mineswooper.board.random.sample", lambda population, k: list(CORNER_MINES)
    )
    return api.set_game(Game(5, 5, len(CORNER_MINES)))


def test_get_game_creates_a_beginner_game_once(monkeypatch):
    monkeypatch.setattr(api, "_game", None)

    game = api.get_game()

    assert (game.rows, game.cols, game.mine_count) == (9, 9, 10)
    assert api.get_game() is game


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("GET", "/", None),
        ("GET", "/api/state", None),
        ("POST", "/api/new", {}),
        ("POST", "/api/reveal", {"row": 0, "col": 0}),
        ("POST", "/api/flag", {"row": 0, "col": 0}),
        ("POST", "/api/chord", {"row": 0, "col": 0}),
        ("POST", "/api/reset", None),
    ],
)
def test_every_endpoint_returns_the_game_state_shape(client, method, path, body):
    response = client.request(method, path, json=body)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == STATE_KEYS
    assert (payload["rows"], payload["cols"]) == (9, 9)
    assert len(payload["grid"]) == 9
    assert all(len(row) == 9 for row in payload["grid"])


def test_state_reports_a_fresh_beginner_game(client):
    payload = client.get("/api/state").json()

    assert payload["status"] == "ready"
    assert (payload["mine_count"], payload["mines_remaining"]) == (10, 10)
    assert payload["elapsed"] == 0.0
    assert payload["exploded"] is None
    assert all(token == COVERED for row in payload["grid"] for token in row)


@pytest.mark.parametrize(
    "difficulty, rows, cols, mine_count",
    [
        ("beginner", 9, 9, 10),
        ("intermediate", 16, 16, 40),
        ("expert", 16, 30, 99),
    ],
)
def test_new_accepts_each_named_difficulty(client, difficulty, rows, cols, mine_count):
    payload = client.post("/api/new", json={"difficulty": difficulty}).json()

    assert (payload["rows"], payload["cols"], payload["mine_count"]) == (rows, cols, mine_count)
    assert payload["status"] == "ready"


def test_new_without_a_body_falls_back_to_the_default_difficulty(client):
    response = client.post("/api/new")

    assert response.status_code == 200
    assert response.json()["rows"] == api.DEFAULT_DIFFICULTY.rows


def test_new_accepts_a_custom_board(client):
    payload = client.post("/api/new", json={"rows": 4, "cols": 6, "mine_count": 3}).json()

    assert (payload["rows"], payload["cols"], payload["mine_count"]) == (4, 6, 3)


def test_new_replaces_the_game_in_progress(client, monkeypatch):
    _install_corner_game(monkeypatch)
    client.post("/api/reveal", json={"row": 1, "col": 1})

    payload = client.post("/api/new", json={"difficulty": "beginner"}).json()

    assert payload["status"] == "ready"
    assert all(token == COVERED for row in payload["grid"] for token in row)


def test_unrecognized_difficulty_is_unprocessable(client):
    response = client.post("/api/new", json={"difficulty": "nightmare"})

    assert response.status_code == 422


def test_the_accepted_difficulty_names_are_exactly_the_presets():
    assert {name.name for name in api.DifficultyName} == {d.name for d in Difficulty}
    assert {name.value for name in api.DifficultyName} == {"beginner", "intermediate", "expert"}


@pytest.mark.parametrize(
    "body",
    [
        {"difficultly": "expert"},
        {"mine_countt": 5},
        {"difficulty": "expert", "extra": 1},
        {"rows": True, "cols": 4, "mine_count": 2},
        {"rows": 4, "cols": 4, "mine_count": False},
    ],
)
def test_a_misspelled_or_mistyped_field_is_unprocessable(client, body):
    """A typo must not quietly yield a different board than the caller asked for."""
    response = client.post("/api/new", json=body)

    assert response.status_code == 422
    assert client.get("/api/state").json()["rows"] == 9


@pytest.mark.parametrize("path", ["/api/reveal", "/api/flag", "/api/chord"])
def test_a_move_with_an_unknown_field_is_unprocessable(client, path):
    assert client.post(path, json={"row": 0, "col": 0, "extra": 1}).status_code == 422
    assert client.post(path, json={"row": True, "col": 0}).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"rows": 0, "cols": 9, "mine_count": 1},
        {"rows": api.MAX_DIMENSION + 1, "cols": 9, "mine_count": 1},
        {"rows": 9, "cols": 10**9, "mine_count": 1},
        {"rows": 9, "cols": -1, "mine_count": 1},
        {"rows": 2, "cols": 2, "mine_count": 4},
        {"rows": 2, "cols": 2, "mine_count": -1},
        {"rows": 4},
        {"rows": 4, "cols": 4},
        {"difficulty": "beginner", "rows": 4, "cols": 4, "mine_count": 2},
    ],
)
def test_invalid_custom_dimensions_are_a_bad_request(client, body):
    response = client.post("/api/new", json=body)

    assert response.status_code == 400
    assert response.json()["detail"]
    # The rejected request left the running game untouched.
    assert client.get("/api/state").json()["rows"] == 9


@pytest.mark.parametrize("path", ["/api/reveal", "/api/flag", "/api/chord"])
@pytest.mark.parametrize(
    "move", [{"row": -1, "col": 0}, {"row": 0, "col": 9}, {"row": 99, "col": 99}]
)
def test_out_of_bounds_coordinates_are_a_bad_request(client, path, move):
    response = client.post(path, json=move)

    assert response.status_code == 400
    assert response.json()["detail"]
    # The server is still serving the same game.
    assert client.get("/api/state").status_code == 200


@pytest.mark.parametrize("path", ["/api/reveal", "/api/flag", "/api/chord"])
def test_a_move_without_coordinates_is_unprocessable(client, path):
    assert client.post(path, json={"row": 0}).status_code == 422
    assert client.post(path, json={"row": "x", "col": 0}).status_code == 422


POST_PATHS = ["/api/new", "/api/reveal", "/api/flag", "/api/chord", "/api/reset"]


@pytest.mark.parametrize("path", POST_PATHS)
@pytest.mark.parametrize("origin", ["https://evil.example", "http://127.0.0.1:9999"])
def test_a_post_from_another_site_is_forbidden(client, monkeypatch, path, origin):
    """A cross-origin form POST is a CORS simple request and skips preflight.

    Without this check any page the user happened to be browsing could reset their game.
    """
    _install_corner_game(monkeypatch)
    client.post("/api/reveal", json={"row": 1, "col": 1})
    before = client.get("/api/state").json()

    response = client.post(
        path,
        content="row=0&col=0",
        headers={"Origin": origin, "Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 403
    # The same game is still running: only elapsed, which ticks on its own, may have moved.
    after = client.get("/api/state").json()
    assert {key: value for key, value in after.items() if key != "elapsed"} == {
        key: value for key, value in before.items() if key != "elapsed"
    }


@pytest.mark.parametrize("path", POST_PATHS)
def test_a_post_from_the_apps_own_page_is_allowed(client, path):
    """The frontend is served from this same host, and browsers send Origin on its POSTs too."""
    body = {"row": 0, "col": 0} if path not in {"/api/new", "/api/reset"} else {}

    response = client.post(path, json=body, headers={"Origin": "http://testserver"})

    assert response.status_code == 200


def test_a_post_with_no_origin_header_is_allowed(client):
    """curl and the CLI send no Origin; only browser pages do."""
    assert client.post("/api/reset").status_code == 200


def test_reveal_starts_the_game_and_uncovers_the_cell(client, monkeypatch):
    _install_corner_game(monkeypatch)

    payload = client.post("/api/reveal", json={"row": 1, "col": 1}).json()

    assert payload["status"] == "playing"
    assert payload["grid"][1][1] == "2"


def test_flag_toggles_and_moves_the_mine_counter(client):
    flagged = client.post("/api/flag", json={"row": 0, "col": 0}).json()
    assert flagged["grid"][0][0] == FLAGGED
    assert flagged["mines_remaining"] == 9

    unflagged = client.post("/api/flag", json={"row": 0, "col": 0}).json()
    assert unflagged["grid"][0][0] == COVERED
    assert unflagged["mines_remaining"] == 10


def test_chord_reveals_the_neighbors_of_a_satisfied_number(client, monkeypatch):
    _install_corner_game(monkeypatch)
    client.post("/api/reveal", json={"row": 1, "col": 1})
    client.post("/api/flag", json={"row": 0, "col": 0})
    client.post("/api/flag", json={"row": 0, "col": 2})

    payload = client.post("/api/chord", json={"row": 1, "col": 1}).json()

    assert payload["status"] == "playing"
    assert payload["grid"][0][1] == "2"
    assert payload["grid"][1][0] == "1"
    assert payload["grid"][2][2] == "1"


def test_an_illegal_move_is_a_no_op_rather_than_an_error(client, monkeypatch):
    _install_corner_game(monkeypatch)
    client.post("/api/reveal", json={"row": 1, "col": 1})

    response = client.post("/api/chord", json={"row": 4, "col": 4})

    assert response.status_code == 200
    assert response.json()["grid"][4][4] == COVERED


def test_losing_reports_the_explosion_and_the_mines(client, monkeypatch):
    _install_corner_game(monkeypatch)
    client.post("/api/reveal", json={"row": 1, "col": 1})

    payload = client.post("/api/reveal", json={"row": 0, "col": 0}).json()

    assert payload["status"] == "lost"
    assert payload["exploded"] == [0, 0]
    assert payload["grid"][0][0] == EXPLODED
    assert payload["grid"][3][1] == MINE


def test_a_game_in_progress_never_reveals_a_mine(client, monkeypatch):
    _install_corner_game(monkeypatch)

    response = client.post("/api/reveal", json={"row": 1, "col": 1})

    payload = response.json()
    assert payload["status"] == "playing"
    tokens = {token for row in payload["grid"] for token in row}
    assert tokens <= {COVERED, FLAGGED, "0", "1", "2", "3", "4", "5", "6", "7", "8"}
    # Not even as a substring of the serialized grid: the mine-revealing tokens appear nowhere
    # in the part of the response that describes cells. ("mine_count" legitimately does.)
    grid_text = json.dumps(payload["grid"])
    assert MINE not in grid_text
    assert EXPLODED not in grid_text


def test_reset_restarts_the_same_board(client, monkeypatch):
    _install_corner_game(monkeypatch)
    client.post("/api/reveal", json={"row": 1, "col": 1})
    client.post("/api/flag", json={"row": 0, "col": 0})

    payload = client.post("/api/reset").json()

    assert payload["status"] == "ready"
    assert (payload["rows"], payload["cols"], payload["mine_count"]) == (5, 5, 3)
    assert payload["mines_remaining"] == 3
    assert payload["elapsed"] == 0.0
    assert all(token == COVERED for row in payload["grid"] for token in row)


def test_index_and_state_report_the_same_game(client, monkeypatch):
    _install_corner_game(monkeypatch)
    client.post("/api/reveal", json={"row": 1, "col": 1})

    index, state = client.get("/").json(), client.get("/api/state").json()

    assert index["grid"] == state["grid"]
    assert index["status"] == state["status"] == "playing"


def test_server_binds_loopback_only(monkeypatch):
    calls = []
    monkeypatch.setattr(server.uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs)))

    server.main()

    assert calls == [(api.app, {"host": "127.0.0.1", "port": server.PORT})]
    assert server.HOST == "127.0.0.1"
