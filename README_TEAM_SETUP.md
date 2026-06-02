# Team Setup Guide

This project combines a Python web app with a Tableau MCP server integration.

## 1) Clone

```bash
git clone <YOUR_REPO_URL>
cd tableau-mcp
```

## 2) Python setup

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Environment file

Create a local `.env` from the template:

```bash
cp .env_template .env
```

Then fill at minimum:

- `TABLEAU_MCP_FILEPATH`
- `SERVER`
- `SITE_NAME`
- `PAT_NAME`
- `PAT_VALUE`
- `OPENAI_API_KEY`

Do not commit `.env`.

## 4) Optional Node build (if you use local tableau-mcp code)

If your `.env` points to a local `tableau-mcp` build, run:

```bash
cd tableau-mcp-experimental
npm install
npm run build
cd ..
```

## 5) Run app

```bash
python web_app.py
```

Open:

- `http://localhost:8000`

## 6) Troubleshooting

- If port is busy: close existing process on `8000` and restart.
- If Tableau auth fails: re-check `PAT_NAME`, `PAT_VALUE`, `SERVER`, `SITE_NAME`.
- If MCP tools fail to start: verify `TABLEAU_MCP_FILEPATH` points to a valid built `index.js`.
