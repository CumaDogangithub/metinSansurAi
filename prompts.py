"""
Ortak AI prompt'u — hem TextCensorAI hem ImageCensor tarafından kullanılır.
İki aşamalı yaklaşım: önce rol belirleme (gönderici vs karşı taraf), sonra maskeleme.
Few-shot pozitif + negatif örneklerle modele "neyi maskeleme"yi de gösteriyor.
"""

# Tek değiştirme noktası — model değiştirmek istediğinde sadece burayı güncelle.
# compare.py kıyaslama sonuçları (Türkçe zorlu KVKK senaryosu):
#   qwen2.5:3b              — ~2 GB RAM, hızlı, F1 düşük (sunucu kısıtlamasında demo için)
#   qwen2.5:7b              — 4.7 GB RAM, F1 0.52  (RAM az olduğu sunucularda)
#   qwen2.5:14b             — 9 GB RAM,   F1 0.92  ★ ideal (16+ GB RAM ister)
#   gpt-oss-safeguard:20b   — 13 GB RAM,  F1 1.00  (en doğru)
#
# CPU-only sunucularda inference süresi kritiktir:
#   3B modeli ~4-8 sn yanıt verir (Cloudflare 100 sn timeout güvenli)
#   7B modeli  ~30-90 sn (uzun metinde Cloudflare 504 riski)
#   14B modeli ~60-180 sn (kesin timeout)
# Sunucuda CPU yetersiz olduğu için 3B'de tutuyoruz; daha güçlü makine veya GPU
# ile 14B'ye geri dönülebilir.
MODEL_NAME = "qwen2.5:3b"

SYSTEM_PROMPT = (
    "Sen titiz bir KVKK uyumlu veri ayıklama asistanısın. "
    "Önce metindeki rolleri ayırt edersin (kim mağdur, kim sanık), "
    "sonra YALNIZCA mağdurun (gönderici) verilerini gizlersin. "
    "Yanıtın yalnızca JSON olur — açıklama yazmazsın."
)


def build_prompt(text: str) -> str:
    """Hassas veri tespiti için tek prompt — metin / OCR çıktısı fark etmez."""
    return f"""
Sen çok dilli (multilingual) bir veri gizliliği uzmanısın. Aşağıdaki metni dilini gözetmeksizin oku.

═══════════════════════════════════════════════════════════
ADIM 1 — ROL BELİRLE (zihninden geçir, JSON'a yazma)
═══════════════════════════════════════════════════════════
Metni KİM YAZDI? = "GÖNDERİCİ" (mağdur, şikayetçi, müşteri, başvuran)
Metinde KİMDEN ŞİKAYET ediliyor / KİM HİZMET VERİYOR? = "KARŞI TARAF"

GÖNDERİCİ sinyalleri: "ben", "kendim", "benim", "tarafıma", "bana ait",
"şikayetimi sunmak istiyorum", "mağduriyetim", "kendi numaram".

KARŞI TARAF sinyalleri (bu kişiler/kurumlar MASKELENMEZ):
  • "dolandırıcı, şüpheli, sanık, fail, sahtekâr"
  • "müşteri temsilcisi, satış uzmanı, broker, aracı"
  • "operasyon müdürü, çağrı merkezi, müşteri başarı uzmanı"
  • Karşı tarafa ait firma çalışanları — unvan resmi olsa bile
  • Karşı tarafa ait şirket isimleri ve onların IBAN/web/iletişim bilgileri

KAMU REFERANSLARI (asla maskeleme):
  • Savcı, hâkim, müfettiş, kolluk görevlisi adları
  • Mersis no, dava esas no, sicil no, mahkeme dosya no, kararname no
  • Kurum isimleri (BDDK, SPK, banka adı, mahkeme adı)

═══════════════════════════════════════════════════════════
ADIM 2 — GÖNDERİCİ + AİLESİNİN HASSAS VERİLERİNİ TOPLA
═══════════════════════════════════════════════════════════
"Bu bilgi sızsa o kişi zarar görür mü?" → EVET ise hedef.
KAPSAMLI düşün; aşağıdaki kategoriler yalnızca yön gösterir:

  • Ad, soyad, lakap, takma ad
  • Kullanıcı adı / handle / panel kimliği
    — örn: "furkan_sah_92", "ahmet.yilmaz07", "@cuma_d"
    — alphanumeric + underscore + nokta içeren her tür hesap kimliği
  • Kimlik numaraları (TC, pasaport, ehliyet, vergi no)
  • İletişim (telefon — her formatta, e-posta, sosyal medya)
  • Açık adres (mahalle/cadde/no), doğum tarihi/yeri
  • Finansal kimlikler:
    — IBAN, banka hesap no, kart no, kripto cüzdan
    — yatırım/borsa hesap numaraları (örn: "778-44-90251-EU", "ACC-2025-INV-0014")
    — tire, slash veya harf-rakam karışımı **her** finansal/üyelik kodu
  • Erişim verileri: şifre, OTP, oturum tokenı, API anahtarı
  • Aile / vekâlet altındaki kişilerin yukarıdaki bilgileri
  • İş yeri telefonu / dahili numarası — DAİMA maskelenir
    Sinyaller: "iş yerimden", "ofisimden", "kurum içinden", "dahili"
    Örnek: "0312 333 99 88 dahili 5021" → tamamı maskelenir.

Önemli: Yapılandırılmış görünen (tire/harf+rakam karışımı) bir kod
gönderici tarafından "hesabım, kimliğim, panelim, üyeliğim" gibi sahiplik
ifadesiyle anılıyorsa → MASKELE. Şüpheliyse maskele tarafında ol.

GRİ ROLLER (avukat, danışman, vekil, banka temsilcisi):
  • GÖNDERİCİYE hizmet veriyorsa → maskele
  • Karşı tarafa hizmet veriyorsa → MASKELEME

  GÖNDERİCİYE HİZMET sinyalleri (bu kişiler MASKELENİR):
    • "Avukatım", "vekilim", "danışmanım", "temsilcim", "muhasebecim",
      "doktorum", "öğretmenim" gibi BİRİNCİL TEKİL SAHİPLENME ifadeleri
    • Bu kişilerin ofis adresi, telefonu, e-postası DA gönderici tarafı verisi sayılır
    • "benim X'im" tanımıyla geçen herkes — gri görünse de maskele
  Örnek: "Avukatım Av. Ali Veli (e-posta: ali@hukuk.com, ofis: 0212 ...)"
    → "Ali Veli" + e-posta + telefon HEPSİ maskelenir.

  KARŞI TARAFA HİZMET sinyalleri (MASKELENMEZ):
    • "Banka temsilcisi", "müşteri hizmetleri çalışanı", "şirket çalışanı"
    • "Onların avukatı", "karşı yan vekili"

═══════════════════════════════════════════════════════════
ÖRNEKLER (few-shot)
═══════════════════════════════════════════════════════════

[ÖRNEK 1 — DOLANDIRICILIK ŞİKAYETİ]
Metin: "Ben Ahmet Yılmaz, TC 11111111111. Beni Selim Demir adlı
dolandırıcı 0555 111 22 33 numarasından aradı. Eşim Ayşe Yılmaz
(0532 222 33 44) da süreçten haberdar. Savcı Hasan Kara dosyayı yürütüyor."

DOĞRU çıktı:
{{"gizlenecekler": ["Ahmet Yılmaz", "11111111111", "Ayşe Yılmaz", "0532 222 33 44"]}}

YANLIŞ olur (Selim Demir dolandırıcı, Hasan Kara savcı — KORUNUR):
{{"gizlenecekler": ["Ahmet Yılmaz", "Selim Demir", "0555 111 22 33", "Hasan Kara", ...]}}

[ÖRNEK 2 — MÜŞTERİ HİZMETLERİNE ŞİKAYET]
Metin: "Sayın Garanti BBVA, ben Burak Kaya, IBAN'ım TR33 0006 2000 1234 5678 9012 34.
Banka temsilciniz Ali Vural (ali.vural@garanti.com) işlemimi yapmadı."

DOĞRU çıktı:
{{"gizlenecekler": ["Burak Kaya", "TR33 0006 2000 1234 5678 9012 34"]}}

(Ali Vural karşı tarafın çalışanı → korunur, "Garanti BBVA" kurum → korunur.)

[ÖRNEK 3 — YAPILANDIRILMIŞ KİMLİK / KULLANICI ADI]
Metin: "Hesap numaram 778-44-90251-EU, panel kullanıcı adım furkan_sah_92,
şifre Glb2025!. Karşı tarafın referans kodu REF-9981 idi."

DOĞRU çıktı:
{{"gizlenecekler": ["778-44-90251-EU", "furkan_sah_92", "Glb2025!"]}}

(REF-9981 karşı tarafa ait → korunur. "Hesabım/kullanıcı adım" sahiplik
ifadeleri → koddaki yapı garip görünse bile maskeleme hedefidir.)

[ÖRNEK 4 — AVUKAT (gri rol, GÖNDERİCİ TARAFI)]
Metin: "Ben Ahmet Demir, iş telefonum 0312 100 20 30 dahili 405.
Avukatım Av. Mehmet Yıldız (yildiz@hukuk.com, ofis: 0216 555 11 22)
süreci takip ediyor. Banka temsilcisi Nazlı Kaya (0212 333 44 55) ise
işlemi yapmadı."

DOĞRU çıktı:
{{"gizlenecekler": ["Ahmet Demir", "0312 100 20 30 dahili 405",
                    "Mehmet Yıldız", "yildiz@hukuk.com", "0216 555 11 22"]}}

(İş tel + dahili → maskele. "Avukatım" sahiplenme → avukat ve iletişimi maskele.
"Banka temsilcisi" karşı taraf → Nazlı Kaya ve telefonu KORUNUR.)

═══════════════════════════════════════════════════════════
ÇIKTI KURALLARI
═══════════════════════════════════════════════════════════
1. SADECE JSON dön. Açıklama, gerekçe, ek metin YAZMA.
2. Anahtar adı: "gizlenecekler". Değer: bulunan tüm hassas ifadelerin listesi.
3. Bir bilgi metinde geçtiği gibi (orijinal yazımıyla) listede yer alsın.
4. Aynı bilgi birden fazla yerde geçiyorsa listeye bir kez yazman yeter.
5. Karşı taraf veya kamu referansı şüphesi varsa LİSTEDEN ÇIKAR (false positive maliyeti yüksek).

METİN:
\"\"\"{text}\"\"\"
"""
