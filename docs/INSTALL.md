# Installing AI Invoice Intake

There are two ways to install the project. Pick the one that fits:

| | [Part 1: Run the app](#part-1-run-the-app-with-docker) | [Part 2: Set up for development](#part-2-set-up-for-development) |
|---|---|---|
| **For** | Trying the product, a demo, a review | Changing the code, running the tests |
| **You install** | Git and Docker | Git, Docker, Node.js and Python |
| **Time** | About 10 minutes, most of it the first build | About 20 minutes |

Everything runs on your own computer with synthetic data. Nothing is sent anywhere unless you choose to use OpenAI (see [Settings](#settings-optional)).

---

## Part 1: Run the app with Docker

Docker runs the whole product in containers: the database, the queue, the API, the background worker, the web dashboard and a stand-in for an accounting system. You don't need Python or Node.js for this part.

### Step 1: Install Git and Docker

**Git** downloads the project.

- Windows: install it from [git-scm.com](https://git-scm.com/download/win) and keep the default options.
- macOS: run `xcode-select --install` in Terminal, or install Git with Homebrew.
- Linux: use your package manager, for example `sudo apt install git`.

**Docker** runs the app.

- Windows and macOS: install [Docker Desktop](https://www.docker.com/products/docker-desktop/). On Windows the installer may ask to turn on WSL 2. Say yes, and restart the computer if it asks.
- Linux: install [Docker Engine](https://docs.docker.com/engine/install/) and its Compose plugin (`docker-compose-plugin`).

Docker needs about 4 GB of memory and 2 GB of free disk space for this project. Docker Desktop's defaults are enough.

**Check both.** Open a terminal (PowerShell on Windows, Terminal on macOS or Linux) and run:

```bash
git --version
docker compose version
```

You should see two version numbers. Docker Compose must be **v2.17 or newer**. If the terminal says `command not found` or `is not recognized`, close it and open a new one so it picks up the new programs, then try again.

### Step 2: Start Docker

Installing Docker Desktop doesn't keep it running. **Open Docker Desktop every time before you use the app**, and wait until it shows that the engine is running. On Linux the Docker service usually starts on its own.

Check that Docker answers:

```bash
docker info
```

If it prints a long list of details, Docker is ready. If it prints an error such as `Cannot connect to the Docker daemon` or `error during connect`, Docker isn't running yet. Start Docker Desktop and wait a moment.

### Step 3: Download the project

In the terminal, go to the folder where you keep projects, then run:

```bash
git clone https://github.com/maideps/ai-invoice-intake.git
cd ai-invoice-intake
```

This creates an `ai-invoice-intake` folder and moves into it. Every later command in this part runs **from this folder**.

> No Git? On the [GitHub page](https://github.com/maideps/ai-invoice-intake), choose **Code → Download ZIP**, unzip it, and open a terminal in the unzipped folder (`ai-invoice-intake-main`).

### Step 4: Start the app

```bash
docker compose up --build
```

What happens:

1. **The first time**, Docker downloads the base images and builds two images, one for the backend and one for the dashboard. That takes **about 3 to 5 minutes**, depending on your connection, and prints a lot of build output. Later starts take seconds.
2. Docker starts PostgreSQL and Redis, applies the database migrations, then starts the API, the worker, the dashboard and the demo accounting system.
3. On the first start, the `seed` service uploads the 12 synthetic sample invoices, and the worker reads them right away.

The app is ready when you see this line:

```text
seed-1  | Uploaded 12 sample invoices; the worker extracts them next.
```

The terminal keeps printing what the services do. **Leave this terminal open**: closing it or pressing `Ctrl+C` stops the app.

> Prefer to get the terminal back? Start it in the background with `docker compose up --build -d`, follow the logs with `docker compose logs -f` (`Ctrl+C` stops following, not the app), and check the services with `docker compose ps`.

### Step 5: Open the app

Open **http://localhost:8080** in your browser.

You should see the review queue with **12 invoices in "Needs review"**. Then try the main flow:

1. Open an invoice. The original PDF is on the left and the fields the AI read are on the right.
2. Click a field, such as **Total**. Its value is highlighted where it is printed in the PDF. Amber fields are the ones the model was unsure about.
3. Correct a field if you like, then **Save changes**.
4. Press **Approve** (or the `A` key). A few seconds later the invoice shows **Exported**.

The export went to a demo accounting system that runs alongside the app. To see what it received, open **http://localhost:9000/deliveries**, or run this in a second terminal, from the project folder:

```bash
docker compose logs accounting
```

To record who approves, click your name at the top right ("Acting as") and type one. It appears in the audit trail.

### Step 6: Stop, restart and clean up

All of these run from the project folder.

| To... | Run | What happens to your data |
|---|---|---|
| Stop the app | `Ctrl+C` in the terminal where it runs, or `docker compose stop` | Kept |
| Start it again later | Open Docker Desktop, then `docker compose up` | Kept |
| Update to the latest version | `git pull`, then `docker compose up --build` | Kept |
| Remove the containers | `docker compose down` | Kept; `docker compose up` brings it back |
| Start over with the 12 fresh samples | `docker compose down -v`, then `docker compose up` | **Deleted** |
| Uninstall completely | `docker compose down -v --rmi all`, then delete the folder | **Deleted**, along with the images the app used (including PostgreSQL and Redis; Docker downloads them again if another project needs them) |

### Settings (optional)

You can change the ports, the webhook secret, or use OpenAI instead of the built-in demo extraction. To do that, create a file named **`.env`** in the project folder, next to `docker-compose.yml`, with one setting per line. For example:

```bash
# Use other ports if 8080 or 9000 are taken
INVOICE_INTAKE_WEB_PORT=8081
INVOICE_INTAKE_ACCOUNTING_PORT=9001

# Read invoices with OpenAI instead of the deterministic demo provider
INVOICE_INTAKE_EXTRACTION_PROVIDER=openai
INVOICE_INTAKE_OPENAI_API_KEY=sk-...
```

On Windows you can create the file with `notepad .env`. If Notepad offers to save it as `.env.txt`, choose **All files** as the type so the name stays `.env`.

Then restart the app with `docker compose up -d`. Docker Compose reads `.env` on every start.

About these settings:

- **Your key stays on your computer.** `.env` is listed in `.gitignore`, so Git never commits it.
- **The demo provider** (`fake`, the default) needs no key and no network. It recognises the 12 synthetic samples and returns their correct values. Any other document comes back empty for you to fill in.
- **With `openai`**, each invoice is sent to OpenAI to be read, at a cost of a fraction of a cent per invoice. The app refuses to start if the key is missing.

### Troubleshooting

**The browser says it can't connect to localhost:8080** (in Firefox, "Unable to connect"; in Chrome, "This site can't be reached"):
the app isn't running, or it is still starting. Check the following in order:

1. Is Docker Desktop open and running? `docker info` must answer (Step 2).
2. Did you start the app? Run `docker compose ps` in the project folder. An empty list means it isn't running, so start it with `docker compose up --build` (Step 4).
3. Is it still starting? On the first run, wait for the `Uploaded 12 sample invoices` line.
4. Did you change the port in `.env`? Then open that port instead.

**`Cannot connect to the Docker daemon`, `error during connect`, or `The system cannot find the file specified`** when you run a `docker` command:
Docker isn't running. Open Docker Desktop, wait until the engine is running, and run the command again.

**`port is already allocated` or `Bind for 0.0.0.0:8080 failed`**:
another program already uses port 8080 or 9000. Choose other ports in `.env` (see [Settings](#settings-optional)). To find the program instead:

- Windows: `netstat -ano | findstr :8080` (the last number is the process ID, which Task Manager shows)
- macOS or Linux: `lsof -i :8080`

**The build stops with a download error** (from `pip`, `npm` or a registry):
a network hiccup. Run `docker compose up --build` again. The steps that already finished are cached, so the retry is quick.

**The dashboard opens but says "Can't reach the API"**:
the API is still starting, or it stopped. Run `docker compose ps`: `api` should be `healthy`. If it isn't, `docker compose logs api` shows why.

**Invoices stay in "Queued"**:
the worker isn't running. Run `docker compose ps` to check the `worker` service, and `docker compose logs worker` to see its messages.

**On Windows, Docker Desktop reports a WSL error**:
update WSL with `wsl --update` in PowerShell, then restart Docker Desktop.

**Anything else**:
start from a clean slate with `docker compose down -v` and then `docker compose up --build`. If that doesn't help, `docker compose logs` shows every service's messages.

---

## Part 2: Set up for development

Here you run the API, the worker and the dashboard directly on your computer, with live reload, and use Docker only for PostgreSQL, Redis and the tests. Read Part 1's Steps 1 to 3 first: you need Git, Docker running, and the project folder.

### Step 1: Install Node.js and Python

- **Node.js 20.19 or newer** (22 recommended): from [nodejs.org](https://nodejs.org/). The dashboard's build tool (Vite 7) needs it.
- **Python 3.10 or newer** (the project is developed on 3.14): from [python.org](https://www.python.org/downloads/). On Windows, tick **Add python.exe to PATH** in the installer.

Check both:

```bash
node --version
python --version
```

On macOS and Linux the command may be `python3`. The project's scripts find it either way.

### Step 2: Install the dependencies

From the project folder:

```bash
npm run setup:backend
npm run setup:frontend
```

- `setup:backend` creates a Python virtual environment in `repositories/backend/.venv` and installs the backend with its development tools. It doesn't touch your system Python.
- `setup:frontend` installs the dashboard's packages in `repositories/frontend/node_modules`, plus the Chromium browser that the end-to-end tests use.

Run them again after a `git pull` that changes dependencies. If a command later says `Backend dependencies are not installed` or `Frontend dependencies are not installed`, this step is the fix.

### Step 3: Start PostgreSQL and Redis

These two commands create the development database and queue as containers, once:

```bash
docker run -d --name invoice-intake-db -p 5433:5432 -e POSTGRES_USER=invoice_intake -e POSTGRES_PASSWORD=invoice_intake -e POSTGRES_DB=invoice_intake postgres:16-alpine
docker run -d --name invoice-intake-redis -p 6379:6379 redis:7-alpine
```

The database uses port **5433**, so it doesn't clash with a PostgreSQL you may already run on 5432. After a restart of your computer, bring both back with `docker start invoice-intake-db invoice-intake-redis`.

Then create the tables:

```bash
npm run db:migrate
```

### Step 4: Start the three parts

Each runs in its own terminal, from the project folder, and stops with `Ctrl+C`:

```bash
npm run dev:backend
```

```bash
npm run dev:worker
```

```bash
npm run dev:frontend
```

- `dev:backend`: the API on http://localhost:8000, which reloads when you save a Python file. Interactive API docs are at http://localhost:8000/docs.
- `dev:worker`: the background worker that reads uploaded invoices.
- `dev:frontend`: the dashboard on **http://localhost:5173**, which updates as you edit. It forwards `/api` to the API on port 8000.

### Step 5: Load the sample invoices

With the API running, in a fourth terminal:

```bash
npm run seed
```

It uploads the 12 synthetic invoices. If the database already holds invoices, it does nothing. Open http://localhost:5173 and they appear in the queue.

### Step 6: Run the checks

```bash
npm run check
```

This is the full check that CI also runs on every push: lint, type checks, the tests, the build, and the end-to-end tests in a real browser. It takes a few minutes. Docker must be running, because the tests start their own throwaway PostgreSQL and Redis containers on other ports. Without Docker those tests fail with a message saying so.

Smaller checks while you work:

| Command | Checks |
|---|---|
| `npm run lint` | Code style and the documentation's links |
| `npm run typecheck` | Types (mypy for Python, `tsc` for TypeScript) |
| `npm run test` | The backend and frontend tests |
| `npm run verify-all` | Each repository on its own (`repositories/backend`, `repositories/frontend`) |
| `npm run check-arch` | The architecture rules (for example, the domain layer imports nothing else) |
| `npm run compose:smoke` | The Docker stack from Part 1, end to end, on separate ports |

### Development troubleshooting

- **`The frontend needs Node 20.19 or newer`**: update Node.js (Step 1).
- **`No Python interpreter found`**: install Python, or make sure `python` (or `python3`) works in a new terminal (Step 1).
- **`port is already allocated` for 5433 or 6379**: another database or Redis is using the port. Stop it, or change the port in the `docker run` command and set the matching `INVOICE_INTAKE_DATABASE_URL` or `INVOICE_INTAKE_REDIS_URL` in `repositories/backend/.env` (start from `repositories/backend/.env.example`).
- **After pulling the move to `repositories/`** (feat-013): run `npm run setup:backend` again. The old virtual environment points at the old folder.
- **On Windows, a stopped server keeps its port**: closing a terminal can leave its Python or Node process running. End it in Task Manager, or press `Ctrl+C` in the terminal before closing it.

When you are done, stop the three terminals with `Ctrl+C` and the containers with `docker stop invoice-intake-db invoice-intake-redis`. Your development data stays in the containers until you remove them with `docker rm`.
