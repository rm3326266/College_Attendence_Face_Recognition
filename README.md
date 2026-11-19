# 🎓 AutoAttend — Automatic Face Recognition Attendance System

> A prototype web-based attendance system that uses **face recognition** to automatically detect and mark students present — no manual roll calls needed.

![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5.x-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=flat-square&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## ✨ Features

### 🔧 Maintenance Mode
- **Register new students** via webcam — capture face + enter details (name, roll no, branch, section, semester)
- **Auto-detect existing students** — if a registered face is scanned, shows their details instantly
- **Single-face enforcement** — waits for only one person in frame for accurate registration

### ✅ Working Mode
- **Auto-scan every second** — captures frames from the browser camera and matches against the database
- **Marks attendance automatically** — matched students are marked present for the active time slot
- **Duplicate prevention** — each student can only be marked once per slot
- **Ignores unknowns** — unrecognized faces are silently skipped

### ⏰ Scheduled Time Windows
Scanning activates only during configured intervals:

| Slot | Time Window |
|------|-------------|
| 1 | 10:00 AM – 10:15 AM |
| 2 | 11:00 AM – 11:15 AM |
| 3 | 12:00 PM – 12:15 PM |
| 4 | 2:00 PM – 2:15 PM |
| 5 | 3:00 PM – 3:15 PM |
| 6 | 4:00 PM – 4:15 PM |

- **Auto-start/stop** — scanner activates when a window opens and pauses between windows
- **Live countdown** — shows remaining time in active window and time until next window
- **Force Scan** — admin can bypass time restrictions for demos/testing

### 📊 Dashboard & Records
- **Real-time dashboard** — attendance rate, per-slot progress bars, registered students
- **Attendance records** — filter by date, roll number, or time slot
- **Student directory** — view all registered students

---

## 🏗️ Architecture

```
Browser (Camera via WebRTC)
    │
    │  base64 JPEG frames every 1s
    ▼
Flask Backend (Python)
    ├── Face Detection  →  OpenCV YuNet (DNN)
    ├── Face Encoding   →  OpenCV SFace (128-d embeddings)
    ├── Face Matching    →  Cosine Similarity (threshold: 0.40)
    ├── Database         →  SQLite (students + attendance)
    └── Scheduler        →  Time window management
```

**Key Design**: The camera runs **in the browser** (JavaScript WebRTC), not on the server. This makes the app fully remote, deployable, and cross-platform — works on any device with a browser and camera.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10+, Flask |
| Face Detection | OpenCV DNN — YuNet model |
| Face Recognition | OpenCV DNN — SFace model (128-d embeddings) |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript (WebRTC) |
| Deployment | Gunicorn, Render |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- Webcam (built-in or USB)
- Modern browser (Chrome, Firefox, Edge)

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/AutoAttend.git
cd AutoAttend

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

The app will:
1. Auto-download face detection models (~37 MB, first run only)
2. Create the SQLite database
3. Start on **http://localhost:5000**

### Usage

1. **Open** `http://localhost:5000` in your browser
2. **Go to Maintenance** → Start Camera → Scan a face → Register student details
3. **Go to Working** → Start Auto-Scan → Attendance is marked automatically during time windows
4. **View Dashboard** for real-time stats and records

> **Note**: Camera access requires HTTPS or localhost. The app works on localhost for development.

---

## 📁 Project Structure

```
AutoAttend/
├── app.py                  # Flask web server + API endpoints
├── camera.py               # Face detection (YuNet DNN)
├── face_encoder.py         # Face encoding & matching (SFace DNN)
├── database.py             # SQLite schema + CRUD operations
├── scheduler.py            # Time window management
├── config.py               # All settings & constants
├── requirements.txt        # Python dependencies
├── Procfile                # Deployment (Gunicorn)
├── render.yaml             # Render deploy config
├── models/                 # ONNX models (auto-downloaded)
├── known_faces/            # Stored face images
├── encodings/              # Pickled face encodings
├── templates/
│   ├── base.html           # Shared layout + navbar
│   ├── dashboard.html      # Stats & overview
│   ├── maintenance.html    # Student registration
│   ├── working.html        # Auto-attendance scanning
│   └── attendance.html     # Records & filters
└── static/
    ├── css/style.css       # Dark theme UI
    └── js/camera.js        # WebRTC camera + API client
```

---

## 🔧 Configuration

All settings are in [`config.py`](config.py):

| Setting | Default | Description |
|---------|---------|-------------|
| `FACE_MATCH_THRESHOLD` | `0.40` | Cosine similarity threshold (higher = stricter) |
| `FACE_DETECTION_CONFIDENCE` | `0.70` | Minimum face detection confidence |
| `SCAN_INTERVAL_MS` | `1000` | Browser scan interval (milliseconds) |
| `TIME_WINDOWS` | 6 slots | Configurable scanning time windows |

---

## 🌐 Deployment

### Deploy to Render (Free)

1. Push your code to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects the `render.yaml` config
5. Deploy!

> **Note**: Free tier may have cold starts. The app auto-downloads models on first request.

---

## ⚠️ Limitations (Prototype)

- **Single face per frame** — processes one person at a time for accuracy
- **SQLite** — not suitable for high-concurrency production use (use PostgreSQL)
- **One photo per student** — production systems should store multiple angles
- **No authentication** — anyone can access the admin pages
- **Model size** — ~37 MB models are downloaded on first run

---

## 🗺️ Future Improvements

- [ ] Multi-angle face registration for better accuracy
- [ ] Admin authentication & role-based access
- [ ] PostgreSQL for production database
- [ ] Email/SMS notifications for absent students
- [ ] Export attendance to Excel/CSV
- [ ] Mobile app with native camera
- [ ] Liveness detection (anti-spoofing)

---

## 🧪 Automated Testing

AutoAttend includes a `tests/` suite using **pytest**. It covers time slots, SQLite operations, first-time administrator setup, login/logout, role restrictions, attendance APIs, and simulated face scans without needing a webcam or real student data.

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

For coverage results and details on isolated test data, see [TESTING.md](TESTING.md). GitHub Actions automatically runs the suite on pushes and pull requests.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to open an issue or submit a PR.

---

<p align="center">
  Built with ❤️
</p>
