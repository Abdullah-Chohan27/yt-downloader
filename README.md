# YTGrab — YouTube Video Downloader

A local web app that downloads YouTube videos in the best available quality (video + audio merged into MP4).

---

## 📁 Files

```
yt-downloader/
├── server.py          # Python backend (no frameworks needed)
├── index.html         # Web UI (served by the backend)
├── requirements.txt   # Python dependencies
├── downloads/         # Videos saved here (auto-created)
└── README.md
```

---

## ⚙️ Requirements

- **Python 3.8+** (standard library only — no Flask/Django needed)
- **yt-dlp** (Python package)
- **ffmpeg** (for merging best video + audio)

---

## 🚀 Setup & Run

### Step 1 — Install ffmpeg

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Ubuntu / Debian:**
```bash
sudo apt install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html and add to PATH.

---

### Step 2 — Install Python dependencies

```bash
pip install -r requirements.txt
```

---

### Step 3 — Run the server

```bash
python server.py
```

You'll see:
```
✅ YouTube Downloader running at http://localhost:8765
📁 Downloads will be saved to: /path/to/yt-downloader/downloads
```

---

### Step 4 — Open the app

Go to **http://localhost:8765** in your browser.

---

## 💡 How to Use

1. Paste a YouTube URL into the input box
2. Click **FETCH** to preview the video
3. Click **⬇ DOWNLOAD BEST** to start downloading
4. Watch the progress bar — the file saves to the `downloads/` folder
5. Your downloaded files appear in the list below

---

## 📝 Notes

- Downloads are saved as **MP4** (best video + best audio merged)
- Files are saved in the `downloads/` folder next to `server.py`
- The server runs locally — no data is sent anywhere
- To stop the server, press `Ctrl+C`
