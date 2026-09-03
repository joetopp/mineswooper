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

Enter a move as `row col` (1-indexed), e.g. `3 4`. Your first move is always safe — mines are
placed after it, never on the cell you picked. Reveal every non-mine cell to win; reveal a mine
and the game ends. Press Ctrl+C or Ctrl+D at any prompt to quit.

## Running the tests

```bash
poetry run pytest
```

## Project layout

- `mineswooper/board.py` — the `Cell`/`Board` game engine (mine placement, flood-fill reveal, win
  detection, rendering)
- `mineswooper/minesweeper.py` — the CLI game loop (prompts, input parsing, the entry point)
- `tests/` — the pytest suite
