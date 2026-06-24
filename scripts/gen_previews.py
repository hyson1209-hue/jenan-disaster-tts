# 앵커(화자) 미리듣기 샘플 생성 -> output/voices/supertonic_sid{NN}.wav
# 대시보드의 앵커 미리듣기에 사용된다.
import os, wave, array
import sherpa_onnx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "models", "sherpa-onnx-supertonic-3-tts-int8-2026-05-11")
OUTDIR = os.path.join(ROOT, "output", "voices")
os.makedirs(OUTDIR, exist_ok=True)

PREVIEW_TEXT = "지진 발생 안내입니다. 책상 아래로 몸을 피하고 머리를 보호하시기 바랍니다."

j = lambda f: os.path.join(MODEL, f)
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
tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=model))

for sid in range(tts.num_speakers):
    a = tts.generate(PREVIEW_TEXT, sid=sid, speed=1.0)
    pcm = array.array("h", (max(-32768, min(32767, int(s * 32767))) for s in a.samples))
    out = os.path.join(OUTDIR, f"supertonic_sid{sid:02d}.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(a.sample_rate)
        w.writeframes(pcm.tobytes())
    print(f"sid{sid:02d} -> {out}")
print(f"완료: {tts.num_speakers}개 앵커 프리뷰")
