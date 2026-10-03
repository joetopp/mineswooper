from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictInt

from mineswooper.game import Difficulty, Game, Status

DEFAULT_DIFFICULTY = Difficulty.BEGINNER

# A custom board is capped so that a single request cannot ask the process to allocate an
# arbitrarily large grid. Expert is 16x30, so this leaves plenty of room.
MAX_DIMENSION = 100

app = FastAPI(title="mineswooper", description="A local JSON API over a single Minesweeper game.")

# One game per process, because this is a localhost single-player app. Routes reach it through
# get_game() at request time rather than capturing it at import, so /api/new and /api/reset can
# replace it underneath them. Every handler is `async def`, so handlers run serially on the event
# loop instead of racing each other in a threadpool.
_game: Game | None = None


def get_game() -> Game:
    """Return the process-wide game, starting a beginner game on first use."""
    global _game
    if _game is None:
        _game = Game.from_difficulty(DEFAULT_DIFFICULTY)
    return _game


def set_game(game: Game) -> Game:
    """Replace the process-wide game and return it."""
    global _game
    _game = game
    return game


# The named presets, spelled the way the JSON API accepts them. Derived from Difficulty so the
# two cannot drift: a preset added there is accepted here, instead of passing validation and then
# raising KeyError inside a handler.
DifficultyName = Enum(
    "DifficultyName",
    {member.name: member.name.lower() for member in Difficulty},
    type=str,
)


class NewGameRequest(BaseModel):
    """Either a named difficulty or a full custom size; never a mix, never half a size."""

    # Unknown fields and bool-for-int are rejected, so a typo is a 422 rather than a board the
    # caller did not ask for.
    model_config = ConfigDict(extra="forbid")

    difficulty: DifficultyName | None = None
    rows: StrictInt | None = None
    cols: StrictInt | None = None
    mine_count: StrictInt | None = None


class Move(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: StrictInt
    col: StrictInt


class GameState(BaseModel):
    """The one shape every endpoint returns: Game.to_dict(), typed.

    While the game is ready or playing the grid only ever reports covered cells as COVERED or
    FLAGGED, so a response cannot leak where the mines are.
    """

    status: Status
    rows: int
    cols: int
    mine_count: int
    mines_remaining: int
    elapsed: float
    exploded: list[int] | None
    grid: list[list[str]]


@contextmanager
def _as_bad_request() -> Iterator[None]:
    """Turn the ValueError that Game and Board raise on bad coordinates or sizes into a 400.

    Only a buggy or hostile client can produce one, so it is the client's error, not a crash.
    """
    try:
        yield
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def deny_cross_origin(request: Request) -> None:
    """Refuse a POST that a browser labelled as coming from another site.

    A form or text/plain POST is a CORS "simple request" and skips preflight, so a page the user
    merely visits could otherwise reset their game. Comparing Origin against the request's own
    Host rather than a fixed list keeps the app's own pages working on whatever host and port it
    is served from. A request with no Origin is not from a browser page, so it is left alone.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return
    if urlsplit(origin).netloc != request.headers.get("host"):
        raise HTTPException(status_code=403, detail="Cross-origin requests are not allowed.")


def _state(game: Game) -> GameState:
    return GameState.model_validate(game.to_dict())


def _new_game(request: NewGameRequest) -> Game:
    """Build the game a /api/new request asks for, rejecting anything unbuildable with a 400."""
    custom = (request.rows, request.cols, request.mine_count)
    if request.difficulty is not None and any(value is not None for value in custom):
        raise HTTPException(
            status_code=400,
            detail="Pass either a difficulty or rows, cols and mine_count, not both.",
        )
    if all(value is None for value in custom):
        difficulty = (
            Difficulty[request.difficulty.name] if request.difficulty else DEFAULT_DIFFICULTY
        )
        return Game.from_difficulty(difficulty)
    if any(value is None for value in custom):
        raise HTTPException(
            status_code=400, detail="A custom board needs all of rows, cols and mine_count."
        )

    rows, cols, mine_count = custom
    if not (1 <= rows <= MAX_DIMENSION and 1 <= cols <= MAX_DIMENSION):
        raise HTTPException(
            status_code=400, detail=f"rows and cols must be between 1 and {MAX_DIMENSION}."
        )
    with _as_bad_request():
        return Game(rows, cols, mine_count)


@app.get("/")
async def index() -> GameState:
    return _state(get_game())


@app.get("/api/state")
async def state() -> GameState:
    return _state(get_game())


@app.post("/api/new", dependencies=[Depends(deny_cross_origin)])
async def new(request: NewGameRequest | None = None) -> GameState:
    return _state(set_game(_new_game(request or NewGameRequest())))


@app.post("/api/reveal", dependencies=[Depends(deny_cross_origin)])
async def reveal(move: Move) -> GameState:
    game = get_game()
    with _as_bad_request():
        game.reveal(move.row, move.col)
    return _state(game)


@app.post("/api/flag", dependencies=[Depends(deny_cross_origin)])
async def flag(move: Move) -> GameState:
    game = get_game()
    with _as_bad_request():
        game.toggle_flag(move.row, move.col)
    return _state(game)


@app.post("/api/chord", dependencies=[Depends(deny_cross_origin)])
async def chord(move: Move) -> GameState:
    game = get_game()
    with _as_bad_request():
        game.chord(move.row, move.col)
    return _state(game)


@app.post("/api/reset", dependencies=[Depends(deny_cross_origin)])
async def reset() -> GameState:
    """Start a fresh game on the same board size."""
    game = get_game()
    return _state(set_game(Game(game.rows, game.cols, game.mine_count)))
