import ollama
import json

from prompts import MODEL_NAME, SYSTEM_PROMPT, build_prompt

class TextCensorAI:
        def __init__(self):
            #Bilgisayarında lokal olarak çalışan modeli seçiyoruz (prompts.py)
            self.model_name = MODEL_NAME

        def mask_word(self,word):
            """Python ile kusursuz yıldızlama fonksiyonu"""
            # Eğer kelime çok kısaysa (örn: TC, Su vs.) sadece ilk harfi bırak
            if len(word) <= 2:
                return word[0] + "*" * (len(word) - 1)

            # Kelimenin ilk 2 harfini al, geri kalan uzunluk kadar * koy
            return word[:2] + "*" * (len(word) - 2)


        def censor(self,text):
            # Hibrit prompt: ilke + örnek kategoriler (prompts.py)
            prompt = build_prompt(text)

            # Llama 3'ten sadece JSON dönmesini istiyoruz
            response=ollama.chat(model=self.model_name,messages=[
                {
                    'role':'system',
                    'content': SYSTEM_PROMPT
                },
                {
                    'role':'user',
                    'content':prompt
                }

            ],format ='json')
            
            try:
                #1. AI'dan gelen JSon verisini Python listesine çevir
                result = json.loads(response['message']['content'])
                items_to_hide = result.get('gizlenecekler',[])

                censored_text = text
                
                # 2. Listede bulunan her bir kelimeyi Python ile maskele
                for item in items_to_hide:
                    # "Cuma Doğan" gibi çoklu kelimeleri boşluktan böl ("Cuma","Doğan")
                    #Her birini ayrı ayrı maskele ("Cu**" ,"Do***")
                    masked_item = " ".join([self.mask_word(w) for w in item.split()])
                    
                    #Orijinal metindeki açık halini maskeli haliyle değiştir
                    censored_text = censored_text.replace(item,masked_item)

                return censored_text

            except Exception as e:
                 print("Yapay ZEka JSON formatında yanıt veremedi: ",e)
                 return text

            
        
if __name__ == "__main__":
    
    ai_censor=TextCensorAI()

    ornek_vaka = """
  Sayın BDDK Tüketici Hakem Heyeti Müdürlüğü,

Ben Burak Kaya, T.C. kimlik numaram 99887766554, doğum tarihim 12.03.1988. Ankara Çankaya'da, Bahçelievler Mh. Aşkabat Cd. No:48/12 adresinde ikamet ediyorum.

Olay 5 Ekim 2026 tarihinde başladı. "NorthStar Capital LLP" ismiyle kendisini Dublin merkezli yatırım kuruluşu olarak tanıtan firmanın temsilcisi olduğunu söyleyen Marcus Hoffmann adlı şahıs, +90 850 480 11 22 numaralı çağrı merkezi hattından beni aradı. Şirketin web sitesi northstar-capital[.]eu, mersis no olarak 9988776655443322 paylaşıldı (sahte olduğu sonradan anlaşıldı).

Marcus Bey, +90 533 712 84 90 numaralı GSM hattıma ve burak.kaya@example.com adresime ulaşmak için LinkedIn üzerinden tespit yaptıklarını söyledi. WhatsApp üzerinden iletişim kurduk; kendi numarası olarak +353 1 555 0188'i verdi. "Müşteri başarı uzmanı" sıfatıyla Elena Petrova adlı bir kadın da bana e-posta gönderdi: elena.p@northstar-capital.eu. Türkiye operasyon müdürü olarak tanıtılan Tarkan Ünal (0532 909 11 47) bilgi formu doldurmamı istedi.

Bana sözde "AI destekli kripto panel"i için demo hesap açıldı. Hesap numaram NS-2026-CRY-00481, panel kullanıcı adım burak_kaya88, ilk şifre Nort#2026 olarak verildi (sonradan değiştirdim). 32.000 EUR yatırım yapmam istendi. Ziraat Bankası'ndaki hesabımdan (IBAN TR55 0001 0000 1234 5678 9012 11) iki transfer yaptım. Karşı tarafın IBAN'ı şuydu: TR88 0006 1000 0099 8877 6655 22 (alıcı: "Northstar Trading Ltd. Şti.").

Çekim talebimde "uyumluluk vergisi" adı altında ek 4.000 EUR istediler; bunun üzerine şüphelendim. SPK uyarı listesinde firmayı buldum. 12 Kasım 2026'da Ankara Cumhuriyet Başsavcılığı'na 2026/41250 esas numarasıyla suç duyurusunda bulundum. Soruşturma savcısı Hakan Erdem Bey ile görüştüm.

Avukatım Av. Dilek Sarı Hanım (Sarı Hukuk Bürosu, Tunalı Hilmi Cd. No:84, Çankaya/ANKARA · ofis: 0312 444 22 11 · e-posta: dilek@sarihukuk.av.tr) süreci yürütüyor. Ziraat müşteri temsilcim Onur Aktaş Bey (kavaklidere.subesi@ziraatbank.com.tr · 0312 555 00 11 dahili 2204) chargeback başvurusu hazırladı.

İş yerimden 0312 333 99 88 dahili 5021 numarasından da bana ulaşılabilir. Eşim Selin Kaya (TC: 11223344556, 0535 410 22 33) vekâletim altında işlem yapma yetkisine sahiptir.

Saygılarımla,
Burak Kaya

    """

    print("--- Orijinal Metin ---")
    print(ornek_vaka)

    print("\n--- AI Contextual Sansür ---")
    print(ai_censor.censor(ornek_vaka))
