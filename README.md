# mineswooper

A simple command-line Minesweeper game written in Python.

## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/) for dependency management

## Setup

```bash
poetry install
```

## Running the game

```bash
poetry run minesweeper
```

You'll be prompted for the board size and mine count, with sensible defaults (9x9, 10 mines) if
you just press Enter:

```
Rows [9]:
Columns [9]:
Mines [10]:
  1 2 3 4 5 6 7 8 9
1 . . . . . . . . .
2 . . . . . . . . .
...
Enter row col:
```

Enter a move as `row col` (1-indexed), e.g. `3 4`. Prefix it with `f` to toggle a flag on a
covered cell (`f 3 4`, drawn as `F`), or with `c` to chord a revealed number whose neighboring
flags already match it (`c 3 4`) — chording reveals that number's remaining neighbors, so a
misplaced flag loses the game. Your first move is always safe — mines are placed after it, never
on the cell you picked. Reveal every non-mine cell to win; reveal a mine and the game ends. Press
Ctrl+C or Ctrl+D at any prompt to quit.

## Running the JSON API

```bash
poetry run minesweeper-web
```

This serves a small JSON API over a single game at <http://127.0.0.1:8000> — loopback only, since
the API is unauthenticated. Every endpoint answers with the same game-state snapshot (status,
board size, mines remaining, elapsed seconds, and the grid):

| Endpoint | Body | Effect |
| --- | --- | --- |
| `GET /` | — | the current game |
| `GET /api/state` | — | the current game |
| `POST /api/new` | `{"difficulty": "beginner"}` or `{"rows": 9, "cols": 9, "mine_count": 10}` | start a new game |
| `POST /api/reveal` | `{"row": 0, "col": 0}` | reveal a cell (0-indexed) |
| `POST /api/flag` | `{"row": 0, "col": 0}` | toggle a flag |
| `POST /api/chord` | `{"row": 0, "col": 0}` | chord a revealed number |
| `POST /api/reset` | — | restart on the same board size |

Covered cells are reported as `covered` or `flagged`, so a snapshot of a game in progress never
says where the mines are. Out-of-bounds coordinates and impossible board sizes come back as 400,
an unknown difficulty or an unrecognized field as 422. Interactive docs are at `/docs`.

A `POST` that a browser labels as coming from another site is refused with 403. That is
deliberate: a form POST is a CORS simple request and skips preflight, so without the check any
page you happened to be browsing could reset your game. Requests with no `Origin` header — curl,
scripts, anything that is not a browser page — are unaffected, as are the app's own pages, which
are served from this same host.

## Running the tests

```bash
poetry run pytest
```

## Project layout

- `mineswooper/board.py` — the `Cell`/`Board` game engine (mine placement, flood-fill reveal, win
  detection, rendering)
- `mineswooper/game.py` — the `Game` rules layer shared by both frontends (status, flags, timing,
  serialization)
- `mineswooper/minesweeper.py` — the CLI game loop (prompts, input parsing, the entry point)
- `mineswooper/web/api.py` — the FastAPI app: the request/response models and the JSON endpoints
- `mineswooper/web/server.py` — the `minesweeper-web` entry point (uvicorn on 127.0.0.1)
- `tests/` — the pytest suite
