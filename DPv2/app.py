from flask import Flask, render_template, Response
import picamera2
import io
from picamera2.outputs import FfmpegOutput
from picamera2 import Picamera2
import time
from picamera2.encoders import H264Encoder

app = Flask(__name__)

@app.route('/video_feed')
def video_feed():
    return render_template("video_feed.html")
    

@app.route("/")
def home():
    return render_template("home.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)