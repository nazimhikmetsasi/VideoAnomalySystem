import cv2
import threading
import json
import base64
import time
from kafka import KafkaProducer

class VideoKafkaProducer:
    def __init__(self, source=0, topic='video-stream'):
        # source=0 bilgisayarın kamerasını açar.
        self.cap = cv2.VideoCapture(source)
        self.topic = topic
        
        # Kafka'ya bağlanıyoruz
        self.producer = KafkaProducer(
            bootstrap_servers=['127.0.0.1:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.stopped = False
        print(f"[BİLGİ] Kafka Producer '{self.topic}' kuyruğu için başlatıldı.")

    def start(self):
        # Kamerayı ana programı kilitlememesi için ayrı bir thread (iş parçacığı) üzerinde başlatıyoruz
        t = threading.Thread(target=self.stream_video, args=())
        t.daemon = True
        t.start()
        return self

    def stream_video(self):
        while not self.stopped:
            success, frame = self.cap.read()
            if not success:
                print("[HATA] Kameradan görüntü okunamadı.")
                break

            # Görüntüyü Kafka'dan hızlı akması için boyutlandırıyoruz (Performans Optimizasyonu)
            frame = cv2.resize(frame, (640, 480))
            # Görüntüyü Kafka'dan hızlı akması için boyutlandırıyoruz (Performans Optimizasyonu)
            frame = cv2.resize(frame, (640, 480))
            
            # --- YENİ EKLENEN KISIM: Gece/Düşük Işık Optimizasyonu (CLAHE) ---
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            cl = clahe.apply(l)
            # --- YENİ EKLENEN KISIM: Gece/Düşük Işık Optimizasyonu (CLAHE) ---
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl,a,b))
            frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            # ------------------------------------------------------------------
            
            # Kamerayı ekranda görmek için eklediğimiz satırlar:
            cv2.imshow("MCBU Kamera Test - CLAHE", frame)
            cv2.waitKey(1)
            
            # Kareyi metin formatına (Base64) çeviriyoruz...
            limg = cv2.merge((cl,a,b))
            frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            # ------------------------------------------------------------------
            
            # Kareyi metin formatına (Base64) çeviriyoruz...
            
            # Kareyi metin formatına (Base64) çeviriyoruz ki Kafka'dan JSON olarak geçebilsin
            _, buffer = cv2.imencode('.jpg', frame)
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')

            # Kafka'ya gönderilecek veri paketi (Payload)
            message = {
                "camera_id": "cam_01",
                "timestamp": time.time(),
                "frame_data": jpg_as_text
            }
            
            # Veriyi kuyruğa fırlat
            self.producer.send(self.topic, message)
            
            # Sistemi yormamak için saniyede yaklaşık 30 kareye (FPS) sabitliyoruz
            time.sleep(0.033) 

    def stop(self):
        self.stopped = True
        self.cap.release()
        self.producer.close()
        print("[BİLGİ] Kafka Producer durduruldu.")