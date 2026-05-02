"""
Üç modeli aynı zorlu metinde karşılaştır:
  1) llama3
  2) qwen2.5:14b
  3) gpt-oss-safeguard:20b

Sansürlü çıktıyı + süreyi alır; ardından her önemli alan için
"doğru maskelendi mi / korundu mu" bazlı bir audit yapar ve F1 skoru hesaplar.
Sonuç: konsola tablo + comparison.html (renkli yan yana çıktı).
"""

import time
import html
from pathlib import Path

import ollama
from prompts import SYSTEM_PROMPT, build_prompt

# ----- Test ayarı --------------------------------------------------------
MODELS = ["qwen2.5:7b", "qwen2.5:14b", "gpt-oss-safeguard:20b"]

ZOR_METIN = """Sayın BDDK Tüketici Hakem Heyeti Müdürlüğü,

Ben Mehmet Furkan Şahinoğlu, T.C. kimlik numaram 19283746501, doğum tarihim 14.07.1992. Eskişehir Tepebaşı'nda, Hoşnudiye Mh. Atatürk Cad. No:127/14 adresinde ikamet ediyorum. Aşağıda detaylandıracağım dolandırıcılık vakası hakkında resmi şikayetimi sunmak istiyorum.

Olay 23 Ekim 2025 tarihinde başladı. "GlobalCapital Invest Ltd." isimli, kendisini Londra merkezli yatırım kuruluşu olarak tanıtan bir firmanın temsilcisi olduğunu söyleyen Selim Aykut Demirtaş adlı şahıs, +90 850 222 11 33 numaralı çağrı merkezi hattından beni aradı. Şirketin web sitesi globalcapital-invest[.]com olarak verildi, mersis no olarak 0123456789012345 paylaşıldı (sonradan sahte olduğu anlaşıldı).

Selim Bey, bana ait olan +90 555 478 92 16 numaralı GSM hattımdan ve furkan.sahinoglu.92@gmail.com adresimden ulaşılabileceğimi LinkedIn üzerinden tespit ettiklerini söyledi. WhatsApp üzerinden de iletişim kurduk; kendi numarası olarak +44 20 7946 0958'i verdi (sonradan VoIP olduğu ortaya çıktı). Aynı firmadan "müşteri başarı uzmanı" sıfatıyla Anastasia Kovacheva isimli bir kadın da bana e-posta gönderdi: a.kovacheva@globalcapital-invest.io. Türkiye operasyon müdürü olarak Bülent Aksoy adında biri tanıtıldı (0532 401 88 76).

Bana sözde "AI destekli forex panel"i için demo hesap açıldı. Hesap numaram 778-44-90251-EU, panel kullanıcı adım furkan_sah_92, ilk şifre Glb2025! olarak verildi (kendim sonradan değiştirdim ama erişebildiklerini düşünüyorum). Üç hafta içinde toplam 47.500 EUR yatırım yapmam istendi. Para transferlerini Garanti BBVA'daki hesabımdan (IBAN TR33 0006 2000 1234 5678 9012 34) yaptım. Karşı tarafın IBAN'ı olarak farklı zamanlarda iki ayrı hesap verildi:

  1) ING Bank Türkiye, alıcı: "Atlas Finansal Danışmanlık A.Ş.", IBAN TR99 0009 9000 0099 8877 6655 44
  2) Estonya menşeli "LHV Pank", alıcı: "Globalcap Trading OÜ", IBAN EE38 2200 2210 2014 5685

Para gönderimlerinden sonra hesabımda görünür kâr 71.200 EUR'ya çıktı; ancak çekim talebimde "vergi avansı" adı altında 8.500 EUR daha ödememi istediler. Bunun üzerine 14 Kasım 2025'te Eskişehir Cumhuriyet Başsavcılığı'na 2025/19284 esas numarasıyla suç duyurusunda bulundum. Soruşturma savcısı Mehmet Aydın Bey'in benimle ilgilendiğini biliyorum.

Avukatım Av. Zeynep Kara Hanım (Kara Hukuk Bürosu, Bağdat Cad. No:212, Kadıköy/İSTANBUL · ofis: 0216 411 22 99 · e-posta: zeynep@karahukuk.av.tr) süreci yürütüyor. Ayrıca Garanti BBVA müşteri temsilcim Cansu Erdoğan Hanım (caglayan.subesi@garantibbva.com.tr · 0212 318 18 18 dahili 4471) chargeback talebi için tutanak hazırladı.

Konu hakkında benimle iletişime geçmek için, +90 555 478 92 16 numaramı veya furkan.sahinoglu.92@gmail.com adresimi kullanabilirsiniz. Yedek iletişim olarak iş yerimden 0222 335 04 50 dahili 1207 numarasından da bana ulaşılabilir. Ayrıca eşim Elif Şahinoğlu (TC: 28374659102, 0535 220 11 47) bu süreçte vekâletim altında işlem yapma yetkisine sahiptir.

Saygılarımla,
Mehmet Furkan Şahinoğlu"""


# ----- Audit ground-truth ------------------------------------------------
# (alan, türü, "metinde aynen geçen ifade", maskelenmeli mi?)
GROUND_TRUTH = [
    # === GÖNDERICI (maskelenmeli) ===
    ("Ad-Soyad",          "GÖNDERİCİ",     "Mehmet Furkan Şahinoğlu",          True),
    ("TC",                "GÖNDERİCİ",     "19283746501",                       True),
    ("Doğum tarihi",      "GÖNDERİCİ",     "14.07.1992",                        True),
    ("Açık adres",        "GÖNDERİCİ",     "Hoşnudiye Mh. Atatürk Cad. No:127/14", True),
    ("GSM",               "GÖNDERİCİ",     "+90 555 478 92 16",                 True),
    ("E-posta",           "GÖNDERİCİ",     "furkan.sahinoglu.92@gmail.com",     True),
    ("Hesap no",          "GÖNDERİCİ",     "778-44-90251-EU",                   True),
    ("Kullanıcı adı",     "GÖNDERİCİ",     "furkan_sah_92",                     True),
    ("Şifre",             "GÖNDERİCİ",     "Glb2025!",                          True),
    ("Kendi IBAN",        "GÖNDERİCİ",     "TR33 0006 2000 1234 5678 9012 34",  True),
    ("İş tel + dahili",   "GÖNDERİCİ",     "0222 335 04 50 dahili 1207",        True),
    ("Eş ad-soyad",       "GÖNDERİCİ-AİLE","Elif Şahinoğlu",                    True),
    ("Eş TC",             "GÖNDERİCİ-AİLE","28374659102",                       True),
    ("Eş tel",            "GÖNDERİCİ-AİLE","0535 220 11 47",                    True),
    # === KARŞI TARAF (KORUNMALI) ===
    ("Dolandırıcı 1 ad",  "KARŞI",         "Selim Aykut Demirtaş",              False),
    ("Dolandırıcı 1 tel", "KARŞI",         "+90 850 222 11 33",                 False),
    ("Dolandırıcı 1 wp",  "KARŞI",         "+44 20 7946 0958",                  False),
    ("Dolandırıcı 2 ad",  "KARŞI",         "Anastasia Kovacheva",               False),
    ("Dolandırıcı 2 e-p", "KARŞI",         "a.kovacheva@globalcapital-invest.io", False),
    ("Dolandırıcı 3 ad",  "KARŞI",         "Bülent Aksoy",                      False),
    ("Dolandırıcı 3 tel", "KARŞI",         "0532 401 88 76",                    False),
    ("Karşı IBAN 1",      "KARŞI",         "TR99 0009 9000 0099 8877 6655 44",  False),
    ("Karşı IBAN 2",      "KARŞI",         "EE38 2200 2210 2014 5685",          False),
    # === KAMU / NÖTR (KORUNMALI) ===
    ("Mersis no",         "KAMU",          "0123456789012345",                  False),
    ("Esas no",           "KAMU",          "2025/19284",                        False),
    ("Savcı adı",         "KAMU",          "Mehmet Aydın",                      False),
]


# ----- Çekirdek fonksiyonlar --------------------------------------------
def mask_word(word: str) -> str:
    if len(word) <= 2:
        return word[0] + "*" * (len(word) - 1)
    return word[:2] + "*" * (len(word) - 2)


def censor_with_model(text: str, model: str):
    """Bir modelle metni sansürle. (censored, items, elapsed_s) döner."""
    import json as _json
    prompt = build_prompt(text)
    t0 = time.time()
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        format="json",
    )
    elapsed = time.time() - t0
    try:
        result = _json.loads(response["message"]["content"])
        items = result.get("gizlenecekler", [])
    except Exception as e:
        print(f"  ⚠ JSON parse error ({model}): {e}")
        items = []

    censored = text
    for item in items:
        if not item or not isinstance(item, str):
            continue
        masked = " ".join(mask_word(w) for w in item.split())
        censored = censored.replace(item, masked)
    return censored, items, elapsed


def is_masked(censored_text: str, original_fragment: str) -> bool:
    """Orijinal parça çıktıda hâlâ açık mı?"""
    return original_fragment not in censored_text


def audit(censored_text: str):
    """Her ground-truth alan için: doğru mu? (TP/TN/FP/FN say)."""
    tp = tn = fp = fn = 0
    rows = []
    for label, role, fragment, should_mask in GROUND_TRUTH:
        masked = is_masked(censored_text, fragment)
        if should_mask and masked:
            verdict, kind = "✅", "TP"; tp += 1
        elif should_mask and not masked:
            verdict, kind = "❌ KAÇIRDI", "FN"; fn += 1
        elif not should_mask and not masked:
            verdict, kind = "✅", "TN"; tn += 1
        else:  # not should_mask and masked
            verdict, kind = "⚠ FAZLA", "FP"; fp += 1
        rows.append((label, role, fragment, should_mask, masked, verdict, kind))
    return tp, tn, fp, fn, rows


def f1(tp: int, fp: int, fn: int) -> float:
    if tp + fp == 0 or tp + fn == 0:
        return 0.0
    prec = tp / (tp + fp)
    rec = tp / (tp + fn)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


# ----- Çalıştır + raporla -----------------------------------------------
def main():
    results = []
    for i, model in enumerate(MODELS, 1):
        print(f"\n[{i}/{len(MODELS)}] {model} çalışıyor…")
        try:
            censored, items, elapsed = censor_with_model(ZOR_METIN, model)
        except Exception as e:
            print(f"  HATA: {e}")
            continue
        tp, tn, fp, fn, rows = audit(censored)
        score = f1(tp, fp, fn)
        results.append({
            "model": model,
            "censored": censored,
            "items": items,
            "elapsed": elapsed,
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "f1": score, "rows": rows,
        })
        print(f"  ✓ Tamam — {elapsed:.1f}s · TP={tp} TN={tn} FP={fp} FN={fn} · F1={score:.2f}")

    print_table(results)
    write_html(results)
    print("\n📄  comparison.html oluşturuldu — tarayıcıda açabilirsin.")


def print_table(results):
    print("\n" + "═" * 70)
    print(f"{'Model':<26} {'Süre':>8} {'TP':>4} {'TN':>4} {'FP':>4} {'FN':>4} {'F1':>6}")
    print("─" * 70)
    for r in results:
        print(f"{r['model']:<26} {r['elapsed']:>7.1f}s "
              f"{r['tp']:>4} {r['tn']:>4} {r['fp']:>4} {r['fn']:>4} {r['f1']:>6.2f}")
    print("═" * 70)
    print("TP=doğru maskelendi · TN=doğru korundu · "
          "FP=yanlış maskelendi · FN=kaçırdı")

    # Detaylı: hangi alanı kim kaçırdı
    print("\n--- Alan bazlı (✅=doğru, ❌=kaçırdı, ⚠=fazla maskeledi) ---\n")
    header = f"{'Alan':<22} {'Rol':<14}" + "".join(f"{r['model'][:14]:>16}" for r in results)
    print(header)
    print("-" * len(header))
    n_fields = len(GROUND_TRUTH)
    for i in range(n_fields):
        label, role, frag, should = GROUND_TRUTH[i]
        line = f"{label:<22} {role:<14}"
        for r in results:
            verdict = r["rows"][i][5]
            line += f"{verdict:>16}"
        print(line)


def write_html(results):
    def hl(text):
        """Çıktıdaki yıldızlı parçaları renklendir."""
        import re
        out = html.escape(text)
        out = re.sub(r"(\S*\*+\S*(?:\s+\S*\*+\S*)*)",
                     r'<mark>\1</mark>', out)
        return out.replace("\n", "<br>")

    cards = ""
    for r in results:
        rows_html = ""
        for label, role, frag, should, masked, verdict, kind in r["rows"]:
            cls = {"TP": "ok", "TN": "ok", "FP": "warn", "FN": "err"}[kind]
            rows_html += (
                f"<tr class='{cls}'><td>{html.escape(label)}</td>"
                f"<td>{role}</td>"
                f"<td><code>{html.escape(frag[:40])}{'…' if len(frag)>40 else ''}</code></td>"
                f"<td>{verdict}</td></tr>"
            )
        cards += f"""
<section class='model'>
  <header>
    <h2>{html.escape(r['model'])}</h2>
    <div class='stats'>
      <span>⏱ {r['elapsed']:.1f}s</span>
      <span class='ok'>TP {r['tp']}</span>
      <span class='ok'>TN {r['tn']}</span>
      <span class='warn'>FP {r['fp']}</span>
      <span class='err'>FN {r['fn']}</span>
      <span class='f1'>F1 = {r['f1']:.2f}</span>
    </div>
  </header>
  <pre class='out'>{hl(r['censored'])}</pre>
  <details><summary>Alan bazlı denetim</summary>
    <table><thead><tr><th>Alan</th><th>Rol</th><th>Örnek</th><th>Sonuç</th></tr></thead>
    <tbody>{rows_html}</tbody></table>
  </details>
</section>"""

    page = f"""<!DOCTYPE html>
<html lang='tr'><head><meta charset='UTF-8'>
<title>textSansur · 3 Model Kıyaslama</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif;
         background: #0b0d12; color: #e8ebf3; max-width: 1400px;
         margin: 24px auto; padding: 0 18px; }}
  h1 {{ font-size: 28px; letter-spacing: -0.02em; }}
  .lede {{ color: #9ba3b4; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px,1fr));
          gap: 18px; }}
  .model {{ background: #161a23; border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px; padding: 18px; }}
  .model h2 {{ margin: 0 0 8px; font-size: 16px; font-family: ui-monospace, monospace;
               color: #22d3ee; }}
  .stats {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px;
            font-family: ui-monospace, monospace; margin-bottom: 14px; }}
  .stats span {{ padding: 3px 9px; background: #1d212c; border-radius: 999px; }}
  .stats .ok   {{ color: #34d399; }}
  .stats .warn {{ color: #fbbf24; }}
  .stats .err  {{ color: #f87171; }}
  .stats .f1   {{ color: white; background: #7c5cff; font-weight: 700; }}
  pre.out {{ background: #0b0d12; border: 1px solid rgba(255,255,255,0.06);
             padding: 14px; border-radius: 8px; font-size: 12.5px; line-height: 1.55;
             white-space: pre-wrap; word-break: break-word; max-height: 480px;
             overflow: auto; }}
  mark {{ background: rgba(124,92,255,0.22); color: #c4b5fd; padding: 1px 3px;
          border-radius: 3px; }}
  details {{ margin-top: 12px; font-size: 12.5px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ padding: 6px 8px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }}
  th {{ font-size: 11px; text-transform: uppercase; color: #9ba3b4; letter-spacing: 0.08em; }}
  td code {{ font-size: 11px; color: #c4b5fd; }}
  tr.err td:last-child   {{ color: #f87171; font-weight: 600; }}
  tr.warn td:last-child  {{ color: #fbbf24; font-weight: 600; }}
  tr.ok td:last-child    {{ color: #34d399; }}
</style></head>
<body>
<h1>🔬 textSansur · 3 Model Kıyaslama</h1>
<p class='lede'>Aynı zorlu KVKK senaryosu üç farklı yerel LLM'de çalıştırıldı.
F1 skoru gönderici verisini doğru maskeleme + karşı tarafı doğru koruma performansını ölçer.</p>
<div class='grid'>{cards}</div>
</body></html>"""
    Path("comparison.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
