# 재난 방송 TTS 대시보드 - Flask 백엔드 (Supertonic, 오프라인)
import os, re, json, wave, threading, uuid
import numpy as np
import sherpa_onnx
from flask import Flask, request, jsonify, send_file, abort

# ===== 경로 설정 =====
BASE        = os.path.dirname(os.path.abspath(__file__))
PROJECT     = os.path.dirname(BASE)                       # E:\jenan
INPUT_DIR   = os.path.join(PROJECT, "input")              # 재난 텍스트 유입
PROCESSED   = os.path.join(INPUT_DIR, "processed")        # 송출 완료 보관
OUTPUT_DIR  = os.path.join(PROJECT, "output")
PREVIEW_DIR = os.path.join(OUTPUT_DIR, "voices")          # 앵커 미리듣기 샘플
BROADCAST   = os.path.join(OUTPUT_DIR, "broadcast")       # 생성된 송출 음원
MODEL_DIR   = os.path.join(PROJECT, "models", "sherpa-onnx-supertonic-3-tts-int8-2026-05-11")

for d in (INPUT_DIR, PROCESSED, OUTPUT_DIR, BROADCAST):
    os.makedirs(d, exist_ok=True)

# 앵커(화자) 표시명 - sid 0~9
ANCHOR_NAMES = ["앵커 1", "앵커 2", "앵커 3", "앵커 4", "앵커 5",
                "앵커 6", "앵커 7", "앵커 8", "앵커 9", "앵커 10"]

# ===== Supertonic 모델 1회 로드 =====
def build_tts():
    j = lambda f: os.path.join(MODEL_DIR, f)
    sup = sherpa_onnx.OfflineTtsSupertonicModelConfig(
        duration_predictor=j("duration_predictor.int8.onnx"),
        text_encoder=j("text_encoder.int8.onnx"),
        vector_estimator=j("vector_estimator.int8.onnx"),
        vocoder=j("vocoder.int8.onnx"),
        tts_json=j("tts.json"),
        unicode_indexer=j("unicode_indexer.bin"),
        voice_style=j("voice.bin"),
    )
    model = sherpa_onnx.OfflineTtsModelConfig(supertonic=sup, num_threads=4)
    return sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=model))

print("Supertonic 모델 로딩 중...")
TTS = build_tts()
TTS_LOCK = threading.Lock()    # 모델 생성 호출 직렬화
NUM_SPEAKERS = TTS.num_speakers
print(f"로드 완료. 화자 {NUM_SPEAKERS}명, sr={TTS.sample_rate}")

JOBS = {}   # job_id -> {progress,status,error,wav,duration,sample_rate,peaks}

app = Flask(__name__, static_folder="static", static_url_path="")

# ===== 텍스트 정규화 규칙 (편집 가능, rules.json에 영속) =====
RULES_FILE = os.path.join(BASE, "rules.json")
DEFAULT_RULES = [
    {"find": r"(\d+(?:\.\d+)?)\s*km/h", "replace": r"시속 \1킬로미터", "regex": True},
    {"find": r"(\d+(?:\.\d+)?)\s*m/s",  "replace": r"초속 \1미터",   "regex": True},
    {"find": r"(\d+(?:\.\d+)?)\s*mm",   "replace": r"\1밀리미터",     "regex": True},
    {"find": r"(\d+(?:\.\d+)?)\s*cm",   "replace": r"\1센티미터",     "regex": True},
    {"find": r"(\d+(?:\.\d+)?)\s*km",   "replace": r"\1킬로미터",     "regex": True},
    {"find": r"(\d+(?:\.\d+)?)\s*kg",   "replace": r"\1킬로그램",     "regex": True},
    {"find": "℃",  "replace": "도",      "regex": False},
    {"find": "°C", "replace": "도",      "regex": False},
    {"find": "%",  "replace": " 퍼센트", "regex": False},
    {"find": "~",  "replace": " 에서 ",  "regex": False},
    {"find": "≈",  "replace": " 약 ",    "regex": False},
]

def save_rules(rules):
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

def load_rules():
    try:
        with open(RULES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    save_rules(DEFAULT_RULES)
    return list(DEFAULT_RULES)

RULES = load_rules()

def normalize_text(text, rules=None):
    rules = rules if rules is not None else RULES
    t = text
    for r in rules:
        find = r.get("find", "")
        if not find:
            continue
        rep = r.get("replace", "")
        try:
            t = re.sub(find, rep, t) if r.get("regex") else t.replace(find, rep)
        except re.error:
            continue   # 잘못된 정규식은 건너뜀
    return re.sub(r"[ \t]+", " ", t).strip()

def compute_peaks(samples, n=480):
    if len(samples) == 0:
        return []
    chunk = max(1, len(samples) // n)
    peaks = [float(np.abs(samples[i:i+chunk]).max()) for i in range(0, len(samples), chunk)]
    m = max(peaks) or 1.0
    return [round(p / m, 3) for p in peaks]

def synth_worker(job_id, text, sid, speed):
    job = JOBS[job_id]
    try:
        def cb(samples, progress):
            job["progress"] = int(float(progress) * 100)
            return 1
        with TTS_LOCK:
            job["status"] = "synthesizing"
            audio = TTS.generate(text, sid=sid, speed=speed, callback=cb)
        samples = np.asarray(audio.samples, dtype=np.float32)
        pcm = np.clip(samples * 32767.0, -32768, 32767).astype("<i2")
        wav_path = os.path.join(BROADCAST, f"{job_id}.wav")
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(audio.sample_rate)
            w.writeframes(pcm.tobytes())
        job.update(status="done", progress=100, wav=wav_path,
                   duration=round(len(samples) / audio.sample_rate, 2),
                   sample_rate=audio.sample_rate, peaks=compute_peaks(samples))
    except Exception as e:
        job.update(status="error", error=str(e))

# ===== 라우트 =====
@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/voices")
def api_voices():
    out = []
    for sid in range(NUM_SPEAKERS):
        name = ANCHOR_NAMES[sid] if sid < len(ANCHOR_NAMES) else f"앵커 {sid+1}"
        preview = os.path.join(PREVIEW_DIR, f"supertonic_sid{sid:02d}.wav")
        out.append({"sid": sid, "name": name, "has_preview": os.path.exists(preview)})
    return jsonify(out)

@app.route("/api/voice-preview/<int:sid>")
def api_voice_preview(sid):
    p = os.path.join(PREVIEW_DIR, f"supertonic_sid{sid:02d}.wav")
    if not os.path.exists(p):
        abort(404)
    return send_file(p, mimetype="audio/wav")

def _safe_doc(name):
    name = os.path.basename(name)
    if not name.lower().endswith(".txt"):
        abort(400)
    path = os.path.join(INPUT_DIR, name)
    if not os.path.isfile(path):
        abort(404)
    return path

@app.route("/api/documents")
def api_documents():
    items = []
    for f in sorted(os.listdir(INPUT_DIR)):
        path = os.path.join(INPUT_DIR, f)
        if not (os.path.isfile(path) and f.lower().endswith(".txt")):
            continue
        st = os.stat(path)
        try:
            content = open(path, encoding="utf-8-sig", errors="ignore").read()
        except Exception:
            content = ""
        items.append({
            "name": f, "size": st.st_size, "mtime": st.st_mtime,
            "snippet": content.strip().replace("\n", " ")[:60],
        })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return jsonify(items)

@app.route("/api/document")
def api_document():
    path = _safe_doc(request.args.get("name", ""))
    content = open(path, encoding="utf-8-sig", errors="ignore").read()
    return jsonify({"name": os.path.basename(path), "content": content})

@app.route("/api/rules")
def api_get_rules():
    return jsonify(RULES)

@app.route("/api/rules/default")
def api_get_default_rules():
    return jsonify(DEFAULT_RULES)

@app.route("/api/rules", methods=["POST"])
def api_set_rules():
    global RULES
    data = request.get_json(force=True)
    clean = []
    for r in (data.get("rules") or []):
        find = (r.get("find") or "").strip()
        if not find:
            continue
        clean.append({"find": find, "replace": r.get("replace", ""), "regex": bool(r.get("regex"))})
    save_rules(clean)
    RULES = clean
    return jsonify({"ok": True, "count": len(clean)})

@app.route("/api/normalize-preview", methods=["POST"])
def api_normalize_preview():
    data = request.get_json(force=True)
    return jsonify({"result": normalize_text(data.get("text", ""), data.get("rules"))})

@app.route("/api/synthesize", methods=["POST"])
def api_synthesize():
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "빈 텍스트"}), 400
    sid = int(data.get("sid", 0))
    speed = float(data.get("speed", 1.0))
    if data.get("normalize"):
        text = normalize_text(text, data.get("rules"))
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"progress": 0, "status": "queued"}
    threading.Thread(target=synth_worker, args=(job_id, text, sid, speed), daemon=True).start()
    return jsonify({"job_id": job_id, "normalized_text": text})

@app.route("/api/progress/<job_id>")
def api_progress(job_id):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    resp = {k: v for k, v in job.items() if k != "wav"}
    if job.get("status") == "done":
        resp["audio_url"] = f"/api/audio/{job_id}"
    return jsonify(resp)

@app.route("/api/audio/<job_id>")
def api_audio(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "done":
        abort(404)
    return send_file(job["wav"], mimetype="audio/wav")

@app.route("/api/broadcast", methods=["POST"])
def api_broadcast():
    # 원본 문서를 처리완료로 이동(송출 확정)
    data = request.get_json(force=True)
    name = data.get("source_doc")
    moved = None
    if name:
        try:
            src = _safe_doc(name)
            dst = os.path.join(PROCESSED, os.path.basename(src))
            os.replace(src, dst)
            moved = os.path.basename(dst)
        except Exception:
            moved = None
    return jsonify({"ok": True, "moved": moved})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True)
