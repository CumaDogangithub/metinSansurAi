/* ===========================================================
   textSansur — frontend logic
   =========================================================== */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/* ----- Theme ----- */
const root = document.documentElement;
const savedTheme = localStorage.getItem("textsansur:theme");
if (savedTheme) root.setAttribute("data-theme", savedTheme);
$("#themeToggle").addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("textsansur:theme", next);
});

/* ----- Tabs ----- */
function showTab(name) {
    $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    $$(".panel").forEach((p) => (p.hidden = p.id !== `panel-${name}`));
}
$$(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
$$("[data-go]").forEach((b) => b.addEventListener("click", () => {
    showTab(b.dataset.go);
    $(`#panel-${b.dataset.go}`).scrollIntoView({ behavior: "smooth", block: "start" });
}));

/* ----- Toast ----- */
const toastEl = $("#toast");
let toastTimer;
function toast(msg, kind = "info") {
    clearTimeout(toastTimer);
    toastEl.textContent = msg;
    toastEl.className = `toast ${kind}`;
    toastEl.hidden = false;
    requestAnimationFrame(() => toastEl.classList.add("show"));
    toastTimer = setTimeout(() => {
        toastEl.classList.remove("show");
        setTimeout(() => (toastEl.hidden = true), 300);
    }, 2400);
}

/* ----- Loader ----- */
const loaderEl = $("#loader");
const loaderText = $("#loaderText");
const loaderSub = $("#loaderSub");
const cancelBtn = $("#cancelBtn");
let activeAbort = null;

function showLoader(msg = "İşleniyor…", sub = "Yapay zekâ yerelde çalışıyor, biraz sürebilir.") {
    loaderText.textContent = msg;
    loaderSub.textContent = sub;
    loaderEl.hidden = false;
}
function setLoaderStage(stage) {
    if (stage) loaderSub.textContent = stage;
}
function hideLoader() {
    loaderEl.hidden = true;
    activeAbort = null;
}
cancelBtn.addEventListener("click", () => {
    if (activeAbort) {
        activeAbort.abort();
        toast("İstek iptal edildi", "info");
    }
    hideLoader();
});

/* ----- Health / status polling ----- */
const statusPill = $("#statusPill");
const statusLabel = $("#statusLabel");
let lastHealth = null;

async function fetchHealth() {
    try {
        const r = await fetch("/api/health", { cache: "no-store" });
        if (!r.ok) throw 0;
        const data = await r.json();
        lastHealth = data;

        // Sağ üst durum etiketi
        if (!data.ollama_ready) {
            statusPill.className = "status-pill err";
            statusLabel.textContent = "Ollama kapalı";
        } else if (!data.text_ready || !data.image_ready) {
            statusPill.className = "status-pill";
            statusLabel.textContent = "Modeller yükleniyor…";
        } else {
            statusPill.className = "status-pill ok";
            statusLabel.textContent = `Hazır · ${data.model || "AI"}`;
        }

        // Aktif iş varsa loader alt mesajını güncelle
        if (data.current_job && !loaderEl.hidden) {
            setLoaderStage(data.current_job.stage);
        }
        return data;
    } catch {
        statusPill.className = "status-pill err";
        statusLabel.textContent = "Sunucu erişilemez";
        return null;
    }
}

fetchHealth();
setInterval(fetchHealth, 2500);

/* ===========================================================
   METIN
   =========================================================== */
const inputText = $("#inputText");
const inputMeta = $("#inputMeta");
const outputText = $("#outputText");
const censorBtn = $("#censorBtn");
const copyBtn = $("#copyBtn");
const downloadTxtBtn = $("#downloadTxtBtn");
const textStats = $("#textStats");
let lastCensored = "";

const MAX_INPUT_CHARS = 1500;

function updateInputMeta() {
    const t = inputText.value;
    const len = t.length;
    const words = t.trim() ? t.trim().split(/\s+/).length : 0;
    inputMeta.textContent = `${len.toLocaleString("tr-TR")} / ${MAX_INPUT_CHARS} karakter · ${words} kelime`;
    // Eşiklere göre renklendir
    inputMeta.classList.remove("warn", "danger");
    if (len >= MAX_INPUT_CHARS) inputMeta.classList.add("danger");
    else if (len >= MAX_INPUT_CHARS * 0.85) inputMeta.classList.add("warn");
}
inputText.addEventListener("input", updateInputMeta);
// Yapıştırma sırasında limit aşılırsa kullanıcıya bildir
inputText.addEventListener("paste", (e) => {
    const pasted = (e.clipboardData || window.clipboardData).getData("text") || "";
    const newLen = inputText.value.length - (inputText.selectionEnd - inputText.selectionStart) + pasted.length;
    if (newLen > MAX_INPUT_CHARS) {
        // Tarayıcı maxlength'i otomatik kırpar; sadece uyarı verelim
        toast(`Metin ${MAX_INPUT_CHARS} karaktere kırpıldı`, "info");
    }
});
updateInputMeta();

function highlightMasked(text) {
    // Yıldız içeren kelime gruplarını <mark> ile sar
    const escaped = text.replace(/[<>&]/g, (m) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[m]));
    return escaped.replace(/(\S*\*+\S*(?:\s+\S*\*+\S*)*)/g, (m) => `<mark>${m}</mark>`);
}

function countMasked(text) {
    const m = text.match(/\S*\*+\S*/g);
    return m ? m.length : 0;
}

async function censorText() {
    const text = inputText.value.trim();
    if (!text) { toast("Önce bir metin girin", "err"); return; }
    showLoader("Yapay zekâ analiz ediyor…", "İlk istek 30sn'ye kadar sürebilir (model yükleniyor).");
    censorBtn.disabled = true;
    activeAbort = new AbortController();
    // 120 sn'lik otomatik timeout
    const tmId = setTimeout(() => activeAbort.abort(), 120000);
    try {
        const r = await fetch("/api/censor-text", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
            signal: activeAbort.signal,
        });
        const data = await r.json();
        if (!data.ok) throw new Error(data.error || "Sunucu hatası");
        if (typeof data.censored !== "string") {
            throw new Error("Yanıt 'censored' alanı eksik");
        }
        lastCensored = data.censored;
        outputText.classList.remove("placeholder");
        outputText.contentEditable = "true";
        outputText.innerHTML = highlightMasked(data.censored);
        copyBtn.disabled = false;
        downloadTxtBtn.disabled = false;
        textStats.hidden = false;
        const maskedCount = countMasked(data.censored);
        const detected = data.stats?.detected_count ?? maskedCount;
        $("#statMasked").textContent = maskedCount;
        $("#statChars").textContent = (data.stats?.char_count ?? 0).toLocaleString("tr-TR");
        $("#statTime").textContent = data.stats?.elapsed_ms ?? 0;

        // Kullanıcıya net geri bildirim
        if (detected === 0) {
            toast("AI hassas alan tespit etmedi — metni kontrol et", "info");
        } else if (data.no_match && data.no_match.length) {
            toast(`Uyarı: ${data.no_match.length} alan eşleşmedi (model normalize etti)`, "info");
        } else {
            toast(`Tamam — ${maskedCount} alan maskelendi`, "ok");
        }
    } catch (e) {
        if (e.name === "AbortError") {
            toast("İstek 120 sn içinde tamamlanmadı — daha küçük bir model deneyin", "err");
        } else {
            toast(`Hata: ${e.message}`, "err");
        }
    } finally {
        clearTimeout(tmId);
        hideLoader();
        censorBtn.disabled = false;
    }
}

// İstatistikleri kullanıcı çıktıyı düzenledikçe güncelle
function refreshOutputStats() {
    const txt = outputText.innerText;
    $("#statMasked").textContent = countMasked(txt);
    $("#statChars").textContent = txt.length.toLocaleString("tr-TR");
}
outputText.addEventListener("input", refreshOutputStats);

censorBtn.addEventListener("click", censorText);
inputText.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); censorText(); }
});

async function copyOutput() {
    const txt = (outputText.innerText || "").trim();
    if (!txt) { toast("Kopyalanacak metin yok", "err"); return; }
    try {
        await navigator.clipboard.writeText(txt);
        toast("Panoya kopyalandı", "ok");
    } catch (e) {
        // Eski tarayıcı / izin yoksa execCommand fallback
        const ta = document.createElement("textarea");
        ta.value = txt;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); toast("Panoya kopyalandı", "ok"); }
        catch { toast("Tarayıcı kopyalamayı engelledi", "err"); }
        document.body.removeChild(ta);
    }
}
copyBtn.addEventListener("click", copyOutput);

downloadTxtBtn.addEventListener("click", () => {
    const txt = (outputText.innerText || "").trim();
    if (!txt) return;
    const blob = new Blob([txt], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `maskelenmis-${Date.now()}.txt`;
    a.click(); URL.revokeObjectURL(url);
});

$("#clearTextBtn").addEventListener("click", () => {
    inputText.value = "";
    outputText.innerHTML = "Burada maskelenmiş hâli görünecek…";
    outputText.classList.add("placeholder");
    outputText.contentEditable = "false";
    copyBtn.disabled = true;
    downloadTxtBtn.disabled = true;
    textStats.hidden = true;
    lastCensored = "";
    updateInputMeta();
});

$("#loadSampleBtn").addEventListener("click", async () => {
    try {
        const r = await fetch("/api/sample-text");
        const data = await r.json();
        if (!data.ok || !data.samples?.length) return;
        const sample = data.samples[Math.floor(Math.random() * data.samples.length)];
        inputText.value = sample.text;
        updateInputMeta();
        toast(`Yüklendi: ${sample.title}`, "info");
        inputText.focus();
    } catch { toast("Örnek alınamadı", "err"); }
});

/* ===========================================================
   GÖRSEL EDITÖR (Tkinter BlurEditor → Canvas)
   =========================================================== */
const dropzone = $("#dropzone");
const fileInput = $("#fileInput");
const editorWrap = $("#editorWrap");
const canvas = $("#editorCanvas");
const ctx = canvas.getContext("2d");
const stage = $("#editorStage");
const styleSelect = $("#styleSelect");
const blurRange = $("#blurRange");
const blurVal = $("#blurVal");
const boxesMeta = $("#boxesMeta");
const aiMeta = $("#aiMeta");
const blurStrengthWrap = $("#blurStrengthWrap");

const state = {
    image: null,        // HTMLImageElement (orijinal)
    imageDataUrl: null, // backend'e gönderilecek
    naturalW: 0,
    naturalH: 0,
    fitScale: 1,        // ekrana sığdırma ölçeği
    zoom: 1,            // kullanıcı zoom çarpanı
    boxes: [],          // {x1,y1,x2,y2} — gerçek piksel koordinatları (zoom'dan etkilenmez)
    aiBoxes: [],        // başlangıçtaki AI önerileri (reset için)
    drag: null,         // çizim sırasında geçici kutu (gerçek piksel koordinat)
    history: [],
    selected: null,     // seçili kutunun index'i
    action: null,       // 'draw' | 'move' | 'resize' | 'pan' | null
    resizeDir: null,    // 'nw'|'n'|'ne'|'e'|'se'|'s'|'sw'|'w'
    dragOrigin: null,   // {x, y, box: {...}}
    tool: "draw",       // 'draw' | 'pan'
};

function setTool(t) {
    state.tool = t;
    $$(".tool[data-tool]").forEach((b) => b.classList.toggle("active", b.dataset.tool === t));
    if (canvas) canvas.style.cursor = (t === "pan") ? "grab" : "crosshair";
}

// CSS scale = fitScale * zoom (canvas'ın görüntü oranı)
function displayScale() { return state.fitScale * state.zoom; }

// ---- Helpers: kutu normalizasyonu ve tutamak (handle) ölçütleri ----
const HANDLE_SIZE = 9;   // ekran-pikseli (kare boyutu)
const HANDLE_HIT = 12;   // ekran-pikseli (tıklama hassasiyeti)

function normBox(b) {
    return {
        x1: Math.min(b.x1, b.x2),
        y1: Math.min(b.y1, b.y2),
        x2: Math.max(b.x1, b.x2),
        y2: Math.max(b.y1, b.y2),
    };
}

function getHandles(b) {
    const n = normBox(b);
    const cx = (n.x1 + n.x2) / 2;
    const cy = (n.y1 + n.y2) / 2;
    return [
        { dir: "nw", x: n.x1, y: n.y1, cursor: "nwse-resize" },
        { dir: "n",  x: cx,   y: n.y1, cursor: "ns-resize"   },
        { dir: "ne", x: n.x2, y: n.y1, cursor: "nesw-resize" },
        { dir: "e",  x: n.x2, y: cy,   cursor: "ew-resize"   },
        { dir: "se", x: n.x2, y: n.y2, cursor: "nwse-resize" },
        { dir: "s",  x: cx,   y: n.y2, cursor: "ns-resize"   },
        { dir: "sw", x: n.x1, y: n.y2, cursor: "nesw-resize" },
        { dir: "w",  x: n.x1, y: cy,   cursor: "ew-resize"   },
    ];
}

function hitHandle(b, x, y) {
    const r = HANDLE_HIT / displayScale();
    for (const h of getHandles(b)) {
        if (Math.abs(x - h.x) <= r && Math.abs(y - h.y) <= r) return h;
    }
    return null;
}

// Seçili kutu için silme (×) butonu — kutunun sağ-üst köşesinin DIŞINDA üst tarafta
const DELETE_BTN_SIZE = 22;     // ekran-pikseli (görünür yarıçap*2)
const DELETE_BTN_GAP = 6;       // ekran-pikseli (kutu üst kenarına olan boşluk)

function deleteButtonCenter(b) {
    const n = normBox(b);
    const s = displayScale();
    const sz = DELETE_BTN_SIZE / s;
    const gap = DELETE_BTN_GAP / s;
    return {
        cx: n.x2 - sz / 2,           // sağ kenara hizalı (yarısı içeride yarısı dışarıda hissi)
        cy: n.y1 - gap - sz / 2,     // üst kenardan yukarı, gap kadar uzakta
        r: sz / 2,
    };
}

function hitDeleteButton(b, x, y) {
    const c = deleteButtonCenter(b);
    return Math.hypot(x - c.cx, y - c.cy) <= c.r + 2 / displayScale();
}

function pushHistory() {
    state.history.push(JSON.stringify(state.boxes));
    if (state.history.length > 50) state.history.shift();
}
function popHistory() {
    if (!state.history.length) return;
    state.boxes = JSON.parse(state.history.pop());
    if (state.selected !== null && state.selected >= state.boxes.length) {
        state.selected = null;
    }
    redraw(); updateBoxesMeta();
}

styleSelect.addEventListener("change", () => {
    blurStrengthWrap.style.display = styleSelect.value === "blur" ? "" : "none";
});

blurRange.addEventListener("input", () => { blurVal.textContent = blurRange.value; });

/* ----- Drag & drop ----- */
$("#pickFileBtn").addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); });

["dragenter", "dragover"].forEach((ev) => dropzone.addEventListener(ev, (e) => {
    e.preventDefault(); dropzone.classList.add("drag");
}));
["dragleave", "drop"].forEach((ev) => dropzone.addEventListener(ev, (e) => {
    e.preventDefault(); dropzone.classList.remove("drag");
}));
dropzone.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
});

// Yapıştırma desteği
window.addEventListener("paste", (e) => {
    if ($("#panel-image").hidden) return;
    const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
    if (item) {
        const f = item.getAsFile();
        if (f) handleFile(f);
    }
});

async function handleFile(file) {
    if (!file.type.startsWith("image/")) { toast("Sadece resim dosyası", "err"); return; }
    if (file.size > 16 * 1024 * 1024) { toast("Dosya 16MB'dan büyük", "err"); return; }

    const sub = lastHealth && !lastHealth.image_ready
        ? "OCR motoru ilk kez yükleniyor — 30-90 sn sürebilir."
        : "OCR + AI çalışıyor…";
    showLoader("Resim işleniyor…", sub);
    const fd = new FormData();
    fd.append("image", file);
    activeAbort = new AbortController();
    try {
        const r = await fetch("/api/detect-image", {
            method: "POST", body: fd, signal: activeAbort.signal,
        });
        const data = await r.json();
        if (!data.ok) throw new Error(data.error || "Hata");
        await loadImage(data.image, data.boxes, data);
        toast(`${data.boxes.length} hassas alan bulundu`, "ok");
    } catch (e) {
        if (e.name !== "AbortError") toast(`Hata: ${e.message}`, "err");
    } finally {
        hideLoader();
    }
}

function loadImage(dataUrl, boxes, payload) {
    return new Promise((res) => {
        const img = new Image();
        img.onload = () => {
            state.image = img;
            state.imageDataUrl = dataUrl;
            state.naturalW = img.naturalWidth;
            state.naturalH = img.naturalHeight;
            state.boxes = boxes.map((b) => ({ x1: b.x1, y1: b.y1, x2: b.x2, y2: b.y2 }));
            state.aiBoxes = JSON.parse(JSON.stringify(state.boxes));
            state.history = [];
            state.zoom = 1;
            state.selected = null;

            canvas.width = state.naturalW;
            canvas.height = state.naturalH;

            $("#dropzone").hidden = true;
            editorWrap.hidden = false;
            $("#resultCard").hidden = true;

            // İlk fit
            fitToStage();
            redraw();
            updateBoxesMeta();
            aiMeta.textContent = `${(payload.detected_words || []).length} OCR · ${(payload.ai_targets || []).length} AI hedefi`;
            res();
        };
        img.src = dataUrl;
    });
}

function fitToStage() {
    const maxW = stage.clientWidth - 32;
    const maxH = window.innerHeight * 0.6;
    state.fitScale = Math.min(maxW / state.naturalW, maxH / state.naturalH, 1);
    state.zoom = 1;
    applyDisplaySize();
}

function applyDisplaySize() {
    const s = displayScale();
    canvas.style.width = `${state.naturalW * s}px`;
    canvas.style.height = `${state.naturalH * s}px`;
    const lbl = $("#zoomLabel");
    if (lbl) lbl.textContent = `${Math.round(state.zoom * 100)}%`;
}

function redraw() {
    if (!state.image) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(state.image, 0, 0);
    state.boxes.forEach((b, i) => drawBox(b, i));
    if (state.drag) drawBox(state.drag, -1, true);
}

function drawBox(b, idx, ghost = false) {
    const n = normBox(b);
    const x = n.x1, y = n.y1;
    const w = n.x2 - n.x1, h = n.y2 - n.y1;
    const s = displayScale();
    const isSelected = !ghost && idx === state.selected;
    ctx.save();

    ctx.fillStyle = ghost ? "rgba(16, 185, 129, 0.20)" : "rgba(16, 185, 129, 0.18)";
    ctx.fillRect(x, y, w, h);

    if (isSelected) {
        ctx.strokeStyle = "#0ea5e9";
        ctx.lineWidth = Math.max(2, 2.5 / s);
        ctx.setLineDash([]);
    } else {
        ctx.strokeStyle = ghost ? "#0ea5e9" : "#10b981";
        ctx.lineWidth = Math.max(1.5, 2 / s);
        ctx.setLineDash(ghost ? [8 / s, 6 / s] : []);
    }
    ctx.strokeRect(x, y, w, h);

    if (!ghost && idx >= 0) {
        const fs = 10 / s;
        const pad = 3 / s;
        ctx.font = `600 ${fs}px Inter, sans-serif`;
        const label = `${idx + 1}`;
        const tw = ctx.measureText(label).width + pad * 2;
        const th = fs + pad * 1.6;
        ctx.setLineDash([]);
        ctx.fillStyle = isSelected ? "#0ea5e9" : "#10b981";
        ctx.fillRect(x, y, tw, th);
        ctx.fillStyle = "white";
        ctx.textBaseline = "top";
        ctx.fillText(label, x + pad, y + pad / 2);
    }

    // Seçili kutu için 8 tutamak çiz
    if (isSelected) {
        const hs = HANDLE_SIZE / s;
        ctx.fillStyle = "#0ea5e9";
        ctx.strokeStyle = "white";
        ctx.lineWidth = Math.max(1, 1.5 / s);
        ctx.setLineDash([]);
        for (const hh of getHandles(b)) {
            ctx.fillRect(hh.x - hs / 2, hh.y - hs / 2, hs, hs);
            ctx.strokeRect(hh.x - hs / 2, hh.y - hs / 2, hs, hs);
        }

        // × silme butonu: kırmızı daire + beyaz çapraz işaret
        const c = deleteButtonCenter(b);
        ctx.setLineDash([]);
        // gölge
        ctx.shadowColor = "rgba(0, 0, 0, 0.35)";
        ctx.shadowBlur = 8 / s;
        ctx.shadowOffsetY = 1 / s;
        // kırmızı daire
        ctx.fillStyle = "#ef4444";
        ctx.beginPath();
        ctx.arc(c.cx, c.cy, c.r, 0, Math.PI * 2);
        ctx.fill();
        // beyaz çevre
        ctx.shadowColor = "transparent";
        ctx.strokeStyle = "white";
        ctx.lineWidth = Math.max(1.5, 2 / s);
        ctx.stroke();
        // × işareti
        const cross = c.r * 0.42;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(c.cx - cross, c.cy - cross);
        ctx.lineTo(c.cx + cross, c.cy + cross);
        ctx.moveTo(c.cx + cross, c.cy - cross);
        ctx.lineTo(c.cx - cross, c.cy + cross);
        ctx.stroke();
    }
    ctx.restore();
}

/* ----- Canvas -> gerçek piksel koordinat dönüşümü ----- */
function canvasPos(e) {
    const r = canvas.getBoundingClientRect();
    return {
        x: ((e.clientX - r.left) / r.width) * canvas.width,
        y: ((e.clientY - r.top) / r.height) * canvas.height,
    };
}

function findBoxAt(x, y) {
    // sondan başla (üstte olan kutu önce)
    for (let i = state.boxes.length - 1; i >= 0; i--) {
        const b = state.boxes[i];
        const x1 = Math.min(b.x1, b.x2), x2 = Math.max(b.x1, b.x2);
        const y1 = Math.min(b.y1, b.y2), y2 = Math.max(b.y1, b.y2);
        if (x >= x1 && x <= x2 && y >= y1 && y <= y2) return i;
    }
    return -1;
}

/* ====== Pointer / Touch destekli editör ======
   Tek pointer → çiz / taşı / boyutlandır
   İki pointer → pinch zoom
   Uzun basma (≥500ms hareketsiz) → kutu silme (sağ tık eşdeğeri) */

let pointerDown = false;
const activePointers = new Map();   // id → {x, y, clientX, clientY}
let pinchMode = false;
let pinchStart = { dist: 0, zoom: 1, cx: 0, cy: 0 };
let longPressTimer = null;
const LONG_PRESS_MS = 500;
const LONG_PRESS_TOLERANCE = 8;     // canvas-piksel; bu mesafe altındaki hareket "hareketsiz"

function clearLongPress() {
    if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null; }
}

function pinchDistance() {
    const pts = [...activePointers.values()];
    if (pts.length < 2) return 0;
    const dx = pts[0].clientX - pts[1].clientX;
    const dy = pts[0].clientY - pts[1].clientY;
    return Math.hypot(dx, dy);
}

function pinchCenter() {
    const pts = [...activePointers.values()];
    const sr = stage.getBoundingClientRect();
    return {
        x: ((pts[0].clientX + pts[1].clientX) / 2) - sr.left,
        y: ((pts[0].clientY + pts[1].clientY) / 2) - sr.top,
    };
}

canvas.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 && e.button !== undefined && e.pointerType === "mouse") return;
    e.preventDefault();
    canvas.setPointerCapture(e.pointerId);
    activePointers.set(e.pointerId, {
        x: 0, y: 0, clientX: e.clientX, clientY: e.clientY,
    });

    // İkinci parmak geldiyse → pinch zoom moduna geç
    if (activePointers.size === 2) {
        clearLongPress();
        // Aktif çizimi/taşımayı iptal et
        if (state.action === "draw" && state.drag) {
            state.drag = null;
        }
        state.action = null;
        state.dragOrigin = null;
        pinchMode = true;
        pinchStart.dist = pinchDistance();
        pinchStart.zoom = state.zoom;
        const c = pinchCenter();
        pinchStart.cx = c.x;
        pinchStart.cy = c.y;
        redraw();
        return;
    }

    if (activePointers.size > 2) return;  // 3+ parmak yoksay

    pointerDown = true;
    const { x, y } = canvasPos(e);

    // 0) Pan modu (El tool aktif): tek parmakla resmi kaydır
    if (state.tool === "pan") {
        state.action = "pan";
        state.dragOrigin = {
            clientX: e.clientX,
            clientY: e.clientY,
            scrollLeft: stage.scrollLeft,
            scrollTop: stage.scrollTop,
        };
        canvas.style.cursor = "grabbing";
        return;
    }

    // 1) Seçili kutunun × silme butonuna bastı mı?
    if (state.selected !== null && state.boxes[state.selected]) {
        if (hitDeleteButton(state.boxes[state.selected], x, y)) {
            pushHistory();
            const idx = state.selected;
            state.boxes.splice(idx, 1);
            state.selected = null;
            pointerDown = false;
            state.action = null;
            redraw(); updateBoxesMeta();
            toast("Kutu silindi", "info");
            return;
        }
    }

    // 2) Seçili kutunun resize handle'ına bastı mı?
    if (state.selected !== null && state.boxes[state.selected]) {
        const h = hitHandle(state.boxes[state.selected], x, y);
        if (h) {
            pushHistory();
            state.action = "resize";
            state.resizeDir = h.dir;
            state.dragOrigin = { x, y, box: { ...state.boxes[state.selected] } };
            return;
        }
    }

    // 3) Bir kutu üzerinde mi? → seç + taşımaya başla + uzun basma → silme
    const idx = findBoxAt(x, y);
    if (idx >= 0) {
        if (state.selected !== idx) {
            state.selected = idx;
            redraw();
        }
        pushHistory();
        state.action = "move";
        state.dragOrigin = { x, y, box: { ...state.boxes[idx] }, startX: x, startY: y };

        // Uzun basma: hareketsizse kutuyu sil (mobilde sağ tık yerine)
        clearLongPress();
        longPressTimer = setTimeout(() => {
            const dragged = state.dragOrigin && (
                Math.abs(state.dragOrigin.box.x1 - state.boxes[idx]?.x1) > LONG_PRESS_TOLERANCE ||
                Math.abs(state.dragOrigin.box.y1 - state.boxes[idx]?.y1) > LONG_PRESS_TOLERANCE
            );
            if (!dragged && state.boxes[idx]) {
                state.boxes.splice(idx, 1);
                if (state.selected === idx) state.selected = null;
                else if (state.selected !== null && state.selected > idx) state.selected--;
                pointerDown = false;
                state.action = null;
                state.dragOrigin = null;
                redraw(); updateBoxesMeta();
                toast("Kutu silindi (uzun basma)", "info");
            }
        }, LONG_PRESS_MS);
        return;
    }

    // 3) Boş alana tıklandı → seçimi kaldır + yeni kutu çizmeye başla
    state.selected = null;
    state.action = "draw";
    state.drag = { x1: x, y1: y, x2: x, y2: y };
    redraw();
});

canvas.addEventListener("pointermove", (e) => {
    if (activePointers.has(e.pointerId)) {
        const p = activePointers.get(e.pointerId);
        p.clientX = e.clientX;
        p.clientY = e.clientY;
    }

    // Pinch zoom — iki parmak hareketi
    if (pinchMode && activePointers.size === 2) {
        const dist = pinchDistance();
        if (dist > 0 && pinchStart.dist > 0) {
            const factor = dist / pinchStart.dist;
            setZoom(pinchStart.zoom * factor, pinchStart.cx, pinchStart.cy);
        }
        return;
    }

    // Pan: tek parmakla resmi kaydır
    if (state.action === "pan" && state.dragOrigin) {
        const dx = e.clientX - state.dragOrigin.clientX;
        const dy = e.clientY - state.dragOrigin.clientY;
        stage.scrollLeft = state.dragOrigin.scrollLeft - dx;
        stage.scrollTop = state.dragOrigin.scrollTop - dy;
        return;
    }

    const { x, y } = canvasPos(e);

    // Hover cursor (yalnızca mouse'ta — touch'ta hover yok)
    if (!pointerDown) {
        if (e.pointerType !== "mouse") return;
        if (state.tool === "pan") { canvas.style.cursor = "grab"; return; }
        let cur = "crosshair";
        if (state.selected !== null && state.boxes[state.selected]) {
            // Önce silme butonu, sonra resize handle
            if (hitDeleteButton(state.boxes[state.selected], x, y)) cur = "pointer";
            else {
                const h = hitHandle(state.boxes[state.selected], x, y);
                if (h) cur = h.cursor;
            }
        }
        if (cur === "crosshair") {
            const idx = findBoxAt(x, y);
            if (idx >= 0) cur = "move";
        }
        canvas.style.cursor = cur;
        return;
    }

    // Hareket başladıysa long-press iptal
    if (longPressTimer && state.dragOrigin) {
        const dx = Math.abs(x - (state.dragOrigin.startX ?? state.dragOrigin.x));
        const dy = Math.abs(y - (state.dragOrigin.startY ?? state.dragOrigin.y));
        if (dx > LONG_PRESS_TOLERANCE || dy > LONG_PRESS_TOLERANCE) clearLongPress();
    }

    if (state.action === "draw" && state.drag) {
        state.drag.x2 = x; state.drag.y2 = y;
        redraw();
    } else if (state.action === "move" && state.dragOrigin) {
        const dx = x - state.dragOrigin.x;
        const dy = y - state.dragOrigin.y;
        const o = state.dragOrigin.box;
        state.boxes[state.selected] = {
            x1: o.x1 + dx, y1: o.y1 + dy,
            x2: o.x2 + dx, y2: o.y2 + dy,
        };
        redraw();
    } else if (state.action === "resize" && state.dragOrigin) {
        const o = normBox(state.dragOrigin.box);
        let nx1 = o.x1, ny1 = o.y1, nx2 = o.x2, ny2 = o.y2;
        const d = state.resizeDir;
        if (d.includes("w")) nx1 = x;
        if (d.includes("e")) nx2 = x;
        if (d.includes("n")) ny1 = y;
        if (d.includes("s")) ny2 = y;
        state.boxes[state.selected] = { x1: nx1, y1: ny1, x2: nx2, y2: ny2 };
        redraw();
    }
});

function endPointer(e) {
    if (e && e.pointerId !== undefined) activePointers.delete(e.pointerId);
    clearLongPress();

    // Pinch'ten çıkış: 1 veya 0 pointer kalmış
    if (pinchMode && activePointers.size < 2) {
        pinchMode = false;
        pointerDown = false;
        return;
    }

    if (!pointerDown) return;
    pointerDown = false;

    if (state.action === "draw" && state.drag) {
        const w = Math.abs(state.drag.x2 - state.drag.x1);
        const h = Math.abs(state.drag.y2 - state.drag.y1);
        if (w > 5 && h > 5) {
            pushHistory();
            state.boxes.push({ ...state.drag });
            state.selected = state.boxes.length - 1;
            updateBoxesMeta();
        }
        state.drag = null;
    } else if (state.action === "move" || state.action === "resize") {
        if (state.selected !== null && state.boxes[state.selected]) {
            state.boxes[state.selected] = normBox(state.boxes[state.selected]);
        }
    } else if (state.action === "pan") {
        canvas.style.cursor = state.tool === "pan" ? "grab" : "crosshair";
    }
    state.action = null;
    state.dragOrigin = null;
    state.resizeDir = null;
    redraw();
}

canvas.addEventListener("pointerup", endPointer);
canvas.addEventListener("pointercancel", endPointer);
canvas.addEventListener("pointerleave", (e) => {
    // Sadece mouse leave için drag'i bitir (touch'ta leave doğal davranış)
    if (e.pointerType === "mouse") endPointer(e);
});

// Sağ tık (mouse) → kutu sil. Mobilde uzun basma aynı işi yapıyor.
canvas.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    const { x, y } = canvasPos(e);
    const idx = findBoxAt(x, y);
    if (idx >= 0) {
        pushHistory();
        state.boxes.splice(idx, 1);
        if (state.selected === idx) state.selected = null;
        else if (state.selected !== null && state.selected > idx) state.selected--;
        redraw(); updateBoxesMeta();
        toast("Kutu silindi", "info");
    }
});

function updateBoxesMeta() {
    const n = state.boxes.length;
    boxesMeta.textContent = `${n} kutu`;
}

/* ----- Zoom ----- */
function setZoom(newZoom, centerX, centerY) {
    const old = state.zoom;
    newZoom = Math.max(0.2, Math.min(8, newZoom));
    if (newZoom === old) return;

    // Zoom merkezi belirtilmemişse stage'in görünür merkezi
    const sr = stage.getBoundingClientRect();
    if (centerX == null) centerX = sr.width / 2;
    if (centerY == null) centerY = sr.height / 2;

    // Zoom öncesi cursor altındaki canvas-piksel koordinatı
    const beforeX = stage.scrollLeft + centerX;
    const beforeY = stage.scrollTop + centerY;
    const ratio = newZoom / old;

    state.zoom = newZoom;
    applyDisplaySize();
    redraw();

    // Cursor altındaki noktayı sabit tut: scroll ayarla
    stage.scrollLeft = beforeX * ratio - centerX;
    stage.scrollTop = beforeY * ratio - centerY;
}

$("#zoomInBtn").addEventListener("click", () => setZoom(state.zoom * 1.25));
$("#zoomOutBtn").addEventListener("click", () => setZoom(state.zoom * 0.8));
$("#zoomFitBtn").addEventListener("click", () => { fitToStage(); redraw(); });

canvas.addEventListener("wheel", (e) => {
    if (!e.ctrlKey) return;          // sadece Ctrl + tekerlek (sayfa kaydırmaya engel olmasın)
    e.preventDefault();
    const sr = stage.getBoundingClientRect();
    const cx = e.clientX - sr.left;
    const cy = e.clientY - sr.top;
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    setZoom(state.zoom * factor, cx, cy);
}, { passive: false });

// Pencere yeniden boyutlandığında fit'i koru (yalnızca kullanıcı zoom yapmamışsa)
window.addEventListener("resize", () => {
    if (state.image && Math.abs(state.zoom - 1) < 0.01) {
        fitToStage();
        redraw();
    }
});

$("#undoBtn").addEventListener("click", popHistory);
$("#clearBoxesBtn").addEventListener("click", () => {
    if (!state.boxes.length) return;
    pushHistory();
    state.boxes = [];
    state.selected = null;
    redraw(); updateBoxesMeta();
});
$("#resetBtn").addEventListener("click", () => {
    pushHistory();
    state.boxes = JSON.parse(JSON.stringify(state.aiBoxes));
    state.selected = null;
    redraw(); updateBoxesMeta();
    toast("AI önerileri geri yüklendi", "info");
});

/* ----- Apply blur ----- */
$("#applyBtn").addEventListener("click", async () => {
    if (!state.image) return;
    showLoader("Maske uygulanıyor…", "Görsel işleme tamamen yerel; birkaç saniye sürer.");
    activeAbort = new AbortController();
    try {
        const r = await fetch("/api/apply-blur", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                image: state.imageDataUrl,
                boxes: state.boxes,
                blur: parseInt(blurRange.value, 10),
                style: styleSelect.value,
            }),
            signal: activeAbort.signal,
        });
        const data = await r.json();
        if (!data.ok) throw new Error(data.error || "Hata");
        $("#resultImg").src = data.image;
        $("#resultImg").dataset.url = data.image;
        $("#resultCard").hidden = false;
        $("#resultCard").scrollIntoView({ behavior: "smooth", block: "start" });
        toast("Maske uygulandı", "ok");
    } catch (e) {
        if (e.name !== "AbortError") toast(`Hata: ${e.message}`, "err");
    } finally {
        hideLoader();
    }
});

$("#downloadImgBtn").addEventListener("click", () => {
    const url = $("#resultImg").dataset.url;
    if (!url) return;
    const a = document.createElement("a");
    a.href = url; a.download = `maskelenmis-${Date.now()}.png`;
    a.click();
});

$("#newImgBtn").addEventListener("click", () => {
    state.image = null;
    state.boxes = [];
    state.aiBoxes = [];
    state.history = [];
    fileInput.value = "";
    editorWrap.hidden = true;
    $("#resultCard").hidden = true;
    $("#dropzone").hidden = false;
});

/* ----- Tool butonları (Çiz/El) ----- */
$$(".tool[data-tool]").forEach((b) => {
    b.addEventListener("click", () => setTool(b.dataset.tool));
});

/* ----- Klavye kısayolları ----- */
window.addEventListener("keydown", (e) => {
    if ($("#panel-image").hidden) return;
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
    if ((e.ctrlKey || e.metaKey) && e.key === "z") { e.preventDefault(); popHistory(); return; }
    if (e.key === "+" || e.key === "=") { e.preventDefault(); setZoom(state.zoom * 1.25); return; }
    if (e.key === "-" || e.key === "_") { e.preventDefault(); setZoom(state.zoom * 0.8); return; }
    if (e.key === "0") { e.preventDefault(); fitToStage(); redraw(); return; }
    if (e.key === "d" || e.key === "D") { e.preventDefault(); setTool("draw"); return; }
    if (e.key === "h" || e.key === "H") { e.preventDefault(); setTool("pan"); return; }
    if (e.key === "Delete" || e.key === "Backspace") {
        if (state.selected !== null && state.boxes[state.selected]) {
            e.preventDefault();
            pushHistory();
            state.boxes.splice(state.selected, 1);
            state.selected = null;
            redraw(); updateBoxesMeta();
            toast("Seçili kutu silindi", "info");
        }
        return;
    }
    if (e.key === "Escape") {
        if (state.selected !== null) { state.selected = null; redraw(); }
        return;
    }
    // Ok tuşları → seçili kutuyu 1 piksel kaydır (Shift ile 10 piksel)
    if (state.selected !== null && state.boxes[state.selected]) {
        const step = e.shiftKey ? 10 : 1;
        let dx = 0, dy = 0;
        if (e.key === "ArrowLeft") dx = -step;
        if (e.key === "ArrowRight") dx = step;
        if (e.key === "ArrowUp") dy = -step;
        if (e.key === "ArrowDown") dy = step;
        if (dx || dy) {
            e.preventDefault();
            const b = state.boxes[state.selected];
            state.boxes[state.selected] = {
                x1: b.x1 + dx, y1: b.y1 + dy,
                x2: b.x2 + dx, y2: b.y2 + dy,
            };
            redraw();
        }
    }
});

/* ----- İlk yüklemede stil seçimi durumuna göre slider'ı gizle ----- */
blurStrengthWrap.style.display = "";
