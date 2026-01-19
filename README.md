# Bird Log

A simple Flask + SQLite app for tracking bird sightings.

## Run locally or in a Codespace

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_birds.py
python app.py
```

Or run the Flask CLI command:

```bash
export FLASK_APP=app.py
flask seed-birds
```

Then open `http://localhost:8000` in your browser.

## Usage

- Use the form to add a bird name, location, and optional notes.
- The front page also lists your most recent sightings with descriptions and behavior.
- Click "Use my location" to capture coordinates (browser permission required).
- Autocomplete suggestions come from the bundled UK bird list.
- Verify autocomplete by typing at least 2 characters in the bird field or visiting
  `http://localhost:8000/api/birds?q=rob`.
- Debug database state at `http://localhost:8000/api/debug/db-info`.
- Smoke-test search results at `http://localhost:8000/api/debug/search-test`.
- Use the date filters to update both the Recent list and Map markers (filters are stored
  in the URL query string).
