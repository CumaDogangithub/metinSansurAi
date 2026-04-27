import cv2
import easyocr
import json
import ollama
import tkinter as tk
from PIL import Image,ImageTk


class BlurEditor:
    """Kullanıcının sansür alanlarını görsel oalrak düzenlediği arayüz"""
    def __init__(self,cv_img,ai_boxes,output_path):
        self.output_path=output_path
        self.cv_img=cv_img.copy()

        #Tkinder Penceresini Başlat
        self.root=tk.Tk()
        self.root.title("Gelişmiş Sansür Editörü (Sol Tık:Çiz , Sağ Tık  Sil)")

        #Resim Tkinder'ın analayacağı formata çevir
        self.img_height, self.img_width=self.cv_img.shape[:2]
        self.pil_img = Image.fromarray(cv2.cvtColor(self.cv_img, cv2.COLOR_BGR2RGB))
        self.tk_img = ImageTk.PhotoImage(self.pil_img)

        #Tuval (Canvas) Oluştur
        self.canvas = tk.Canvas(self.root,width=self.img_width,height=self.img_height,cursor = "cross")
        self.canvas.pack()
        self.canvas.create_image(0,0, anchor=tk.NW,image = self.tk_img)

        self.rects = [] #Çizilen Tüm Kutuları Tutan Nesne
        self.current_rect = None
        self.start_x = 0
        self.start_y = 0

        #Yapay Zekanın bulduğu kutuları ekrana çizdir
        for box in ai_boxes:
            self.add_box(box[0],box[1],box[2],box[3])

        #Fare Olayları (Event Binding)
        self.canvas.bind("<ButtonPress-1>", self.on_press)    # Sol Tık Basıldı
        self.canvas.bind("<B1-Motion>", self.on_drag)         # Sol Tık Sürükleniyor
        self.canvas.bind("<ButtonRelease-1>", self.on_release)# Sol Tık Bırakıldı
        self.canvas.bind("<Button-3>", self.on_right_click)   # Sağ Tık (Silme)

        #Kaydet Butonu
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame,
                  text="✅ DEĞİŞİKLİKLERİ UYGULA VE KAYDET",
                  command=self.save_and_close,
                  bg="green",
                  fg="white",
                  font=("Arial", 12, "bold")
                  ).pack()
        
        self.root.mainloop()
    
    def add_box(self,x1,y1,x2,y2):
        #Yarı saydam gri dolgulu, Kırmızı kenarlıklı kutu çiz
        rect_id = self.canvas.create_rectangle(x1,y1,x2,y2,outline="red",width = 2,fill="gray",stipple = "gray50")
        self.rects.append({'id':rect_id,'coords':[x1,y1,x2,y2]})

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.current_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2, fill="gray", stipple="gray50")

    def on_drag(self, event):
        self.canvas.coords(self.current_rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        coords = self.canvas.coords(self.current_rect)
        # Çok küçük yanlışlıkla tıklamaları engelle
        if abs(coords[2] - coords[0]) > 5 and abs(coords[3] - coords[1]) > 5:
            self.rects.append({'id': self.current_rect, 'coords': [int(c) for c in coords]})
        else:
            self.canvas.delete(self.current_rect)
        self.current_rect = None

    def on_right_click(self, event):
        # Tıklanan noktaya en yakın kutuyu bul ve sil
        items = self.canvas.find_withtag("current")
        if items:
            rect_id = items[0]
            self.canvas.delete(rect_id)
            self.rects = [r for r in self.rects if r['id'] != rect_id]          

    def save_and_close(self):
        #Ekranda kalan tüm kutuların koordinatlarını al ve orijinal resme Blur bas
        for r in self.rects:
            x1,y1,x2,y2 = [int(c) for c in r["coords"]]
            #Güvenlik Önlemi: Koordinatları resim dışına taşmaktan koru
            x1, x2 = max(0, min(x1, x2)), min(self.img_width, max(x1, x2))
            y1, y2 = max(0, min(y1, y2)), min(self.img_height, max(y1, y2))
            
            roi = self.cv_img[y1:y2, x1:x2]
            if roi.size > 0:
                blurred = cv2.GaussianBlur(roi, (71, 71), 0)
                self.cv_img[y1:y2, x1:x2] = blurred
        
        cv2.imwrite(self.output_path, self.cv_img)
        print(f"\n[BAŞARILI] Düzenlenmiş resim kaydedildi: {self.output_path}")
        self.root.destroy()




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

        # Blur atmıyoruz, sadece koordinatları topluyoruz
        ai_detected_boxes = []
        for (bbox, text, prob) in results:
            is_target = any(text.strip().lower() in target.lower() for target in targets_to_hide)
            if not is_target and len(text.strip()) > 5 and any(char.isdigit() for char in text):
                clean_text = ''.join(filter(str.isdigit, text))
                is_target = any(clean_text in target.replace(' ','') for target in targets_to_hide)
            
            if is_target:
                top_left = tuple(map(int, bbox[0]))
                bottom_right = tuple(map(int, bbox[2]))
                ai_detected_boxes.append([top_left[0], top_left[1], bottom_right[0], bottom_right[1]])

        # Kullanıcıya sor
        print("AI sansürlenecek alanları belirledi.")
        secim = input("Direkt kaydetmek için 'K', Görsel Editörde düzenlemek için 'D' yazın (K/D): ").strip().upper()

        if secim == 'D':
            print("Editör açılıyor...")
            # Editörü çağır (Düzenleme ve kaydetme işlemini editör yapacak)
            BlurEditor(img, ai_detected_boxes, output_path)
        else:
            # Düzenleme istenmedi, direkt yapay zekanın bulduğu koordinatları blurla
            for box in ai_detected_boxes:
                x1, y1, x2, y2 = box
                roi = img[y1:y2, x1:x2]
                if roi.size > 0:
                    blurred_roi = cv2.GaussianBlur(roi, (71, 71), 0)
                    img[y1:y2, x1:x2] = blurred_roi
            cv2.imwrite(output_path, img)
            print(f"\nİşlem Tamam! Sonuç Kaydedildi: {output_path}")

#Sistemi Test Edelim
if __name__ == "__main__":
    # 1. Önce motoru hiçbir şey vermeden çalıştır (Yapay zeka ve OCR yüklensin)
    censor_engine = ImageCensor() # veya SmartImageCensor() adını ne koyduysan
    
    # 2. Sonra işlemi yapacak olan fonksiyona resimlerin yollarını ver
    censor_engine.process_image("denenecek3.png", "sansurlu3.png")

