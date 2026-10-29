# PulseChat — Real-Time Messaging App

A full-stack Flask + SQLite + Socket.IO starter project with registration, login, direct messages, contact search, and a separate administrator dashboard.

## Requirements
- Python 3.10 or newer
- VS Code
- Internet connection for installing packages

## Run on Windows (VS Code)

1. Extract this folder and open `realtime_messenger` in VS Code.
2. Open **Terminal → New Terminal**.
3. Create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

4. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use Command Prompt terminal and run:

   ```bat
   .venv\Scripts\activate.bat
   ```

5. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

6. Start the app:

   ```powershell
   python app.py
   ```

7. Open **http://127.0.0.1:5000** in your browser.

If `python` is not recognized on Windows, use the full Python executable path or `py -m venv .venv` if the Python launcher is installed.

## First login / administrator dashboard

On first startup, the database is created automatically. The default local administrator is:
- Email: `admin@example.com`
- Password: `ChangeMe123!`

**Change this password before any deployment.** The initial admin is created only when that email does not already exist in the database. To change credentials after first run, update the admin password through a future password-management feature or delete `messenger.db` while the app is stopped (this resets all accounts and messages), then restart with environment variables set.

For a local PowerShell session, set a stronger password before first run:

```powershell
$env:ADMIN_EMAIL="your-admin@example.com"
$env:ADMIN_PASSWORD="use-a-strong-unique-password"
$env:SECRET_KEY="replace-with-a-long-random-secret"
python app.py
```

The admin dashboard is at **http://127.0.0.1:5000/admin**. Regular accounts cannot open it.

## How to test messaging

1. Register a first user in one browser window.
2. Open a private/incognito window or another browser and register a second user.
3. Sign in as each user in separate windows.
4. Search for the other user by name or email and start chatting.
5. Messages are saved in SQLite and delivered in real time while both clients are connected.

## Project structure

```text
realtime_messenger/
├── app.py
├── requirements.txt
├── Procfile
├── .env.example
├── README.md
├── templates/
│   ├── landing.html
│   ├── auth.html
│   ├── chat.html
│   └── admin.html
└── static/
    ├── css/style.css
    └── js/
        ├── chat.js
        └── admin.js
```

## Important production notes

- This is a functional starter, not a security audit or a guarantee of zero errors in every environment.
- Set strong `SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` environment variables before deployment.
- Use HTTPS, secure cookies, a persistent disk/database, backups, rate limiting, and a production database for public use.
- The included SQLite database is suitable for a small demo; concurrent or larger production workloads should use PostgreSQL.
- No end-to-end encryption is implemented. Do not use it for sensitive or confidential communications as-is.
- `Procfile` is a generic deployment start command. A host must support WebSockets and persistent storage for this architecture to work reliably.
