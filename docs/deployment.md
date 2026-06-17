# Deployment

This repo ships two deployable surfaces:

1. `app.py` for Streamlit Cloud or Hugging Face Spaces.
2. `public/` for Vercel static hosting.

## Local smoke test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python download_sample.py --url 'https://www.youtube.com/watch?v=W7aRQGYhuk0'
pytest
streamlit run app.py --server.headless true
```

## Streamlit Cloud

1. Import `Dave711d/OR-tracking`.
2. Set the main file to `app.py`.
3. Use the default Python version or `runtime.txt`.
4. Deploy.

## Hugging Face Spaces

1. Create a new Space with the Streamlit SDK.
2. Import or mirror this GitHub repo.
3. Keep `app.py`, `requirements.txt`, and `runtime.txt` at the repository root.
4. Deploy.

## Vercel

The Vercel deployment is a static browser demo. It does client-side video motion
tracking using `public/app.js`, so it does not need Python, ffmpeg, or server
storage.

```bash
npm install
npm run build
vercel deploy --prod
```

The build output is `dist/`, configured in `vercel.json`.
