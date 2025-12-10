# web_app.py - IMPEX Attendance System Web Application
# Flask-based web server for browser access

import os
import sys
import threading
import time
import base64
import json
from datetime import datetime, date
from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image
import io

# CRITICAL: Set environment variables BEFORE any imports
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
    'rtsp_transport;tcp|'
    'rtsp_flags;prefer_tcp|'
    'fflags;nobuffer|'
    'flags;low_delay|'
    'fflags;flush_packets|'
    'max_delay;500000|'
    'reorder_queue_size;0|'
    'buffer_size;32768'
)

os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
os.environ['OPENCV_VIDEOIO_PRIORITY_OBSENSOR'] = '0'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
os.environ['OPENCV_VIDEOIO_PRIORITY_FFMPEG'] = '1000'
os.environ['OPENCV_VIDEOIO_PRIORITY_DIRECTSHOW'] = '900'

# Setup Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import core modules
from core.face_engine import FaceRecognitionEngine
from core.database_manager import DatabaseManager
from core.config_manager import ConfigManager
from utils.camera_utils import CameraManager
from utils.gpu_utils import detect_gpu_capability

app = Flask(__name__, 
           template_folder='templates',
           static_folder='static')
CORS(app)  # Enable CORS for cross-origin requests

# Global variables
camera_manager = None
face_engine = None
db_manager = None
config = None
current_frame = None
current_detections = []
frame_lock = threading.Lock()
running = False
processing_thread = None
today_attendance = {}
captured_photos = {}
employee_id_map = {}
system_mode = 'checkin'  # Default mode
is_locked = False

def init_system(forced_mode=None):
    """Initialize system components
    
    Args:
        forced_mode: If provided, override config and lock to this mode ('checkin' or 'checkout')
    """
    global camera_manager, face_engine, db_manager, config, employee_id_map, system_mode, is_locked
    
    try:
        print("🚀 Initializing IMPEX Web Attendance System...")
        
        # Load configuration
        config = ConfigManager()
        system_config = config.get_system_config()
        
        # If forced_mode is provided, use it and lock the system
        if forced_mode:
            system_mode = forced_mode
            is_locked = True  # Lock mode when forced
            print(f"🔒 Mode locked to: {system_mode}")
        else:
            system_mode = system_config.get('system_mode', 'checkin')
            is_locked = system_config.get('locked_mode', False)
        
        db_path = system_config.get('database_path', 'data/factory_attendance.db')
        
        # Initialize database
        db_manager = DatabaseManager(db_path=db_path)
        
        # Initialize camera manager
        camera_manager = CameraManager()
        
        # Load employee IDs
        load_employee_ids()
        
        # Load today's attendance
        load_today_attendance()
        
        print(f"✅ System initialized - Mode: {system_mode}, Database: {db_path}")
        return True
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_employee_ids():
    """Load employee IDs from database"""
    global employee_id_map
    try:
        all_staff = db_manager.get_all_staff()
        employee_id_map = {}
        for staff in all_staff:
            staff_id = staff['staff_id']
            employee_id = staff.get('employee_id')
            if employee_id:
                employee_id_map[staff_id] = employee_id
            else:
                if staff_id.startswith('STAFF_'):
                    employee_id_map[staff_id] = staff_id.replace('STAFF_', '')
                else:
                    employee_id_map[staff_id] = staff_id
        print(f"✅ Loaded {len(employee_id_map)} employee IDs")
    except Exception as e:
        print(f"Error loading employee IDs: {e}")

def load_today_attendance():
    """Load today's attendance records"""
    global today_attendance
    try:
        today = date.today()
        attendance_records = db_manager.get_today_attendance(today)
        today_attendance = {}
        for record in attendance_records:
            staff_id = record['staff_id']
            today_attendance[staff_id] = {
                'staff_id': staff_id,
                'check_in_time': record.get('check_in_time'),
                'check_out_time': record.get('check_out_time'),
                'status': record.get('status', 'Present')
            }
        print(f"✅ Loaded {len(today_attendance)} attendance records")
    except Exception as e:
        print(f"Error loading attendance: {e}")
        today_attendance = {}

def get_employee_id(staff_id):
    """Get employee ID for staff"""
    return employee_id_map.get(staff_id, staff_id.replace('STAFF_', '') if staff_id.startswith('STAFF_') else staff_id)

def process_video_loop():
    """Process video frames in background thread"""
    global current_frame, current_detections, running, face_engine
    
    while running:
        try:
            frame = camera_manager.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue
            
            with frame_lock:
                current_frame = frame.copy()
            
            # Detect faces
            if face_engine:
                detections = face_engine.detect_faces(frame)
                detection_info = []
                
                for detection in detections:
                    bbox = detection['bbox']
                    embedding = detection['embedding']
                    det_confidence = detection.get('confidence', 0.0)
                    
                    # Identify person
                    person_type, person_id, rec_confidence = face_engine.identify_person(embedding)
                    
                    detection_info.append({
                        'bbox': bbox.tolist() if isinstance(bbox, np.ndarray) else list(bbox),
                        'confidence': float(det_confidence),
                        'person_type': person_type,
                        'person_id': person_id,
                        'recognition_confidence': float(rec_confidence) if rec_confidence else 0.0
                    })
                    
                    # Process attendance for staff
                    if person_type == 'staff' and person_id and rec_confidence >= 0.55:
                        process_attendance(person_id, frame, bbox, rec_confidence)
                
                with frame_lock:
                    current_detections = detection_info
            
            time.sleep(0.03)  # ~30 FPS processing
        except Exception as e:
            print(f"Processing error: {e}")
            time.sleep(0.1)

def process_attendance(staff_id, frame, bbox, confidence):
    """Process attendance for recognized staff"""
    global today_attendance, captured_photos
    
    try:
        now = datetime.now()
        current_time = time.time()
        
        # Debounce: only process once per 30 seconds per staff_id
        if not hasattr(process_attendance, 'last_processed'):
            process_attendance.last_processed = {}
        
        last_time = process_attendance.last_processed.get(staff_id, 0)
        if current_time - last_time < 30.0:
            return
        
        process_attendance.last_processed[staff_id] = current_time
        
        # Capture photo
        x1, y1, x2, y2 = map(int, bbox)
        x1 = max(0, x1 - 10)
        y1 = max(0, y1 - 10)
        x2 = min(frame.shape[1], x2 + 10)
        y2 = min(frame.shape[0], y2 + 10)
        
        captured_photo = frame[y1:y2, x1:x2].copy()
        captured_photos[staff_id] = captured_photo.tolist()  # Convert to list for JSON
        
        # Record attendance
        if system_mode == 'checkin':
            record_checkin(staff_id, now, float(confidence))
        else:
            record_checkout(staff_id, now, float(confidence))
            
    except Exception as e:
        print(f"Attendance processing error: {e}")

def record_checkin(staff_id, check_time, confidence):
    """Record check-in"""
    try:
        expected_time = datetime.strptime('09:00:00', '%H:%M:%S').time()
        is_late = check_time.time() > expected_time
        
        if is_late:
            minutes_late = int((check_time.time().hour * 60 + check_time.time().minute) - 
                             (expected_time.hour * 60 + expected_time.minute))
        else:
            minutes_late = 0
        
        status = f"{minutes_late} min Late" if is_late else "On Time"
        # Late minutes relative to 09:00 for event logging (every after-09:05 counts)
        late_minutes_event = max(0, int((check_time.time().hour * 60 + check_time.time().minute) - (expected_time.hour * 60 + expected_time.minute)))
        
        today_attendance[staff_id] = {
            'staff_id': staff_id,
            'check_in_time': check_time.isoformat(),
            'status': status,
            'confidence': float(confidence)
        }
        
        # Save to database
        db_manager.record_staff_attendance(staff_id, 'check_in', float(confidence))
        print(f"✅ Check-in: {staff_id} at {check_time.strftime('%I:%M %p')} - {status}")
    except Exception as e:
        print(f"Check-in error: {e}")

def record_checkout(staff_id, check_time, confidence):
    """Record check-out"""
    try:
        if staff_id in today_attendance:
            today_attendance[staff_id]['check_out_time'] = check_time.isoformat()
        else:
            today_attendance[staff_id] = {
                'staff_id': staff_id,
                'check_out_time': check_time.isoformat(),
                'confidence': float(confidence)
            }
        
        db_manager.record_staff_attendance(staff_id, 'check_out', float(confidence))
        print(f"✅ Check-out: {staff_id} at {check_time.strftime('%I:%M %p')}")
    except Exception as e:
        print(f"Check-out error: {e}")

def generate_frames():
    """Generate video frames with overlays for streaming"""
    global current_frame, current_detections
    
    while True:
        try:
            detections = []
            with frame_lock:
                if current_frame is None:
                    # Generate black frame with "Camera Disconnected" message
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, 'Camera Disconnected', (150, 240), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                else:
                    frame = current_frame.copy()
                    detections = current_detections.copy()
            
            # Draw face detection boxes
            for det in detections:
                bbox = det.get('bbox')
                if not bbox:
                    continue
                
                x1, y1, x2, y2 = map(int, bbox)
                person_type = det.get('person_type', 'unknown')
                person_id = det.get('person_id')
                rec_confidence = det.get('recognition_confidence', 0.0)
                
                # Draw bounding box
                color = (255, 144, 30)  # Blue
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
                
                # Add labels
                text_y = max(50, y1)
                cv2.putText(frame, 'FACIAL RECOGNITION', (x1, text_y - 40), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)
                cv2.putText(frame, 'HUMAN MOTION DETECTED', (x1, text_y - 18), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
                
                if person_type == 'staff' and person_id and rec_confidence >= 0.55:
                    employee_id = get_employee_id(person_id)
                    cv2.putText(frame, f'ID: {employee_id}', (x1, text_y - 2), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Overlay texts removed (impex / LIVE handled via HTML overlay images)
            
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                continue
            
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.033)  # ~30 FPS
            
        except Exception as e:
            print(f"Frame generation error: {e}")
            time.sleep(0.1)

# Flask Routes

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html', system_mode=system_mode, is_locked=is_locked)

@app.route('/checkin')
def checkin_page():
    """Check-in specific page"""
    return render_template('dashboard.html', system_mode=system_mode, is_locked=True, view_mode='checkin')

@app.route('/checkout')
def checkout_page():
    """Check-out specific page"""
    return render_template('dashboard.html', system_mode=system_mode, is_locked=True, view_mode='checkout')

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/attendance/today', methods=['GET'])
def get_today_attendance():
    """Get today's attendance records"""
    try:
        # Load fresh data
        today_data = db_manager.get_today_attendance()
        attendance_records = today_data.get('attendance', []) if isinstance(today_data, dict) else []
        checkin_events = today_data.get('checkins', []) if isinstance(today_data, dict) else []

        # Build attendance list from staff_attendance (unique per staff/day)
        attendance_list = []
        for att in attendance_records:
            staff_id = att.get('staff_id')
            staff_info = db_manager.get_staff_info(staff_id)
            employee_id = get_employee_id(staff_id)
            
            photo_data = None
            if staff_id in captured_photos:
                try:
                    photo_array = np.array(captured_photos[staff_id], dtype=np.uint8)
                    _, buffer = cv2.imencode('.jpg', photo_array)
                    photo_data = base64.b64encode(buffer).decode('utf-8')
                except Exception as e:
                    print(f"Error encoding photo for {staff_id}: {e}")
            
            attendance_list.append({
                'staff_id': staff_id,
                'employee_id': employee_id,
                'name': staff_info.get('name', 'Unknown') if staff_info else 'Unknown',
                'check_in_time': att.get('check_in_time').isoformat() if att.get('check_in_time') else None,
                'check_out_time': att.get('check_out_time').isoformat() if att.get('check_out_time') else None,
                'status': att.get('status', 'Present'),
                'photo': photo_data
            })

        # Build check-in events list (multiple per day)
        checkin_list = []
        for ev in checkin_events:
            staff_id = ev.get('staff_id')
            staff_info = db_manager.get_staff_info(staff_id)
            employee_id = get_employee_id(staff_id)
            check_time_raw = ev.get('check_time')
            check_time_iso = None
            if ev.get('date') and check_time_raw:
                check_time_iso = f"{ev['date']}T{check_time_raw}"

            photo_data = None
            if staff_id in captured_photos:
                try:
                    photo_array = np.array(captured_photos[staff_id], dtype=np.uint8)
                    _, buffer = cv2.imencode('.jpg', photo_array)
                    photo_data = base64.b64encode(buffer).decode('utf-8')
                except Exception as e:
                    print(f"Error encoding photo for {staff_id}: {e}")

            checkin_list.append({
                'staff_id': staff_id,
                'employee_id': employee_id,
                'name': staff_info.get('name', 'Unknown') if staff_info else 'Unknown',
                'check_time': check_time_iso,
                'status': ev.get('status', 'Present'),
                'late_minutes': ev.get('late_minutes', 0),
                'photo': photo_data
            })
        
        return jsonify({'attendance': attendance_list, 'checkins': checkin_list, 'mode': system_mode})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/staff/all', methods=['GET'])
def get_all_staff():
    """Get all staff members"""
    try:
        all_staff = db_manager.get_all_staff()
        staff_list = []
        for staff in all_staff:
            staff_list.append({
                'staff_id': staff['staff_id'],
                'employee_id': get_employee_id(staff['staff_id']),
                'name': staff.get('name', 'Unknown'),
                'department': staff.get('department', '')
            })
        return jsonify({'staff': staff_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/start', methods=['POST'])
def start_system():
    """Start face recognition system"""
    global running, face_engine, processing_thread
    
    try:
        if running:
            return jsonify({'status': 'already_running'})
        
        data = request.get_json(silent=True) or {}
        requested_mode = data.get('mode')
        if requested_mode in ['checkin', 'checkout']:
            global system_mode
            system_mode = requested_mode

        # Initialize face engine
        gpu_available = detect_gpu_capability()
        face_engine = FaceRecognitionEngine(gpu_mode=gpu_available)
        
        # Start camera
        if not camera_manager.start_camera():
            return jsonify({'error': 'Failed to start camera'}), 500
        
        running = True
        
        # Start processing thread
        processing_thread = threading.Thread(target=process_video_loop, daemon=True)
        processing_thread.start()
        
        return jsonify({'status': 'started', 'gpu_enabled': gpu_available})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/stop', methods=['POST'])
def stop_system():
    """Stop face recognition system"""
    global running
    
    try:
        running = False
        if camera_manager:
            camera_manager.stop_camera()
        return jsonify({'status': 'stopped'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/status', methods=['GET'])
def get_system_status():
    """Get system status"""
    camera_connected = False
    if camera_manager:
        camera_connected = camera_manager.cap.isOpened() if hasattr(camera_manager, 'cap') and camera_manager.cap else False
    
    return jsonify({
        'running': running,
        'mode': system_mode,
        'locked': is_locked,
        'camera_connected': camera_connected
    })

@app.route('/api/system/mode', methods=['POST'])
def set_mode():
    """Set attendance mode (if not locked)"""
    global system_mode
    
    if is_locked:
        return jsonify({'error': 'System is locked'}), 403
    
    data = request.json
    new_mode = data.get('mode')
    if new_mode in ['checkin', 'checkout']:
        system_mode = new_mode
        return jsonify({'status': 'updated', 'mode': system_mode})
    return jsonify({'error': 'Invalid mode'}), 400

if __name__ == '__main__':
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='IMPEX Attendance System Web Server')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on (default: 5000)')
    parser.add_argument('--mode', type=str, choices=['checkin', 'checkout'], default=None,
                       help='Lock system to this mode (checkin or checkout). If not provided, uses config.')
    
    args = parser.parse_args()
    
    # Initialize system with forced mode if provided
    forced_mode = args.mode if args.mode else None
    if not init_system(forced_mode=forced_mode):
        print("❌ Failed to initialize system")
        sys.exit(1)
    
    # Get configuration
    host = '0.0.0.0'  # Listen on all interfaces
    port = args.port
    
    print("=" * 70)
    print("🌐 IMPEX ATTENDANCE SYSTEM - WEB SERVER")
    print("=" * 70)
    print(f"📍 Server starting on: http://localhost:{port}")
    print(f"📍 Network access: http://<your-ip>:{port}")
    print(f"📍 System Mode: {system_mode.upper()}")
    print(f"📍 Locked: {is_locked}")
    print("=" * 70)
    if system_mode == 'checkin':
        print(f"💡 Check-In Page: http://localhost:{port}/checkin")
    else:
        print(f"💡 Check-Out Page: http://localhost:{port}/checkout")
    print("=" * 70)
    
    # Run Flask app
    app.run(host=host, port=port, debug=False, threaded=True)

