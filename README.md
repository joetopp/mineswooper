# mineswooper

Minesweeper in Python: a command-line game, and a Windows 95-style web frontend over a small
JSON API. Both play the same rules engine.

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

Moves are `row col`, 1-indexed, with an optional action prefix:

| Command | Effect |
| --- | --- |
| `3 4` | reveal row 3, column 4 |
| `f 3 4` | toggle a flag on a covered cell, drawn as `F` |
| `c 3 4` | chord a revealed number whose neighboring flags already match it |

Chording reveals that number's remaining neighbors, so a misplaced flag loses the game. Your
first move is always safe — mines are placed after it, never on the cell you picked. Reveal
every non-mine cell to win; reveal a mine and the game ends. Press Ctrl+C or Ctrl+D at any
prompt to quit.

## Playing in the browser

```bash
poetry run minesweeper-web
```

Then open <http://127.0.0.1:8000/static/>. The same process serves both the page and the JSON
API, and it has to: **the page must be served, not opened over `file://`**. Loaded off disk it
is a different origin from the API, so its GETs fail for want of CORS headers and its POSTs come
back 403. There is nothing to build first — the frontend is three hand-written files in
`mineswooper/web/static/` (`index.html`, `style.css`, `app.js`), with no build step, no npm and
no CDN. Flags, mines and the smiley are inline SVG, so there are no image files either. Edit a
file, reload the page.

| Action | Mouse |
| --- | --- |
| Reveal a cell | left click |
| Flag a cell | right click — the browser's context menu is suppressed over the window |
| Chord a revealed number | both buttons at once, middle click, **or** left click on the number |
| New game on the same board | click the smiley |
| Change the board | the Game menu: Beginner, Intermediate, Expert, or Custom... |

Custom boards are asked for in an in-page dialog rather than `window.prompt()`, and a size the
server would refuse is refused there first. The mine counter and the timer are three-digit LED
displays: the counter goes negative when you over-flag, and the timer starts on the first reveal
and freezes at game over, taking its reading from the server rather than from the browser.

That third way to chord — a plain left click on an already-revealed number — is a deliberate
deviation from the original game, where that click does nothing. A trackpad has no middle button
and no comfortable two-button hold, so without it there would be no way to chord at all. It only
applies to open numbered cells, so it never takes a reveal away from you.

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
says where the mines are. The one exception comes after a loss, when a flag on a cell that held
no mine is reported as `wrong_flag` — the frontend crosses those out, the way the original game
does, and by then the round is over and there is nothing left to give away.

Out-of-bounds coordinates and impossible board sizes come back as 400, an unknown difficulty or
an unrecognized field as 422. Interactive docs are at `/docs`.

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
- `mineswooper/web/static/` — the browser frontend: `index.html`, `style.css`, `app.js`
- `tests/` — the pytest suite
