# Bird Log

A simple Flask + SQLite app for tracking bird sightings.

## Run locally or in a Codespace

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:8000` in your browser.

## Usage

- Use the form to add a bird name, location, and optional notes.
- The front page also lists your most recent sightings with descriptions and behavior.
- Click "Use my location" to capture coordinates (browser permission required).
