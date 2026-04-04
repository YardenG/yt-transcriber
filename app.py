#!/usr/bin/env python3
"""
YT Transcriber - YouTube Transcript Fetcher
A standalone web app to pull, view, copy, and download transcripts from YouTube videos.
"""

import os
import re
import json
from flask import Flask, render_template_string, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
import urllib.request
import urllib.error

app = Flask(__name__)

# Initialize the API (v1.x syntax)
yt_api = YouTubeTranscriptApi()


def extract_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
    return ""


def get_video_title(video_id: str) -> str:
    """Fetch video title from YouTube (no API key needed)."""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            match = re.search(r'<title>(.*?)</title>', html)
            if match:
                title = match.group(1).replace(" - YouTube", "").strip()
                return title
    except Exception:
        pass
    return f"Video {video_id}"


def fetch_transcript(video_id: str) -> dict:
    """Fetch transcript for a single video. Supports v0.x and v1.x API."""
    try:
        title = get_video_title(video_id)
        entries = []
        lang = "en"
        is_auto = False

        # Try v1.x API first (YouTubeTranscriptApi instance methods)
        try:
            transcript_list = yt_api.list(video_id)
            # Find best transcript
            transcript = None

            for t in transcript_list:
                if t.language_code == "en" and not t.is_generated:
                    transcript = t
                    break

            if transcript is None:
                for t in transcript_list:
                    if t.language_code == "en":
                        transcript = t
                        break

            if transcript is None:
                for t in transcript_list:
                    transcript = t
                    break

            if transcript:
                lang = transcript.language_code
                is_auto = transcript.is_generated
                fetched = transcript.fetch()
                # Handle different entry formats
                for entry in fetched:
                    if hasattr(entry, 'text'):
                        entries.append({"text": entry.text, "start": entry.start, "duration": getattr(entry, 'duration', 0)})
                    elif isinstance(entry, dict):
                        entries.append(entry)
                    else:
                        entries.append({"text": str(entry), "start": 0, "duration": 0})

        except AttributeError:
            # Fall back to v0.x API (class methods)
            try:
                raw = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
                entries = raw
            except Exception:
                raw = YouTubeTranscriptApi.get_transcript(video_id)
                entries = raw

        if not entries:
            return {"error": "No transcript available for this video", "video_id": video_id}

        # Build full text
        full_text = " ".join([
            e.get("text", e.text if hasattr(e, 'text') else str(e))
            for e in entries
        ])

        # Build timestamped version
        timestamped = []
        for entry in entries:
            start = entry.get("start", 0) if isinstance(entry, dict) else getattr(entry, 'start', 0)
            text = entry.get("text", "") if isinstance(entry, dict) else getattr(entry, 'text', str(entry))
            minutes = int(float(start) // 60)
            seconds = int(float(start) % 60)
            timestamp = f"{minutes:02d}:{seconds:02d}"
            timestamped.append({
                "time": timestamp,
                "start": float(start),
                "text": text,
            })

        last_entry = entries[-1] if entries else {}
        last_start = last_entry.get("start", 0) if isinstance(last_entry, dict) else getattr(last_entry, 'start', 0)
        last_dur = last_entry.get("duration", 0) if isinstance(last_entry, dict) else getattr(last_entry, 'duration', 0)

        return {
            "video_id": video_id,
            "title": title,
            "language": lang,
            "is_auto_generated": is_auto,
            "full_text": full_text,
            "timestamped": timestamped,
            "word_count": len(full_text.split()),
            "duration_seconds": int(float(last_start) + float(last_dur)),
        }

    except Exception as e:
        error_msg = str(e)
        if "IP" in error_msg or "blocked" in error_msg:
            return {"error": "YouTube is temporarily blocking requests. Try again in a minute.", "video_id": video_id}
        return {"error": error_msg, "video_id": video_id}


# ── HTML TEMPLATE ──

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YT Transcriber</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #08080c;
            --surface: #101016;
            --surface2: #18181f;
            --border: #25252f;
            --text: #e4e4e8;
            --text-dim: #7a7a88;
            --accent: #ef4444;
            --accent-glow: rgba(239, 68, 68, 0.15);
            --success: #22c55e;
            --font-display: 'Outfit', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: var(--font-display);
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }

        .app {
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 24px 80px;
        }

        /* Header */
        .logo {
            font-size: 32px;
            font-weight: 700;
            letter-spacing: -1px;
            margin-bottom: 6px;
        }
        .logo span { color: var(--accent); }
        .subtitle {
            font-size: 14px;
            color: var(--text-dim);
            font-weight: 300;
        }

        /* Input Area */
        .input-section {
            margin-top: 40px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
        }

        .input-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-dim);
            margin-bottom: 12px;
            font-weight: 500;
        }

        textarea {
            width: 100%;
            min-height: 120px;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-family: var(--font-mono);
            font-size: 14px;
            padding: 16px;
            resize: vertical;
            outline: none;
            transition: border-color 0.2s;
        }
        textarea:focus { border-color: var(--accent); }
        textarea::placeholder { color: var(--text-dim); opacity: 0.5; }

        .btn-row {
            display: flex;
            gap: 12px;
            margin-top: 16px;
        }

        .btn {
            padding: 12px 28px;
            border-radius: 10px;
            font-family: var(--font-display);
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }

        .btn-primary {
            background: var(--accent);
            color: #fff;
            box-shadow: 0 0 20px var(--accent-glow);
        }
        .btn-primary:hover { filter: brightness(1.1); transform: translateY(-1px); }
        .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

        .btn-ghost {
            background: transparent;
            color: var(--text-dim);
            border: 1px solid var(--border);
        }
        .btn-ghost:hover { border-color: var(--text-dim); color: var(--text); }

        /* Status */
        .status {
            margin-top: 16px;
            font-size: 13px;
            color: var(--text-dim);
            min-height: 20px;
        }
        .status.loading { color: var(--accent); }
        .status.error { color: #f87171; }
        .status.success { color: var(--success); }

        /* Results */
        .results { margin-top: 32px; }

        .result-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            margin-bottom: 20px;
            overflow: hidden;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .result-header {
            padding: 20px 24px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 1px solid var(--border);
            gap: 16px;
        }

        .result-title {
            font-size: 16px;
            font-weight: 600;
            line-height: 1.4;
            flex: 1;
        }

        .result-meta {
            display: flex;
            gap: 16px;
            font-size: 12px;
            color: var(--text-dim);
            margin-top: 6px;
            flex-wrap: wrap;
        }

        .result-actions {
            display: flex;
            gap: 8px;
            flex-shrink: 0;
        }

        .btn-sm {
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            border: 1px solid var(--border);
            background: var(--surface2);
            color: var(--text-dim);
            font-family: var(--font-display);
            transition: all 0.15s;
        }
        .btn-sm:hover { border-color: var(--accent); color: var(--text); }
        .btn-sm.copied { border-color: var(--success); color: var(--success); }

        /* Tabs */
        .tabs {
            display: flex;
            border-bottom: 1px solid var(--border);
        }

        .tab {
            padding: 12px 20px;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-dim);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.15s;
            background: none;
            border-top: none;
            border-left: none;
            border-right: none;
            font-family: var(--font-display);
        }
        .tab:hover { color: var(--text); }
        .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

        /* Transcript Body */
        .transcript-body {
            padding: 20px 24px;
            max-height: 500px;
            overflow-y: auto;
            font-size: 14px;
            line-height: 1.8;
        }

        .transcript-body::-webkit-scrollbar { width: 6px; }
        .transcript-body::-webkit-scrollbar-track { background: transparent; }
        .transcript-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

        .transcript-text {
            color: var(--text);
            white-space: pre-wrap;
            font-family: var(--font-display);
        }

        .ts-line {
            display: flex;
            gap: 16px;
            padding: 4px 0;
            border-bottom: 1px solid var(--border);
        }
        .ts-line:last-child { border-bottom: none; }

        .ts-time {
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--accent);
            flex-shrink: 0;
            padding-top: 2px;
            cursor: pointer;
            min-width: 48px;
        }
        .ts-time:hover { text-decoration: underline; }

        .ts-text {
            color: var(--text);
            font-size: 14px;
        }

        .error-card {
            background: var(--surface);
            border: 1px solid #7f1d1d;
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 20px;
            color: #fca5a5;
            font-size: 14px;
        }
        .error-card strong { color: #f87171; }

        /* Responsive */
        @media (max-width: 600px) {
            .app { padding: 24px 16px 60px; }
            .logo { font-size: 26px; }
            .result-header { flex-direction: column; }
            .result-actions { width: 100%; }
            .btn-sm { flex: 1; text-align: center; }
            .btn-row { flex-direction: column; }
            .btn { width: 100%; text-align: center; }
        }
    </style>
</head>
<body>
    <div class="app">
        <div class="logo"><span>YT</span> Transcriber</div>
        <div class="subtitle">Pull transcripts from YouTube videos. Copy, download, or read with timestamps.</div>

        <div class="input-section">
            <div class="input-label">YouTube URLs (one per line)</div>
            <textarea id="urlInput" placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ&#10;https://youtu.be/another-video&#10;https://youtube.com/shorts/short-id"></textarea>
            <div class="btn-row">
                <button class="btn btn-primary" id="fetchBtn" onclick="fetchTranscripts()">Fetch Transcripts</button>
                <button class="btn btn-ghost" onclick="clearAll()">Clear</button>
            </div>
            <div class="status" id="status"></div>
        </div>

        <div class="results" id="results"></div>
    </div>

    <script>
        async function fetchTranscripts() {
            const urls = document.getElementById('urlInput').value.trim().split('\\n').filter(u => u.trim());
            if (!urls.length) return;

            const btn = document.getElementById('fetchBtn');
            const status = document.getElementById('status');
            const results = document.getElementById('results');

            btn.disabled = true;
            btn.textContent = 'Fetching...';
            status.className = 'status loading';
            status.textContent = `Fetching ${urls.length} transcript(s)...`;
            results.innerHTML = '';

            for (let i = 0; i < urls.length; i++) {
                status.textContent = `Fetching ${i + 1} of ${urls.length}...`;

                try {
                    const resp = await fetch('/api/transcript', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: urls[i].trim() })
                    });
                    const data = await resp.json();

                    if (data.error) {
                        results.innerHTML += renderError(data);
                    } else {
                        results.innerHTML += renderResult(data, i);
                    }
                } catch (e) {
                    results.innerHTML += renderError({ error: e.message, video_id: urls[i] });
                }
            }

            btn.disabled = false;
            btn.textContent = 'Fetch Transcripts';
            status.className = 'status success';
            status.textContent = `Done. ${urls.length} video(s) processed.`;
        }

        function renderError(data) {
            return `<div class="error-card"><strong>Error:</strong> ${data.error}<br><span style="color:#7a7a88">${data.video_id || ''}</span></div>`;
        }

        function renderResult(data, idx) {
            const dur = data.duration_seconds;
            const mins = Math.floor(dur / 60);
            const secs = dur % 60;
            const duration = `${mins}:${secs.toString().padStart(2, '0')}`;

            let tsHtml = '';
            if (data.timestamped) {
                tsHtml = data.timestamped.map(t =>
                    `<div class="ts-line"><a class="ts-time" href="https://youtube.com/watch?v=${data.video_id}&t=${Math.floor(t.start)}" target="_blank">${t.time}</a><span class="ts-text">${t.text}</span></div>`
                ).join('');
            }

            return `
            <div class="result-card" id="card-${idx}">
                <div class="result-header">
                    <div>
                        <div class="result-title">${data.title}</div>
                        <div class="result-meta">
                            <span>${data.word_count.toLocaleString()} words</span>
                            <span>${duration}</span>
                            <span>${data.is_auto_generated ? 'Auto-generated' : 'Manual'} (${data.language})</span>
                        </div>
                    </div>
                    <div class="result-actions">
                        <button class="btn-sm" onclick="copyText('${idx}', this)">Copy</button>
                        <button class="btn-sm" onclick="downloadText('${idx}', '${data.title}')">Download</button>
                    </div>
                </div>
                <div class="tabs">
                    <button class="tab active" onclick="showTab(${idx}, 'plain', this)">Plain Text</button>
                    <button class="tab" onclick="showTab(${idx}, 'timestamps', this)">Timestamps</button>
                </div>
                <div class="transcript-body">
                    <div id="tab-${idx}-plain" class="transcript-text">${data.full_text}</div>
                    <div id="tab-${idx}-timestamps" style="display:none">${tsHtml}</div>
                </div>
            </div>`;
        }

        function showTab(idx, tab, el) {
            document.getElementById(`tab-${idx}-plain`).style.display = tab === 'plain' ? '' : 'none';
            document.getElementById(`tab-${idx}-timestamps`).style.display = tab === 'timestamps' ? '' : 'none';
            el.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
        }

        function copyText(idx, btn) {
            const el = document.getElementById(`tab-${idx}-plain`);
            navigator.clipboard.writeText(el.textContent).then(() => {
                btn.textContent = 'Copied!';
                btn.classList.add('copied');
                setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
            });
        }

        function downloadText(idx, title) {
            const el = document.getElementById(`tab-${idx}-plain`);
            const blob = new Blob([el.textContent], { type: 'text/plain' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = (title || 'transcript').replace(/[^a-zA-Z0-9 ]/g, '') + '.txt';
            a.click();
        }

        function clearAll() {
            document.getElementById('urlInput').value = '';
            document.getElementById('results').innerHTML = '';
            document.getElementById('status').textContent = '';
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/transcript", methods=["POST"])
def api_transcript():
    data = request.get_json()
    url = data.get("url", "")

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL", "video_id": url})

    result = fetch_transcript(video_id)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  YT Transcriber running at http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
