import cv2
import os

# Set UDP transport
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'

rtsp_url = "rtsp://admin:Ikhlas@123@192.168.1.12:554/h264/ch1/main/av_stream"

print(f"Testing camera connection: {rtsp_url}")

cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

if cap.isOpened():
    print("✅ Camera connection successful!")

    # Try to read a frame
    for i in range(10):
        ret, frame = cap.read()
        if ret:
            print(f"✅ Frame {i + 1} captured: {frame.shape}")
            cv2.imshow('Test Feed', frame)
            cv2.waitKey(1000)  # Show for 1 second
            break
        else:
            print(f"❌ Frame {i + 1} failed")

    cv2.destroyAllWindows()
else:
    print("❌ Camera connection failed!")

cap.release()
