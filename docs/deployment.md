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
tracking using `public/app.js` plus browser-side canonical table identity
stitching in `public/browser_identity.mjs`, so it does not need Python, ffmpeg,
or server storage.

The same static surface supports live browser inputs. `Live camera` uses the
browser camera/capture-card API over HTTPS or localhost. `Stream URL` can attach
a browser-playable HTTP(S) video stream, but the stream must allow CORS canvas
pixel reads or the browser will display the video without permitting analysis.
For OR feeds such as RTSP, NDI, or SDI, run the conversion on an edge workstation
inside the hospital network and expose a CORS-enabled browser stream to the
static UI.

`.vercelignore` intentionally excludes `app.py` and the Python package from the
Vercel upload so Vercel does not auto-detect the Streamlit entrypoint as a Python
serverless function. `vercel.json` also sets `framework` to `null`, which is
Vercel's "Other" framework preset for static/custom builds.

```bash
npm install
npm run build
vercel deploy --prod
```

The build output is `dist/`, configured in `vercel.json`.
