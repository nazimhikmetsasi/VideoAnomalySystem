YOLO fine-tune icin etiket klasoru.
Her JPG icin ayni isimde .txt dosyasi:
  images/frame_001.jpg  ->  labels/frame_001.txt

YOLO label formati (person = class 0):
  0 0.5 0.5 0.3 0.6
  (class x_center y_center width height — normalize 0-1)

LabelImg veya Roboflow ile etiketleyebilirsiniz.
