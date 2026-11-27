# Setup (Windows, step by step)

These steps take a fresh clone to the running app. Commands are for **Windows CMD** and run from the repo root unless a step says otherwise. Scripts that read downloaded data run with `python -I` (isolated mode), so a stray file in the current folder can't be imported by mistake.

## 1. Prerequisites
| Tool | Version used | Check |
|---|---|---|
| Git | any recent | `git --version` |
| Python | 3.12 (3.12.10 used) | `py -3.12 --version` |
| Node.js + npm | 22 (22.22.3 used) | `node --version` |
| PostgreSQL | 17, with `psql` on PATH | `psql --version` |
| Disk | about 2 GB free (raw data is about 610 MB) | |

## 2. Get the code
```
git clone https://github.com/springboardmentor441p-coderr/Powered-Public-Transit-Route-Optimization.git
cd Powered-Public-Transit-Route-Optimization
git checkout tayyaba-haroon
```

## 3. Python environment
```
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```
- Every version is pinned with `==`, and PyTorch is the CPU build.
- Your prompt shows `(.venv)` while the environment is active.
- Activate it again in every new CMD window.

## 4. PostgreSQL: a role and two databases (once)
Open `psql` as the `postgres` superuser, for example with `psql -U postgres`, and run:
```sql
CREATE ROLE routeranker LOGIN PASSWORD '<choose a password>';
CREATE DATABASE routeranker OWNER routeranker;
CREATE DATABASE routeranker_test OWNER routeranker;
```
- `routeranker` holds the app's data. `routeranker_test` is used only by the tests and browser checks, which empty it.
- The role is **not** a superuser, so a leaked app password can't reach other databases or create users.

## 5. The `.env` file
```
copy backend\.env.example backend\.env
notepad backend\.env
```
Replace `CHANGE_ME` in both lines with the `routeranker` role's own password:
```
DATABASE_URL=postgresql://routeranker:<password>@localhost:5432/routeranker
TEST_DATABASE_URL=postgresql://routeranker:<password>@localhost:5432/routeranker_test
```
- `backend\.env` is gitignored. **Never commit it**, and never put the `postgres` superuser's password there.
- Characters such as `@ : / # %` in the password must be percent-encoded. For example, `@` becomes `%40`.

## 6. Data: run the pipeline
The README's [Reproduce the pipeline](../README.md#reproduce-the-pipeline) lists the stage commands in order: download, reconstruction, features, models, groups and route lines.
- They write `data/raw/`, `data/processed/<data_version>/`, `artifacts/` and `reports/`.
- Stage 4b (neural networks) is an optional extra. The app doesn't need it.
- A raw file is never overwritten. If a newer ridership export is downloaded, it sits beside the old one.

## 7. Import into PostgreSQL
```
python -I backend\importer\import_data.py --create-schema
python -I backend\importer\import_stage7.py
python -I backend\replay\build_forecasts.py
python -I backend\importer\import_stage8.py
python -I backend\scenarios\save_examples.py
```
| Command | What it does | Safe to repeat? |
|---|---|---|
| `import_data.py --create-schema` | creates the schema; checks every processed file's sha256 against its manifest; loads the data version; writes `reports\stage6_import_report.md` | refuses a version that is already imported. On an existing schema, use `--version-dir data\processed\<data_version>` for a new version |
| `import_stage7.py` | adds the replay tables and the forecast targets | refuses a second load |
| `build_forecasts.py` | stores all June–July forecasts (14,036 rows), then checks them against Stage 4a's test scores | yes: a second run stores nothing and re-verifies every row |
| `import_stage8.py` | adds the scenarios table | yes |
| `save_examples.py` | saves the three example scenarios once and exports `reports\stage8_scenario_examples.json` | yes: a second run saves nothing and only re-checks |

To load the **test** database instead, add `--url-var TEST_DATABASE_URL` to each command. Also send the outputs elsewhere, so the committed reports aren't overwritten:
```
python -I backend\importer\import_data.py --create-schema --url-var TEST_DATABASE_URL --report %TEMP%\import_test.md
python -I backend\importer\import_stage7.py --url-var TEST_DATABASE_URL
python -I backend\replay\build_forecasts.py --url-var TEST_DATABASE_URL
python -I backend\importer\import_stage8.py --url-var TEST_DATABASE_URL
python -I backend\scenarios\save_examples.py --url-var TEST_DATABASE_URL --out %TEMP%\examples_test.json
```

## 8. Run the app
Window 1, the API:
```
.venv\Scripts\activate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Window 2, the screens:
```
cd frontend
npm ci
npm run dev
```
- Open **http://localhost:5173**. Vite forwards every `/api` request to the API on port 8000.
- The API's interactive docs are at http://127.0.0.1:8000/docs.
- `npm ci` is only needed the first time, or after `package-lock.json` changes.
- Stop either server with `Ctrl+C` in its window.

## 9. Tests and checks
From the repo root:
```
python -m pytest
```
- The pipeline tests need the processed data. The API tests need `TEST_DATABASE_URL`.
- Integration tests skip until the stage they check has been run.
- A full run takes 8–30 minutes, depending on the machine, and leaves `routeranker_test` empty.

From `frontend\`:
```
npx tsc -b
npm run lint
npx vitest run
npm run build
```

### Browser checks
These use Playwright, which is only needed in development. Install the browser once:
```
cd frontend
npx playwright install chromium
```
The historical click-through and the layout screenshots are read-only. Run them with both servers up:
```
node scripts\clickthrough.mjs
node scripts\screens.mjs %TEMP%\shots / /closer-look /route/22 /alike /shared-stops /compare?routes=49,X49 /data
```
The replay and scenario checks create replay sessions and saved scenarios, which can never be deleted. So they **refuse to run** unless the API reports `routeranker_test`. Load the test database first (step 7, with `--url-var TEST_DATABASE_URL`). Then run a temporary API and Vite on other ports, so your own servers are untouched:
```
:: terminal 1 (repo root): an API on the test database
set ROUTERANKER_URL_VAR=TEST_DATABASE_URL
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010

:: terminal 2 (frontend\): a Vite that forwards to it
set ROUTERANKER_API=http://127.0.0.1:8010
npx vite --port 5180 --strictPort

:: terminal 3 (frontend\)
set APP_URL=http://localhost:5180
node scripts\replay_check.mjs %TEMP%\replay_shots
node scripts\scenario_check.mjs %TEMP%\scenario_shots
node scripts\clickthrough.mjs
```
- Each check prints `ok` or `FAIL` per step and ends with "all checks passed" or the number of failures.
- Stop the two temporary servers with `Ctrl+C` afterwards.

### Screenshots
The README's screenshots come from `node scripts\doc_screenshots.mjs <folder>`, run against an API and Vite on 8010/5180.
- The script is read-only, except for its replay shot. That creates one replay session and presses Reset, which makes a second session.
- You can name shots to retake only those, for example `node scripts\doc_screenshots.mjs <folder> scenarios data`.
- The PNGs were then reduced to 256 colours with ffmpeg, which is not a project dependency: `ffmpeg -i in.png -vf "split[a][b];[a]palettegen[p];[b][p]paletteuse" out.png`.

## 10. Troubleshooting
| Symptom | Cause and fix |
|---|---|
| `'.venv\Scripts\activate' is not recognized` | You're not in the repo root, or the venv wasn't created. Run `cd` to the repo root, then repeat step 3. In PowerShell, use `.venv\Scripts\Activate.ps1`. |
| `ModuleNotFoundError: No module named 'pandas'` (or `fastapi`) | The venv isn't active in this window. Run `.venv\Scripts\activate`. |
| `ModuleNotFoundError: No module named 'backend'` | The command was run from another folder. Run it from the repo root. |
| `[Errno 10048] … only one usage of each socket address` / Vite says port 5173 is in use | Another program is already using the port. Find it with `netstat -ano \| findstr :8000` (or `:5173`), then stop that window, or pick another port: `--port 8001` for the API (and `set ROUTERANKER_API=http://127.0.0.1:8001` before `npm run dev`), or `npx vite --port 5174`. |
| Screens show "Could not load this – the API is not reachable (is uvicorn running on 127.0.0.1:8000?)", or "the API answered with no data" | The API isn't running, or Vite forwards to the wrong port. Start the API (step 8) and check http://127.0.0.1:8000/api/health. If the API uses another port, set `ROUTERANKER_API` before starting Vite. |
| `IMPORT REFUSED … group_names.json: sha256 … differs from its manifest` | The file's line endings were changed after it was hashed. `.gitattributes` keeps `analytics/config/*.json` at LF on checkout, even with Git's `core.autocrlf=true` on Windows. If you edited the file in an editor that saves CRLF, restore it with `git checkout -- analytics/config`. |
| `password authentication failed for user "routeranker"` | The password in `backend\.env` doesn't match the role, or it contains an unencoded `@ : / # %`. |
| `database "routeranker_test" does not exist` | Step 4 wasn't completed for the test database. |
| `ImportRefused: <data_version> is already imported; a changed export must become a new data version` | That's expected: the import never loads a version twice. To start again on the **test** database, run `python -m pytest`, which empties it. The app database is never emptied by any script. |
| The replay or scenario check prints `REFUSED: … reads routeranker` | That's the safety check working. Start the temporary API with `set ROUTERANKER_URL_VAR=TEST_DATABASE_URL` (see Browser checks). |
| The replay or scenario check reports "no saved examples" or loads forever | The test database is empty (a full pytest run empties it). Load it again with step 7 and `--url-var TEST_DATABASE_URL`. |
| `browserType.launch: Executable doesn't exist` | Run `npx playwright install chromium` in `frontend\`. |
| Maps show no background | The OpenStreetMap tiles need internet access. Route lines and data still work. |
| After an import, the app still shows old results | Restart the API after the Stage 7 and Stage 8 steps. |
