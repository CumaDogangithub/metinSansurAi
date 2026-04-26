import cv2
import easyocr
import json
import numpy as np
import ollama

class ImageCensor:
    def __init__(self):
        print("OCR Motoru Yükleniyor ...")
        #Türkçe ve İngilizce destekli okuyucu (Ekran kartını kullanması için gpu=True)
        self.reader = easyocr.Reader(['tr','en'],gpu = True)
        self.model_name = 'llama3'

    def get_targets_from_ai(self,full_text):
        """Llama 3'e metnin tamamını verip sansürleneceklerin listesini (JSON) alır"""
        prompt = f"""
        Sen çok dilli bir veri gizliliği uzmanısın. Aşağıdaki metni oku.
        GÖREVİN: Metni YAZAN/GÖNDEREN asıl kişiye (müşteri, mağdur) ait kişisel bilgileri (Ad, Soyad, Telefon, TC vb.) tespit etmektir.
        
        KURALLAR:
        1. Karşı tarafın (aracı kurum, şirket, müşteri temsilcisi) bilgilerini ASLA seçme.
        2. Çıktı olarak SADECE tespit ettiğin gönderici bilgilerini JSON formatında ver.
        
        ÖRNEK ÇIKTI FORMATI:
        {{"gizlenecekler": ["Ahmet Yılmaz", "0532 999 88 77"]}}

        METİN:
        "{full_text}"
        """

        try:
            response = ollama.chat(model=self.model_name,messages=[
                {'role':'user','content':prompt}
            ],format = 'json')

            result = json.loads(response['message']['content'])
            return result.get('gizlenecekler',[])
        except Exception as e:
            print("AI Yanıt Hatası:",e)
            return []
        
    def process_image(self,image_path,output_path):
        #1.Resim oku
        img=cv2.imread(image_path)
        if img is None:
            print("Hata: Resim Bulunmadı!")
            return
        
        #2.Resimdeki tüm metinkleri ve koordinatları çıkar
        print("Resim taranıyor ...")
        results = self.reader.readtext(img)
        
        #3.AI'ın okuyabilmesi için tüm metni birleştir (Bağlam oluştur)
        full_text = " ".join([text for (bbox, text, prob) in results])
        print(f"Okunan Metin : {full_text}\n")

        #4. Yapay Zekaya sor:"Kimi sansürlemeliyim ?"
        print("Yapay zeka analiz ediyor ...")
        targets_to_hide = self.get_targets_from_ai(full_text)
        print(f"AI Tarafından Hedeflenenler : {targets_to_hide}\n")

        #5. Koordinatlara Geri Dön ve Eşleşenleri Blurla
        for (bbox,text,prob) in results:
            #OCR "Cuma",AI ise "Cuma Doğan" demiş olabilir.
            #Bu yüzden OCD'ın bulduğu kelime, Aı'ın hedeleri içinde geçiyor mu diye bakıyoruz
            is_target = any(text.strip().lower() in target.lower() for target in targets_to_hide)

            #Ekstra güvenlik:Rakam içeren telefon/TC gibi veriler parçalı okunmuş olabilir
            #Eğer 5 haneden uzun bir rakam dizisiyse ve hedeflerde geçiyorsa onu da yakala
            if not is_target and len(text.strip()) > 5 and any(char.isdigit() for char in text):
                clean_text = ''.join(filter(str.isdigit,text))
                is_target = any(clean_text in target.replace(' ','') for target in targets_to_hide)
            
            if is_target:
                #Koordinatları al
                top_left = tuple(map(int,bbox[0]))
                bottom_right = tuple(map(int,bbox[2]))

                x1,y1 = top_left[0], top_left[1]
                x2,y2 = bottom_right[0],bottom_right[1]

                #Resim kes (Region of Interest)
                roi = img[y1:y2,x1:x2]

                #Güçlü bir sansür (Gaussian Blur) uygula
                blurred_roi = cv2.GaussianBlur(roi,(51,51),0)

                #sansürlü kısmı orijinal resme geri yapıştır
                img[y1:y2, x1:x2] = blurred_roi
                print(f"Sansürlendi: {text}")
        #6. Sonucu Kaydet
        cv2.imwrite(output_path,img)
        print(f"\nİşlem Tamam! Sonuç Kaydedildi : {output_path}")

#Sistemi Test Edelim
if __name__ == "__main__":
    # 1. Önce motoru hiçbir şey vermeden çalıştır (Yapay zeka ve OCR yüklensin)
    censor_engine = ImageCensor() # veya SmartImageCensor() adını ne koyduysan
    
    # 2. Sonra işlemi yapacak olan fonksiyona resimlerin yollarını ver
    censor_engine.process_image("denenecek2.png", "sansurlu2.png")

