from ultralytics import YOLO
from time import sleep
# Load a pretrained YOLO26n model
model = YOLO("flame/runs/detect/flame-1/weights/best.pt")

# Single stream with batch-size 1 inference
source_rtsp = "rtsp://192.168.50.62:8554/cam"  # RTSP, RTMP, TCP, or IP streaming address

# Run batched inference on a list of images
results = model(source_rtsp, stream=True, show=True, conf=0.50)  # return a generator of Results objects

# Process results generator
for result in results:
    boxes = result.boxes  # Boxes object for bounding box outputs
    masks = result.masks  # Masks object for segmentation masks outputs
    keypoints = result.keypoints  # Keypoints object for pose outputs
    probs = result.probs  # Probs object for classification outputs
    obb = result.obb  # Oriented boxes object for OBB outputs
    if len(result.boxes.conf) > 0: #Tjekker om confidence valuen stiger. Så snart detecter en flamme bliver den triggered.
        print('IIIILDDDDDDDDDDDDDDDDDD')
        break
