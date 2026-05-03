"""
Flask web wrapper for textSansur.
Backend AI/OCR mantığı (TextCensorAI, ImageCensor) olduğu gibi kullanılır;
bu dosya yalnızca tarayıcıya hizmet eden bir HTTP arayüzüdür.
"""

import base64
import io
import os
import time
import uuid
from threading import Lock, Thread

import cv2
import numpy as np
import requests as pyrequests
from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS
from PIL import Image

from TextCensorAI import TextCensorAI
from ImageCensor import ImageCensor
from prompts import MODEL_NAME

APP_NAME = "Veri Maskeleme"
APP_TAGLINE = "AI ile Akıllı Veri Maskeleme"

# Ollama adresi — Docker compose'da 'http://ollama:11434' olur, lokalde varsayılan 127.0.0.1
# 'ollama' Python paketi de bu env değişkenini otomatik okur, ek ayar gerekmez.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
os.environ["OLLAMA_HOST"] = OLLAMA_HOST   # alt importlar için garanti


app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

# AI motorları sadece bir kez yüklensin (özellikle EasyOCR ağır)
_engines = {"text": None, "image": None}
_engine_lock = Lock()
_status = {
    "text_ready": False,
    "image_ready": False,
    "ollama_ready": False,
    "warmup_started": False,
    "warmup_log": [],
    "current_job": None,  # {"kind": "text"|"image", "stage": "...", "started": ts}
}
_status_lock = Lock()


def _log(msg: str):
    print(f"[textSansur] {msg}", flush=True)
    with _status_lock:
        _status["warmup_log"].append(f"{time.strftime('%H:%M:%S')} {msg}")
        _status["warmup_log"] = _status["warmup_log"][-20:]


def _set_stage(kind: str, stage: str):
    with _status_lock:
        _status["current_job"] = {"kind": kind, "stage": stage, "started": time.time()}


def _clear_stage():
    with _status_lock:
        _status["current_job"] = None


def get_text_engine() -> TextCensorAI:
    with _engine_lock:
        if _engines["text"] is None:
            _log("TextCensorAI yükleniyor…")
            _engines["text"] = TextCensorAI()
            with _status_lock:
                _status["text_ready"] = True
            _log("TextCensorAI hazır")
        return _engines["text"]


def get_image_engine() -> ImageCensor:
    with _engine_lock:
        if _engines["image"] is None:
            _log("ImageCensor yükleniyor (EasyOCR modelleri ilk seferde yavaş olabilir)…")
            _engines["image"] = ImageCensor()
            with _status_lock:
                _status["image_ready"] = True
            _log("ImageCensor hazır")
        return _engines["image"]


def _check_ollama() -> bool:
    try:
        r = pyrequests.get(f"{OLLAMA_HOST.rstrip('/')}/api/tags", timeout=2)
        if r.status_code == 200:
            with _status_lock:
                _status["ollama_ready"] = True
            return True
    except Exception:
        pass
    with _status_lock:
        _status["ollama_ready"] = False
    return False


def warmup():
    """Sunucu başlangıcında AI motorlarını önyükle (arka plan thread)."""
    with _status_lock:
        if _status["warmup_started"]:
            return
        _status["warmup_started"] = True
    _log("Warmup başladı")
    if _check_ollama():
        _log(f"Ollama erişilebilir: {OLLAMA_HOST}")
    else:
        _log(f"UYARI: Ollama {OLLAMA_HOST} adresinde bulunamadı — `ollama serve` çalıştırın")
    try:
        get_text_engine()
    except Exception as e:
        _log(f"TextCensorAI hata: {e}")
    try:
        get_image_engine()
    except Exception as e:
        _log(f"ImageCensor hata: {e}")
    _log("Warmup tamam — sunucu kullanıma hazır")


def cv_to_data_url(img_bgr) -> str:
    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        raise RuntimeError("PNG encode failed")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def data_url_to_cv(data_url: str):
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    raw = base64.b64decode(data_url)
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


@app.route("/")
def index():
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    cb = 0
    for root, _, files in os.walk(static_dir):
        for f in files:
            try:
                m = os.path.getmtime(os.path.join(root, f))
                if m > cb: cb = m
            except OSError:
                pass
    resp = app.make_response(
        render_template(
            "index.html",
            model_name=MODEL_NAME,
            app_name=APP_NAME,
            app_tagline=APP_TAGLINE,
            cache_buster=int(cb),
        )
    )
    # HTML her zaman yeniden yüklensin — eski cached HTML eski ?v= göstermesin
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.after_request
def _no_cache_for_static(resp):
    # JS/CSS dosyaları için de cache'i bertaraf et (en sıkı kural)
    if request.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/api/health")
def health():
    # Ollama'yı her seferinde tekrar kontrol et (ucuz, 2s timeout)
    _check_ollama()
    with _status_lock:
        return jsonify(
            {
                "ok": True,
                "model": MODEL_NAME,
                "text_ready": _status["text_ready"],
                "image_ready": _status["image_ready"],
                "ollama_ready": _status["ollama_ready"],
                "warmup_started": _status["warmup_started"],
                "current_job": _status["current_job"],
                "log": _status["warmup_log"][-6:],
            }
        )


def _ollama_censor(text: str):
    """Doğrudan Ollama'ya prompt yolla, JSON yanıtını yakala.
    Hata durumunda dict döndürür; sessiz hata yutmaz."""
    import json as _json
    from ollama import Client as _OllamaClient
    from prompts import build_prompt as _build, SYSTEM_PROMPT as _sys

    try:
        # 90 sn'de yanıt yoksa düş — Cloudflare 100 sn 504'ten önce bizim 503'ümüzü dönsün
        client = _OllamaClient(host=OLLAMA_HOST, timeout=90)
        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _sys},
                {"role": "user", "content": _build(text)},
            ],
            format="json",
            options={"temperature": 0.1, "num_ctx": 4096},
            keep_alive="30m",   # modeli 30dk RAM'de tut → soğuk yükleme yok
        )
        raw = response["message"]["content"]
    except Exception as e:
        # OOM, timeout, network — kullanıcıya net mesaj
        return {
            "ok": False,
            "error": (
                f"Ollama yanıt vermedi ({e}). Sunucu RAM yetersizse model "
                f"yüklenememiş olabilir; daha küçük model deneyin (qwen2.5:7b veya 3b)."
            ),
        }

    try:
        parsed = _json.loads(raw)
    except Exception as e:
        return {
            "ok": False,
            "error": f"Model JSON döndürmedi ({e}). Yanıt başlangıcı: {raw[:160]}",
            "raw": raw[:500],
        }

    items = parsed.get("gizlenecekler", [])
    if not isinstance(items, list):
        return {"ok": False, "error": "Yanıt 'gizlenecekler' anahtarı liste değil"}

    # Maskelemeyi kendimiz uygula (TextCensorAI.mask_word ile aynı mantık)
    import re as _re

    def _mask(w: str) -> str:
        if len(w) <= 2:
            return w[0] + "*" * (len(w) - 1) if w else w
        return w[:2] + "*" * (len(w) - 2)

    def _safe_replace(text_in: str, needle: str, replacement: str) -> tuple:
        """Sadece kelime sınırlarında değiştir → mersis ortasında TC alt-dizisini yakalama."""
        # \b sayısal/alfabe sınırı; hem ASCII hem Unicode için çalışır
        pattern = r"(?<![\w])" + _re.escape(needle) + r"(?![\w])"
        new_text, n = _re.subn(pattern, lambda _m: replacement, text_in)
        return new_text, n

    # Uzun item'ları önce işle (örn: "Burak Kaya"yı "Kaya"dan önce maskele)
    sorted_items = sorted(
        [i for i in items if isinstance(i, str) and i.strip()],
        key=lambda s: -len(s),
    )

    censored = text
    applied = []
    for item in sorted_items:
        masked = " ".join(_mask(p) for p in item.split())
        new_censored, count = _safe_replace(censored, item, masked)
        if count > 0:
            censored = new_censored
            applied.append(item)
        else:
            applied.append(f"[no-match: {item}]")
    return {"ok": True, "censored": censored, "items": items, "applied": applied}


@app.route("/api/censor-text", methods=["POST"])
def api_censor_text():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Boş metin"}), 400

    if not _check_ollama():
        return jsonify({"ok": False, "error": f"Ollama servisi çalışmıyor ({OLLAMA_HOST}). `ollama serve` komutunu çalıştırın veya OLLAMA_HOST env değişkenini kontrol edin."}), 503

    t0 = time.time()
    _set_stage("text", "Yapay zekâ analizi…")
    try:
        result = _ollama_censor(text)
    finally:
        _clear_stage()

    if not result.get("ok"):
        return jsonify(result), 502

    censored = result["censored"]
    items = result.get("items", [])

    # İstatistik
    masked_count = censored.count("*")
    import re

    masked_words = re.findall(r"\S*\*+\S*", censored)

    no_match = [a for a in result.get("applied", []) if str(a).startswith("[no-match")]
    return jsonify(
        {
            "ok": True,
            "original": text,
            "censored": censored,
            "items": items,
            "no_match": no_match,
            "stats": {
                "elapsed_ms": int((time.time() - t0) * 1000),
                "masked_chars": masked_count,
                "masked_words": len(masked_words),
                "char_count": len(text),
                "word_count": len(text.split()),
                "detected_count": len(items),
            },
        }
    )


@app.route("/api/detect-image", methods=["POST"])
def api_detect_image():
    """Resim yükle -> OCR + AI çalıştır -> orijinal resmi ve önerilen sansür kutularını döner."""
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "image dosyası gerekli"}), 400

    file = request.files["image"]
    raw = file.read()
    if not raw:
        return jsonify({"ok": False, "error": "Boş dosya"}), 400

    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"ok": False, "error": "Resim çözülemedi"}), 400

    if not _check_ollama():
        return jsonify({"ok": False, "error": f"Ollama servisi çalışmıyor ({OLLAMA_HOST}). `ollama serve` komutunu çalıştırın veya OLLAMA_HOST env değişkenini kontrol edin."}), 503

    t0 = time.time()
    _set_stage("image", "OCR motoru yükleniyor…")
    try:
        engine = get_image_engine()

        # ImageCensor.process_image içindeki adımları (Tkinter olmadan) çoğaltıyoruz
        _set_stage("image", "Resim taranıyor (OCR)…")
        results = engine.reader.readtext(img)
        full_text = " ".join([text for (_bbox, text, _prob) in results])
        _set_stage("image", "Yapay zekâ hassas alanları belirliyor…")
        targets = engine.get_targets_from_ai(full_text) if full_text.strip() else []
    finally:
        pass  # boxes hesabı bittikten sonra clear edeceğiz

    boxes = []
    detected_words = []
    for (bbox, text, prob) in results:
        is_target = any(
            text.strip().lower() in target.lower() for target in targets
        )
        if (
            not is_target
            and len(text.strip()) > 5
            and any(ch.isdigit() for ch in text)
        ):
            clean_text = "".join(filter(str.isdigit, text))
            is_target = any(
                clean_text in target.replace(" ", "") for target in targets
            )
        if is_target:
            tl = tuple(map(int, bbox[0]))
            br = tuple(map(int, bbox[2]))
            boxes.append(
                {"x1": tl[0], "y1": tl[1], "x2": br[0], "y2": br[1], "label": text}
            )
            detected_words.append(text)

    h, w = img.shape[:2]
    payload = {
        "ok": True,
        "image": cv_to_data_url(img),
        "width": w,
        "height": h,
        "boxes": boxes,
        "ocr_text": full_text,
        "ai_targets": targets,
        "detected_words": detected_words,
        "stats": {
            "elapsed_ms": int((time.time() - t0) * 1000),
            "ocr_count": len(results),
            "target_count": len(boxes),
        },
    }
    _clear_stage()
    return jsonify(payload)


@app.route("/api/apply-blur", methods=["POST"])
def api_apply_blur():
    """Frontend'den gelen kutuları orijinal resme uygular (gaussian blur)."""
    data = request.get_json(force=True, silent=True) or {}
    image_b64 = data.get("image")
    boxes = data.get("boxes", [])
    blur_strength = int(data.get("blur", 71))
    style = data.get("style", "blur")  # "blur" | "black" | "pixelate"

    if blur_strength % 2 == 0:
        blur_strength += 1
    blur_strength = max(15, min(151, blur_strength))

    if not image_b64:
        return jsonify({"ok": False, "error": "image gerekli"}), 400

    img = data_url_to_cv(image_b64)
    if img is None:
        return jsonify({"ok": False, "error": "Resim çözülemedi"}), 400

    h, w = img.shape[:2]
    for box in boxes:
        x1 = max(0, min(int(box["x1"]), int(box["x2"])))
        x2 = min(w, max(int(box["x1"]), int(box["x2"])))
        y1 = max(0, min(int(box["y1"]), int(box["y2"])))
        y2 = min(h, max(int(box["y1"]), int(box["y2"])))
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        roi = img[y1:y2, x1:x2]
        if roi.size == 0:
            continue
        if style == "black":
            img[y1:y2, x1:x2] = 0
        elif style == "pixelate":
            small = cv2.resize(
                roi, (max(1, (x2 - x1) // 12), max(1, (y2 - y1) // 12)),
                interpolation=cv2.INTER_LINEAR,
            )
            img[y1:y2, x1:x2] = cv2.resize(
                small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST
            )
        else:
            img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (blur_strength, blur_strength), 0)

    return jsonify({"ok": True, "image": cv_to_data_url(img)})


@app.route("/api/sample-text")
def api_sample_text():
    samples = [
        (
            "Şikayet metni",
            "Merhaba, ben Ahmet Yılmaz. Geçen hafta GlobalTrade FX isimli bir firmaya yatırım "
            "yaptım. Beni 0555 111 22 33 numarasından Mehmet isminde bir müşteri temsilcisi "
            "aradı. Kendi numaram olan 0532 999 88 77 üzerinden bana ulaştılar. E-postam "
            "ahmet.yilmaz@mail.com. Parayı gönderdikten sonra hesabımı kapattılar.",
        ),
        (
            "İş başvurusu",
            "Sayın yetkili, ben Burak Kaya. ABC Yazılım A.Ş. firmasında açık olan yazılım "
            "geliştirici pozisyonu için başvurmak istiyorum. CV'me burak.kaya@example.com "
            "adresinden veya 0533 444 55 66 numarasından ulaşabilirsiniz.",
        ),
        (
            "Kısa bildirim",
            "Müşteri Ayşe Kara (TC: 12345678901), siparişinin kargoya verilmediğini "
            "belirtti. İletişim: ayse.kara@example.com / 0212 555 11 22.",
        ),
    ]
    return jsonify({"ok": True, "samples": [{"title": t, "text": x} for t, x in samples]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n>>> textSansur web arayüzü:  http://127.0.0.1:{port}")
    print(">>> AI motorları arka planda yükleniyor; tarayıcıda durum çubuğu güncellenecek.\n")
    Thread(target=warmup, daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
