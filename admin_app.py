# admin_app.py - IMPEX Attendance System Admin Web Application
# Comprehensive admin panel with all management features

import os
import sys
import threading
import time
import base64
import json
from datetime import datetime, date, timedelta
from flask import Flask, render_template, Response, jsonify, request, send_file
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image
import io
import csv
import sqlite3
from sklearn.metrics.pairwise import cosine_similarity

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
from utils.report_generator import ReportGenerator

app = Flask(__name__, 
           template_folder='templates',
           static_folder='static')
CORS(app)

# Global variables
db_manager = None
config = None
face_engine = None
report_generator = None
camera_manager = None

def init_admin_system():
    """Initialize admin system components"""
    global db_manager, config, face_engine, report_generator
    
    try:
        print("🚀 Initializing IMPEX Admin System...")
        
        # Load configuration
        config = ConfigManager()
        system_config = config.get_system_config()
        db_path = system_config.get('database_path', 'data/factory_attendance.db')
        
        # Initialize database
        db_manager = DatabaseManager(db_path=db_path)
        
        # Initialize report generator
        report_generator = ReportGenerator()
        
        print(f"✅ Admin system initialized - Database: {db_path}")
        return True
    except Exception as e:
        print(f"❌ Admin initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==================== ROUTES ====================

@app.route('/')
def admin_index():
    """Admin dashboard page"""
    return render_template('admin.html')

# ==================== STAFF MANAGEMENT API ====================

@app.route('/api/admin/staff/all', methods=['GET'])
def get_all_staff_admin():
    """Get all staff members with full details"""
    try:
        all_staff = db_manager.get_all_staff()
        staff_list = []
        for staff in all_staff:
            # Get employee ID
            employee_id = staff.get('employee_id')
            if not employee_id:
                if staff['staff_id'].startswith('STAFF_'):
                    employee_id = staff['staff_id'].replace('STAFF_', '')
                else:
                    employee_id = staff['staff_id']
            
            # Get attendance stats
            today = date.today()
            attendance_data = db_manager.get_today_attendance(today)
            attendance_records = attendance_data.get('attendance', []) if isinstance(attendance_data, dict) else []
            
            staff_attendance = next((a for a in attendance_records if a.get('staff_id') == staff['staff_id']), None)
            
            staff_list.append({
                'staff_id': staff['staff_id'],
                'employee_id': employee_id,
                'name': staff.get('name', 'Unknown'),
                'department': staff.get('department', ''),
                'added_date': staff.get('added_date', ''),
                'is_active': staff.get('is_active', True),
                'has_photo': staff.get('photo') is not None,
                'today_check_in': staff_attendance.get('check_in_time').isoformat() if staff_attendance and staff_attendance.get('check_in_time') else None,
                'today_check_out': staff_attendance.get('check_out_time').isoformat() if staff_attendance and staff_attendance.get('check_out_time') else None,
                'today_status': staff_attendance.get('status') if staff_attendance else 'Absent'
            })
        return jsonify({'success': True, 'staff': staff_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/staff/add', methods=['POST'])
def add_staff_admin():
    """Add new staff member with duplicate detection and multiple photo support"""
    try:
        data = request.get_json()
        staff_id = data.get('staff_id', '').strip()
        name = data.get('name', '').strip()
        department = data.get('department', '').strip()
        photos_data = data.get('photos')  # Array of base64 encoded images (for 5-angle capture)
        photo_data = data.get('photo')  # Single base64 encoded image (fallback)
        
        if not staff_id or not name:
            return jsonify({'success': False, 'error': 'Staff ID and Name are required'}), 400
        
        # Check for duplicate by staff_id first
        existing_staff = db_manager.get_staff_info(staff_id)
        if existing_staff:
            # Remove duplicate with same staff_id
            print(f"⚠️ Duplicate staff_id found: {staff_id}. Removing existing entry...")
            db_manager.delete_staff_member(staff_id)
        
        # Decode photos - handle both array and single photo
        photo_arrays = []
        
        if photos_data and isinstance(photos_data, list) and len(photos_data) > 0:
            # Multiple photos from 5-angle capture
            for idx, photo_data_item in enumerate(photos_data):
                try:
                    if ',' in photo_data_item:
                        photo_data_item = photo_data_item.split(',')[1]
                    photo_bytes = base64.b64decode(photo_data_item)
                    nparr = np.frombuffer(photo_bytes, np.uint8)
                    photo_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if photo_array is not None:
                        photo_arrays.append(photo_array)
                except Exception as e:
                    print(f"Photo {idx+1} decode error: {e}")
        elif photo_data:
            # Single photo fallback
            try:
                if ',' in photo_data:
                    photo_data = photo_data.split(',')[1]
                photo_bytes = base64.b64decode(photo_data)
                nparr = np.frombuffer(photo_bytes, np.uint8)
                photo_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if photo_array is not None:
                    photo_arrays.append(photo_array)
            except Exception as e:
                print(f"Photo decode error: {e}")
        
        if len(photo_arrays) == 0:
            return jsonify({'success': False, 'error': 'At least one photo is required'}), 400
        
        # Initialize face engine for embedding extraction
        gpu_available = detect_gpu_capability()
        face_engine = FaceRecognitionEngine(gpu_mode=gpu_available)
        
        # Extract embeddings from all photos
        embeddings = []
        valid_photos = []
        
        for idx, photo_array in enumerate(photo_arrays):
            detections = face_engine.detect_faces(photo_array)
            
            if not detections:
                print(f"⚠️ No face detected in photo {idx+1}")
                continue
            
            if len(detections) > 1:
                print(f"⚠️ Multiple faces detected in photo {idx+1}, using first face")
            
            embeddings.append(detections[0]['embedding'])
            valid_photos.append(photo_array)
        
        if len(embeddings) == 0:
            return jsonify({'success': False, 'error': 'No faces detected in any photo'}), 400
        
        if len(embeddings) < 3:
            return jsonify({'success': False, 'error': f'At least 3 photos with faces are required. Found {len(embeddings)} valid photos.'}), 400
        
        # Average embeddings from all photos for better recognition
        avg_embedding = np.mean(embeddings, axis=0)
        
        # Check for duplicate by face similarity
        all_staff = db_manager.get_all_staff()
        duplicate_found = False
        duplicate_staff_id = None
        
        for staff in all_staff:
            if staff.get('embedding') is None:
                continue
            
            try:
                import pickle
                existing_embedding = pickle.loads(staff['embedding'])
                
                # Calculate cosine similarity
                similarity = cosine_similarity([avg_embedding], [existing_embedding])[0][0]
                
                # Threshold for duplicate detection (0.85 = 85% similarity)
                if similarity > 0.85:
                    duplicate_found = True
                    duplicate_staff_id = staff['staff_id']
                    print(f"⚠️ Duplicate face found: {staff_id} matches existing {duplicate_staff_id} (similarity: {similarity:.3f})")
                    break
            except Exception as e:
                print(f"Error checking similarity with {staff.get('staff_id')}: {e}")
                continue
        
        # Remove duplicate if found
        if duplicate_found and duplicate_staff_id:
            print(f"🗑️ Removing duplicate staff member: {duplicate_staff_id}")
            db_manager.delete_staff_member(duplicate_staff_id)
        
        # Use the first valid photo for storage (or you could store all photos)
        primary_photo = valid_photos[0]
        
        # Get showcase photo if provided
        showcase_photo = None
        showcase_photo_data = data.get('showcase_photo')
        if showcase_photo_data:
            try:
                if ',' in showcase_photo_data:
                    showcase_photo_data = showcase_photo_data.split(',')[1]
                photo_bytes = base64.b64decode(showcase_photo_data)
                nparr = np.frombuffer(photo_bytes, np.uint8)
                showcase_photo = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            except Exception as e:
                print(f"Showcase photo decode error: {e}")
        
        # Save to database with averaged embedding
        success = db_manager.add_staff_member(staff_id, name, department, avg_embedding, primary_photo, showcase_photo)
        
        if success:
            message = f'Staff member added successfully with {len(embeddings)} photos'
            if duplicate_found:
                message += f' (removed duplicate: {duplicate_staff_id})'
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': 'Failed to add staff member'}), 500
            
    except Exception as e:
        print(f"Error adding staff: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/staff/update', methods=['POST'])
def update_staff_admin():
    """Update staff member"""
    try:
        data = request.get_json()
        staff_id = data.get('staff_id', '').strip()
        name = data.get('name', '').strip()
        department = data.get('department', '').strip()
        photo_data = data.get('photo')  # Optional, base64 encoded
        
        if not staff_id:
            return jsonify({'success': False, 'error': 'Staff ID is required'}), 400
        
        # Get existing staff info
        staff_info = db_manager.get_staff_info(staff_id)
        if not staff_info:
            return jsonify({'success': False, 'error': 'Staff member not found'}), 404
        
        # Update basic info
        if name:
            conn = db_manager.lock
            with db_manager.lock:
                import sqlite3
                conn = sqlite3.connect(db_manager.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE staff SET name = ?, department = ?
                    WHERE staff_id = ?
                ''', (name, department, staff_id))
                conn.commit()
                conn.close()
        
        # Update photo if provided
        if photo_data:
            try:
                if ',' in photo_data:
                    photo_data = photo_data.split(',')[1]
                photo_bytes = base64.b64decode(photo_data)
                nparr = np.frombuffer(photo_bytes, np.uint8)
                photo_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if photo_array is not None:
                    # Extract new embedding
                    gpu_available = detect_gpu_capability()
                    face_engine = FaceRecognitionEngine(gpu_mode=gpu_available)
                    detections = face_engine.detect_faces(photo_array)
                    
                    if detections:
                        embedding = detections[0]['embedding']
                        # Update embedding and photo
                        with db_manager.lock:
                            import sqlite3
                            conn = sqlite3.connect(db_manager.db_path)
                            cursor = conn.cursor()
                            import pickle
                            embedding_blob = pickle.dumps(embedding)
                            success, buffer = cv2.imencode('.jpg', photo_array)
                            photo_blob = buffer.tobytes() if success else None
                            
                            if photo_blob:
                                cursor.execute('''
                                    UPDATE staff SET embedding = ?, photo = ?
                                    WHERE staff_id = ?
                                ''', (embedding_blob, photo_blob, staff_id))
                            else:
                                cursor.execute('''
                                    UPDATE staff SET embedding = ?
                                    WHERE staff_id = ?
                                ''', (embedding_blob, staff_id))
                            conn.commit()
                            conn.close()
            except Exception as e:
                print(f"Photo update error: {e}")
        
        # Update showcase photo if provided (separate from regular photo)
        showcase_photo_data = data.get('showcase_photo')
        if showcase_photo_data:
            try:
                if ',' in showcase_photo_data:
                    showcase_photo_data = showcase_photo_data.split(',')[1]
                photo_bytes = base64.b64decode(showcase_photo_data)
                nparr = np.frombuffer(photo_bytes, np.uint8)
                showcase_photo_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if showcase_photo_array is not None:
                    db_manager.update_staff_showcase_photo(staff_id, showcase_photo_array)
            except Exception as e:
                print(f"Showcase photo update error: {e}")
        
        return jsonify({'success': True, 'message': 'Staff member updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/staff/delete', methods=['POST'])
def delete_staff_admin():
    """Delete staff member"""
    try:
        data = request.get_json()
        staff_id = data.get('staff_id', '').strip()
        
        if not staff_id:
            return jsonify({'success': False, 'error': 'Staff ID is required'}), 400
        
        success = db_manager.delete_staff_member(staff_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Staff member deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete staff member'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/staff/<staff_id>/photo', methods=['GET'])
def get_staff_photo(staff_id):
    """Get staff photo"""
    try:
        staff_info = db_manager.get_staff_info(staff_id)
        if staff_info and staff_info.get('photo'):
            photo_blob = staff_info['photo']
            return Response(photo_blob, mimetype='image/jpeg')
        else:
            # Return placeholder image
            img = Image.new('RGB', (200, 200), color='gray')
            img_io = io.BytesIO()
            img.save(img_io, 'JPEG')
            img_io.seek(0)
            return Response(img_io, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/staff/<staff_id>/showcase-photo', methods=['GET'])
def get_staff_showcase_photo(staff_id):
    """Get staff showcase photo (for display during detection)"""
    try:
        showcase_photo = db_manager.get_staff_showcase_photo(staff_id)
        if showcase_photo is not None:
            success, buffer = cv2.imencode('.jpg', showcase_photo)
            if success:
                return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # Return placeholder if no showcase photo
        img = Image.new('RGB', (300, 400), color='gray')
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG')
        img_io.seek(0)
        return Response(img_io, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/staff/<staff_id>/showcase-photo', methods=['POST'])
def update_staff_showcase_photo(staff_id):
    """Update showcase photo for staff member"""
    try:
        data = request.get_json()
        photo_data = data.get('photo')  # Base64 encoded image
        
        if not photo_data:
            return jsonify({'success': False, 'error': 'Photo data is required'}), 400
        
        # Decode photo
        try:
            if ',' in photo_data:
                photo_data = photo_data.split(',')[1]
            photo_bytes = base64.b64decode(photo_data)
            nparr = np.frombuffer(photo_bytes, np.uint8)
            photo_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if photo_array is not None:
                success = db_manager.update_staff_showcase_photo(staff_id, photo_array)
                if success:
                    return jsonify({'success': True, 'message': 'Showcase photo updated successfully'})
                else:
                    return jsonify({'success': False, 'error': 'Failed to update showcase photo'}), 500
            else:
                return jsonify({'success': False, 'error': 'Invalid image data'}), 400
        except Exception as e:
            print(f"Photo decode error: {e}")
            return jsonify({'success': False, 'error': f'Failed to decode image: {str(e)}'}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== ATTENDANCE API ====================

@app.route('/api/admin/attendance/today', methods=['GET'])
def get_today_attendance_admin():
    """Get today's attendance with full details"""
    try:
        target_date = request.args.get('date')
        if target_date:
            try:
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            except:
                target_date = date.today()
        else:
            target_date = date.today()
        
        attendance_data = db_manager.get_today_attendance(target_date)
        attendance_records = attendance_data.get('attendance', []) if isinstance(attendance_data, dict) else []
        checkin_events = attendance_data.get('checkins', []) if isinstance(attendance_data, dict) else []
        
        # Enrich with staff info
        attendance_list = []
        for att in attendance_records:
            staff_id = att.get('staff_id')
            staff_info = db_manager.get_staff_info(staff_id)
            
            employee_id = staff_info.get('employee_id') if staff_info else None
            if not employee_id and staff_id:
                if staff_id.startswith('STAFF_'):
                    employee_id = staff_id.replace('STAFF_', '')
                else:
                    employee_id = staff_id
            
            attendance_list.append({
                'staff_id': staff_id,
                'employee_id': employee_id,
                'name': staff_info.get('name', 'Unknown') if staff_info else 'Unknown',
                'department': staff_info.get('department', '') if staff_info else '',
                'date': att.get('date'),
                'check_in_time': att.get('check_in_time').isoformat() if att.get('check_in_time') else None,
                'check_out_time': att.get('check_out_time').isoformat() if att.get('check_out_time') else None,
                'status': att.get('status', 'Absent'),
                'confidence': att.get('confidence', 0.0)
            })
        
        # Enrich check-in events
        checkin_list = []
        for ev in checkin_events:
            staff_id = ev.get('staff_id')
            staff_info = db_manager.get_staff_info(staff_id)
            
            employee_id = staff_info.get('employee_id') if staff_info else None
            if not employee_id and staff_id:
                if staff_id.startswith('STAFF_'):
                    employee_id = staff_id.replace('STAFF_', '')
                else:
                    employee_id = staff_id
            
            checkin_list.append({
                'staff_id': staff_id,
                'employee_id': employee_id,
                'name': staff_info.get('name', 'Unknown') if staff_info else 'Unknown',
                'department': staff_info.get('department', '') if staff_info else '',
                'date': ev.get('date'),
                'check_time': ev.get('check_time'),
                'status': ev.get('status', 'Present'),
                'late_minutes': ev.get('late_minutes', 0),
                'confidence': ev.get('confidence', 0.0)
            })
        
        return jsonify({
            'success': True,
            'date': target_date.isoformat(),
            'attendance': attendance_list,
            'checkins': checkin_list
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/attendance/range', methods=['GET'])
def get_attendance_range():
    """Get attendance for date range"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({'success': False, 'error': 'Start date and end date are required'}), 400
        
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get attendance for each date in range
        all_attendance = []
        current_date = start_date
        while current_date <= end_date:
            attendance_data = db_manager.get_today_attendance(current_date)
            attendance_records = attendance_data.get('attendance', []) if isinstance(attendance_data, dict) else []
            
            for att in attendance_records:
                staff_id = att.get('staff_id')
                staff_info = db_manager.get_staff_info(staff_id)
                
                employee_id = staff_info.get('employee_id') if staff_info else None
                if not employee_id and staff_id:
                    if staff_id.startswith('STAFF_'):
                        employee_id = staff_id.replace('STAFF_', '')
                    else:
                        employee_id = staff_id
                
                all_attendance.append({
                    'staff_id': staff_id,
                    'employee_id': employee_id,
                    'name': staff_info.get('name', 'Unknown') if staff_info else 'Unknown',
                    'department': staff_info.get('department', '') if staff_info else '',
                    'date': current_date.isoformat(),
                    'check_in_time': att.get('check_in_time').isoformat() if att.get('check_in_time') else None,
                    'check_out_time': att.get('check_out_time').isoformat() if att.get('check_out_time') else None,
                    'status': att.get('status', 'Absent'),
                    'confidence': att.get('confidence', 0.0)
                })
            
            current_date += timedelta(days=1)
        
        return jsonify({
            'success': True,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'attendance': all_attendance
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/attendance/export', methods=['GET'])
def export_attendance():
    """Export attendance to CSV"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date:
            start_date = date.today()
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = start_date
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Employee ID', 'Name', 'Department', 'Date', 'Check In', 'Check Out', 'Status', 'Confidence'])
        
        # Get data
        current_date = start_date
        while current_date <= end_date:
            attendance_data = db_manager.get_today_attendance(current_date)
            attendance_records = attendance_data.get('attendance', []) if isinstance(attendance_data, dict) else []
            
            for att in attendance_records:
                staff_id = att.get('staff_id')
                staff_info = db_manager.get_staff_info(staff_id)
                
                employee_id = staff_info.get('employee_id') if staff_info else staff_id
                if not employee_id and staff_id.startswith('STAFF_'):
                    employee_id = staff_id.replace('STAFF_', '')
                
                writer.writerow([
                    employee_id,
                    staff_info.get('name', 'Unknown') if staff_info else 'Unknown',
                    staff_info.get('department', '') if staff_info else '',
                    current_date.isoformat(),
                    att.get('check_in_time').strftime('%H:%M:%S') if att.get('check_in_time') else '',
                    att.get('check_out_time').strftime('%H:%M:%S') if att.get('check_out_time') else '',
                    att.get('status', 'Absent'),
                    f"{att.get('confidence', 0.0):.2f}"
                ])
            
            current_date += timedelta(days=1)
        
        output.seek(0)
        filename = f"attendance_{start_date}_{end_date}.csv"
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== CAMERA CONFIG API ====================

@app.route('/api/admin/camera/config', methods=['GET'])
def get_camera_config():
    """Get camera configuration"""
    try:
        camera_settings = config.get_camera_settings()
        return jsonify({'success': True, 'config': camera_settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/camera/config', methods=['POST'])
def save_camera_config():
    """Save camera configuration"""
    try:
        data = request.get_json()
        config.save_camera_settings(data)
        return jsonify({'success': True, 'message': 'Camera configuration saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/camera/test', methods=['POST'])
def test_camera():
    """Test camera connection"""
    try:
        data = request.get_json()
        camera_source = data.get('camera_source')
        source_type = data.get('source_type', 'usb')
        
        if source_type == 'usb':
            camera_source = int(camera_source)
        
        cap = cv2.VideoCapture(camera_source)
        
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return jsonify({'success': True, 'message': 'Camera connection successful'})
            else:
                return jsonify({'success': False, 'error': 'Cannot read from camera'}), 400
        else:
            return jsonify({'success': False, 'error': 'Cannot connect to camera'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== CAMERA CAPTURE API ====================

@app.route('/api/admin/camera/stream')
def camera_stream():
    """Stream camera feed for photo capture"""
    def generate():
        global camera_manager
        try:
            # Initialize camera manager if not exists
            if camera_manager is None:
                camera_manager = CameraManager()
                if not camera_manager.start_camera():
                    # Return a placeholder image
                    img = Image.new('RGB', (640, 480), color='gray')
                    img_io = io.BytesIO()
                    img.save(img_io, 'JPEG')
                    img_io.seek(0)
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + img_io.getvalue() + b'\r\n')
                    return
            
            frame_count = 0
            while True:
                try:
                    frame = camera_manager.get_frame()
                    if frame is not None:
                        # Encode frame as JPEG
                        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if ret:
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                            frame_count += 1
                    else:
                        time.sleep(0.03)  # ~30 FPS
                    
                    # Check if camera is still connected
                    if not camera_manager.is_connected():
                        break
                        
                except Exception as e:
                    print(f"Frame generation error: {e}")
                    time.sleep(0.1)
        except Exception as e:
            print(f"Camera stream error: {e}")
            # Return a placeholder image on error
            img = Image.new('RGB', (640, 480), color='gray')
            img_io = io.BytesIO()
            img.save(img_io, 'JPEG')
            img_io.seek(0)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + img_io.getvalue() + b'\r\n')
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/admin/camera/capture', methods=['POST'])
def camera_capture():
    """Capture a single frame from camera"""
    global camera_manager
    try:
        # Initialize camera manager if not exists
        if camera_manager is None:
            camera_manager = CameraManager()
            if not camera_manager.start_camera():
                return jsonify({'success': False, 'error': 'Failed to start camera'}), 500
        
        # Wait a bit for camera to stabilize
        time.sleep(0.1)
        
        # Get frame
        frame = None
        for _ in range(10):  # Try up to 10 times
            frame = camera_manager.get_frame()
            if frame is not None:
                break
            time.sleep(0.05)
        
        if frame is None:
            return jsonify({'success': False, 'error': 'Failed to capture frame'}), 500
        
        # Encode as JPEG and convert to base64
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if ret:
            img_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            return jsonify({
                'success': True,
                'image': f'data:image/jpeg;base64,{img_base64}'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to encode image'}), 500
            
    except Exception as e:
        print(f"Camera capture error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/camera/stop', methods=['POST'])
def camera_stop():
    """Stop camera stream"""
    global camera_manager
    try:
        if camera_manager:
            camera_manager.stop_camera()
            camera_manager = None
        return jsonify({'success': True, 'message': 'Camera stopped'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== STATISTICS API ====================

@app.route('/api/admin/statistics/dashboard', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        today = date.today()
        
        # Get all staff
        all_staff = db_manager.get_all_staff()
        total_staff = len(all_staff)
        
        # Get today's attendance
        attendance_data = db_manager.get_today_attendance(today)
        attendance_records = attendance_data.get('attendance', []) if isinstance(attendance_data, dict) else []
        
        present_count = len([a for a in attendance_records if a.get('check_in_time')])
        absent_count = total_staff - present_count
        checked_out_count = len([a for a in attendance_records if a.get('check_out_time')])
        
        # Get late arrivals
        late_count = 0
        for att in attendance_records:
            check_in = att.get('check_in_time')
            if check_in:
                check_in_time = check_in.time() if hasattr(check_in, 'time') else datetime.strptime(str(check_in), '%H:%M:%S').time()
                if check_in_time > datetime.strptime('09:00:00', '%H:%M:%S').time():
                    late_count += 1
        
        # Get this week's stats
        week_start = today - timedelta(days=today.weekday())
        week_attendance = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_data = db_manager.get_today_attendance(day)
            day_records = day_data.get('attendance', []) if isinstance(day_data, dict) else []
            week_attendance.append({
                'date': day.isoformat(),
                'present': len([a for a in day_records if a.get('check_in_time')])
            })
        
        return jsonify({
            'success': True,
            'stats': {
                'total_staff': total_staff,
                'present_today': present_count,
                'absent_today': absent_count,
                'checked_out_today': checked_out_count,
                'late_today': late_count,
                'attendance_rate': (present_count / total_staff * 100) if total_staff > 0 else 0,
                'week_attendance': week_attendance
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== REAL-TIME DATA API ====================

@app.route('/api/admin/realtime/attendance', methods=['GET'])
def get_realtime_attendance():
    """Get real-time attendance updates"""
    try:
        today = date.today()
        attendance_data = db_manager.get_today_attendance(today)
        attendance_records = attendance_data.get('attendance', []) if isinstance(attendance_data, dict) else []
        checkin_events = attendance_data.get('checkins', []) if isinstance(attendance_data, dict) else []
        
        # Get recent check-ins (last 10)
        recent_checkins = sorted(checkin_events, key=lambda x: x.get('check_time', ''), reverse=True)[:10]
        
        # Enrich with staff info
        enriched_checkins = []
        for ev in recent_checkins:
            staff_id = ev.get('staff_id')
            staff_info = db_manager.get_staff_info(staff_id)
            
            employee_id = staff_info.get('employee_id') if staff_info else None
            if not employee_id and staff_id:
                if staff_id.startswith('STAFF_'):
                    employee_id = staff_id.replace('STAFF_', '')
                else:
                    employee_id = staff_id
            
            enriched_checkins.append({
                'staff_id': staff_id,
                'employee_id': employee_id,
                'name': staff_info.get('name', 'Unknown') if staff_info else 'Unknown',
                'check_time': ev.get('check_time'),
                'status': ev.get('status', 'Present'),
                'late_minutes': ev.get('late_minutes', 0)
            })
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'recent_checkins': enriched_checkins,
            'total_present': len([a for a in attendance_records if a.get('check_in_time')])
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== UNKNOWN ENTRIES API ====================

@app.route('/api/admin/unknown-entries', methods=['GET'])
def get_unknown_entries():
    """Get unknown entries (persons without recognized faces or with covered faces)"""
    try:
        date_filter = request.args.get('date')
        limit = int(request.args.get('limit', 100))
        
        print(f"📋 Getting unknown entries: date_filter={date_filter}, limit={limit}")
        entries = db_manager.get_unknown_entries(date_filter=date_filter, limit=limit)
        print(f"📋 Retrieved {len(entries)} unknown entries from database")
        
        # Enrich entries with image URLs
        enriched_entries = []
        for entry in entries:
            enriched_entries.append({
                'id': entry['id'],
                'track_id': entry['track_id'],
                'entry_type': entry['entry_type'],
                'date': entry['date'],
                'time': entry['time'],
                'detection_time': entry['detection_time'],
                'face_detected': entry['face_detected'],
                'face_confidence': entry['face_confidence'],
                'recognition_confidence': entry['recognition_confidence'],
                'reason': entry['reason'],
                'system_mode': entry['system_mode'],
                'is_processed': entry['is_processed'],
                'image_url': f'/api/admin/unknown-entries/{entry["id"]}/image'
            })
        
        print(f"📋 Returning {len(enriched_entries)} enriched entries to frontend")
        return jsonify({
            'success': True,
            'entries': enriched_entries,
            'count': len(enriched_entries)
        })
    except Exception as e:
        print(f"❌ Error getting unknown entries: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/unknown-entries/<int:entry_id>/image', methods=['GET'])
def get_unknown_entry_image(entry_id):
    """Get full body image for an unknown entry"""
    try:
        image = db_manager.get_unknown_entry_image(entry_id)
        if image is None:
            # Return placeholder image
            img = Image.new('RGB', (400, 600), color='gray')
            img_io = io.BytesIO()
            img.save(img_io, 'JPEG')
            img_io.seek(0)
            return Response(img_io, mimetype='image/jpeg')
        
        # Convert numpy array to JPEG
        success, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if success:
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        else:
            return jsonify({'error': 'Failed to encode image'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/unknown-entries/<int:entry_id>/mark-processed', methods=['POST'])
def mark_unknown_entry_processed(entry_id):
    """Mark an unknown entry as processed"""
    try:
        success = db_manager.mark_unknown_entry_processed(entry_id)
        if success:
            return jsonify({'success': True, 'message': 'Entry marked as processed'})
        else:
            return jsonify({'success': False, 'error': 'Failed to mark entry as processed'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/unknown-entries/<int:entry_id>/recheck-staff', methods=['POST'])
def recheck_unknown_entry_as_staff(entry_id):
    """
    Re-check an unknown entry image against the staff database.

    - If a staff member is confidently matched, the entry is marked as processed.
    - If the staff member already has a recent check-in around the detection time,
      no new check-in is created to avoid duplicates.
    - If there is no recent check-in, a new check-in is recorded.
    """
    global face_engine, db_manager

    try:
        if db_manager is None:
            return jsonify({'success': False, 'error': 'Database not initialized'}), 500

        # Lazily initialize face engine for admin re-checks
        if face_engine is None:
            gpu_available = detect_gpu_capability()
            face_engine = FaceRecognitionEngine(gpu_mode=gpu_available)

        # Get full body image for this unknown entry
        image = db_manager.get_unknown_entry_image(entry_id)
        if image is None:
            return jsonify({'success': False, 'error': 'Image not found for this entry'}), 404

        # Detect faces in the stored image
        detections = face_engine.detect_faces(image)
        if not detections:
            return jsonify({'success': False, 'error': 'No face detected in stored image'}), 400

        # Pick detection with highest detection confidence
        best_det = max(detections, key=lambda d: d.get('confidence', 0.0))
        embedding = best_det['embedding']

        # Identify person
        person_type, person_id, rec_confidence = face_engine.identify_person(embedding)
        rec_confidence = float(rec_confidence) if rec_confidence is not None else 0.0

        if person_type != 'staff' or not person_id or rec_confidence < 0.6:
            return jsonify({
                'success': False,
                'error': 'No matching staff found for this entry',
                'details': {
                    'person_type': person_type,
                    'person_id': person_id,
                    'recognition_confidence': rec_confidence
                }
            }), 200

        staff_id = person_id

        # Load entry metadata (date, time, mode)
        with db_manager.lock:
            conn = sqlite3.connect(db_manager.db_path)
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT date, time, system_mode
                FROM unknown_entries
                WHERE id = ?
                ''',
                (entry_id,)
            )
            row = cursor.fetchone()
            conn.close()

        if not row:
            return jsonify({'success': False, 'error': 'Unknown entry not found in database'}), 404

        date_str, time_str, system_mode = row
        system_mode = system_mode or 'checkin'

        # Parse detection datetime
        try:
            detection_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except Exception:
            detection_dt = datetime.now()

        # Check if this staff already has a check-in close to detection time
        with db_manager.lock:
            conn = sqlite3.connect(db_manager.db_path)
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT check_time
                FROM staff_checkins
                WHERE staff_id = ? AND date = ?
                ORDER BY check_time DESC
                ''',
                (staff_id, date_str)
            )
            rows = cursor.fetchall()
            conn.close()

        already_captured = False
        last_check_time_str = None
        if rows:
            last_check_time_str = rows[0][0]
            try:
                last_dt = datetime.strptime(f"{date_str} {last_check_time_str}", "%Y-%m-%d %H:%M:%S")
                diff_minutes = abs((detection_dt - last_dt).total_seconds()) / 60.0
                # If detection is within 5 minutes of the last check-in, treat it as the same session
                already_captured = diff_minutes <= 5.0
            except Exception:
                already_captured = False

        check_in_created = False

        # Only create a new check-in if this looks like a new appearance
        if not already_captured:
            attendance_type = 'check_in' if system_mode == 'checkin' else 'check_out'
            result = db_manager.record_staff_attendance(staff_id, attendance_type, rec_confidence)
            check_in_created = bool(result.get('success'))

        # Mark this unknown entry as processed since it's actually staff
        db_manager.mark_unknown_entry_processed(entry_id)

        return jsonify({
            'success': True,
            'staff_id': staff_id,
            'recognition_confidence': rec_confidence,
            'already_captured': already_captured,
            'check_in_created': check_in_created,
            'last_check_time': last_check_time_str,
            'system_mode': system_mode
        })

    except Exception as e:
        print(f"❌ Error re-checking unknown entry as staff: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/unknown-entries/<int:entry_id>', methods=['DELETE'])
def delete_unknown_entry(entry_id):
    """Delete an unknown entry"""
    try:
        success = db_manager.delete_unknown_entry(entry_id)
        if success:
            return jsonify({'success': True, 'message': 'Entry deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete entry'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/unknown-entries/stats', methods=['GET'])
def get_unknown_entries_stats():
    """Get statistics about unknown entries"""
    try:
        date_filter = request.args.get('date')
        if not date_filter:
            date_filter = date.today().isoformat()
        
        entries = db_manager.get_unknown_entries(date_filter=date_filter, limit=10000)
        
        stats = {
            'total_today': len(entries),
            'no_face': len([e for e in entries if e['entry_type'] == 'no_face']),
            'unknown_person': len([e for e in entries if e['entry_type'] == 'unknown_person']),
            'covered_face': len([e for e in entries if e['entry_type'] == 'covered_face']),
            'checkin': len([e for e in entries if e['system_mode'] == 'checkin']),
            'checkout': len([e for e in entries if e['system_mode'] == 'checkout']),
            'processed': len([e for e in entries if e['is_processed']]),
            'unprocessed': len([e for e in entries if not e['is_processed']])
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'date': date_filter
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='IMPEX Attendance System Admin Server')
    parser.add_argument('--port', type=int, default=5001, help='Port to run the admin server on (default: 5001)')
    
    args = parser.parse_args()
    
    if not init_admin_system():
        print("❌ Failed to initialize admin system")
        sys.exit(1)
    
    host = '0.0.0.0'
    port = args.port
    
    print("=" * 70)
    print("🔐 IMPEX ATTENDANCE SYSTEM - ADMIN SERVER")
    print("=" * 70)
    print(f"📍 Admin Panel: http://localhost:{port}")
    print(f"📍 Network access: http://<your-ip>:{port}")
    print("=" * 70)
    
    app.run(host=host, port=port, debug=False, threaded=True)

