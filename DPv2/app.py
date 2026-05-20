from flask import Flask, render_template, Response
import picamera2
import io

app = Flask(__name__)

""" def generate_frames():
    
    
    
    
    with picamera2.Picamera2() as camera:  # Fix 1: use picamera2 correctly
        camera.configure(camera.create_video_configuration(main={"size": (640, 480)}))
        camera.start()
        stream = io.BytesIO()  # Fix 2: BytesIO not bytesIO (capital B)

        while True:  # Fix 3: capture_continuous doesn't exist in picamera2
            stream.seek(0)
            stream.truncate()
            camera.capture_file(stream, format='jpeg')
            stream.seek(0)
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + stream.read() + b'\r\n' """

@app.route('/video_feed')
def video_feed():
    
    
    return render_template("video_feed.html")
    #return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')  # Fix 4: return ONLY Response, not a tuple

@app.route("/")
def home():
    return render_template("home.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)