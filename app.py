import os, re
from flask import Flask, render_template_string, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
import urllib.request

app = Flask(__name__)

COOKIE_PATH = None
for path in ["/etc/secrets/cookies.txt", os.path.join(os.path.dirname(__file__), "cookies.txt")]:
    if os.path.exists(path):
        COOKIE_PATH = path
        break

def extract_video_id(url):
    for p in [r'(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})', r'^([a-zA-Z0-9_-]{11})$']:
        m = re.search(p, url.strip())
        if m:
            return m.group(1)
    return ""

def get_video_title(video_id):
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'<title>(.*?)</title>', html)
            if m:
                return m.group(1).replace(" - YouTube", "").strip()
    except Exception:
        pass
    return "Video " + video_id

def fetch_transcript(video_id):
    try:
        title = get_video_title(video_id)
        kwargs = {}
        if COOKIE_PATH:
            kwargs["cookies"] = COOKIE_PATH
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id, **kwargs)
        transcript = None
        lang = "en"
        is_auto = False
        try:
            transcript = transcript_list.find_manually_created_transcript(["en"])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(["en"])
                is_auto = True
            except Exception:
                for t in transcript_list:
                    transcript = t
                    lang = t.language_code
                    is_auto = t.is_generated
                    break
        if not transcript:
            return {"error": "No transcript available", "video_id": video_id}
        entries = transcript.fetch()
        full_text = " ".join([e["text"] for e in entries])
        timestamped = []
        for e in entries:
            mins = int(e["start"] // 60)
            secs = int(e["start"] % 60)
            timestamped.append({"time": str(mins).zfill(2) + ":" + str(secs).zfill(2), "start": e["start"], "text": e["text"]})
        last = entries[-1] if entries else {"start": 0, "duration": 0}
        return {
            "video_id": video_id, "title": title, "language": lang,
            "is_auto_generated": is_auto, "full_text": full_text,
            "timestamped": timestamped, "word_count": len(full_text.split()),
            "duration_seconds": int(last["start"] + last.get("duration", 0)),
        }
    except Exception as e:
        msg = str(e)
        if "IP" in msg or "blocked" in msg:
            return {"error": "YouTube is blocking requests from this server. Try adding cookies.", "video_id": video_id}
        return {"error": msg, "video_id": video_id}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>YT Transcriber</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#08080c;--sf:#101016;--sf2:#18181f;--bd:#25252f;--tx:#e4e4e8;--dim:#7a7a88;--ac:#ef4444;--ok:#22c55e;--fd:'Outfit',sans-serif;--fm:'JetBrains Mono',monospace}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--fd);background:var(--bg);color:var(--tx);min-height:100vh}
.app{max-width:900px;margin:0 auto;padding:40px 24px 80px}
.logo{font-size:32px;font-weight:700;letter-spacing:-1px;margin-bottom:6px}
.logo span{color:var(--ac)}
.sub{font-size:14px;color:var(--dim);font-weight:300}
.inp{margin-top:40px;background:var(--sf);border:1px solid var(--bd);border-radius:16px;padding:24px}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--dim);margin-bottom:12px;font-weight:500}
textarea{width:100%;min-height:120px;background:var(--sf2);border:1px solid var(--bd);border-radius:10px;color:var(--tx);font-family:var(--fm);font-size:14px;padding:16px;resize:vertical;outline:none}
textarea:focus{border-color:var(--ac)}
.br{display:flex;gap:12px;margin-top:16px}
.btn{padding:12px 28px;border-radius:10px;font-family:var(--fd);font-size:14px;font-weight:600;cursor:pointer;border:none}
.bp{background:var(--ac);color:#fff;box-shadow:0 0 20px rgba(239,68,68,0.15)}
.bp:hover{filter:brightness(1.1)}.bp:disabled{opacity:0.4;cursor:not-allowed}
.bg{background:transparent;color:var(--dim);border:1px solid var(--bd)}
.bg:hover{border-color:var(--dim);color:var(--tx)}
.st{margin-top:16px;font-size:13px;color:var(--dim);min-height:20px}
.st.ld{color:var(--ac)}.st.ok{color:var(--ok)}
.res{margin-top:32px}
.card{background:var(--sf);border:1px solid var(--bd);border-radius:16px;margin-bottom:20px;overflow:hidden}
.ch{padding:20px 24px;display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--bd);gap:16px}
.ct{font-size:16px;font-weight:600;line-height:1.4;flex:1}
.cm{display:flex;gap:16px;font-size:12px;color:var(--dim);margin-top:6px;flex-wrap:wrap}
.ca{display:flex;gap:8px;flex-shrink:0}
.bs{padding:6px 14px;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;border:1px solid var(--bd);background:var(--sf2);color:var(--dim);font-family:var(--fd)}
.bs:hover{border-color:var(--ac);color:var(--tx)}
.tabs{display:flex;border-bottom:1px solid var(--bd)}
.tab{padding:12px 20px;font-size:13px;font-weight:500;color:var(--dim);cursor:pointer;border:none;border-bottom:2px solid transparent;background:none;font-family:var(--fd)}
.tab:hover{color:var(--tx)}.tab.on{color:var(--ac);border-bottom-color:var(--ac)}
.tbody{padding:20px 24px;max-height:500px;overflow-y:auto;font-size:14px;line-height:1.8}
.ttext{color:var(--tx);white-space:pre-wrap;font-family:var(--fd)}
.tsl{display:flex;gap:16px;padding:4px 0;border-bottom:1px solid var(--bd)}
.tsl:last-child{border-bottom:none}
.tst{font-family:var(--fm);font-size:12px;color:var(--ac);flex-shrink:0;min-width:48px;cursor:pointer;text-decoration:none}
.tst:hover{text-decoration:underline}
.tsx{color:var(--tx);font-size:14px}
.err{background:var(--sf);border:1px solid #7f1d1d;border-radius:16px;padding:20px 24px;margin-bottom:20px;color:#fca5a5;font-size:14px}
.err b{color:#f87171}
@media(max-width:600px){.app{padding:24px 16px 60px}.ch{flex-direction:column}.ca{width:100%}.bs{flex:1;text-align:center}.br{flex-direction:column}.btn{width:100%;text-align:center}}
</style>
</head>
<body>
<div class="app">
<div class="logo"><span>YT</span> Transcriber</div>
<div class="sub">Pull transcripts from YouTube videos. Copy, download, or read with timestamps.</div>
<div class="inp">
<div class="lbl">YouTube URLs (one per line)</div>
<textarea id="urls" placeholder="https://www.youtube.com/watch?v=VIDEO_ID"></textarea>
<div class="br">
<button class="btn bp" id="fbtn" onclick="doFetch()">Fetch Transcripts</button>
<button class="btn bg" onclick="doClear()">Clear</button>
</div>
<div class="st" id="stat"></div>
</div>
<div class="res" id="res"></div>
</div>
<script>
async function doFetch() {
  var lines = document.getElementById("urls").value.trim().split("\n").filter(function(u){return u.trim();});
  if (lines.length === 0) return;
  var btn = document.getElementById("fbtn");
  var stat = document.getElementById("stat");
  var res = document.getElementById("res");
  btn.disabled = true;
  btn.textContent = "Fetching...";
  stat.className = "st ld";
  res.innerHTML = "";
  for (var i = 0; i < lines.length; i++) {
    stat.textContent = "Fetching " + (i+1) + " of " + lines.length + "...";
    try {
      var resp = await fetch("/api/transcript", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url: lines[i].trim()})
      });
      var data = await resp.json();
      if (data.error) {
        res.innerHTML += '<div class="err"><b>Error:</b> ' + data.error + '<br><span style="color:#7a7a88">' + (data.video_id || "") + '</span></div>';
      } else {
        res.innerHTML += buildCard(data, i);
      }
    } catch(e) {
      res.innerHTML += '<div class="err"><b>Error:</b> ' + e.message + '</div>';
    }
  }
  btn.disabled = false;
  btn.textContent = "Fetch Transcripts";
  stat.className = "st ok";
  stat.textContent = "Done. " + lines.length + " video(s) processed.";
}

function buildCard(d, idx) {
  var dur = d.duration_seconds;
  var mm = Math.floor(dur / 60);
  var ss = dur % 60;
  var durStr = mm + ":" + (ss < 10 ? "0" : "") + ss;
  var tsRows = "";
  if (d.timestamped) {
    for (var j = 0; j < d.timestamped.length; j++) {
      var t = d.timestamped[j];
      tsRows += '<div class="tsl"><a class="tst" href="https://youtube.com/watch?v=' + d.video_id + '&t=' + Math.floor(t.start) + '" target="_blank">' + t.time + '</a><span class="tsx">' + t.text + '</span></div>';
    }
  }
  var safeTitle = (d.title || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  var h = '<div class="card">';
  h += '<div class="ch"><div><div class="ct">' + safeTitle + '</div>';
  h += '<div class="cm"><span>' + d.word_count + ' words</span><span>' + durStr + '</span><span>' + (d.is_auto_generated ? "Auto" : "Manual") + ' (' + d.language + ')</span></div>';
  h += '</div><div class="ca">';
  h += '<button class="bs" onclick="doCopy(' + idx + ',this)">Copy</button>';
  h += '<button class="bs" onclick="doDl(' + idx + ')">Download</button>';
  h += '</div></div>';
  h += '<div class="tabs"><button class="tab on" onclick="showT(' + idx + ',0,this)">Plain Text</button><button class="tab" onclick="showT(' + idx + ',1,this)">Timestamps</button></div>';
  h += '<div class="tbody"><div id="p' + idx + '" class="ttext">' + d.full_text + '</div><div id="t' + idx + '" style="display:none">' + tsRows + '</div></div>';
  h += '</div>';
  return h;
}

function showT(idx, mode, el) {
  document.getElementById("p" + idx).style.display = mode === 0 ? "" : "none";
  document.getElementById("t" + idx).style.display = mode === 1 ? "" : "none";
  var tabs = el.parentElement.querySelectorAll(".tab");
  for (var i = 0; i < tabs.length; i++) tabs[i].className = "tab";
  el.className = "tab on";
}

function doCopy(idx, btn) {
  var el = document.getElementById("p" + idx);
  navigator.clipboard.writeText(el.textContent).then(function() {
    btn.textContent = "Copied!";
    btn.style.borderColor = "#22c55e";
    btn.style.color = "#22c55e";
    setTimeout(function() { btn.textContent = "Copy"; btn.style.borderColor = ""; btn.style.color = ""; }, 2000);
  });
}

function doDl(idx) {
  var el = document.getElementById("p" + idx);
  var blob = new Blob([el.textContent], {type: "text/plain"});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "transcript_" + idx + ".txt";
  a.click();
}

function doClear() {
  document.getElementById("urls").value = "";
  document.getElementById("res").innerHTML = "";
  document.getElementById("stat").textContent = "";
}
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/transcript", methods=["POST"])
def api_transcript():
    data = request.get_json()
    video_id = extract_video_id(data.get("url", ""))
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL", "video_id": data.get("url", "")})
    return jsonify(fetch_transcript(video_id))

@app.route("/health")
def health():
    return jsonify({"status": "ok", "cookies": COOKIE_PATH is not None})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
