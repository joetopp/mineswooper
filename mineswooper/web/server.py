from __future__ import annotations

import uvicorn

from mineswooper.web.api import app

# Loopback only, never 0.0.0.0: the API is unauthenticated and hands out a game to anyone who
# can reach it.
HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
