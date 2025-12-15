# 🚀 Starting NAVI - Quick Guide

This guide ensures you NEVER see a blank panel again!

## ✅ Auto-Start (Recommended)

The extension now automatically starts the frontend server for you. Just:

1. Open the NAVI panel in VS Code sidebar
2. Wait a few seconds for the frontend to start
3. Done! 🎉

## 🛠️ Manual Start (If Auto-Start Fails)

### Option 1: Use VS Code Task
1. Press `Cmd/Ctrl + Shift + P`
2. Type: `Tasks: Run Task`
3. Select: `dev: start all (backend + frontend + watch)`

### Option 2: Run in Terminal
```bash
# Terminal 1: Start Backend
cd /path/to/autonomous-engineering-platform
source .venv/bin/activate
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8787

# Terminal 2: Start Frontend
cd /path/to/autonomous-engineering-platform/frontend
npm run dev
```

## 🔍 Troubleshooting

### Blank Panel?
1. Check if frontend server is running: `lsof -i :3000`
2. If not, run: `cd frontend && npm run dev`
3. Reload VS Code window: `Cmd/Ctrl + Shift + P` → `Developer: Reload Window`

### Port Already in Use?
```bash
# Kill process on port 3000
lsof -ti :3000 | xargs kill -9

# Kill process on port 8787
lsof -ti :8787 | xargs kill -9
```

### Dependencies Not Installed?
```bash
# Install frontend dependencies
cd frontend && npm install

# Install backend dependencies
pip install -r requirements.txt
```

## ⚙️ Settings

Make sure these settings are in your `.vscode/settings.json`:

```json
{
  "aep.development.useReactDevServer": true,
  "aep.navi.backendUrl": "http://127.0.0.1:8787"
}
```

## 📝 What Changed?

The extension now:
- ✅ **Automatically detects** if the frontend server is running
- ✅ **Auto-starts** the server if it's not running
- ✅ **Shows helpful error messages** instead of blank panels
- ✅ **Provides clear instructions** if something goes wrong

You should never see a blank panel again! 🎊
