import ollama
import json

class TextCensorAI:
        def __init__(self):
            #Bilgisayarında lokal olarak çalışan modeli seçiyoruz
            self.model_name="llama3"

        def mask_word(self,word):
            """Python ile kusursuz yıldızlama fonksiyonu"""
            # Eğer kelime çok kısaysa (örn: TC, Su vs.) sadece ilk harfi bırak
            if len(word) <= 2:
                return word[0] + "*" * (len(word) - 1)
            
            # Kelimenin ilk 2 harfini al, geri kalan uzunluk kadar * koy
            return word[:2] + "*" * (len(word) - 2)

        
        def censor(self,text):
            #Yapay zekaya vereceğimiz zeko odlu talimat(System Promt)
            prompt = f"""
            Sen çok dilli (multilingual) bir veri gizliliği uzmanısın. Aşağıdaki metni (hangi dilde yazılmış olursa olsun) oku.
            
            GÖREVİN: 
            Metni YAZAN/GÖNDEREN asıl kişiye (müşteri, kullanıcı veya şikayetçi) ait kişisel bilgileri (Ad, Soyad, Telefon, E-posta, TC vb.) tespit etmektir.
            
            KURALLAR:
            1. Metin bir şikayet, bilgi talebi, resmi bir e-posta veya normal bir mesaj olabilir. Metni kim yazmışsa onun adını/iletişim bilgisini bul.
            2. Karşı tarafın (aracı kurum, şirket, müşteri temsilcisi, firma, broker) isimlerini ve iletişim bilgilerini ASLA seçme.
            3. Çıktı olarak SADECE tespit ettiğin gönderici bilgilerini JSON formatında ver. Başka hiçbir kelime yazma.

            ÖRNEK ÇIKTI FORMATI:
            {{"gizlenecekler": ["Ahmet Yılmaz", "CUMA DOĞAN", "0532 999 88 77", "john@mail.com"]}}

            METİN:
            "{text}"
            """

            # Llama 3'ten sadece JSON dönmesini istiyoruz
            response=ollama.chat(model=self.model_name,messages=[
                {
                    'role':'system',
                    'content':"Sen katı kulları olan bir veri ayıklama asistanısın."
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
    Merhaba, ben Ahmet Yılmaz. Geçen hafta GlobalTrade FX isimli bir firmaya yatırım yaptım. 
    Beni 0555 111 22 33 numarasından Mehmet isminde bir müşteri temsilcisi aradı. 
    Kendi numaram olan 0532 999 88 77 üzerinden bana ulaştılar. 
    Parayı gönderdikten sonra hesabımı kapattılar.

    """

    print("--- Orijinal Metin ---")
    print(ornek_vaka)

    print("\n--- AI Contextual Sansür ---")
    print(ai_censor.censor(ornek_vaka))
