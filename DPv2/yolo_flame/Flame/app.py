# from flask import Flask, render_template
# import numpy as np


# RTSP_URL = "rtsp://192.168.137.254:8554/cam"
# app = Flask(__name__)


# @app.route("/")
# def home():
#     return render_template("home.html")

# if __name__ == ('__main__'):
#     app.run(host="0.0.0.0", debug=True)

from flask import Flask, render_template, Response
import numpy as np
import cv2
from ultralytics import YOLO

RTSP_URL = "rtsp://169.254.50.82:8554/cam"
app = Flask(__name__)

model = YOLO(r"C:\Users\surin\OneDrive\Skrivebord\archive\Flame\runs\detect\flame-1\weights\best.pt")


def generate_frames():
    cap = cv2.VideoCapture(RTSP_URL)
    while True:
        success, frame = cap.read()
        if not success:
            break
        small_frame = cv2.resize(frame, (320, 240))
        results = model(small_frame, verbose=False)
        annotated_frame = results[0].plot()
        _, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)




    