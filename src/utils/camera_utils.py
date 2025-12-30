# src/utils/camera_utils.py
import cv2
import threading
import time
from queue import Queue
import os


def check_camera_permissions():
    """Check if camera access is available"""
    try:
        # Quick test to see if any camera is accessible
        for i in range(3):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret:
                    return True, i
            if cap:
                cap.release()

        return False, None

    except Exception as e:
        print(f"Camera permission check failed: {e}")
        return False, None


def get_available_cameras():
    """Get list of available camera indices"""
    available_cameras = []

    for index in range(10):
        try:
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    available_cameras.append(index)
                    print(f"Camera available at index: {index}")
            cap.release()
        except:
            continue

    return available_cameras


def find_working_camera_index():
    """Find the first working camera index with backend selection"""
    # Set environment to disable OBSENSOR
    import os
    os.environ['OPENCV_VIDEOIO_PRIORITY_OBSENSOR'] = '0'
    os.environ['OPENCV_VIDEOIO_PRIORITY_DIRECTSHOW'] = '1000'

    backends_to_try = [cv2.CAP_DSHOW, cv2.CAP_V4L2, cv2.CAP_ANY]

    for backend in backends_to_try:
        print(f"Testing backend: {backend}")
        for index in range(10):
            try:
                cap = cv2.VideoCapture(index, backend)
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None:
                        print(f"✅ Working camera found at index: {index} with backend: {backend}")
                        return index, backend
                cap.release()
            except Exception as e:
                continue

    print("❌ No working camera found with any backend")
    return None, None


class CameraManager:
    def __init__(self):
        from core.config_manager import ConfigManager
        self.config = ConfigManager()

        # Find working camera index
        self.working_camera_index = find_working_camera_index()

        self.cap = None
        self.frame_queue = Queue(maxsize=1)  # Single frame buffer for lowest latency
        self.running = False
        self.capture_thread = None
    
    def _get_rtsp_options(self):
        """Get RTSP transport options based on camera_settings.json"""
        camera_settings = self.config.get_camera_settings()
        transport = camera_settings.get('transport', 'TCP').upper()
        
        if transport == 'UDP':
            rtsp_transport = 'udp'
        else:
            rtsp_transport = 'tcp'  # Default to TCP
        
        # Build RTSP options string
        options = (
            f'rtsp_transport;{rtsp_transport}|'
            'fflags;nobuffer|'
            'flags;low_delay|'
            'framedrop;1|'  # Drop frames to reduce latency
            'strict;experimental|'
            'tune;zerolatency|'  # Zero latency tuning
            'preset;ultrafast|'  # Fastest encoding preset
            'buffer_size;512000|'  # Smaller buffer
            'max_delay;0|'  # No delay tolerance
            'reorder_queue_size;0|'  # No reordering
            'sync;ext'  # External sync
        )
        
        return options, rtsp_transport

    def start_camera(self):
        """Start camera with automatic index detection and backend selection"""
        try:
            camera_settings = self.config.get_camera_settings()
            print(f"🚀 Starting camera with settings: {camera_settings}")

            if camera_settings.get('source_type') == 'usb':
                # USB camera path
                camera_index, backend = find_working_camera_index()
                if camera_index is not None:
                    print(f"📹 Using USB camera index: {camera_index} with backend: {backend}")
                    return self._attempt_connection(camera_index, backend)
                else:
                    print("❌ No working USB camera found")
                    return False
            else:
                # RTSP camera path - Load from camera_settings.json
                camera_source = camera_settings.get('rtsp_url')
                transport = camera_settings.get('transport', 'TCP').upper()
                print(f"📹 Connecting to RTSP camera: {camera_source} (Transport: {transport})")

                # Set RTSP environment variables based on transport setting from camera_settings.json
                rtsp_options, rtsp_transport = self._get_rtsp_options()
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = rtsp_options
                print(f"🔧 Using RTSP transport: {rtsp_transport} (from camera_settings.json)")

                # CRITICAL: Actually attempt the connection
                if self._attempt_connection(camera_source, cv2.CAP_FFMPEG):
                    return True
                print("❌ Initial connection failed. Rediscovery is disabled to preserve configured IP.")
                return False

        except Exception as e:
            print(f"❌ Camera start error: {e}")
            return False

    def _attempt_connection(self, camera_source, backend=cv2.CAP_ANY):
        """Ultra-low latency camera connection optimized for EZVIZ"""
        try:
            print(f"🔌 Attempting ultra-low latency connection to {camera_source}")

            # RTSP settings based on camera_settings.json
            if isinstance(camera_source, str) and 'rtsp://' in camera_source:
                # Set RTSP options based on transport setting from camera_settings.json
                rtsp_options, rtsp_transport = self._get_rtsp_options()
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = rtsp_options
                print(f"🔧 RTSP connection using transport: {rtsp_transport} (from camera_settings.json)")

            self.cap = cv2.VideoCapture(camera_source, backend)

            if not self.cap.isOpened():
                print(f"❌ Failed to open camera source: {camera_source}")
                return False

            # Get settings from camera_settings.json
            camera_settings = self.config.get_camera_settings()
            buffer_size = camera_settings.get('buffer_size', 1)  # Lower buffer = less lag
            target_fps = camera_settings.get('fps', 30)  # Increased default FPS
            
            # Apply buffer size and FPS from camera_settings.json - OPTIMIZED FOR LOW LATENCY
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimum buffer for lowest latency
            self.cap.set(cv2.CAP_PROP_FPS, target_fps)
            print(f"🔧 Camera buffer_size: 1 (optimized), fps: {target_fps} (from camera_settings.json)")

            # Additional EZVIZ optimizations
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('H', '2', '6', '4'))

            # Test connection with timeout
            start_time = time.time()
            for attempt in range(5):  # Reduced attempts for faster startup
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    connection_time = time.time() - start_time
                    print(f"✅ Ultra-low latency connection established in {connection_time:.2f}s")

                    # Start optimized capture thread
                    self.running = True
                    self.capture_thread = threading.Thread(target=self._ultra_low_latency_capture, daemon=True)
                    self.capture_thread.start()

                    return True
                time.sleep(0.2)

            print("❌ Failed to establish stable connection")
            self.cap.release()
            return False

        except Exception as e:
            print(f"❌ Connection attempt error: {e}")
            return False

    def _update_ip_and_retry(self):
        """Scan the network for the camera, update IP, and retry connection"""
        try:
            new_ip = self._scan_for_camera()
            if not new_ip:
                return False
            self.config.update_camera_ip(new_ip)
            new_url = self.config.get_camera_settings().get('rtsp_url')
            print(f"🔄 Retrying connection with new IP: {new_url}")
            return self._attempt_connection(new_url, cv2.CAP_FFMPEG)
        except Exception as e:
            print(f"❌ IP update retry error: {e}")
            return False

    def _scan_for_camera(self, network_range="192.168.1.0/24"):
        """Scan network to find a reachable camera"""
        try:
            import ipaddress
            network = ipaddress.IPv4Network(network_range, strict=False)
            for ip in network.hosts():
                ip_str = str(ip)
                if self._test_port(ip_str, 554):
                    print(f"📡 Camera discovered at {ip_str}")
                    return ip_str
        except Exception as e:
            print(f"❌ Scan error: {e}")
        return None

    def _test_port(self, ip, port):
        """Check if a TCP port is open"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _ultra_low_latency_capture(self):
        """Ultra-optimized frame capture with latency reduction - ensures first frame is immediately available"""
        consecutive_failures = 0
        max_failures = 5  # Reduced for faster failure detection
        frame_count = 0
        first_frame_processed = False

        while self.running and self.cap:
            try:
                if not self.cap.isOpened():
                    time.sleep(0.05)
                    continue

                # For first frame, don't skip - process immediately to start detection ASAP
                # After first frame, skip buffered frames to get latest (reduces latency)
                if not first_frame_processed:
                    # Process first frame immediately - no skipping
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        first_frame_processed = True
                        frame_count += 1
                        print("✅ First frame captured - Face detection will start immediately")
                        # Put first frame in queue for immediate processing
                        try:
                            if not self.frame_queue.empty():
                                self.frame_queue.get_nowait()
                            self.frame_queue.put_nowait(frame)
                        except:
                            pass
                    else:
                        time.sleep(0.01)
                    continue
                else:
                    # Skip frames in buffer to get latest (reduces latency) - OPTIMIZED
                    for _ in range(3):  # Skip 3 frames to get freshest frame (reduces lag)
                        ret, _ = self.cap.read()
                        if not ret:
                            break

                    # Get the latest frame
                    ret, frame = self.cap.read()

                if ret and frame is not None:
                    consecutive_failures = 0
                    frame_count += 1

                    # Clear old frames from queue aggressively
                    while not self.frame_queue.empty():
                        try:
                            self.frame_queue.get_nowait()
                        except:
                            break

                    # Only keep the latest frame
                    try:
                        self.frame_queue.put_nowait(frame)
                    except:
                        pass  # Queue full, skip this frame

                    if frame_count % 100 == 0:
                        print(f"📹 Ultra-low latency capture: {frame_count} frames processed")

                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        print("❌ Too many consecutive failures in ultra-low latency mode")
                        break

                    time.sleep(0.01)  # Minimal pause

            except Exception as e:
                print(f"❌ Ultra-low latency capture error: {e}")
                consecutive_failures += 1
                time.sleep(0.01)

        print("🛑 Ultra-low latency capture thread stopped")

    def _capture_frames(self):
        """Enhanced frame capture with stability improvements - ensures first frame is immediately available"""
        consecutive_failures = 0
        max_failures = 10
        frame_count = 0
        last_frame = None  # Keep last good frame for stability
        first_frame_processed = False

        while self.running and self.cap:
            try:
                if not self.cap.isOpened():
                    time.sleep(0.1)
                    continue

                ret, frame = self.cap.read()

                if ret and frame is not None:
                    consecutive_failures = 0
                    frame_count += 1
                    last_frame = frame.copy()  # Store last good frame
                    
                    # Log first frame to confirm immediate capture
                    if not first_frame_processed:
                        first_frame_processed = True
                        print("✅ First frame captured - Face detection will start immediately")

                    # Clear old frames from queue
                    while self.frame_queue.full():
                        try:
                            self.frame_queue.get_nowait()
                        except:
                            break

                    self.frame_queue.put(frame)

                    if frame_count % 100 == 0:
                        print(f"📹 Captured {frame_count} frames successfully")

                else:
                    consecutive_failures += 1

                    # Use last good frame to prevent black frames
                    if last_frame is not None and consecutive_failures < 5:
                        if not self.frame_queue.full():
                            self.frame_queue.put(last_frame)

                    if consecutive_failures >= max_failures:
                        print("❌ Too many consecutive failures")
                        break

                    time.sleep(0.05)  # Slightly longer pause for recovery

            except Exception as e:
                print(f"❌ Frame capture error: {e}")
                consecutive_failures += 1
                time.sleep(0.05)

    def _attempt_reconnect(self):
        """Attempt to reconnect camera"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            print("❌ Max reconnect attempts reached")
            return False

        self.reconnect_attempts += 1
        print(f"🔄 Reconnect attempt {self.reconnect_attempts}")

        if self.cap:
            self.cap.release()

        time.sleep(2)

        camera_settings = self.config.get_camera_settings()
        camera_source = camera_settings.get('rtsp_url')

        return self._attempt_connection(camera_source)

    def get_frame(self):
        """Get latest frame"""
        try:
            if not self.frame_queue.empty():
                return self.frame_queue.get_nowait()
        except:
            pass
        return None

    def stop_camera(self):
        """Stop camera"""
        print("🛑 Stopping camera...")
        self.running = False

        if self.capture_thread:
            self.capture_thread.join(timeout=3)

        if self.cap:
            self.cap.release()
            self.cap = None

        # Clear queue
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except:
                break

        print("✅ Camera stopped")

    @staticmethod
    def get_camera_for_capture():
        """Get camera source for photo capture (prioritizes configured camera from camera_settings.json)"""
        try:
            from core.config_manager import ConfigManager
            config = ConfigManager()
            camera_settings = config.get_camera_settings()

            if camera_settings.get('source_type') in ['rtsp', 'ip']:
                # Use RTSP camera from camera_settings.json
                rtsp_url = camera_settings.get('rtsp_url')
                transport = camera_settings.get('transport', 'TCP').upper()
                rtsp_transport = 'udp' if transport == 'UDP' else 'tcp'
                
                print(f"📹 Using RTSP camera for capture: {rtsp_url} (Transport: {rtsp_transport} from camera_settings.json)")

                # Set RTSP options based on transport from camera_settings.json
                rtsp_options = (
                    f'rtsp_transport;{rtsp_transport}|'
                    'fflags;nobuffer|'
                    'flags;low_delay'
                )
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = rtsp_options

                cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        cap.release()
                        return rtsp_url, cv2.CAP_FFMPEG
                cap.release()

            # Fallback to USB camera detection
            camera_index, backend = find_working_camera_index()
            if camera_index is not None:
                return camera_index, backend

            return None, None

        except Exception as e:
            print(f"Camera source detection error: {e}")
            return None, None

    def is_connected(self):
        """Check connection status"""
        return self.running and self.cap and self.cap.isOpened()
