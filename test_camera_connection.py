#!/usr/bin/env python3
"""
Diagnostic script to test camera connectivity at 192.168.29.12
Tests HTTP web interface, RTSP streams, and network connectivity
"""

import cv2
import socket
import requests
import time
from urllib.parse import urlparse

CAMERA_IP = "192.168.29.12"
RTSP_PORT = 554
HTTP_PORT = 80
USERNAME = "admin"
PASSWORD = "123456"

# Common RTSP stream paths for different camera brands
RTSP_PATHS = [
    "",  # No path (base RTSP)
    "/stream1",
    "/stream2",
    "/Streaming/Channels/101",  # Hikvision
    "/Streaming/Channels/1",    # Hikvision alternative
    "/cam/realmonitor",         # Dahua
    "/live",                    # Generic
    "/h264/ch1/main/av_stream", # Some IP cameras
    "/h264",                    # Generic H.264
    "/videoMain",               # Some cameras
    "/video",                   # Generic
]

def test_port(host, port, timeout=3):
    """Test if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"❌ Port test error: {e}")
        return False

def test_http_interface(ip, port=80):
    """Test HTTP web interface"""
    print(f"\n🌐 Testing HTTP web interface at http://{ip}:{port}")
    
    urls_to_test = [
        f"http://{ip}:{port}/",
        f"http://{ip}:{port}/#/home/live",
        f"http://{USERNAME}:{PASSWORD}@{ip}:{port}/",
        f"http://{USERNAME}:{PASSWORD}@{ip}:{port}/#/home/live",
    ]
    
    for url in urls_to_test:
        try:
            print(f"  Testing: {url}")
            response = requests.get(url, timeout=5, auth=(USERNAME, PASSWORD) if '@' not in url else None)
            print(f"  ✅ Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✅ Successfully connected to HTTP interface!")
                return True
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Failed: {e}")
    
    return False

def test_rtsp_stream(rtsp_url, transport='tcp'):
    """Test RTSP stream connection"""
    print(f"\n📹 Testing RTSP stream: {rtsp_url} (transport: {transport})")
    
    # Set RTSP transport
    os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = f'rtsp_transport;{transport}'
    
    try:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        
        if not cap.isOpened():
            print(f"  ❌ Cannot open RTSP stream")
            return False
        
        print(f"  ✅ Stream opened, attempting to read frame...")
        
        # Try to read a frame with timeout
        start_time = time.time()
        timeout = 10
        
        for attempt in range(5):
            ret, frame = cap.read()
            if ret and frame is not None:
                height, width = frame.shape[:2]
                elapsed = time.time() - start_time
                print(f"  ✅ Success! Frame captured: {width}x{height} (took {elapsed:.2f}s)")
                cap.release()
                return True
            time.sleep(1)
        
        print(f"  ❌ Cannot read frames from stream")
        cap.release()
        return False
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    import os
    
    print("=" * 60)
    print(f"🔍 Camera Diagnostic Tool for {CAMERA_IP}")
    print("=" * 60)
    
    # Test 1: Basic network connectivity
    print(f"\n1️⃣ Testing network connectivity...")
    if test_port(CAMERA_IP, RTSP_PORT):
        print(f"  ✅ RTSP port {RTSP_PORT} is open")
    else:
        print(f"  ❌ RTSP port {RTSP_PORT} is closed or unreachable")
    
    if test_port(CAMERA_IP, HTTP_PORT):
        print(f"  ✅ HTTP port {HTTP_PORT} is open")
    else:
        print(f"  ❌ HTTP port {HTTP_PORT} is closed or unreachable")
    
    # Test 2: HTTP web interface
    print(f"\n2️⃣ Testing HTTP web interface...")
    http_works = test_http_interface(CAMERA_IP, HTTP_PORT)
    
    # Test 3: RTSP streams with different paths
    print(f"\n3️⃣ Testing RTSP streams with different paths...")
    working_streams = []
    
    for path in RTSP_PATHS:
        if path:
            rtsp_url = f"rtsp://{USERNAME}:{PASSWORD}@{CAMERA_IP}:{RTSP_PORT}{path}"
        else:
            rtsp_url = f"rtsp://{USERNAME}:{PASSWORD}@{CAMERA_IP}:{RTSP_PORT}"
        
        if test_rtsp_stream(rtsp_url, 'tcp'):
            working_streams.append(rtsp_url)
            print(f"\n  ✅ WORKING STREAM FOUND: {rtsp_url}")
            break
    
    # Try UDP if TCP didn't work
    if not working_streams:
        print(f"\n  🔄 Trying UDP transport...")
        for path in RTSP_PATHS[:3]:  # Try first few paths with UDP
            if path:
                rtsp_url = f"rtsp://{USERNAME}:{PASSWORD}@{CAMERA_IP}:{RTSP_PORT}{path}"
            else:
                rtsp_url = f"rtsp://{USERNAME}:{PASSWORD}@{CAMERA_IP}:{RTSP_PORT}"
            
            if test_rtsp_stream(rtsp_url, 'udp'):
                working_streams.append(rtsp_url)
                print(f"\n  ✅ WORKING STREAM FOUND (UDP): {rtsp_url}")
                break
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"HTTP Web Interface: {'✅ Accessible' if http_works else '❌ Not accessible'}")
    print(f"RTSP Streams Found: {len(working_streams)}")
    
    if working_streams:
        print(f"\n✅ Recommended RTSP URL:")
        print(f"   {working_streams[0]}")
    else:
        print(f"\n❌ No working RTSP streams found")
        print(f"\n💡 Troubleshooting tips:")
        print(f"   1. Verify camera IP address: {CAMERA_IP}")
        print(f"   2. Check username/password: {USERNAME}/{PASSWORD}")
        print(f"   3. Ensure camera is powered on and connected to network")
        print(f"   4. Check firewall settings")
        print(f"   5. Try accessing web interface directly in browser")
        print(f"   6. Verify RTSP is enabled on camera")

if __name__ == "__main__":
    main()

