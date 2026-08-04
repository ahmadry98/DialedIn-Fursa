# DialedIN AI Shot Analysis

AI espresso shot coach for DialedIN. The app collects machine, grinder, dose, grind setting, roast, taste, and shot timing/video through chat, analyzes audio timing, and recommends the next grind adjustment.

## Project Location

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
```

## First-Time Setup After Moving The Folder

If `.venv/bin/uvicorn` says `bad interpreter`, recreate the virtual environment because the old venv stored the previous path.

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
deactivate 2>/dev/null || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r services/agent/requirements.txt
python -m pip install -r services/espresso_mcp/requirements.txt
python -m pip install -r modeling/requirements.txt
```

## Run Backend

Use `0.0.0.0` so the iPhone simulator or real phone can reach the backend through your Mac LAN IP.

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
source .venv/bin/activate
python -m uvicorn services.agent.app:app --host 0.0.0.0 --port 8000
```

Local backend URL:

```text
http://127.0.0.1:8000
```

LAN backend URL:

```text
http://192.168.68.101:8000
```

## Run Web Frontend

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project/services/frontend
npm run dev -- --hostname 0.0.0.0
```

Local frontend URL:

```text
http://localhost:3000
```

LAN/mobile frontend URL:

```text
http://192.168.68.101:3000
```

## Run DialedIn Mobile App

The mobile app currently opens the web AI Shot Analysis screen from:

```text
http://192.168.68.101:3000
```

Run the Expo app:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
npm run ios
```

To override the AI chat URL:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
EXPO_PUBLIC_AI_SHOT_ANALYSIS_URL=http://YOUR_MAC_IP:3000 npm run ios
```

## Useful Checks

Agent graph tests:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
source .venv/bin/activate
python -m unittest services.agent.tests.test_graph
```

Frontend typecheck and build:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project/services/frontend
npm run typecheck
npm run build
```

DialedIn mobile lint:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
npm run lint
```

## Current Mobile Direction

The current mobile integration opens the web AI chat as a temporary bridge. The planned product direction is:

1. Build the AI Shot Analysis chat natively inside `dialedin-mobile`.
2. Call the FastAPI `/chat` endpoint directly from Expo.
3. Upload shot videos to S3 instead of relying on local `data/raw-videos/...` paths.
4. Show timing and recommendation conclusions in a native mobile analysis screen.
