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
import mediapipe as mp

# Setup Python path BEFORE importing core modules
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.deepsort_tracker import DeepSort, Detection as DSDetection
from core.face_engine import FaceRecognitionEngine
from core.database_manager import DatabaseManager
from core.config_manager import ConfigManager
from utils.camera_utils import CameraManager
from utils.gpu_utils import detect_gpu_capability

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
recent_track_roles = {}  # track_id -> 'staff' or 'unknown'
simple_tracks = []       # legacy lightweight tracker state (kept for fallback)
next_track_id = 1        # incremental track id

# DeepSort-style appearance-based tracker for stable IDs
deepsort_tracker = DeepSort()
track_states = {}  # track_id -> dict with staff/unknown history

# MediaPipe face detection + unknown-embedding cache
_mp_face_detector = None
recent_unknowns = []  # list of dicts: {'embedding': np.ndarray, 'ts': float}


def init_mediapipe_face_detector(min_detection_confidence: float = 0.5):
    """Initialize a global MediaPipe face detector (server-side), if available.

    This is used as an auxiliary detector/tracker and to satisfy the
    requirement of integrating MediaPipe into the web tracking pipeline.
    It is written defensively to support different MediaPipe versions.
    """
    global _mp_face_detector
    if _mp_face_detector is not None:
        return _mp_face_detector

    try:
        # Prefer the classic solutions API if present
        from mediapipe import solutions as mp_solutions
        FaceDetectionClass = mp_solutions.face_detection.FaceDetection
        _mp_face_detector = FaceDetectionClass(
            model_selection=0,
            min_detection_confidence=min_detection_confidence
        )
        print("✅ MediaPipe FaceDetection (solutions API) initialized for web tracking.")
    except Exception as e:
        # If this fails (e.g., new Tasks-only build), log and disable MediaPipe usage.
        print(f"⚠️ MediaPipe FaceDetection not available or incompatible: {e}")

        # #region agent log
        try:
            import json as _json, time as _time
            log_entry = {
                "sessionId": "debug-session",
                "runId": "mediapipe-init",
                "hypothesisId": "H1",
                "location": "web_app.py:init_mediapipe_face_detector",
                "message": "MediaPipe FaceDetection init failed",
                "data": {
                    "exception": str(e),
                    "mediapipe_dir": getattr(mp, "__file__", None),
                },
                "timestamp": int(_time.time() * 1000),
            }
            with open(r"c:\Users\ADMIN\Desktop\Impex Projects\impex_factory\Impex_factory_attendence\.cursor\debug.log", "a", encoding="utf-8") as _f:
                _f.write(_json.dumps(log_entry) + "\n")
        except Exception:
            pass
        # #endregion agent log

        _mp_face_detector = None

    return _mp_face_detector


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two 1D vectors."""
    if a is None or b is None:
        return 0.0
    if a.ndim != 1 or b.ndim != 1:
        a = a.reshape(-1)
        b = b.reshape(-1)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a / na, b / nb))


def is_same_unknown(embedding: np.ndarray,
                    similarity_threshold: float = 0.7,
                    max_age_seconds: float = 300.0) -> bool:
    """
    Check if an unknown face embedding matches a recently-seen unknown.

    This prevents the same unknown person from being recorded multiple times
    in a short time window, even if the tracker temporarily loses them.
    """
    global recent_unknowns
    if embedding is None:
        return False

    now = time.time()
    # Keep only recent entries
    recent_unknowns = [
        item for item in recent_unknowns
        if now - item["ts"] <= max_age_seconds
    ]

    if not recent_unknowns:
        recent_unknowns.append({"embedding": embedding, "ts": now})
        return False

    for item in recent_unknowns:
        sim = _cosine_similarity(embedding, item["embedding"])
        if sim >= similarity_threshold:
            # Same physical unknown person seen again → treat as duplicate
            return True

    # New unknown person
    recent_unknowns.append({"embedding": embedding, "ts": now})
    return False


def is_probable_staff_from_embedding(embedding: np.ndarray,
                                     similarity_threshold: float = 0.6) -> bool:
    """
    Check if an embedding is reasonably close to any known staff embedding.

    This acts as a safety net so that a registered staff is not recorded
    as an unknown entry when recognition confidence is slightly below
    the normal threshold or when the tracker briefly loses the face.
    """
    if embedding is None or face_engine is None:
        return False

    try:
        staff_db = getattr(face_engine, "staff_database", None)
        if not staff_db:
            return False

        # Re-use the optimized matcher from FaceRecognitionEngine
        match_id, score = face_engine._match_against_database(embedding, staff_db)
        if match_id and score >= similarity_threshold:
            return True
    except Exception as e:
        # Fail safe: if anything goes wrong, don't block unknowns
        print(f"Staff similarity check error: {e}")

    return False

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

def is_good_frame(frame):
    """Check if frame is good quality for processing (not too blurry or dark)"""
    if frame is None:
        return False
    
    # Convert to grayscale for analysis
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    
    # Check brightness (avoid too dark frames)
    mean_brightness = np.mean(gray)
    if mean_brightness < 30:  # Too dark
        return False
    
    # Check blur using Laplacian variance (simple and fast)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < 50:  # Too blurry
        return False
    
    return True
def _bbox_iou(b1, b2):
    """Compute IoU between two [x1, y1, x2, y2] boxes."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    area1 = max(0, (b1[2] - b1[0])) * max(0, (b1[3] - b1[1]))
    area2 = max(0, (b2[2] - b2[0])) * max(0, (b2[3] - b2[1]))
    union = area1 + area2 - inter
    if union <= 0:
        return 0.0
    return float(inter) / float(union)


def assign_simple_tracks(bboxes, max_stale_seconds=5.0, iou_threshold=0.3):
    """
    Legacy IoU-only tracker (kept for fallback / reference). The main tracker
    used by the system is now DeepSort (see deepsort_tracker).
    """
    global simple_tracks, next_track_id
    now = time.time()

    # Drop stale tracks
    simple_tracks = [t for t in simple_tracks if now - t["last_seen"] <= max_stale_seconds]

    assigned_ids = []
    used_track_ids = set()

    for bbox in bboxes:
        bbox = list(map(float, bbox))
        best_iou = 0.0
        best_track = None

        for t in simple_tracks:
            if t["id"] in used_track_ids:
                continue
            iou = _bbox_iou(bbox, t["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_track = t

        if best_track is not None and best_iou >= iou_threshold:
            # Reuse existing track
            best_track["bbox"] = bbox
            best_track["last_seen"] = now
            track_id = best_track["id"]
            used_track_ids.add(track_id)
        else:
            # Start new track
            track_id = next_track_id
            next_track_id += 1
            simple_tracks.append({"id": track_id, "bbox": bbox, "last_seen": now})
            used_track_ids.add(track_id)

        assigned_ids.append(track_id)

    return assigned_ids


def _get_or_create_track_state(track_id: int):
    """
    Internal helper to retrieve or create a per-track state object.

    State fields:
        first_seen: timestamp when track was first created
        last_seen: last update timestamp
        consecutive_staff_frames: number of consecutive frames with strong staff recognition
        locked_staff: bool - once True, this track is always treated as staff
        staff_id: best staff_id assigned to this track
        best_staff_score: highest recognition score seen for staff
        has_staff_like_match: whether this track ever had an embedding close to staff
        unknown_recorded: whether an unknown DB record was already written
        best_unknown_frame: cached best-quality frame for unknown snapshot
        best_unknown_bbox: bbox associated with best_unknown_frame
        best_unknown_conf: best detection confidence seen for unknown
    """
    now = time.time()
    state = track_states.get(track_id)
    if state is None:
        state = {
            "first_seen": now,
            "last_seen": now,
            "consecutive_staff_frames": 0,
            "locked_staff": False,
            "staff_id": None,
            "best_staff_score": 0.0,
            "has_staff_like_match": False,
            "unknown_recorded": False,
            "best_unknown_frame": None,
            "best_unknown_bbox": None,
            "best_unknown_conf": 0.0,
        }
        track_states[track_id] = state
    else:
        state["last_seen"] = now
    return state


def _prune_stale_track_states(max_age_seconds: float = 5.0):
    """Remove per-track states that have not been updated recently."""
    now = time.time()
    stale_ids = [
        tid for tid, st in track_states.items()
        if now - st.get("last_seen", now) > max_age_seconds
    ]
    for tid in stale_ids:
        track_states.pop(tid, None)

def process_video_loop():
    """Process video frames in background thread with smart frame skipping"""
    global current_frame, current_detections, running, face_engine
    
    # FPS tracking for terminal output
    fps_counter = 0
    fps_start_time = time.time()
    last_fps_print = time.time()
    frame_counter = 0
    processed_frames = 0
    
    # Frame skipping configuration
    # On GPU we can afford slightly higher detection frequency while keeping things stable.
    FRAME_SKIP_INTERVAL = 2  # Process every 2nd frame for detection
    MIN_PROCESS_INTERVAL = 0.06  # Minimum 0.06s between detections (~16 FPS max detection rate)
    last_detection_time = 0
    
    while running:
        try:
            frame = camera_manager.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            
            frame_counter += 1
            fps_counter += 1
            
            # Always update display frame for smooth video
            with frame_lock:
                current_frame = frame.copy()
            
            # Smart frame skipping: only process good frames at intervals
            current_time = time.time()
            should_process = (
                frame_counter % FRAME_SKIP_INTERVAL == 0 and  # Every Nth frame
                (current_time - last_detection_time) >= MIN_PROCESS_INTERVAL and  # Time-based throttling
                is_good_frame(frame)  # Quality check
            )
            
            # Detect faces only on selected frames
            if should_process and face_engine:
                processed_frames += 1
                last_detection_time = current_time
                
                # Ensure MediaPipe is initialized (for integration / auxiliary checks)
                mp_detector = init_mediapipe_face_detector()
                if mp_detector is not None:
                    try:
                        _ = mp_detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    except Exception as _e:
                        # If MediaPipe processing fails, continue with main pipeline.
                        pass

                detections = face_engine.detect_faces(frame)
                detection_info = []

                # Build DeepSort detections (appearance features come from embeddings)
                ds_detections = []
                for d in detections:
                    try:
                        ds_detections.append(DSDetection(d['bbox'], d['embedding']))
                    except Exception:
                        # Skip malformed detections gracefully
                        continue

                ds_tracks = deepsort_tracker.update(ds_detections) if ds_detections else []

                # Map DeepSort track outputs back to our detections via IoU
                det_bboxes = [d['bbox'] for d in detections]
                track_ids = [None] * len(detections)
                for track_id, t_bbox, _feat in ds_tracks:
                    best_iou = 0.0
                    best_idx = None
                    for idx, det_bbox in enumerate(det_bboxes):
                        iou = _bbox_iou(det_bbox, t_bbox)
                        if iou > best_iou:
                            best_iou = iou
                            best_idx = idx
                    if best_idx is not None and best_iou >= 0.3 and track_ids[best_idx] is None:
                        track_ids[best_idx] = int(track_id)

                for det_idx, detection in enumerate(detections):
                    bbox = detection['bbox']
                    embedding = detection['embedding']
                    det_confidence = detection.get('confidence', 0.0)
                    track_id = track_ids[det_idx] if det_idx < len(track_ids) else None

                    # Identify person
                    person_type, person_id, rec_confidence = face_engine.identify_person(embedding)

                    # Track-level state for stronger staff/unknown decisions
                    if track_id is not None:
                        state = track_states.get(track_id)
                        if state is None:
                            state = {
                                "first_seen": current_time,
                                "staff_id": None,
                                "best_staff_score": 0.0,
                                "stable_staff_frames": 0,
                                "staff_confirmed": False,
                                "unknown_recorded": False,
                            }
                            track_states[track_id] = state

                    detection_info.append({
                        'bbox': bbox.tolist() if isinstance(bbox, np.ndarray) else list(bbox),
                        'confidence': float(det_confidence),
                        'person_type': person_type,
                        'person_id': person_id,
                        'recognition_confidence': float(rec_confidence) if rec_confidence else 0.0,
                        'track_id': int(track_id) if track_id is not None else None,
                    })

                    # If confidently recognized as staff, mark this track as staff and record attendance
                    if person_type == 'staff' and person_id and rec_confidence >= 0.55:
                        if track_id is not None:
                            recent_track_roles[track_id] = 'staff'
                            state = track_states.get(track_id)
                            if state:
                                # Update staff history for this track
                                if state["staff_id"] is None or state["staff_id"] == person_id:
                                    state["staff_id"] = person_id
                                    state["best_staff_score"] = max(state["best_staff_score"], float(rec_confidence))
                                    state["stable_staff_frames"] += 1
                                    if state["stable_staff_frames"] >= 2:
                                        state["staff_confirmed"] = True
                                else:
                                    # Different staff ID appearing on same track: reset history
                                    state["staff_id"] = person_id
                                    state["best_staff_score"] = float(rec_confidence)
                                    state["stable_staff_frames"] = 1
                                    state["staff_confirmed"] = False
                                # Once staff is confirmed, never allow unknown recording for this track
                                state["unknown_recorded"] = False
                        process_attendance(person_id, frame, bbox, rec_confidence)
                    # For unknown / low-confidence detections, avoid recording as unknown
                    # if this track was already seen as staff recently.
                    elif person_type in ('unknown', 'staff'):
                        if track_id is not None and recent_track_roles.get(track_id) == 'staff':
                            # Same physical track already known as staff → skip unknown entry
                            continue
                        # If track history says staff is confirmed for this track, never downgrade to unknown
                        if track_id is not None:
                            state = track_states.get(track_id)
                            if state and state.get("staff_confirmed"):
                                continue
                        # Safety net: if this embedding still matches a staff member
                        # reasonably well, don't log it as unknown.
                        if is_probable_staff_from_embedding(embedding):
                            continue

                        # Only consider unknown after the track has had time to stabilize
                        if track_id is not None:
                            state = track_states.get(track_id)
                            if state:
                                track_age = current_time - state.get("first_seen", current_time)
                                if track_age < 0.8:  # wait ~0.8s before deciding unknown
                                    continue
                                if state.get("unknown_recorded"):
                                    # Already recorded one unknown for this track
                                    continue

                        # Embedding-based deduplication for unknown persons
                        if person_type == 'unknown' or (person_type == 'staff' and (rec_confidence or 0.0) < 0.55):
                            if is_same_unknown(embedding):
                                # Same unknown person already recorded recently → skip
                                continue

                        process_unknown_entry(
                            frame,
                            bbox,
                            det_confidence,
                            rec_confidence,
                            person_type,
                            track_id
                        )

                        if track_id is not None:
                            state = track_states.get(track_id)
                            if state:
                                state["unknown_recorded"] = True
                
                with frame_lock:
                    current_detections = detection_info
            
            # Calculate and print FPS to terminal every second
            if current_time - last_fps_print >= 1.0:
                elapsed = current_time - fps_start_time
                if elapsed > 0:
                    fps = fps_counter / elapsed
                    detection_fps = processed_frames / elapsed if processed_frames > 0 else 0
                    print(f"📊 FPS: {fps:.1f} | Detection FPS: {detection_fps:.1f} | Total: {frame_counter} | Processed: {processed_frames}")
                    fps_counter = 0
                    processed_frames = 0
                    fps_start_time = current_time
                last_fps_print = current_time
            
            time.sleep(0.01)  # Fast frame capture for smooth display
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

def process_unknown_entry(frame, bbox, det_confidence, rec_confidence, person_type, track_id=None):
    """Process and record unknown entries (persons not recognized as staff)
    
    Args:
        frame: full video frame (numpy array)
        bbox: face bounding box
        det_confidence: face detection confidence
        rec_confidence: recognition confidence
        person_type: 'unknown' or 'staff' (low confidence)
        track_id: stable track identifier (if None, will be generated from bbox)
    """
    global db_manager, system_mode
    
    try:
        if not db_manager:
            return
        
        current_time = time.time()
        
        # Debounce: only process once per N seconds per track_id
        if not hasattr(process_unknown_entry, 'last_processed'):
            process_unknown_entry.last_processed = {}
        
        # Normalize track_id to int when provided; we no longer synthesize IDs
        # from the bbox, because unknown-person deduplication is handled by
        # embedding similarity in is_same_unknown().
        if track_id is not None:
            track_id = int(track_id)
        
        # Check if we've processed this track recently
        last_time = process_unknown_entry.last_processed.get(track_id, 0)
        # Increase debounce window so the same person is not saved many times
        if current_time - last_time < 180.0:  # 180 seconds debounce
            return
        
        process_unknown_entry.last_processed[track_id] = current_time
        
        # Determine entry type and reason
        entry_type = 'unknown_person'
        reason = 'Face detected but not recognized as staff'
        has_face = det_confidence > 0.3
        
        if det_confidence < 0.3:
            entry_type = 'covered_face'
            reason = 'Face partially covered or low detection confidence'
        elif rec_confidence < 0.5 and rec_confidence > 0:
            entry_type = 'unknown_person'
            reason = 'Face detected but person not in staff database'
        elif not has_face:
            entry_type = 'no_face'
            reason = 'No face detected'
        
        # Expand bounding box to capture full body
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = map(int, bbox)
        face_height = max(1, y2 - y1)
        face_width = max(1, x2 - x1)
        
        # Expand to capture full body (estimated)
        expand_down = int(face_height * 6)
        expand_up = int(face_height * 1.5)
        expand_sides = int(face_width * 1.5)
        
        # Calculate full body bounding box
        body_x1 = max(0, x1 - expand_sides)
        body_y1 = max(0, y1 - expand_up)
        body_x2 = min(w, x2 + expand_sides)
        body_y2 = min(h, y2 + expand_down)
        
        # Extract full body image
        full_body_image = frame[body_y1:body_y2, body_x1:body_x2].copy()
        
        # Make sure we have a valid image
        if full_body_image.size == 0 or full_body_image.shape[0] < 50 or full_body_image.shape[1] < 50:
            # Fallback: use face bounding box with some expansion
            full_body_image = frame[max(0, y1-20):min(h, y2+20), max(0, x1-20):min(w, x2+20)].copy()
        
        if full_body_image.size == 0:
            return
        
        # Record unknown entry in database
        entry_id = db_manager.record_unknown_entry(
            track_id=track_id,
            entry_type=entry_type,
            frame_image=full_body_image,
            face_bbox=[x1, y1, x2, y2],
            person_bbox=[body_x1, body_y1, body_x2, body_y2],
            face_detected=has_face,
            face_confidence=float(det_confidence),
            recognition_confidence=float(rec_confidence),
            reason=reason,
            system_mode=system_mode
        )
        
        if entry_id:
            print(f"✅ Unknown entry recorded: Entry ID {entry_id}, Track ID {track_id}, Type: {entry_type}, Reason: {reason}")
        else:
            print(f"❌ Failed to record unknown entry: Track ID {track_id}")
            
    except Exception as e:
        print(f"❌ Error processing unknown entry: {e}")
        import traceback
        traceback.print_exc()

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

