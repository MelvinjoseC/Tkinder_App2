# Marine-Ops Tkinter Desktop Launcher (Current MySQL setup)

The project already includes `desktop_app.py`, a thin PyWebView shell that
launches Django and loads the React SPA inside a Tkinter window. Follow these
steps whenever you want to package or demo the application in its present
configuration (still pointing at your MySQL database).

## 1. Prerequisites
1. Python 3.11+ with `pip`.
2. Node.js 18+ if you plan to rebuild the React bundle.
3. The MySQL server reachable from the client machine; update the `.env` file or
   environment variables with the proper credentials (`MYSQL_HOST`, `MYSQL_DB`,
   etc.).

Create a virtual environment once per machine:

```powershell
python -m venv .venv
. .\.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Build/Refresh the React SPA (optional)
Only required when you change frontend code.

```powershell
cd front-end/front-end/marine-ops
npm install          # first build only
npm run build
robocopy build ..\..\..\cargo-updations\cargo-updations\Loading_Computer\frontend_build /MIR
```

This copies the production bundle into Django’s `frontend_build/` folder where
WhiteNoise can serve it.

## 3. Prepare Django Assets
These commands should be run from `cargo-updations/cargo-updations/Loading_Computer`
inside your virtualenv.

```powershell
python manage.py collectstatic --noinput   # only after new frontend build or updates
python manage.py migrate                   # keeps MySQL schema in sync
```

## 4. Run the Desktop Shell
While the virtualenv is active:

```powershell
python desktop_app.py
```

The script checks whether Django is already running on `127.0.0.1:8000`. If not,
it launches `manage.py runserver --noreload` and spawns a PyWebView window that
hosts the SPA. Close the window (or hit `Ctrl+C`) to stop both the window and
the development server.

## 5. Optional: Package with PyInstaller
If you need a distributable executable while still using the remote/local MySQL
instance, you can build one with PyInstaller:

```powershell
pyinstaller desktop_app.py `
  --name MarineOps `
  --noconsole `
  --add-data "frontend_build;frontend_build" `
  --add-data "staticfiles;staticfiles"
```

Ship the contents of `dist/MarineOps/` to your client. They still need access to
the configured MySQL host and an `.env` file (or environment variables) with the
correct credentials placed alongside the executable.

## 6. Switching to SQLite Later
When you’re ready to offer a fully offline build, you can set
`DJANGO_USE_SQLITE=1` before running the launcher and copy a pre-populated
`db.sqlite3` file into the project. No additional code changes are required—the
existing settings already honor that flag.
