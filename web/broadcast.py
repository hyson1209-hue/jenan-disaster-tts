# 긴급 송출(오버라이드) 제어 — 절체기 트리거 + 서버측 재생 + 워치독 + as-run 로그
# 하드웨어 없으면 자동으로 시뮬레이션 모드. 환경변수로 실제 장비 전환.
import os, time, json, wave, threading

BASE    = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(BASE)
OUTPUT  = os.path.join(PROJECT, "output")
ASRUN   = os.path.join(OUTPUT, "asrun.jsonl")
os.makedirs(OUTPUT, exist_ok=True)

# ===== 설정 (실제 장비에 맞게 환경변수로) =====
RELAY_BACKEND = os.environ.get("TTS_RELAY", "sim")        # 'sim' | 'serial'
RELAY_PORT    = os.environ.get("TTS_RELAY_PORT", "COM3")
RELAY_BAUD    = int(os.environ.get("TTS_RELAY_BAUD", "9600"))
RELAY_ON_HEX  = os.environ.get("TTS_RELAY_ON",  "A00101A2")  # 절체 ON(→Backup) 바이트(보드 사양에 맞게)
RELAY_OFF_HEX = os.environ.get("TTS_RELAY_OFF", "A00100A1")  # 절체 OFF(→Main)

PLAYER_BACKEND = os.environ.get("TTS_PLAYER", "sim")      # 'sim' | 'device'
OUTPUT_DEVICE  = os.environ.get("TTS_OUT_DEVICE", "")     # sounddevice 출력 장치명/번호, 빈값=기본
MAX_AIR_SECONDS = int(os.environ.get("TTS_MAX_AIR", "120"))  # 워치독 상한(이 시간 넘으면 강제 복귀)


def _wav_info(path):
    with wave.open(path, "rb") as w:
        return w.getnframes(), w.getframerate(), w.getnchannels()


# ---------- 절체기(릴레이) ----------
class SimRelay:
    def __init__(self, log): self.log = log
    def engage(self):  self.log("relay", "ENGAGE  → Backup(TTS) 절체 [SIM]")
    def release(self): self.log("relay", "RELEASE → Main(정규방송) 복귀 [SIM]")

class SerialRelay:
    def __init__(self, log):
        import serial
        self.ser = serial.Serial(RELAY_PORT, RELAY_BAUD, timeout=1)
        self.on, self.off = bytes.fromhex(RELAY_ON_HEX), bytes.fromhex(RELAY_OFF_HEX)
        self.log = log
    def engage(self):  self.ser.write(self.on);  self.log("relay", "ENGAGE → Backup(TTS) 절체")
    def release(self): self.ser.write(self.off); self.log("relay", "RELEASE → Main 복귀")

def _build_relay(log):
    if RELAY_BACKEND == "serial":
        try:
            return SerialRelay(log)
        except Exception as e:
            log("relay", f"serial 초기화 실패 → SIM 사용 ({e})")
    return SimRelay(log)


# ---------- 재생기 (서버측, 방송 출력 장치로) ----------
class SimPlayer:
    def play(self, path, stop_event):
        frames, sr, _ = _wav_info(path)
        end = time.time() + frames / float(sr)
        while time.time() < end and not stop_event.is_set():
            time.sleep(0.05)

class DevicePlayer:
    def __init__(self, device): self.device = device or None
    def play(self, path, stop_event):
        import numpy as np, sounddevice as sd
        frames, sr, ch = _wav_info(path)
        with wave.open(path, "rb") as w:
            raw = w.readframes(frames)
        data = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
        if ch > 1:
            data = data.reshape(-1, ch)
        sd.play(data, sr, device=self.device)
        end = time.time() + frames / float(sr) + 0.2
        while time.time() < end and not stop_event.is_set():
            time.sleep(0.05)
        sd.stop()

def _build_player():
    if PLAYER_BACKEND == "device":
        try:
            import sounddevice  # noqa: F401
            return DevicePlayer(OUTPUT_DEVICE)
        except Exception:
            pass
    return SimPlayer()


# ---------- 송출 오케스트레이션 ----------
class AirController:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"on_air": False, "since": None, "what": None, "repeats": 0}
        self._stop = threading.Event()
        self.relay = _build_relay(self._log)
        self.player = _build_player()

    def _log(self, kind, msg, **extra):
        rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, "msg": msg, **extra}
        try:
            with open(ASRUN, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def air(self, wav_path, label="", repeats=1):
        with self.lock:
            if self.state["on_air"]:
                return {"ok": False, "error": "이미 송출 중입니다"}
            self.state.update(on_air=True, since=time.strftime("%H:%M:%S"),
                              what=label, repeats=repeats)
        self._stop.clear()
        threading.Thread(target=self._run, args=(wav_path, label, repeats), daemon=True).start()
        return {"ok": True}

    def _run(self, wav_path, label, repeats):
        self._log("air_start", "긴급 오버라이드 송출 시작",
                  label=label, repeats=repeats, wav=os.path.basename(wav_path))
        watchdog = threading.Timer(MAX_AIR_SECONDS, self._force_stop)
        watchdog.start()
        try:
            self.relay.engage()
            for _ in range(max(1, repeats)):
                if self._stop.is_set():
                    break
                self.player.play(wav_path, self._stop)
        except Exception as e:
            self._log("air_error", str(e))
        finally:
            self.relay.release()          # 어떤 경우에도 정규방송 복귀
            watchdog.cancel()
            with self.lock:
                self.state.update(on_air=False, since=None, what=None, repeats=0)
            self._log("air_end", "송출 종료 · 정규방송 복귀")

    def _force_stop(self):
        self._log("watchdog", f"타임아웃 {MAX_AIR_SECONDS}s 초과 — 강제 종료·복귀")
        self._stop.set()

    def stop(self):
        if self.state["on_air"]:
            self._log("manual_stop", "운영자 수동 중지")
        self._stop.set()
        return {"ok": True}

    def status(self):
        with self.lock:
            s = dict(self.state)
        s.update(relay=RELAY_BACKEND, player=PLAYER_BACKEND, max_air=MAX_AIR_SECONDS)
        return s

    def recent(self, n=50):
        if not os.path.exists(ASRUN):
            return []
        try:
            with open(ASRUN, encoding="utf-8") as f:
                lines = f.readlines()[-n:]
            return [json.loads(x) for x in lines if x.strip()]
        except Exception:
            return []
