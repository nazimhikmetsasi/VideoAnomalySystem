from core.pipeline import VideoKafkaProducer
import time

kamera = VideoKafkaProducer(source=0).start()
time.sleep(10) # 10 saniye boyunca kamerayı çekip Kafka'ya basacak
kamera.stop()