/* The Minesweeper frontend: it asks the JSON API in mineswooper/web/api.py for a game state and
   draws it. Hand-written, no build step, no dependencies — loaded with a plain <script> tag. */

(() => {
  "use strict";

  // The per-cell grid tokens the API uses; see mineswooper/game.py.
  const COVERED = "covered";
  const FLAGGED = "flagged";
  const MINE = "mine";
  const EXPLODED = "exploded";
  const WRONG_FLAG = "wrong_flag";

  const NUMBER = /^[1-8]$/;

  // Mirrors MAX_DIMENSION in mineswooper/web/api.py, so the custom dialog can say no before the
  // server has to.
  const MAX_DIMENSION = 100;

  /* Inline SVG ------------------------------------------------------------- */

  // Everything drawn inside a cell or on the face button is inline SVG: nothing binary to
  // commit, and the shapes stay sharp instead of blurring like a scaled bitmap.

  const FLAG_SVG = `<svg viewBox="0 0 16 16" aria-hidden="true">
    <polygon points="7,2 7,7 2.5,4.5" fill="#ff0000" />
    <rect x="7" y="2" width="1" height="7" fill="#000000" />
    <rect x="5" y="9" width="5" height="1" fill="#000000" />
    <rect x="3" y="11" width="10" height="2" fill="#000000" />
  </svg>`;

  const MINE_BODY = `<g stroke="#000000" stroke-width="1">
      <line x1="8" y1="1.5" x2="8" y2="14.5" />
      <line x1="1.5" y1="8" x2="14.5" y2="8" />
      <line x1="3.5" y1="3.5" x2="12.5" y2="12.5" />
      <line x1="12.5" y1="3.5" x2="3.5" y2="12.5" />
    </g>
    <circle cx="8" cy="8" r="4.2" fill="#000000" />
    <rect x="5.6" y="5.6" width="2" height="2" fill="#ffffff" />`;

  const MINE_SVG = `<svg viewBox="0 0 16 16" aria-hidden="true">${MINE_BODY}</svg>`;

  // A flag the player got wrong, shown only once the game is lost: the mine that was never
  // there, struck out in red.
  const WRONG_FLAG_SVG = `<svg viewBox="0 0 16 16" aria-hidden="true">
    ${MINE_BODY}
    <g stroke="#ff0000" stroke-width="1.6">
      <line x1="2" y1="2" x2="14" y2="14" />
      <line x1="14" y1="2" x2="2" y2="14" />
    </g>
  </svg>`;

  const EYES = `<circle cx="7" cy="8" r="1.1" fill="#000000" />
    <circle cx="13" cy="8" r="1.1" fill="#000000" />`;

  const SMILE = `<path d="M5.6 11.6 Q10 15.8 14.4 11.6" fill="none" stroke="#000000"
    stroke-width="1.2" />`;

  const face = (features) => `<svg viewBox="0 0 20 20" aria-hidden="true">
    <circle cx="10" cy="10" r="8.5" fill="#ffff00" stroke="#000000" />
    ${features}
  </svg>`;

  // The four states of the one button that matters: at rest, holding a click, won, lost.
  const FACES = {
    playing: face(EYES + SMILE),
    down: face(`${EYES}
      <circle cx="10" cy="13" r="2.1" fill="none" stroke="#000000" stroke-width="1.2" />`),
    won: face(`<path d="M3.5 6.6 H16.5" stroke="#000000" stroke-width="1.2" />
      <path d="M4.6 7.4 H9.2 L8.4 10.8 H5.8 Z" fill="#000000" />
      <path d="M10.8 7.4 H15.4 L14.2 10.8 H11.6 Z" fill="#000000" />
      ${SMILE}`),
    lost: face(`<g stroke="#000000" stroke-width="1.2">
        <line x1="5.4" y1="6.4" x2="8.6" y2="9.6" />
        <line x1="8.6" y1="6.4" x2="5.4" y2="9.6" />
        <line x1="11.4" y1="6.4" x2="14.6" y2="9.6" />
        <line x1="14.6" y1="6.4" x2="11.4" y2="9.6" />
        <path d="M5.6 14.4 Q10 10.2 14.4 14.4" fill="none" />
      </g>`),
  };

  /* Three-digit LED displays ----------------------------------------------- */

  // A seven-segment digit in a 13x23 box, the proportions of the original counter. The segments
  // carry their conventional names: a is the top bar, g the middle one, b and c the right pair.
  const SEGMENTS = ["a", "b", "c", "d", "e", "f", "g"];
  const ARM = 1.5; // half a segment's thickness, which is also the length of its mitred tip

  const bar = (y) =>
    `1.5,${y} 3,${y - ARM} 10,${y - ARM} 11.5,${y} 10,${y + ARM} 3,${y + ARM}`;

  const post = (x, top, bottom) =>
    `${x},${top} ${x + ARM},${top + ARM} ${x + ARM},${bottom - ARM} ` +
    `${x},${bottom} ${x - ARM},${bottom - ARM} ${x - ARM},${top + ARM}`;

  const SEGMENT_POINTS = {
    a: bar(2.5),
    b: post(10.5, 2.5, 11.5),
    c: post(10.5, 11.5, 20.5),
    d: bar(20.5),
    e: post(2.5, 11.5, 20.5),
    f: post(2.5, 2.5, 11.5),
    g: bar(11.5),
  };

  const LIT = {
    0: "abcdef",
    1: "bc",
    2: "abdeg",
    3: "abcdg",
    4: "bcfg",
    5: "acdfg",
    6: "acdefg",
    7: "abc",
    8: "abcdefg",
    9: "abcdfg",
    "-": "g",
  };

  const DIGIT_SVG = `<svg viewBox="0 0 13 23" aria-hidden="true">${SEGMENTS.map(
    (name) => `<polygon class="segment" points="${SEGMENT_POINTS[name]}" />`
  ).join("")}</svg>`;

  // "-12" when the player has over-flagged, "007" for a timer that just started. Both displays
  // are three digits wide, so a value that does not fit is pinned at the extreme.
  function digits(value) {
    const rounded = Math.round(value);
    if (rounded > 999) {
      return "999";
    }
    if (rounded < 0) {
      return `-${String(Math.min(99, -rounded)).padStart(2, "0")}`;
    }
    return String(rounded).padStart(3, "0");
  }

  function createDisplay(element) {
    const label = element.getAttribute("aria-label");
    element.innerHTML = DIGIT_SVG.repeat(3);
    const places = [...element.querySelectorAll("svg")].map((svg) =>
      svg.querySelectorAll(".segment")
    );

    return (value) => {
      const text = digits(value);
      element.setAttribute("aria-label", `${label}: ${text}`);
      places.forEach((polygons, place) => {
        const lit = LIT[text.charAt(place)] ?? "";
        SEGMENTS.forEach((name, index) => {
          polygons[index].classList.toggle("on", lit.includes(name));
        });
      });
    };
  }

  /* Elements and state ----------------------------------------------------- */

  const app = document.getElementById("app");
  const gridElement = document.getElementById("grid");
  const faceButton = document.getElementById("face");
  const menuBar = document.querySelector(".menu-bar");
  const menuButton = document.getElementById("game-menu-button");
  const menu = document.getElementById("game-menu");
  const modal = document.getElementById("custom-modal");
  const customForm = document.getElementById("custom-form");
  const customRows = document.getElementById("custom-rows");
  const customCols = document.getElementById("custom-cols");
  const customMines = document.getElementById("custom-mines");
  const customError = document.getElementById("custom-error");
  const showMineCount = createDisplay(document.getElementById("mine-counter"));
  const showTimer = createDisplay(document.getElementById("timer"));

  let snapshot = null; // the last game state the server sent
  let receivedAt = 0; // performance.now() when it arrived, so the clock can tick between moves
  let cells = []; // one element per cell, row-major
  let tokens = []; // the token each of those elements is currently showing
  let gridCols = 0; // the board the grid elements were built for
  let mood = null; // which face is drawn
  let ticker = null; // the timer's interval handle, non-null only while the game is playing

  let pressed = null; // the covered cell drawn held down, which follows a left-button drag
  let armed = false; // a left press started on the board, so its release is ours to act on
  let origin = null; // the cell that left press started on, which alone its release may chord
  let swallowUntilRelease = false; // a chord has fired; mouseups are dead until the mouse is idle

  const status = () => (snapshot === null ? "ready" : snapshot.status);
  const isOver = () => status() === "won" || status() === "lost";
  const indexOf = (cell) => Number(cell.dataset.row) * gridCols + Number(cell.dataset.col);
  const tokenOf = (cell) => tokens[indexOf(cell)];

  /* Talking to the API ----------------------------------------------------- */

  // Moves go out one at a time. The server keeps a single game, and applying its answers in the
  // order they were asked for keeps a slow response from redrawing the board backwards.
  let queue = Promise.resolve();

  function enqueue(task) {
    queue = queue.then(task).catch(report);
    return queue;
  }

  async function request(method, path, body) {
    const options = { method, headers: {} };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(describe(payload, response));
    }
    return payload;
  }

  // FastAPI answers 400 with a string detail and 422 with a list of per-field errors.
  function describe(payload, response) {
    const detail = payload?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail) && detail[0]?.msg) {
      return detail[0].msg;
    }
    return `The server answered ${response.status}.`;
  }

  function report(error) {
    // There is nothing useful to draw: the board still shows the last state the server confirmed.
    console.error("mineswooper:", error.message ?? error);
  }

  function apply(state) {
    snapshot = state;
    receivedAt = performance.now();
    render();
    return state;
  }

  function move(path, cell) {
    if (cell === null || isOver()) {
      return;
    }
    const body = { row: Number(cell.dataset.row), col: Number(cell.dataset.col) };
    enqueue(() => request("POST", path, body).then(apply));
  }

  const newGame = (body) => request("POST", "/api/new", body).then(apply);

  /* Drawing ---------------------------------------------------------------- */

  function buildGrid(rows, cols) {
    const fragment = document.createDocumentFragment();
    cells = [];
    tokens = [];
    for (let row = 0; row < rows; row += 1) {
      for (let col = 0; col < cols; col += 1) {
        const cell = document.createElement("div");
        cell.className = "cell";
        cell.dataset.row = String(row);
        cell.dataset.col = String(col);
        cells.push(cell);
        tokens.push(COVERED);
        fragment.appendChild(cell);
      }
    }
    gridCols = cols;
    pressed = null;
    armed = false;
    gridElement.style.setProperty("--cols", String(cols));
    gridElement.replaceChildren(fragment);
  }

  function paint(cell, token) {
    cell.className = "cell";
    cell.textContent = "";
    delete cell.dataset.count;
    if (token === COVERED) {
      return;
    }
    if (token === FLAGGED) {
      cell.innerHTML = FLAG_SVG;
      return;
    }
    cell.classList.add("open");
    if (token === MINE) {
      cell.innerHTML = MINE_SVG;
    } else if (token === EXPLODED) {
      cell.classList.add("exploded");
      cell.innerHTML = MINE_SVG;
    } else if (token === WRONG_FLAG) {
      cell.innerHTML = WRONG_FLAG_SVG;
    } else if (NUMBER.test(token)) {
      cell.dataset.count = token;
      cell.textContent = token;
    }
  }

  function render() {
    if (snapshot.cols !== gridCols || snapshot.rows * snapshot.cols !== cells.length) {
      buildGrid(snapshot.rows, snapshot.cols);
    }
    // Only the cells whose token changed are touched, so a repaint cannot flicker the board or
    // rub out the cell the player is holding down.
    snapshot.grid.forEach((row, rowIndex) => {
      row.forEach((token, colIndex) => {
        const index = rowIndex * snapshot.cols + colIndex;
        if (token !== tokens[index]) {
          paint(cells[index], token);
          tokens[index] = token;
        }
      });
    });
    showMineCount(snapshot.mines_remaining);
    setFace();
    tick();
  }

  function setFace(override) {
    const next = override ?? (isOver() ? status() : "playing");
    if (next !== mood) {
      mood = next;
      faceButton.innerHTML = FACES[next];
    }
  }

  // The server owns the clock; this only interpolates between its answers, and stops moving the
  // moment the game is over, because `elapsed` freezes then.
  function elapsed() {
    if (snapshot === null) {
      return 0;
    }
    const since = snapshot.status === "playing" ? (performance.now() - receivedAt) / 1000 : 0;
    return Math.max(0, Math.floor(snapshot.elapsed + since));
  }

  function tick() {
    showTimer(elapsed());
    const running = status() === "playing";
    if (running && ticker === null) {
      ticker = window.setInterval(() => showTimer(elapsed()), 200);
    } else if (!running && ticker !== null) {
      window.clearInterval(ticker);
      ticker = null;
    }
  }

  /* Mouse input ------------------------------------------------------------ */

  function cellAt(target) {
    const element = target?.closest ? target.closest(".cell") : null;
    return element !== null && element.parentNode === gridElement ? element : null;
  }

  function press(cell) {
    if (pressed === cell) {
      return;
    }
    release();
    if (cell !== null && tokenOf(cell) === COVERED) {
      pressed = cell;
      cell.classList.add("pressed");
    }
  }

  function release() {
    if (pressed !== null) {
      pressed.classList.remove("pressed");
      pressed = null;
    }
  }

  gridElement.addEventListener("mousedown", (event) => {
    // Keep the browser from starting a text selection or a middle-click autoscroll.
    event.preventDefault();
    const cell = cellAt(event.target);
    const bothButtons = (event.buttons & 1) !== 0 && (event.buttons & 2) !== 0;

    if (bothButtons || event.button === 1) {
      // The classic two-button chord, and middle click for a mouse that has a third button.
      swallowUntilRelease = true;
      armed = false;
      release();
      setFace();
      move("/api/chord", cell);
      return;
    }
    // ctrl+click is the macOS right click, and Chrome reports it as button 0 with ctrlKey.
    if (event.button === 2 || (event.button === 0 && event.ctrlKey)) {
      move("/api/flag", cell);
      return;
    }
    if (event.button === 0 && !isOver()) {
      armed = cell !== null;
      origin = cell;
      press(cell);
      setFace("down");
    }
  });

  // Holding the left button and dragging moves the press, so a click can be re-aimed or called
  // off by letting go away from the board.
  gridElement.addEventListener("mouseover", (event) => {
    if (!armed || (event.buttons & 1) === 0) {
      return;
    }
    press(cellAt(event.target));
  });

  gridElement.addEventListener("mouseleave", release);

  // On window rather than the grid: a press released off the board has to be cleaned up too.
  window.addEventListener("mouseup", (event) => {
    if (swallowUntilRelease) {
      // Releasing the first of two held buttons fires a mouseup with the other still down, and
      // releasing the second fires another. The chord already happened on mousedown, so every
      // mouseup is dead until no button is left pressed.
      if (event.buttons === 0) {
        swallowUntilRelease = false;
      }
      return;
    }
    if (event.button !== 0 || !armed) {
      return;
    }
    armed = false;
    const cell = cellAt(event.target);
    const startedHere = cell !== null && cell === origin;
    origin = null;
    release();
    setFace();
    if (cell === null) {
      return;
    }
    if (tokenOf(cell) === COVERED) {
      move("/api/reveal", cell);
    } else if (startedHere && NUMBER.test(tokenOf(cell))) {
      // A left click on an open number chords it. A trackpad has neither a second button nor a
      // middle click, so without this there is no way to chord at all; the original game does
      // not behave this way. Only a press that began on this number counts: dragging onto one
      // and letting go is how a click is called off, and must never fire a move.
      move("/api/chord", cell);
    }
  });

  // Right-clicking the board plants a flag, so the browser's own menu has to stay shut.
  app.addEventListener("contextmenu", (event) => event.preventDefault());

  faceButton.addEventListener("click", () => {
    enqueue(() => request("POST", "/api/reset").then(apply));
  });

  /* The Game menu ---------------------------------------------------------- */

  function openMenu(open) {
    menu.hidden = !open;
    menuButton.setAttribute("aria-expanded", String(open));
  }

  menuButton.addEventListener("click", () => openMenu(menu.hidden));

  menu.addEventListener("click", (event) => {
    const item = event.target.closest(".menu-item");
    if (item === null) {
      return;
    }
    openMenu(false);
    if (item.dataset.difficulty) {
      enqueue(() => newGame({ difficulty: item.dataset.difficulty }));
    } else {
      openCustomDialog();
    }
  });

  document.addEventListener("mousedown", (event) => {
    if (!menu.hidden && !menuBar.contains(event.target)) {
      openMenu(false);
    }
  });

  /* The Custom Field dialog ------------------------------------------------ */

  // In-page, not window.prompt(): a prompt cannot be styled, cannot ask three questions at once,
  // and blocks the page while it is open.
  function openCustomDialog() {
    customRows.value = String(snapshot?.rows ?? 9);
    customCols.value = String(snapshot?.cols ?? 9);
    customMines.value = String(snapshot?.mine_count ?? 10);
    showDialogError(null);
    modal.hidden = false;
    customRows.focus();
    customRows.select();
  }

  const closeCustomDialog = () => {
    modal.hidden = true;
  };

  function showDialogError(message) {
    customError.textContent = message ?? "";
    customError.hidden = message === null;
  }

  function whole(input) {
    const value = Number(input.value);
    return Number.isInteger(value) ? value : NaN;
  }

  customForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const rows = whole(customRows);
    const cols = whole(customCols);
    const mineCount = whole(customMines);

    if (!(rows >= 1 && rows <= MAX_DIMENSION) || !(cols >= 1 && cols <= MAX_DIMENSION)) {
      showDialogError(`Height and width must be whole numbers from 1 to ${MAX_DIMENSION}.`);
      return;
    }
    if (!(mineCount >= 0 && mineCount <= rows * cols - 1)) {
      showDialogError(
        `Mines must be a whole number from 0 to ${rows * cols - 1}, leaving room for the ` +
          "first click."
      );
      return;
    }

    enqueue(() =>
      newGame({ rows, cols, mine_count: mineCount }).then(closeCustomDialog, (error) =>
        showDialogError(error.message)
      )
    );
  });

  document.getElementById("custom-cancel").addEventListener("click", closeCustomDialog);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      openMenu(false);
      closeCustomDialog();
    }
  });

  /* Start ------------------------------------------------------------------ */

  setFace();
  showMineCount(0);
  showTimer(0);
  enqueue(() => request("GET", "/api/state").then(apply));
})();
