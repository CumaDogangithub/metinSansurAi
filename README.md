# Veri Maskeleme · KVKK Uyumlu AI Maskeleyici

> **Yerel** çalışan, internete hiçbir veri göndermeyen, bağlam farkındalığına sahip kişisel veri (PII) maskeleme aracı. Hem **metin** hem **görsel** üzerinde çalışır; ne olduğu değil **kime ait olduğu** kararını verebilen bir prompt mimarisi kullanır.

![Stack](https://img.shields.io/badge/python-3.10+-blue)
![Ollama](https://img.shields.io/badge/ollama-qwen2.5%3A14b-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Status](https://img.shields.io/badge/status-aktif-brightgreen)

---

## Öne Çıkan Özellikler

- **%100 yerel** — yapay zekâ çıkarımı sizin makinenizde, veriler asla buluta gönderilmez
- **Bağlam farkındalığı** — bir KVKK şikayet dilekçesinde dolandırıcının ismini sansürlemez, sadece gönderici verilerini gizler
- **Metin maskeleme** — Türkçe + İngilizce + çoklu dil; ad/TC/telefon/e-posta/IBAN/adres/şifre/aile bilgileri vb.
- **Görsel maskeleme** — EasyOCR + AI; otomatik kutu önerisi + tarayıcı içi interaktif editör
- **Tarayıcı editörü** — kutu çizme, taşıma, 8 köşeden boyutlandırma, zoom, pan, undo/redo, mobil dokunmatik destek
- **3 sansür stili** — Gaussian Blur (şiddet ayarlanabilir), Pixelate, Siyah Bant
- **Hızlı** — `keep_alive` ile model RAM'de tutulur, ısındıktan sonra 2-3 sn yanıt süresi
- **Karşılaştırma scripti** — aynı metni 3 farklı modele gönderip F1 skorlarını ölçen `compare.py`
- **Docker uyumlu** — `OLLAMA_HOST` env değişkeni ile uzak/konteyner Ollama desteği

---

## Hızlı Başlangıç

> **🏠 Yerel kurulum varsayılanı = en yüksek doğruluk** (qwen2.5:14b + tam prompt → **F1 0.92**).
> Sunucu/Docker dağıtımı için daha küçük model + lite prompt env değişkenleriyle ayrı yapılandırılır
> (aşağıda Docker bölümü).

### Gereksinimler

| Bileşen | Sürüm | Notlar |
|---|---|---|
| Python | 3.10+ | sistem genelinde |
| RAM | 16 GB+ | qwen2.5:14b için (8 GB ile qwen2.5:7b kullanın) |
| Disk | ~10 GB | model indirimi |
| OS | Windows / macOS / Linux | hepsinde test edildi |

### 1. Ollama'yı kurun

[ollama.com/download](https://ollama.com/download) adresinden indirip kurun. Kurulduktan sonra arka planda otomatik servis verir (`http://127.0.0.1:11434`).

### 2. Modeli çekin

**Yerel kurulum varsayılanı** `qwen2.5:14b` (16 GB+ RAM gerekir, F1 0.92):

```bash
ollama pull qwen2.5:14b
```

Donanım yetmiyorsa alternatifler:

| Model | RAM | F1 | Yorum |
|---|---|---|---|
| `qwen2.5:14b` | 9 GB | **0.92** ★ | yerel varsayılan, en iyi denge |
| `qwen2.5:7b` | 4.7 GB | 0.52 | RAM kısıtlı sistemler — gri rolleri kaçırır |
| `qwen2.5:3b` | 2 GB | düşük | düşük kapasite sunucular (CPU-only Docker) |
| `gpt-oss-safeguard:20b` | 13 GB | 1.00 | en doğru, %30 yavaş |

Modeli değiştirmek için iki yol:

**a)** [`prompts.py`](prompts.py) → `MODEL_NAME = "qwen2.5:7b"` (tek satır)

**b)** Env değişkeni — kalıcı kod değişikliği yapmadan:
```bash
# Linux / macOS
MODEL_NAME=qwen2.5:7b python app.py

# Windows PowerShell
$env:MODEL_NAME = "qwen2.5:7b"; python app.py
```

### 3. Python bağımlılıkları

```bash
pip install -r requirements.txt
```

> **Not:** EasyOCR ilk import'ta OCR modellerini otomatik indirir (~100 MB).

### 4. Çalıştırın

```bash
python app.py
```

Tarayıcıda → [http://127.0.0.1:5000](http://127.0.0.1:5000)

İlk istek modeli RAM'e yüklerken **~6 sn**, sonraki istekler `keep_alive=30m` sayesinde **~2.3 sn**.

---

## Docker Compose Kurulumu (Sunucu Dağıtımı)

İki konteyner: biri Ollama, biri Flask uygulaması. Modeller `./ollama_data/` klasöründe **kalıcı** tutulur — konteyner silinse bile 9 GB'lık model tekrar indirilmez.

> **Donanıma göre iki örnek var.** RAM/CPU yeterliyse 14B'yi kullanın, kısıtlı VPS'lerde küçük model + lite prompt'a düşün.

### A) Güçlü sunucu — 14B + tam prompt (önerilen)

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    ports: ["11434:11434"]
    volumes:
      - ./ollama_data:/root/.ollama
    restart: unless-stopped

  app:
    build: .
    container_name: veri-maskeleme
    depends_on: [ollama]
    ports: ["5000:5000"]
    environment:
      OLLAMA_HOST: http://ollama:11434
      # MODEL_NAME ve PROMPT_MODE varsayılan: qwen2.5:14b + full
    restart: unless-stopped
```

```bash
docker compose up -d
docker exec -it ollama ollama pull qwen2.5:14b
```

### B) Kısıtlı VPS (CPU-only, < 16 GB RAM) — demo modu

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: textsansur_ollama
    ports: ["11434:11434"]
    volumes:
      - ./ollama_data:/root/.ollama
    restart: unless-stopped

  flask:
    build: .
    container_name: textsansur_flask
    depends_on: [ollama]
    ports: ["5000:5000"]
    environment:
      OLLAMA_HOST: http://ollama:11434
      MODEL_NAME: qwen2.5:3b      # küçük model
      PROMPT_MODE: lite           # sıkıştırılmış prompt
    restart: unless-stopped
```

```bash
docker compose up -d
docker exec -it textsansur_ollama ollama pull qwen2.5:3b
```

### Env değişkenleri özeti

| Değişken | Yerel default | Sunucu (demo) | Açıklama |
|---|---|---|---|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | `http://ollama:11434` | Ollama adresi |
| `MODEL_NAME` | `qwen2.5:14b` | `qwen2.5:3b` | LLM modeli |
| `PROMPT_MODE` | `full` | `lite` | Prompt boyutu (~3700 vs ~950 kr) |

---

## Mimari

```
Tarayici (Frontend)  -- Vanilla JS + Canvas API + Pointer Events
        |
        v  HTTP/JSON
Flask (app.py)       -- HTTP API katmani
   /api/censor-text  -> metin maskeleme
   /api/detect-image -> OCR + AI tespit
   /api/apply-blur   -> kutu uygulama
   /api/health       -> durum
        |
        +--> Ollama (qwen2.5:14b + prompts.py)
        +--> EasyOCR (Turkce + Ingilizce)
```

### Dosya yapisi

```
.
├── app.py              # Flask sunucusu + endpoint'ler
├── prompts.py          # AI prompt'u + MODEL_NAME (tek değiştirme noktası)
├── TextCensorAI.py     # Eski Tkinter kullanımı için korundu
├── ImageCensor.py      # OCR + AI image pipeline
├── compare.py          # 3 modeli kıyaslayan benchmark scripti
├── requirements.txt    # Python bağımlılıkları
├── templates/index.html
├── static/css/style.css
├── static/js/app.js
└── README.md
```

---

## Prompt Mimarisi (Kalp)

Bu projenin asıl değeri: **iki aşamalı + few-shot hibrit prompt**. İki versiyon vardır:

| Versiyon | Boyut | Kullanım | F1 |
|---|---|---|---|
| `build_prompt` (full) | ~3700 kr | YEREL (varsayılan) | **0.92** |
| `build_prompt_lite` | ~950 kr | Sunucu (CPU-only) | düşük |

`PROMPT_MODE` env değişkeniyle seçilir; varsayılan `full`. Yerel kurulumda hiçbir şey set etmeden tam prompt çalışır.

### Tam prompt — yerel kurulumda kullanılan versiyon

Aşağıdaki yapı [`prompts.py:build_prompt()`](prompts.py) içindedir; iki aşamalı + 4 few-shot örnekli:

```
ADIM 1 — ROL BELİRLE (zihninden geçir, JSON'a yazma)
═══════════════════════════════════════════════════════════
Metni KİM YAZDI? = "GÖNDERİCİ" (mağdur, şikayetçi, müşteri)
Metinde KİMDEN ŞİKAYET ediliyor? = "KARŞI TARAF"

GÖNDERİCİ sinyalleri: "ben", "kendim", "bana ait", "şikayetimi sunmak"…

KARŞI TARAF sinyalleri (MASKELENMEZ):
  • dolandırıcı, şüpheli, sanık, fail, sahtekâr
  • müşteri temsilcisi, satış uzmanı, broker, aracı
  • operasyon müdürü, çağrı merkezi
  • Karşı tarafa ait şirket isimleri ve onların IBAN/web/iletişim

KAMU REFERANSLARI (asla maskeleme):
  • Savcı, hâkim, müfettiş adları
  • Mersis, dava esas no, sicil, mahkeme dosya no
  • Kurum isimleri (BDDK, SPK, banka adı)

ADIM 2 — GÖNDERİCİ + AİLESİNİN HASSAS VERİLERİNİ TOPLA
═══════════════════════════════════════════════════════════
İlke: "Bu bilgi sızsa o kişi zarar görür mü?" → EVET ise hedef.
KAPSAMLI düşün; örnek kategoriler:
  • Ad, soyad, lakap
  • Kullanıcı adı / handle (örn: "ahmet_91", "@user")
  • Kimlik numaraları (TC, pasaport, ehliyet, vergi no)
  • İletişim (telefon, e-posta, sosyal medya)
  • Açık adres (mahalle/cadde/no), doğum tarihi/yeri
  • Finansal: IBAN, banka hesap, kart, kripto cüzdan
  • Yatırım/üyelik kodları (örn: "778-44-90251-EU")
  • Erişim: şifre, OTP, oturum tokenı
  • Aile / vekâlet altındaki kişiler
  • İş yeri telefonu / dahili — DAİMA maskele

GRİ ROLLER (avukat, danışman, banka temsilcisi):
  • GÖNDERİCİYE hizmet veriyorsa → maskele
  • Karşı tarafa hizmet veriyorsa → MASKELEME

  GÖNDERİCİYE HİZMET sinyalleri:
    • "Avukatım", "vekilim", "danışmanım", "temsilcim"
    • Bu kişilerin ofis adresi/tel/email DA gönderici tarafıdır

ÖRNEKLER (few-shot)
═══════════════════════════════════════════════════════════
[ÖRNEK 1] Metin: "Ben Ahmet, TC 11111111111. Beni Selim
adlı dolandırıcı 0555... aradı. Eşim Ayşe (0532...)..."
DOĞRU: {"gizlenecekler": ["Ahmet", "11111111111", "Ayşe", "0532..."]}

[ÖRNEK 2] Banka şikayeti — kurum çalışanı ASLA maskelenmez.
[ÖRNEK 3] Yapılandırılmış ID — sahiplenme ifadesiyle MASKELE.
[ÖRNEK 4] Avukat (gri rol, gönderici tarafı) — MASKELE.

ÇIKTI KURALLARI
═══════════════════════════════════════════════════════════
1. SADECE JSON dön. Açıklama yazma.
2. Anahtar: "gizlenecekler". Liste değer.
3. Bilgiyi metinde geçtiği gibi yaz.
4. Şüpheliyse listeden ÇIKAR (false positive maliyetlidir).
```

Tam metin ve few-shot örneklerinin gövdesi: [`prompts.py:build_prompt()`](prompts.py)

### Lite prompt — sunucu demo modunda kullanılan versiyon

Aynı mantık 4-5x sıkıştırılmış. Karşı IBAN/dolandırıcı vurgusu özet, tek örnekli.
Detay için [`prompts.py:build_prompt_lite()`](prompts.py).

---

## Model Performansı

`compare.py` ile aynı zorlu KVKK senaryosunda ölçülen sonuçlar:

| Model | İlk çağrı | Warm | F1 | Yorum |
|---|---|---|---|---|
| llama3 | 5 sn | ~1.5 sn | 0.71 | Hızlı ama gri rolleri kaçırır |
| qwen2.5:7b | 12 sn | ~3 sn | **0.52** | Dolandırıcıyı yanlışlıkla maskeler — riskli |
| **qwen2.5:14b** | 6.5 sn | **2.3 sn** | **0.92** | Hız + doğruluk dengesi (önerilen) |
| gpt-oss-safeguard:20b | 15 sn | ~6 sn | **1.00** | Mükemmel, %30 yavaş |

Kendi makinenizde test:

```bash
python compare.py
```

Çıktı: hem konsolda tablo, hem `comparison.html` (yan yana renkli karşılaştırma).

---

## Frontend Özellikleri

### Metin paneli

- Düzenlenebilir çıktı (model bir alan kaçırırsa elle ekleyebilirsiniz)
- Panoya kopyala / `.txt` indir
- Canlı maskeleme istatistikleri
- Örnek metin yükleyici

### Görsel editör

- Drag & drop, pano yapıştır (Ctrl+V), dosya seç
- AI önerdiği kutular otomatik gösterilir
- **Çiz tool**: boş alan + sürükle = yeni kutu; kutu üstünde tık = seç + taşı; köşeden = boyutlandır
- **El (pan) tool**: tek parmak/mouse sürükle = resmi kaydır
- **Silme**: sağ tık (mouse), uzun basma (mobil), seçili kutudaki kırmızı **×** butonu, `Del` tuşu
- **Zoom**: butonlar / `Ctrl+tekerlek` (mouse) / pinch (mobil) / `+` `-` `0`
- **Mobil tam destek**: Pointer Events, touch-action: none, pinch zoom, uzun basma
- 3 sansür stili: Blur / Pixelate / Siyah Bant

---

## Klavye Kısayolları

| Tuş | İşlem |
|---|---|
| `Ctrl + Enter` | Metni maskele |
| `Ctrl + Z` | Geri al |
| `Del` / `Backspace` | Seçili kutuyu sil |
| `Esc` | Seçimi kaldır |
| Ok tuşları | Seçili kutuyu 1 px taşı |
| `Shift + Ok` | 10 px taşı |
| `D` | Çiz moduna geç |
| `H` | El (pan) moduna geç |
| `Ctrl + Tekerlek` | Zoom (cursor altından) |
| `+` / `-` | Zoom in/out |
| `0` | Sığdır |

---

## Yapılandırma

### Env değişkenleri (en pratik)

```bash
MODEL_NAME=qwen2.5:14b      # varsayılan; sunucuda qwen2.5:3b
PROMPT_MODE=full            # varsayılan; sunucuda lite
OLLAMA_HOST=http://...      # varsayılan: http://127.0.0.1:11434
PORT=5000                   # Flask port
```

### Modeli koddan değiştir

[`prompts.py`](prompts.py)

```python
MODEL_NAME = os.environ.get("MODEL_NAME", "qwen2.5:14b")
# qwen2.5:14b (yerel) | qwen2.5:7b | qwen2.5:3b (demo) | gpt-oss-safeguard:20b
```

### Marka adı / başlık

[`app.py`](app.py)

```python
APP_NAME = "Veri Maskeleme"
APP_TAGLINE = "AI ile Akıllı Veri Maskeleme"
```

### Ollama adresi (Docker / uzak sunucu)

```bash
# Linux / macOS
OLLAMA_HOST=http://ollama:11434 python app.py

# Windows PowerShell
$env:OLLAMA_HOST = "http://ollama:11434"; python app.py
```

Varsayılan: `http://127.0.0.1:11434`

### Port

```bash
PORT=8000 python app.py
```

---

## Sorun Giderme

| Hata | Çözüm |
|---|---|
| `Ollama servisi çalışmıyor` | Terminal'de `ollama serve` çalıştırın. Docker'daysa `OLLAMA_HOST` doğru mu? |
| İlk istek 60+ sn | Model RAM'e yükleniyor; sonraki istekler 2-3 sn |
| `Model JSON döndürmedi` | Metni kısaltıp tekrar deneyin veya daha güçlü modele geçin |
| Frontend eski hâliyle açılıyor | `Cache-Control: no-store` eklendi; yine olursa Ctrl+F5 |
| EasyOCR donuyor | İlk import'ta model indiriyor; birkaç dakika bekleyin |
| Mobilde kutu çizemiyorum | Toolbar'da "Çiz" tool'u aktif olmalı (default) |

---

## Yol Haritası

- [ ] Toplu metin işleme (CSV/JSON girdi)
- [ ] PDF maskeleme (her sayfa için EasyOCR + tek dosya çıktı)
- [ ] Web arayüzünde "Karşılaştırma sekmesi"
- [ ] Browser uzantısı (sayfa metnini sağ tık → maskele)
- [ ] OCR sonuçlarını cache'leme
- [ ] CUDA otomatik tespit

---

## Katkıda Bulunma

PR'lar açıktır. Önce bir issue açıp tartışalım. Stil rehberi:

- Backend: PEP-8, fonksiyon başına `_ollama_censor` gibi açık isimler
- Frontend: vanilla JS, harici dependency yok
- Prompt değişiklikleri: önce `compare.py` ile F1 skorunu ölçün, regression yapmasın

---

## Lisans

MIT — istediğiniz gibi kullanabilirsiniz. KVKK uyumluluğu için kullanıyorsanız üretim öncesi kendi senaryolarınızda doğrulamayı unutmayın.

---

## Teşekkürler

- [Ollama](https://ollama.com) — yerel LLM çalıştırma
- [Alibaba Qwen](https://github.com/QwenLM/Qwen2.5) — model
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) — OCR motoru
- [OpenAI gpt-oss](https://huggingface.co/openai/gpt-oss-safeguard-20b) — alternatif model

---

**Geliştiren:** Cuma Doğan · 2026
