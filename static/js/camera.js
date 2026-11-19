/**
 * camera.js — Browser-side WebRTC camera capture for the Attendance System.
 *
 * Accesses the user's camera via getUserMedia, draws frames to a hidden canvas,
 * and periodically sends base64-encoded frames to the Flask backend via /api/scan.
 */

// ─── State ───────────────────────────────────────────────────
let videoStream = null;
let scanInterval = null;
let isScanning = false;
let currentImage = null; // Stores the latest captured base64 image

// ─── DOM Elements (set on init) ──────────────────────────────
let video, canvas, ctx, statusEl, resultEl, annotatedImg;
let scanAnnouncementEl = null;
let previousAnnouncement = "";

/**
 * Initialize the camera module.
 * Call this after the DOM is loaded with the IDs of your elements.
 */
function initCamera(videoId, canvasId, statusId, resultId, annotatedId) {
    video = document.getElementById(videoId);
    canvas = document.getElementById(canvasId);
    ctx = canvas.getContext("2d");
    statusEl = document.getElementById(statusId);
    resultEl = document.getElementById(resultId);
    annotatedImg = document.getElementById(annotatedId);
    scanAnnouncementEl = document.getElementById("scan-announcement");
}

/**
 * Start the camera stream.
 */
async function startCamera() {
    try {
        // Check if getUserMedia is supported
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            const isLocalhost = location.hostname === "localhost" || location.hostname === "127.0.0.1";
            if (!isLocalhost && location.protocol !== "https:") {
                setStatus("❌ Camera requires HTTPS or localhost. Open http://localhost:" + location.port + location.pathname + " instead, or run the server with: python app.py --ssl", "error");
            } else {
                setStatus("❌ Camera API not available in this browser.", "error");
            }
            return false;
        }

        videoStream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
                facingMode: "user"
            },
            audio: false
        });

        video.srcObject = videoStream;
        await video.play();

        // Match canvas size to video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        setStatus("📷 Camera started. Ready to scan.", "success");
        return true;
    } catch (err) {
        console.error("Camera error:", err);
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
            setStatus("❌ Camera permission denied. Please click the camera icon in your browser's address bar and allow access, then refresh.", "error");
        } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
            setStatus("❌ No camera found. Please connect a webcam.", "error");
        } else if (err.name === "NotReadableError" || err.name === "TrackStartError") {
            setStatus("❌ Camera is in use by another app. Close other apps and retry.", "error");
        } else if (err.name === "OverconstrainedError") {
            setStatus("❌ Camera doesn't support the requested resolution. Retrying...", "error");
            // Retry with minimal constraints
            try {
                videoStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                video.srcObject = videoStream;
                await video.play();
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                setStatus("📷 Camera started. Ready to scan.", "success");
                return true;
            } catch (retryErr) {
                setStatus("❌ Camera failed: " + retryErr.message, "error");
            }
        } else {
            setStatus("❌ Camera error: " + err.message + ". Make sure you're using HTTPS or localhost.", "error");
        }
        return false;
    }
}

/**
 * Stop the camera stream.
 */
function stopCamera() {
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
    stopScanning();
    setStatus("Camera stopped.", "info");
}

/**
 * Capture a single frame from the video as a base64 JPEG string.
 */
function captureFrame() {
    if (!video || !video.videoWidth) return null;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    return canvas.toDataURL("image/jpeg", 0.8);
}

/**
 * Start periodic scanning — captures a frame every `intervalMs` and sends it to the backend.
 */
function startScanning(intervalMs = 1000) {
    if (isScanning) return;
    isScanning = true;

    setStatus("🔍 Scanning...", "success");
    scanInterval = setInterval(async () => {
        await scanOnce();
    }, intervalMs);

    // Also scan immediately
    scanOnce();
}

/**
 * Stop periodic scanning.
 */
function stopScanning() {
    if (scanInterval) {
        clearInterval(scanInterval);
        scanInterval = null;
    }
    isScanning = false;
}

/**
 * Capture one frame, send to /api/scan, and handle the response.
 */
async function scanOnce() {
    const frameData = captureFrame();
    if (!frameData) return;

    currentImage = frameData;

    try {
        const response = await fetch("/api/scan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: frameData })
        });

        const result = await response.json();
        handleScanResult(result);
    } catch (err) {
        console.error("Scan error:", err);
    }
}

/**
 * Handle the scan result from the backend.
 * Dispatches a custom event so page-specific JS can react.
 */
function handleScanResult(result) {
    // Show annotated image if available
    if (result.annotated_image && annotatedImg) {
        annotatedImg.src = "data:image/jpeg;base64," + result.annotated_image;
        annotatedImg.style.display = "block";
    }

    // Update the result display
    if (resultEl) {
        resultEl.className = "scan-result " + result.status;
        resultEl.innerHTML = formatResult(result);
        // Avoid reading repeated "no face" or "no match" messages every second.
        if (scanAnnouncementEl && !["no_face", "no_match"].includes(result.status)) {
            const announcement = result.message || result.status;
            if (announcement !== previousAnnouncement) {
                scanAnnouncementEl.textContent = announcement;
                previousAnnouncement = announcement;
            }
        }
    }

    // Dispatch custom event for page-specific handling
    document.dispatchEvent(new CustomEvent("scanResult", { detail: result }));
}

/**
 * Format the scan result into HTML for display.
 */
function formatResult(result) {
    switch (result.status) {
        case "no_face":
            return `<p class="no-face">👤 ${result.message}</p>`;

        case "multiple_faces":
            return `<p class="multiple-faces">👥 ${result.message}</p>`;

        case "new_face":
            return `<p class="new-face">🆕 ${result.message}</p>`;

        case "existing":
            const s = result.student;
            return `
                <div class="existing-student">
                    <p>⚠️ ${result.message}</p>
                    <div class="student-details">
                        <p><strong>Name:</strong> ${s.name}</p>
                        <p><strong>Roll No:</strong> ${s.roll_no}</p>
                        <p><strong>Branch:</strong> ${s.branch}</p>
                        <p><strong>Section:</strong> ${s.section || "N/A"}</p>
                        <p><strong>Semester:</strong> ${s.semester}</p>
                        <p><strong>Confidence:</strong> ${result.confidence}%</p>
                    </div>
                </div>`;

        case "marked":
            return `<p class="marked">✅ ${result.message} (${result.confidence}% confidence)</p>`;

        case "already_marked":
            return `<p class="already-marked">ℹ️ ${result.message}</p>`;

        case "no_match":
            return `<p class="no-match">🔍 ${result.message}</p>`;

        case "outside_window":
            return `<p class="outside-window">⏰ ${result.message}</p>`;

        case "error":
            return `<p class="error">❌ ${result.message}</p>`;

        default:
            return `<p>${result.message || JSON.stringify(result)}</p>`;
    }
}

/**
 * Register a new student — sends the current image + form data to /api/register.
 */
async function registerStudent(formData) {
    if (!currentImage) {
        setStatus("❌ No face image captured. Please scan first.", "error");
        return null;
    }

    const payload = {
        image: currentImage,
        roll_no: formData.roll_no,
        name: formData.name,
        branch: formData.branch,
        section: formData.section || "",
        semester: formData.semester || 1
    };

    try {
        const response = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            setStatus(`✅ ${result.message}`, "success");
        } else {
            setStatus(`❌ ${result.error}`, "error");
        }

        return result;
    } catch (err) {
        console.error("Registration error:", err);
        setStatus("❌ Network error during registration.", "error");
        return null;
    }
}

/**
 * Switch operating mode via the API.
 */
async function switchMode(mode) {
    try {
        const response = await fetch("/api/mode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode })
        });
        const result = await response.json();
        setStatus(`Switched to ${result.mode} mode.`, "info");
        return result;
    } catch (err) {
        console.error("Mode switch error:", err);
        return null;
    }
}

/**
 * Set the status message display.
 */
function setStatus(message, type = "info") {
    if (statusEl) {
        statusEl.textContent = message;
        statusEl.className = "status " + type;
    }
}
