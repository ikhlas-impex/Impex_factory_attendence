# src/ui/attendance_dashboard.py - IMPEX Head Office Attendance Dashboard
# Matches the exact design from the images provided

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk, ImageDraw, ImageFont
import threading
import time
from datetime import datetime, date, time as dt_time
import numpy as np
import os
import sqlite3
import pickle
from collections import defaultdict

# Import optimized modules - DO NOT CHANGE face recognition model parameters
from core.face_engine import FaceRecognitionEngine
from core.tracking_manager import TrackingManager
from utils.camera_utils import CameraManager
from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager

class ImpexAttendanceDashboard:
    """IMPEX Head Office Attendance Dashboard matching the exact design from images"""
    
    def __init__(self, root, gpu_available=False, system_mode=None):
        self.parent = root
        self.gpu_available = gpu_available
        self.running = False
        self.config = ConfigManager()
        
        # Get system configuration
        system_config = self.config.get_system_config()
        self.is_locked = system_config.get('locked_mode', False)
        self.allow_mode_switch = system_config.get('allow_mode_switch', True) and not self.is_locked
        
        # Determine initial mode: use system_mode parameter, then system config, then default
        if system_mode:
            initial_mode = system_mode
        else:
            initial_mode = system_config.get('system_mode', 'checkin')
        
        # Get database path from system config
        db_path = system_config.get('database_path', 'data/factory_attendance.db')
        self.db_manager = DatabaseManager(db_path=db_path)
        
        # Attendance mode: 'checkin' or 'checkout' (locked if in locked mode)
        self.attendance_mode = tk.StringVar(value=initial_mode)
        
        # Track today's attendance
        self.today_attendance = {}  # staff_id -> attendance_data
        self.captured_photos = {}  # staff_id -> captured_image
        
        # Initialize face recognition - DO NOT CHANGE MODEL PARAMETERS
        self.face_engine = None
        self.tracking_manager = None
        self.camera_manager = CameraManager()
        
        # Frame processing
        self.current_frame = None
        self.current_detections = []  # Store detections for drawing
        self.frame_lock = threading.Lock()
        self.capture_lock = threading.Lock()
        
        # Auto-registration
        self.auto_register_enabled = True
        self.registered_today = set()
        
        # Entry/Exit tracking - only capture when person leaves and returns
        self.person_track_status = {}  # track_id -> {'in_frame': bool, 'last_seen': time, 'captured': bool, 'bbox': [...]}
        self.person_track_timeout = 2.0  # Person considered "left" after 2 seconds of no detection
        
        # Unknown entry tracking - track unknown persons to avoid duplicates
        self.unknown_track_status = {}  # track_id -> {'in_frame': bool, 'last_seen': time, 'captured': bool, 'bbox': [...]}
        
        # Motion detection for catching fast-moving persons (even without face detection)
        self.motion_detector = None
        self.background_subtractor = None
        self.last_frame_for_motion = None
        self.motion_detection_enabled = True
        self.motion_capture_interval = 0.2  # Capture motion every 0.2 seconds (very fast for fast-moving persons)
        self.last_motion_capture_time = {}  # motion_id -> last capture time
        self.last_motion_detection_time = 0  # Last time motion detection ran
        self.motion_detection_interval = 0.03  # Run motion detection every 0.03s (~33 FPS) - very fast
        
        # Employee ID mapping - MUST be initialized early
        self.employee_id_map = {}
        
        # Load background/logo image
        self.background_image = None
        self.background_photo = None
        self.load_background_image()
        
        # Load employee card icons
        self.employee_icons = {}
        self.load_employee_icons()
        
        # Setup UI
        self.setup_ui()
        
        # Load employee IDs from database
        self.load_employee_ids()
        
        # Load today's attendance
        self.load_today_attendance()
        
        # Load fake employees for testing (if needed)
        self.load_fake_employees()
    
    def setup_ui(self):
        """Setup the UI to match the exact design from images"""
        # Configure main window style
        self.parent.configure(bg='#f0f0f0')
        
        # Create main container
        main_container = tk.Frame(self.parent, bg='#f0f0f0')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create split view: Left (camera) + Right (attendance)
        paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # LEFT PANEL - Live Camera Feed
        self.setup_camera_panel(paned)
        
        # RIGHT PANEL - Attendance Panel
        self.setup_attendance_panel(paned)
        
        # BOTTOM BANNER - "POWERED BY INNOVATION & INDUSTRY 4.0 DEPARTMENT"
        self.setup_bottom_banner(main_container)
    
    def setup_camera_panel(self, paned):
        """Setup left camera panel with live feed and background image"""
        camera_frame = tk.Frame(paned, bg='#1a1a1a')
        paned.add(camera_frame, weight=3)
        
        # Video display area - using Canvas to support background image
        self.video_canvas = tk.Canvas(
            camera_frame,
            bg='black',
            highlightthickness=0
        )
        self.video_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Video label that will display on canvas - positioned in center
        self.video_label = tk.Label(
            self.video_canvas,
            bg='black',
            text="Camera Disconnected",
            fg='white',
            font=('Arial', 14)
        )
        # Place video label in center of canvas initially
        self.video_label_id = self.video_canvas.create_window(
            self.video_canvas.winfo_reqwidth()//2 if self.video_canvas.winfo_reqwidth() > 0 else 400,
            self.video_canvas.winfo_reqheight()//2 if self.video_canvas.winfo_reqheight() > 0 else 300,
            anchor='center',
            window=self.video_label
        )
        
        # Update canvas background and center video when canvas is resized
        def on_canvas_configure(event):
            self.update_canvas_background()
            # Center video label
            if hasattr(self, 'video_label_id'):
                center_x = event.width // 2
                center_y = event.height // 2
                self.video_canvas.coords(self.video_label_id, center_x, center_y)
        
        self.video_canvas.bind('<Configure>', on_canvas_configure)
        
        # Add background image if available
        self.parent.after(100, self.update_canvas_background)  # Update after UI is ready
        
        # Camera controls
        control_frame = tk.Frame(camera_frame, bg='#1a1a1a')
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_btn = tk.Button(
            control_frame,
            text="▶ Start",
            command=self.start_recognition,
            bg='#2d5a27',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=5
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(
            control_frame,
            text="⏹ Stop",
            command=self.stop_recognition,
            bg='#5a2727',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=5,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.camera_status_label = tk.Label(
            control_frame,
            text="Camera: Disconnected",
            bg='#1a1a1a',
            fg='red',
            font=('Arial', 9)
        )
        self.camera_status_label.pack(side=tk.LEFT, padx=20)
    
    def setup_attendance_panel(self, paned):
        """Setup right attendance panel matching the image design with background"""
        # Create canvas with background for attendance panel
        attendance_canvas = tk.Canvas(paned, bg='#8B4513', highlightthickness=0)
        paned.add(attendance_canvas, weight=2)
        
        # Create frame for attendance content that will be placed on canvas
        attendance_frame = tk.Frame(attendance_canvas, bg='#8B4513')
        attendance_canvas.create_window(0, 0, anchor='nw', window=attendance_frame)
        
        # Configure canvas scroll region and background
        def configure_scroll_region(event=None):
            attendance_canvas.configure(scrollregion=attendance_canvas.bbox('all'))
            # Update background image size
            if hasattr(self, 'background_image') and self.background_image:
                try:
                    canvas_width = attendance_canvas.winfo_width()
                    canvas_height = attendance_canvas.winfo_height()
                    if canvas_width > 1 and canvas_height > 1:
                        bg_scaled = self.background_image.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                        bg_photo_scaled = ImageTk.PhotoImage(bg_scaled)
                        attendance_canvas.delete('background')
                        attendance_canvas.create_image(0, 0, anchor='nw', image=bg_photo_scaled, tags='background')
                        attendance_canvas.tag_lower('background')  # Put background behind all other elements
                        attendance_canvas.bg_image = bg_photo_scaled  # Keep reference
                except Exception as e:
                    pass  # Silently fail if background update fails
        
        attendance_canvas.bind('<Configure>', configure_scroll_region)
        attendance_frame.bind('<Configure>', configure_scroll_region)
        
        # Store reference
        self.attendance_canvas = attendance_canvas
        self.attendance_frame = attendance_frame
        
        # Header section
        header_frame = tk.Frame(attendance_frame, bg='#8B4513')
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Title (Check In / Check Out) - set based on initial mode
        initial_mode = self.attendance_mode.get()
        initial_title = "Check In" if initial_mode == 'checkin' else "Check Out"
        self.title_label = tk.Label(
            header_frame,
            text=initial_title,
            bg='#8B4513',
            fg='#FF8C00',  # Orange text
            font=('Arial', 24, 'bold')
        )
        self.title_label.pack(anchor=tk.W)
        
        # Date and time display
        date_time_frame = tk.Frame(header_frame, bg='#8B4513')
        date_time_frame.pack(fill=tk.X, pady=5)
        
        self.date_label = tk.Label(
            date_time_frame,
            text=datetime.now().strftime("%d.%m.%Y"),
            bg='#8B4513',
            fg='white',
            font=('Arial', 18, 'bold')
        )
        self.date_label.pack(anchor=tk.W)
        
        self.time_label = tk.Label(
            date_time_frame,
            text=datetime.now().strftime("%I:%M %p"),
            bg='#8B4513',
            fg='white',
            font=('Arial', 18, 'bold')
        )
        self.time_label.pack(anchor=tk.W)
        
        # Mode toggle - only show if mode switching is allowed
        mode_frame = tk.Frame(header_frame, bg='#8B4513')
        if self.allow_mode_switch:
            mode_frame.pack(fill=tk.X, pady=10)
            
            tk.Button(
                mode_frame,
                text="Check In",
                command=lambda: self.set_mode('checkin'),
                bg='#FF8C00',
                fg='white',
                font=('Arial', 10, 'bold'),
                padx=10
            ).pack(side=tk.LEFT, padx=5)
            
            tk.Button(
                mode_frame,
                text="Check Out",
                command=lambda: self.set_mode('checkout'),
                bg='#FF8C00',
                fg='white',
                font=('Arial', 10, 'bold'),
                padx=10
            ).pack(side=tk.LEFT, padx=5)
        else:
            # Hide mode toggle if locked
            mode_frame.pack_forget()
        
        # Scrollable employee cards container
        scroll_frame = tk.Frame(attendance_frame, bg='#8B4513')
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create scrollbar
        scrollbar = ttk.Scrollbar(scroll_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Canvas for scrollable content
        self.cards_canvas = tk.Canvas(
            scroll_frame,
            bg='#8B4513',
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.cards_canvas.yview)
        
        # Frame inside canvas for cards
        self.cards_container = tk.Frame(self.cards_canvas, bg='#8B4513')
        self.cards_canvas.create_window((0, 0), window=self.cards_container, anchor='nw')
        
        self.cards_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # For checkout mode - remaining count
        self.remaining_frame = tk.Frame(attendance_frame, bg='#8B4513')
        self.remaining_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.remaining_label = tk.Label(
            self.remaining_frame,
            text="REMAINING : 0",
            bg='#228B22',  # Green background
            fg='white',
            font=('Arial', 14, 'bold'),
            padx=20,
            pady=10
        )
        self.remaining_label.pack()
        
        # Show/hide based on initial mode
        if initial_mode == 'checkout':
            self.remaining_frame.pack()
        else:
            self.remaining_frame.pack_forget()  # Hidden for check-in
        
        # Update time periodically
        self.update_time()
        
        # Initial card display
        self.refresh_attendance_cards()
    
    def setup_bottom_banner(self, parent):
        """Setup bottom banner"""
        banner = tk.Frame(parent, bg='#2d2d2d', height=30)
        banner.pack(side=tk.BOTTOM, fill=tk.X)
        banner.pack_propagate(False)
        
        label = tk.Label(
            banner,
            text="POWERED BY INNOVATION & INDUSTRY 4.0 DEPARTMENT",
            bg='#2d2d2d',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        label.pack(pady=5)
    
    def set_mode(self, mode):
        """Set attendance mode (checkin/checkout) - respects locked mode"""
        # Check if mode switching is allowed
        if not self.allow_mode_switch:
            print(f"⚠️ Mode switching disabled - system is locked to {self.attendance_mode.get()}")
            return
        
        self.attendance_mode.set(mode)
        
        if mode == 'checkin':
            self.title_label.config(text="Check In")
            self.remaining_frame.pack_forget()
        else:
            self.title_label.config(text="Check Out")
            self.remaining_frame.pack()
        
        self.refresh_attendance_cards()
        self.update_remaining_count()
    
    def update_time(self):
        """Update date and time display"""
        now = datetime.now()
        self.date_label.config(text=now.strftime("%d.%m.%Y"))
        self.time_label.config(text=now.strftime("%I:%M %p"))
        
        # Schedule next update
        self.parent.after(1000, self.update_time)
    
    def start_recognition(self):
        """Start face recognition and attendance tracking"""
        try:
            print("🚀 Starting IMPEX Attendance Recognition...")
            
            # Initialize engines - DO NOT CHANGE MODEL PARAMETERS
            gpu_mode = self.gpu_available
            self.face_engine = FaceRecognitionEngine(gpu_mode=gpu_mode)
            self.tracking_manager = TrackingManager(gpu_mode=gpu_mode)
            
            # Initialize motion detection for catching fast-moving persons
            if self.motion_detection_enabled:
                try:
                    # Use MOG2 background subtractor for motion detection
                    self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
                        history=500, varThreshold=50, detectShadows=True
                    )
                    print("✅ Motion detection initialized for catching fast-moving persons")
                except Exception as e:
                    print(f"⚠️ Motion detection initialization failed: {e}")
                    self.motion_detection_enabled = False
            
            # Verify face engine is ready before starting camera
            if self.face_engine is None:
                messagebox.showerror("Engine Error", "Face recognition engine failed to initialize")
                return
            
            print("✅ Face recognition engine ready - Detection will start on first frame")
            
            # Start camera
            if not self.camera_manager.start_camera():
                messagebox.showerror("Camera Error", "Failed to start camera")
                return
            
            self.running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.camera_status_label.config(text="Camera: Connected", fg='green')
            
            # Start processing thread - Detection will start immediately on first frame
            self.process_thread = threading.Thread(target=self.process_video, daemon=True)
            self.process_thread.start()
            
            # Start video display thread
            self.display_thread = threading.Thread(target=self.display_video, daemon=True)
            self.display_thread.start()
            
            print("✅ Attendance recognition started - Face detection active on all frames")
            
        except Exception as e:
            print(f"❌ Start error: {e}")
            messagebox.showerror("Error", f"Failed to start: {e}")
    
    def stop_recognition(self):
        """Stop face recognition"""
        self.running = False
        self.camera_manager.stop_camera()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.camera_status_label.config(text="Camera: Disconnected", fg='red')
        print("⏹ Recognition stopped")
    
    def _is_good_frame(self, frame, strict=True):
        """Check if frame is good quality for processing (not too blurry or dark)
        
        Args:
            frame: Video frame to check
            strict: If True, use strict quality checks. If False, use lenient checks for unknown detection.
        """
        if frame is None:
            return False
        
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        # Check brightness (avoid too dark frames)
        mean_brightness = np.mean(gray)
        
        if strict:
            # Strict quality check for staff recognition (needs good quality)
            if mean_brightness < 30:  # Too dark
                return False
            
            # Check blur using Laplacian variance (simple and fast)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian_var < 50:  # Too blurry
                return False
        else:
            # Lenient quality check for unknown person detection
            # Allow slightly darker and blurrier frames to catch moving persons
            if mean_brightness < 15:  # Only reject very dark frames (was 30)
                return False
            
            # Check blur using Laplacian variance - more lenient
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian_var < 20:  # Only reject very blurry frames (was 50)
                return False
        
        return True

    def process_video(self):
        """Process video frames for face recognition - OPTIMIZED WITH SMART FRAME SKIPPING"""
        if not hasattr(self, 'last_processed'):
            self.last_processed = {}
        
        # Initialize frame counter to track that detection starts from frame 1
        frame_counter = 0
        
        # FPS tracking for terminal output
        fps_counter = 0
        fps_start_time = time.time()
        last_fps_print = time.time()
        processed_frames = 0
        
        # Frame skipping configuration - REDUCED for better unknown person capture
        FRAME_SKIP_INTERVAL = 2  # Process every 2nd frame for detection (was 3)
        MIN_PROCESS_INTERVAL = 0.05  # Minimum 0.05s between detections (20 FPS max detection rate, was 0.1s)
        last_detection_time = 0
        
        # Unknown person capture configuration
        UNKNOWN_CAPTURE_INTERVAL = 2.0  # Capture same unknown person every 2 seconds if still in frame
        last_unknown_capture_time = {}  # track_id -> last capture time
        
        while self.running:
            try:
                frame = self.camera_manager.get_frame()
                if frame is None:
                    time.sleep(0.01)  # Ultra-fast check
                    continue
                
                frame_counter += 1
                fps_counter += 1
                
                # Log first frame to confirm detection starts immediately
                if frame_counter == 1:
                    print("✅ Face detection started - Processing first frame from camera")
                
                with self.frame_lock:
                    self.current_frame = frame.copy()
                
                # Smart frame skipping: only process good frames at intervals
                current_time = time.time()
                
                # Use strict quality check for normal processing
                is_good_quality = self._is_good_frame(frame, strict=True)
                # Use lenient quality check for unknown detection (to catch moving persons)
                is_acceptable_quality = self._is_good_frame(frame, strict=False)
                
                should_process = (
                    frame_counter % FRAME_SKIP_INTERVAL == 0 and  # Every Nth frame
                    (current_time - last_detection_time) >= MIN_PROCESS_INTERVAL and  # Time-based throttling
                    is_good_quality  # Quality check for staff recognition
                )
                
                # Also process frames with acceptable quality for unknown detection
                # This ensures we don't miss unknown persons due to quality checks
                # IMPORTANT: Process lenient quality frames to capture moving/blurry unknown persons
                # We process these even alongside good quality frames to ensure no misses
                should_process_for_unknown = (
                    frame_counter % FRAME_SKIP_INTERVAL == 0 and  # Every Nth frame
                    (current_time - last_detection_time) >= MIN_PROCESS_INTERVAL and  # Time-based throttling
                    is_acceptable_quality  # Acceptable quality (includes both good and lenient)
                )
                
                # CRITICAL: Motion detection runs on EVERY frame (independent of face detection)
                # This ensures we catch fast-moving persons even when face detection doesn't run
                if self.motion_detection_enabled and self.background_subtractor is not None:
                    time_since_last_motion = current_time - self.last_motion_detection_time
                    if time_since_last_motion >= self.motion_detection_interval:
                        # Run motion detection (no quality checks - works on any frame)
                        # Initialize empty sets if face detection hasn't run yet
                        current_track_ids_for_motion = current_track_ids if 'current_track_ids' in locals() else set()
                        current_staff_ids_for_motion = current_staff_ids_detected if 'current_staff_ids_detected' in locals() else set()
                        self.detect_and_capture_motion(frame, current_time, current_track_ids_for_motion, current_staff_ids_for_motion)
                        self.last_motion_detection_time = current_time
                
                # Detect faces only on selected frames
                if should_process or should_process_for_unknown:
                    processed_frames += 1
                    last_detection_time = current_time
                    
                    # Mark if this is a lenient quality frame (for unknown detection only)
                    is_lenient_quality_frame = should_process_for_unknown and not should_process
                    
                    detections = self.face_engine.detect_faces(frame)
                    
                    # Track currently detected persons
                    current_track_ids = set()
                    current_staff_ids_detected = set()  # Track all detected staff (even if not shown)
                    detection_info = []  # Will only contain detections to show (after entry/exit logic)
                    unknown_detections = []  # Store unknown detections for processing
                    
                    for detection in detections:
                        bbox = detection['bbox']
                        embedding = detection['embedding']
                        det_confidence = detection.get('confidence', 0.0)
                        
                        # Generate track ID based on face position and size
                        x1, y1, x2, y2 = map(int, bbox)
                        face_center_x = (x1 + x2) // 2
                        face_center_y = (y1 + y2) // 2
                        face_size = (x2 - x1) * (y2 - y1)
                        track_id = hash((face_center_x // 50, face_center_y // 50, face_size // 1000))
                        track_id = abs(track_id) % 1000000
                        current_track_ids.add(track_id)
                        
                        # CRITICAL: Check if this is a staff member FIRST
                        # This ensures we properly verify staff before marking as unknown
                        # For lenient quality frames, we still try to identify but prioritize unknown capture
                        person_type, person_id, rec_confidence = self.face_engine.identify_person(embedding)
                        
                        # Enhanced staff verification: double-check with higher threshold
                        # For lenient quality frames, use slightly lower threshold to avoid false positives
                        is_confirmed_staff = False
                        if person_type == 'staff' and person_id:
                            # Additional verification: check if staff_id exists in database
                            staff_info = self.db_manager.get_staff_info(person_id)
                            # Use lower threshold for lenient quality frames to be more conservative
                            min_confidence = 0.50 if is_lenient_quality_frame else 0.55
                            if staff_info and rec_confidence >= min_confidence:
                                is_confirmed_staff = True
                                print(f"✅ Confirmed Staff: {person_id} (confidence: {rec_confidence:.3f}, quality: {'lenient' if is_lenient_quality_frame else 'good'})")
                        
                        # Update tracking status
                        if is_confirmed_staff:
                            # Track that this staff member is currently detected
                            current_staff_ids_detected.add(person_id)
                            
                            # Staff member detected - use staff_id as track key
                            staff_track_key = f"staff_{person_id}"
                            
                            # Get or create track status
                            if staff_track_key not in self.person_track_status:
                                self.person_track_status[staff_track_key] = {
                                    'in_frame': False,
                                    'last_seen': 0,
                                    'captured': False,
                                    'bbox': None,
                                    'track_id': track_id
                                }
                            
                            track_status = self.person_track_status[staff_track_key]
                            track_status['track_id'] = track_id  # Update track_id
                            
                            # If person was not in frame before (just entered or returned)
                            if not track_status['in_frame']:
                                # Check if this is a return (was captured before)
                                if track_status['captured']:
                                    # Person returned - reset capture flag to allow new capture
                                    print(f"✅ Staff {person_id} returned to frame - capturing attendance")
                                    track_status['captured'] = False
                                    track_status['in_frame'] = True
                                    track_status['last_seen'] = current_time
                                    track_status['bbox'] = bbox
                                    
                                    # Now capture and process attendance
                                    self.process_attendance(person_id, frame, bbox, rec_confidence)
                                    
                                    # Show detection on screen (only after return) - with timestamp
                                    info = {
                                        'bbox': bbox,
                                        'confidence': det_confidence,
                                        'person_type': person_type,
                                        'person_id': person_id,
                                        'recognition_confidence': rec_confidence,
                                        'detected': True,
                                        'show_until': current_time + 2.0  # Show for 2 seconds, then hide
                                    }
                                    detection_info.append(info)
                                else:
                                    # First time seeing this person - mark as in frame but don't capture yet
                                    print(f"👁️ Staff {person_id} detected in frame - waiting for them to leave before capture")
                                    track_status['in_frame'] = True
                                    track_status['last_seen'] = current_time
                                    track_status['bbox'] = bbox
                                    # Don't show on screen or capture yet - wait for them to leave
                            else:
                                # Person still in frame - update last seen time
                                track_status['last_seen'] = current_time
                                track_status['bbox'] = bbox
                                # Don't show on screen - they're still in frame
                                # Remove from current_detections if they were showing before
                                with self.frame_lock:
                                    self.current_detections = [
                                        d for d in self.current_detections 
                                        if d.get('person_id') != person_id
                                    ]
                        
                        # Handle unknown persons - anyone NOT confirmed as staff
                        # This includes: unknown, customer, or staff with low confidence/no ID
                        # IMPORTANT: For lenient quality frames, we prioritize capturing unknown persons
                        # even if staff recognition is uncertain
                        else:
                            # Unknown person - capture EVERY time they pass (not just on entry/exit)
                            # This works for both good quality and lenient quality frames
                            unknown_track_key = f"unknown_{track_id}"
                            
                            # Log if this is from a lenient quality frame
                            if is_lenient_quality_frame:
                                print(f"📸 Processing unknown on lenient quality frame (may be moving/blurry)")
                            
                            if unknown_track_key not in self.unknown_track_status:
                                self.unknown_track_status[unknown_track_key] = {
                                    'in_frame': False,
                                    'last_seen': 0,
                                    'captured': False,
                                    'bbox': bbox,
                                    'face_confidence': det_confidence,
                                    'recognition_confidence': rec_confidence,
                                    'track_id': track_id,
                                    'first_detected': current_time
                                }
                            
                            track_status = self.unknown_track_status[unknown_track_key]
                            track_status['track_id'] = track_id  # Update track_id
                            track_status['bbox'] = bbox
                            track_status['face_confidence'] = det_confidence
                            track_status['recognition_confidence'] = rec_confidence
                            
                            # IMPROVED: Capture unknown person immediately when detected
                            # Check if enough time has passed since last capture (to avoid duplicates)
                            last_capture = last_unknown_capture_time.get(track_id, 0)
                            time_since_last_capture = current_time - last_capture
                            
                            # Capture if:
                            # 1. First time seeing this person (not in frame before), OR
                            # 2. Person is in frame but enough time has passed (UNKNOWN_CAPTURE_INTERVAL)
                            should_capture = False
                            
                            if not track_status['in_frame']:
                                # Person just entered frame - capture immediately
                                should_capture = True
                                track_status['in_frame'] = True
                                track_status['first_detected'] = current_time
                                print(f"📸 Unknown person detected (NEW): type={person_type}, track_id={track_id}, conf={rec_confidence:.2f} - capturing immediately")
                            elif time_since_last_capture >= UNKNOWN_CAPTURE_INTERVAL:
                                # Person still in frame but enough time passed - capture again
                                should_capture = True
                                print(f"📸 Unknown person detected (REPEAT): type={person_type}, track_id={track_id}, conf={rec_confidence:.2f} - capturing again (interval: {time_since_last_capture:.1f}s)")
                            
                            if should_capture:
                                # Update last capture time
                                last_unknown_capture_time[track_id] = current_time
                                track_status['last_seen'] = current_time
                                
                                # Capture unknown entry immediately (save to database)
                                unknown_detections.append({
                                    'bbox': bbox,
                                    'face_confidence': det_confidence,
                                    'recognition_confidence': rec_confidence,
                                    'has_face': True,
                                    'track_id': track_id,
                                    'person_type': person_type
                                })
                                
                                # Also show on screen briefly
                                info = {
                                    'bbox': bbox,
                                    'confidence': det_confidence,
                                    'person_type': 'unknown',
                                    'person_id': None,
                                    'recognition_confidence': rec_confidence,
                                    'detected': True,
                                    'show_until': current_time + 3.0  # Show for 3 seconds
                                }
                                detection_info.append(info)
                            else:
                                # Update last seen but don't capture yet (too soon)
                                track_status['last_seen'] = current_time
                    
                    # Check for persons who left the frame (not detected in current cycle)
                    # For staff members
                    for track_key, status in list(self.person_track_status.items()):
                        if track_key.startswith('staff_'):
                            staff_id = track_key.replace('staff_', '')
                            if staff_id in current_staff_ids_detected:
                                # Staff member is detected - update last seen if in frame
                                if status['in_frame']:
                                    status['last_seen'] = current_time
                            else:
                                # Staff member NOT detected in current cycle
                                if status['in_frame']:
                                    time_since_last_seen = current_time - status['last_seen']
                                    if time_since_last_seen > self.person_track_timeout:
                                        # Person has been gone long enough - mark as left
                                        status['in_frame'] = False
                                        if not status['captured']:
                                            status['captured'] = True
                                            print(f"⏱️ Staff {staff_id} left frame - ready for capture on return")
                    
                    # For unknown persons
                    for track_key, status in list(self.unknown_track_status.items()):
                        track_id = status.get('track_id')
                        if track_id and track_id in current_track_ids:
                            # Unknown person is detected - update last seen if in frame
                            if status['in_frame']:
                                status['last_seen'] = current_time
                        else:
                            # Unknown person NOT detected in current cycle
                            if track_id and status['in_frame']:
                                time_since_last_seen = current_time - status['last_seen']
                                if time_since_last_seen > self.person_track_timeout:
                                    # Unknown person left frame
                                    status['in_frame'] = False
                                    if not status['captured']:
                                        status['captured'] = True
                                        print(f"⏱️ Unknown person (track {track_id}) left frame - ready for capture on return")
                    
                    # Process unknown entries immediately (captured when detected)
                    if unknown_detections:
                        print(f"📝 Processing {len(unknown_detections)} unknown entry/entries...")
                        self.process_unknown_entries(frame, unknown_detections, current_time)
                        
                        # Clean up old capture times (keep only recent ones)
                        current_time_cleanup = current_time
                        tracks_to_remove = [
                            tid for tid, last_time in last_unknown_capture_time.items()
                            if current_time_cleanup - last_time > 60.0  # Remove if not seen for 60 seconds
                        ]
                        for tid in tracks_to_remove:
                            last_unknown_capture_time.pop(tid, None)
                    
                    # Motion detection already runs above on every frame
                    # This section is kept for backward compatibility but motion detection
                    # is now handled earlier in the loop for maximum speed
                    
                    # Store detections for display - only show persons who just returned
                    # Also filter out old detections that exceeded their display time
                    current_time_check = current_time
                    filtered_info = []
                    for det in detection_info:
                        show_until = det.get('show_until', current_time_check + 10.0)  # Default 10s if no timestamp
                        if current_time_check < show_until:
                            filtered_info.append(det)
                    detection_info = filtered_info
                    
                    with self.frame_lock:
                        # Also filter existing detections by show_until time
                        existing_filtered = []
                        for det in self.current_detections:
                            show_until = det.get('show_until', current_time_check + 10.0)
                            if current_time_check < show_until:
                                existing_filtered.append(det)
                        # Combine with new detections (new ones take priority)
                        combined_detections = existing_filtered + detection_info
                        # Remove duplicates by person_id or track_id
                        seen = set()
                        unique_detections = []
                        for det in combined_detections:
                            key = det.get('person_id') or f"track_{det.get('bbox', [0,0,0,0])[0]}"
                            if key not in seen:
                                seen.add(key)
                                unique_detections.append(det)
                        self.current_detections = unique_detections
                else:
                    # If not processing, filter detections by show_until time and in_frame status
                    with self.frame_lock:
                        filtered_detections = []
                        current_time_check = current_time
                        for det in self.current_detections:
                            # Check if detection has expired
                            show_until = det.get('show_until', current_time_check + 10.0)
                            if current_time_check >= show_until:
                                continue  # Skip expired detections
                            
                            # Check if person is still in frame (shouldn't show)
                            person_id = det.get('person_id')
                            if person_id:
                                staff_track_key = f"staff_{person_id}"
                                if staff_track_key in self.person_track_status:
                                    track_status = self.person_track_status[staff_track_key]
                                    # Don't show if person is currently in frame
                                    if track_status['in_frame']:
                                        continue  # Skip - person is still in frame
                            
                            filtered_detections.append(det)
                        self.current_detections = filtered_detections
                
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
                time.sleep(0.05)
    
    def process_attendance(self, staff_id, frame, bbox, confidence):
        """Process attendance for recognized staff member"""
        try:
            mode = self.attendance_mode.get()
            now = datetime.now()
            
            # Mark this staff member as captured (so they won't be captured again until they leave and return)
            staff_track_key = f"staff_{staff_id}"
            if staff_track_key in self.person_track_status:
                self.person_track_status[staff_track_key]['captured'] = True
            
            # Capture photo for display
            x1, y1, x2, y2 = map(int, bbox)
            x1 = max(0, x1 - 10)
            y1 = max(0, y1 - 10)
            x2 = min(frame.shape[1], x2 + 10)
            y2 = min(frame.shape[0], y2 + 10)
            
            captured_photo = frame[y1:y2, x1:x2].copy()
            self.captured_photos[staff_id] = captured_photo
            
            # Record attendance
            if mode == 'checkin':
                self.record_checkin(staff_id, now, confidence)
            else:
                self.record_checkout(staff_id, now, confidence)
            
            # Auto-register if enabled and not already registered today
            if self.auto_register_enabled and staff_id not in self.registered_today:
                self.registered_today.add(staff_id)
            
            # Refresh UI
            self.parent.after(0, self.refresh_attendance_cards)
            if mode == 'checkout':
                self.parent.after(0, self.update_remaining_count)
            
        except Exception as e:
            print(f"Attendance processing error: {e}")
    
    def detect_and_capture_motion(self, frame, current_time, current_face_track_ids, current_staff_ids):
        """Detect motion and capture persons even when face detection fails (for fast-moving persons)
        
        OPTIMIZED for speed - runs very frequently to catch fast-moving persons
        """
        try:
            if frame is None or self.background_subtractor is None:
                return
            
            # OPTIMIZED: Resize frame for faster processing (motion detection doesn't need full resolution)
            # Use smaller resolution for motion detection to speed it up
            h, w = frame.shape[:2]
            scale = 1.0
            if w > 640:  # Only resize if frame is large
                scale = 640.0 / w
                new_w = 640
                new_h = int(h * scale)
                frame_small = cv2.resize(frame, (new_w, new_h))
            else:
                frame_small = frame
            
            # Process frame for motion detection (faster on smaller frame)
            gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY) if len(frame_small.shape) == 3 else frame_small
            
            # Apply background subtraction (fast operation)
            fg_mask = self.background_subtractor.apply(gray)
            
            # OPTIMIZED: Faster noise removal with smaller kernel
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))  # Smaller kernel = faster
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
            
            # Find contours (moving objects) - OPTIMIZED for speed
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Use small frame dimensions for area calculations
            h_small, w_small = frame_small.shape[:2]
            min_area = (w_small * h_small) * 0.01  # At least 1% of frame area
            max_area = (w_small * h_small) * 0.5   # At most 50% of frame area
            
            motion_detections = []
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Filter by size (person-sized objects)
                if area < min_area or area > max_area:
                    continue
                
                # Get bounding box (on small frame)
                x, y, bw, bh = cv2.boundingRect(contour)
                
                # Scale back to original frame coordinates
                x = int(x / scale)
                y = int(y / scale)
                bw = int(bw / scale)
                bh = int(bh / scale)
                
                # Skip if too small (not a person) - use scaled dimensions
                if bw < 40 or bh < 80:  # Slightly smaller threshold for faster detection
                    continue
                
                # Calculate center and generate motion ID
                center_x = x + bw // 2
                center_y = y + bh // 2
                motion_id = hash((center_x // 100, center_y // 100, area // 1000))
                motion_id = abs(motion_id) % 1000000
                
                # Check if this motion corresponds to a known face track or staff
                # If it does, skip (already handled by face detection)
                is_known_face = False
                for face_track_id in current_face_track_ids:
                    # Check if motion is near any face detection
                    # This is approximate - if motion center is close to face area, assume it's the same person
                    if abs(motion_id - face_track_id) < 10000:  # Rough check
                        is_known_face = True
                        break
                
                if is_known_face:
                    continue  # Skip - already handled by face detection
                
                # Check if we've captured this motion recently
                last_capture = self.last_motion_capture_time.get(motion_id, 0)
                time_since_capture = current_time - last_capture
                
                if time_since_capture < self.motion_capture_interval:
                    continue  # Too soon to capture again
                
                # This is a new motion detection without face - capture it
                bbox = [x, y, x + bw, y + bh]
                
                # OPTIMIZED: Try face detection on full frame (faster than ROI extraction)
                # But limit to motion region to speed up
                # Expand ROI slightly to ensure we catch the face
                expand = 20
                roi_x1 = max(0, x - expand)
                roi_y1 = max(0, y - expand)
                roi_x2 = min(frame.shape[1], x + bw + expand)
                roi_y2 = min(frame.shape[0], y + bh + expand)
                roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
                
                has_face = False
                face_confidence = 0.0
                face_detections = []
                
                if roi.size > 0 and roi.shape[0] > 30 and roi.shape[1] > 30:
                    # Try face detection on this region (fast - only on motion area)
                    try:
                        face_detections = self.face_engine.detect_faces(roi)
                        has_face = len(face_detections) > 0
                        face_confidence = face_detections[0]['confidence'] if face_detections else 0.0
                    except:
                        # If face detection fails, continue with motion detection
                        pass
                    
                    # Adjust bbox to frame coordinates if face was detected in ROI
                    if face_detections:
                        face_bbox_roi = face_detections[0]['bbox']
                        face_bbox = [
                            roi_x1 + int(face_bbox_roi[0]),
                            roi_y1 + int(face_bbox_roi[1]),
                            roi_x1 + int(face_bbox_roi[2]),
                            roi_y1 + int(face_bbox_roi[3])
                        ]
                    else:
                        face_bbox = None
                    
                    # OPTIMIZED: Quick staff check - only if face was detected
                    # Skip staff check if no face (faster processing)
                    person_type = 'unknown'
                    rec_confidence = 0.0
                    is_staff = False
                    
                    if face_detections:
                        embedding = face_detections[0].get('embedding')
                        if embedding is not None:
                            # Quick staff identification
                            person_type, person_id, rec_confidence = self.face_engine.identify_person(embedding)
                            
                            # Check if staff (lower threshold for motion detections)
                            if person_type == 'staff' and person_id:
                                staff_info = self.db_manager.get_staff_info(person_id)
                                if staff_info and rec_confidence >= 0.45:  # Lower threshold for speed
                                    is_staff = True
                    
                    # Skip if confirmed staff
                    if is_staff:
                        continue
                    
                    # This is NOT staff - capture as unknown entry
                    print(f"🏃 Motion detected (no face/fast-moving): motion_id={motion_id}, has_face={has_face}, person_type={person_type}, conf={rec_confidence:.2f}")
                    
                    # Update capture time
                    self.last_motion_capture_time[motion_id] = current_time
                    
                    # Capture as unknown entry
                    motion_detections.append({
                        'bbox': bbox,
                        'face_bbox': face_bbox,
                        'face_confidence': face_confidence,
                        'recognition_confidence': rec_confidence,
                        'has_face': has_face,
                        'track_id': motion_id,
                        'person_type': person_type,
                        'motion_detected': True
                    })
            
            # Process motion detections as unknown entries
            if motion_detections:
                print(f"📸 Capturing {len(motion_detections)} motion-based unknown entry/entries...")
                self.process_unknown_entries(frame, motion_detections, current_time)
                
        except Exception as e:
            print(f"❌ Motion detection error: {e}")
            import traceback
            traceback.print_exc()
    
    def process_unknown_entries(self, frame, unknown_detections, current_time):
        """Process and capture unknown entries (persons without recognized faces or with covered faces)"""
        try:
            h, w = frame.shape[:2]
            system_mode = self.attendance_mode.get()
            
            for idx, detection in enumerate(unknown_detections):
                # Handle both face-based and motion-based detections
                # Motion detections have 'face_bbox' separate from 'bbox'
                is_motion = detection.get('motion_detected', False)
                
                if is_motion:
                    # Motion-based: use motion bbox for person, face_bbox for face (if available)
                    person_bbox = detection['bbox']  # Full body bbox from motion
                    face_bbox = detection.get('face_bbox', None)  # Face bbox if face was found
                else:
                    # Face-based: use face bbox
                    person_bbox = detection['bbox']
                    face_bbox = detection['bbox']
                
                face_confidence = detection.get('face_confidence', 0.0)
                rec_confidence = detection.get('recognition_confidence', 0.0)
                has_face = detection.get('has_face', True)
                track_id = detection.get('track_id', 0)
                person_type = detection.get('person_type', 'unknown')
                
                # Track ID should already be provided from the caller
                if track_id == 0:
                    # Fallback: generate track ID if not provided
                    x1, y1, x2, y2 = map(int, person_bbox)
                    face_center_x = (x1 + x2) // 2
                    face_center_y = (y1 + y2) // 2
                    face_size = (x2 - x1) * (y2 - y1)
                    track_id = hash((face_center_x // 50, face_center_y // 50, face_size // 1000))
                    track_id = abs(track_id) % 1000000
                
                # Determine entry type and reason with enhanced checking
                # Check if this is a motion-based detection (no face detected initially)
                is_motion_detection = detection.get('motion_detected', False)
                
                entry_type = 'unknown_person'
                reason = 'Face detected but not recognized as staff'
                
                # Enhanced reason determination
                if is_motion_detection:
                    # Motion-based detection (fast-moving person, face might not be detected)
                    if has_face:
                        entry_type = 'unknown_person'
                        reason = f'Fast-moving person detected (motion-based), face found but not recognized as staff (confidence: {rec_confidence:.2f})'
                    else:
                        entry_type = 'no_face'
                        reason = 'Fast-moving person detected (motion-based), no face detected - person moved too quickly'
                elif person_type == 'customer':
                    entry_type = 'customer'
                    reason = 'Recognized as customer, not staff member'
                elif face_confidence < 0.3:
                    entry_type = 'covered_face'
                    reason = 'Face partially covered or low detection confidence'
                elif rec_confidence < 0.5 and rec_confidence > 0:
                    entry_type = 'unknown_person'
                    reason = f'Face detected but person not in staff database (confidence: {rec_confidence:.2f})'
                elif rec_confidence == 0.0:
                    entry_type = 'unknown_person'
                    reason = 'Face detected but no match found in staff database'
                elif not has_face:
                    entry_type = 'no_face'
                    reason = 'No face detected'
                
                # Expand bounding box to capture full body
                # For motion detections, bbox is already full body, so use it directly
                # For face detections, expand from face bbox
                if is_motion and person_bbox:
                    # Motion detection already has full body bbox
                    body_x1, body_y1, body_x2, body_y2 = map(int, person_bbox)
                    # Use face_bbox if available, otherwise use person_bbox center
                    if face_bbox:
                        x1, y1, x2, y2 = map(int, face_bbox)
                    else:
                        # No face detected - use center of person bbox as approximate face location
                        center_x = (body_x1 + body_x2) // 2
                        center_y = body_y1 + (body_y2 - body_y1) // 7  # Face is about 1/7 from top
                        face_size = min((body_x2 - body_x1) // 3, (body_y2 - body_y1) // 4)
                        x1, y1 = center_x - face_size, center_y - face_size
                        x2, y2 = center_x + face_size, center_y + face_size
                else:
                    # Face detection - expand from face bbox
                    x1, y1, x2, y2 = map(int, face_bbox) if face_bbox else map(int, person_bbox)
                    face_height = y2 - y1
                    face_width = x2 - x1
                    
                    # Expand to capture full body (estimated)
                    # Expand downward by ~6x face height, upward by ~1x, sideways by ~2x
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
                    # Fallback: use person bbox directly
                    body_x1, body_y1, body_x2, body_y2 = map(int, person_bbox)
                    full_body_image = frame[body_y1:body_y2, body_x1:body_x2].copy()
                
                # Record unknown entry in database
                # Use face_bbox if available, otherwise use approximate face location
                face_bbox_for_db = [x1, y1, x2, y2] if (face_bbox or not is_motion) else None
                
                print(f"💾 Attempting to record unknown entry: Track ID {track_id}, Type: {entry_type}, Motion: {is_motion}")
                entry_id = self.db_manager.record_unknown_entry(
                    track_id=track_id,
                    entry_type=entry_type,
                    frame_image=full_body_image,
                    face_bbox=face_bbox_for_db,
                    person_bbox=[body_x1, body_y1, body_x2, body_y2],
                    face_detected=has_face,
                    face_confidence=float(face_confidence),
                    recognition_confidence=float(rec_confidence),
                    reason=reason,
                    system_mode=system_mode
                )
                
                if entry_id:
                    # Mark this track as captured (so they won't be captured again until they leave and return)
                    unknown_track_key = f"unknown_{track_id}"
                    if unknown_track_key in self.unknown_track_status:
                        self.unknown_track_status[unknown_track_key]['captured'] = True
                    print(f"✅ Unknown entry SUCCESSFULLY recorded in database: Entry ID {entry_id}, Track ID {track_id}, Type: {entry_type}, Reason: {reason}")
                else:
                    print(f"❌ FAILED to record unknown entry in database: Track ID {track_id}, Type: {entry_type}")
                
        except Exception as e:
            print(f"❌ Error processing unknown entries: {e}")
            import traceback
            traceback.print_exc()
    
    def record_checkin(self, staff_id, check_time, confidence):
        """Record check-in"""
        try:
            # Calculate if late
            expected_time = dt_time(9, 0)  # 9:00 AM
            is_late = check_time.time() > expected_time
            
            if is_late:
                minutes_late = int((check_time.time().hour * 60 + check_time.time().minute) - 
                                 (expected_time.hour * 60 + expected_time.minute))
            else:
                minutes_late = 0
            
            status = f"{minutes_late} min Late" if is_late else "On Time"
            
            # Store attendance data
            self.today_attendance[staff_id] = {
                'staff_id': staff_id,
                'check_in_time': check_time,
                'status': status,
                'confidence': confidence
            }
            
            # Save to database - convert confidence to float to avoid SQLite type errors
            confidence_float = float(confidence) if confidence is not None else 1.0
            self.db_manager.record_staff_attendance(staff_id, 'check_in', confidence_float)
            
            print(f"✅ Check-in: {staff_id} at {check_time.strftime('%I:%M %p')} - {status}")
            
        except Exception as e:
            print(f"Check-in error: {e}")
    
    def record_checkout(self, staff_id, check_time, confidence):
        """Record check-out"""
        try:
            # Update attendance data
            if staff_id in self.today_attendance:
                self.today_attendance[staff_id]['check_out_time'] = check_time
            else:
                self.today_attendance[staff_id] = {
                    'staff_id': staff_id,
                    'check_out_time': check_time,
                    'confidence': confidence
                }
            
            # Save to database - convert confidence to float to avoid SQLite type errors
            confidence_float = float(confidence) if confidence is not None else 1.0
            self.db_manager.record_staff_attendance(staff_id, 'check_out', confidence_float)
            
            print(f"✅ Check-out: {staff_id} at {check_time.strftime('%I:%M %p')}")
            
        except Exception as e:
            print(f"Check-out error: {e}")
    
    def refresh_attendance_cards(self):
        """Refresh the attendance cards display"""
        try:
            # Ensure employee_id_map exists
            if not hasattr(self, 'employee_id_map') or self.employee_id_map is None:
                self.employee_id_map = {}
                self.load_employee_ids()
            
            # Clear existing cards
            for widget in self.cards_container.winfo_children():
                widget.destroy()
            
            mode = self.attendance_mode.get()
            now = datetime.now()
            
            # Get all staff or today's attendance based on mode
            if mode == 'checkin':
                # Show all staff with today's check-in status
                all_staff = self.db_manager.get_all_staff()
                display_items = []
                
                for staff in all_staff:
                    staff_id = staff['staff_id']
                    if staff_id in self.today_attendance:
                        display_items.append({
                            'staff_id': staff_id,
                            'name': staff.get('name', 'Unknown'),
                            'employee_id': self.get_employee_id(staff_id),
                            'time': self.today_attendance[staff_id]['check_in_time'],
                            'status': self.today_attendance[staff_id]['status'],
                            'photo': self.captured_photos.get(staff_id)
                        })
                    else:
                        # Not checked in yet
                        display_items.append({
                            'staff_id': staff_id,
                            'name': staff.get('name', 'Unknown'),
                            'employee_id': self.get_employee_id(staff_id),
                            'time': None,
                            'status': None,
                            'photo': None
                        })
            else:
                # Check-out mode: show checked-in staff
                display_items = []
                for staff_id, att_data in self.today_attendance.items():
                    if 'check_in_time' in att_data:
                        staff_info = self.db_manager.get_staff_info(staff_id)
                        display_items.append({
                            'staff_id': staff_id,
                            'name': staff_info.get('name', 'Unknown') if staff_info else 'Unknown',
                            'employee_id': self.get_employee_id(staff_id),
                            'time': att_data.get('check_out_time', att_data['check_in_time']),
                            'status': 'Checked Out' if 'check_out_time' in att_data else 'Checked In',
                            'photo': self.captured_photos.get(staff_id)
                        })
            
            # Sort by time (most recent first)
            display_items.sort(key=lambda x: x['time'] or datetime.min, reverse=True)
            
            # Create cards in grid (3 columns)
            rows_frame = None
            for i, item in enumerate(display_items[:20]):  # Show max 20
                if i % 3 == 0:
                    rows_frame = tk.Frame(self.cards_container, bg='#8B4513')
                    rows_frame.pack(fill=tk.X, padx=5, pady=5)
                
                self.create_employee_card(rows_frame, item, mode)
            
            # Update canvas scroll region
            self.cards_container.update_idletasks()
            self.cards_canvas.config(scrollregion=self.cards_canvas.bbox('all'))
            
        except Exception as e:
            print(f"Refresh cards error: {e}")
            import traceback
            traceback.print_exc()
    
    def create_employee_card(self, parent, item, mode):
        """Create a single employee card matching the image design"""
        card_frame = tk.Frame(
            parent,
            bg='#654321',  # Dark brown card
            relief=tk.RAISED,
            borderwidth=2
        )
        card_frame.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        # Photo/avatar with icon overlay
        photo_frame = tk.Frame(card_frame, bg='#654321', width=80, height=80)
        photo_frame.pack(pady=5)
        photo_frame.pack_propagate(False)
        
        # Create canvas for photo with icon overlay
        photo_canvas = tk.Canvas(
            photo_frame,
            width=70,
            height=70,
            bg='lightgray',
            highlightthickness=0
        )
        photo_canvas.pack(padx=5, pady=5)
        
        photo_label = tk.Label(photo_frame, bg='lightgray', width=70, height=70)
        photo_label.pack_forget()  # Hide label, use canvas instead
        
        # Determine which icon/photo to show
        has_photo = item['photo'] is not None
        has_checkin = item['time'] is not None
        
        # Display photo if available (from captured attendance photo)
        if has_photo:
            try:
                photo = item['photo']
                if isinstance(photo, np.ndarray):
                    # Resize photo to fit canvas
                    photo_resized = cv2.resize(photo, (70, 70))
                    photo_rgb = cv2.cvtColor(photo_resized, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(photo_rgb)
                    
                    # Add profile icon overlay on top of photo if checked in
                    if has_checkin and 'profile' in self.employee_icons:
                        try:
                            # Load Vector-2.png icon for overlay
                            icon_paths = [
                                'assets/icons/Vector-2.png',
                                './assets/icons/Vector-2.png',
                                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'icons', 'Vector-2.png'),
                                os.path.join(os.getcwd(), 'assets', 'icons', 'Vector-2.png')
                            ]
                            icon_path = None
                            for path in icon_paths:
                                if os.path.exists(path):
                                    icon_path = path
                                    break
                            
                            if icon_path:
                                icon_img = Image.open(icon_path)
                                if icon_img.mode != 'RGBA':
                                    icon_img = icon_img.convert('RGBA')
                                # Resize icon to overlay size (smaller, positioned in corner)
                                icon_img = icon_img.resize((25, 25), Image.Resampling.LANCZOS)
                                # Paste icon in bottom-right corner with transparency
                                pil_image = pil_image.convert('RGBA')
                                pil_image.paste(icon_img, (70-25-5, 70-25-5), icon_img)
                        except Exception as e:
                            print(f"Error adding icon overlay: {e}")
                    
                    photo_tk = ImageTk.PhotoImage(pil_image)
                    photo_canvas.create_image(35, 35, anchor='center', image=photo_tk)
                    photo_canvas.image = photo_tk  # Keep reference
            except Exception as e:
                print(f"Error displaying photo: {e}")
                # Fall through to icon display
                has_photo = False
        
        # Display icon if no photo available
        if not has_photo:
            try:
                # Choose icon based on check-in status
                # Checked in employees: use Group 3.png (default icon)
                # Not checked in: use Vector-1.png (placeholder icon)
                if has_checkin:
                    # Employee has checked in - use default/Group 3 icon
                    if 'default' in self.employee_icons:
                        icon_photo = self.employee_icons['default']
                    elif 'profile' in self.employee_icons:
                        icon_photo = self.employee_icons['profile']
                    else:
                        icon_photo = None
                else:
                    # Employee hasn't checked in - use placeholder/Vector-1 icon
                    if 'placeholder' in self.employee_icons:
                        icon_photo = self.employee_icons['placeholder']
                    elif 'default' in self.employee_icons:
                        icon_photo = self.employee_icons['default']
                    else:
                        icon_photo = None
                
                if icon_photo:
                    # Center icon on canvas
                    photo_canvas.create_image(35, 35, anchor='center', image=icon_photo)
                    photo_canvas.icon = icon_photo  # Keep reference
                else:
                    # No icon available - show gray rectangle
                    photo_canvas.create_rectangle(5, 5, 65, 65, fill='lightgray', outline='gray', width=2)
            except Exception as e:
                print(f"Error displaying icon: {e}")
                # Fallback to simple rectangle
                photo_canvas.create_rectangle(5, 5, 65, 65, fill='lightgray', outline='gray', width=2)
        
        # Employee ID
        id_label = tk.Label(
            card_frame,
            text=f"ID: {item['employee_id']}",
            bg='#654321',
            fg='white',
            font=('Arial', 9)
        )
        id_label.pack()
        
        # Time
        if item['time']:
            time_text = item['time'].strftime("%I:%M %p")
        else:
            time_text = "--:--"
        
        time_label = tk.Label(
            card_frame,
            text=time_text,
            bg='#654321',
            fg='white',
            font=('Arial', 9)
        )
        time_label.pack()
        
        # Status
        if item['status']:
            status_color = 'green' if item['status'] == 'On Time' else 'red'
            status_label = tk.Label(
                card_frame,
                text=item['status'],
                bg='#654321',
                fg=status_color,
                font=('Arial', 9, 'bold')
            )
            status_label.pack()
    
    def update_remaining_count(self):
        """Update remaining count for checkout mode"""
        if self.attendance_mode.get() == 'checkout':
            checked_in_count = sum(1 for att in self.today_attendance.values() 
                                  if 'check_in_time' in att)
            checked_out_count = sum(1 for att in self.today_attendance.values() 
                                   if 'check_out_time' in att)
            remaining = checked_in_count - checked_out_count
            
            self.remaining_label.config(text=f"REMAINING : {remaining}")
    
    def display_video(self):
        """Display video feed with overlays - OPTIMIZED FOR HIGH FPS"""
        while self.running:
            try:
                with self.frame_lock:
                    if self.current_frame is None:
                        time.sleep(0.02)  # Reduced wait time
                        continue
                    frame = self.current_frame.copy()
                    detections = self.current_detections.copy()
                
                # Draw face detection boxes and overlays FIRST
                frame = self.draw_face_detections(frame, detections)
                
                # Add camera overlays matching the image
                frame = self.add_camera_overlays(frame)
                
                # Add timestamp
                timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                cv2.putText(frame, timestamp, (10, frame.shape[0] - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Add background image overlay to frame if available
                if self.background_image:
                    frame = self.add_background_overlay(frame)
                
                # Resize for display (optimize size)
                display_frame = cv2.resize(frame, (800, 600))
                display_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(display_rgb)
                photo = ImageTk.PhotoImage(image=pil_image)
                
                # Update canvas with video
                if hasattr(self, 'video_canvas'):
                    # Remove old video image
                    self.video_canvas.delete('video_image')
                    # Hide the text label
                    self.video_label.config(text="")
                    # Get canvas size
                    canvas_width = self.video_canvas.winfo_width()
                    canvas_height = self.video_canvas.winfo_height()
                    
                    if canvas_width > 1 and canvas_height > 1:
                        # Scale photo to fit canvas
                        photo_width = photo.width()
                        photo_height = photo.height()
                        scale_x = canvas_width / photo_width
                        scale_y = canvas_height / photo_height
                        scale = min(scale_x, scale_y)
                        new_width = int(photo_width * scale)
                        new_height = int(photo_height * scale)
                        
                        # Resize photo
                        pil_resized = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        photo_resized = ImageTk.PhotoImage(pil_resized)
                        
                        # Center the image
                        x = canvas_width // 2
                        y = canvas_height // 2
                        self.video_canvas.create_image(x, y, anchor='center', image=photo_resized, tags='video_image')
                        self.video_canvas.tag_raise('video_image')  # Above background
                        self.video_canvas.video_image = photo_resized  # Keep reference
                else:
                    # Fallback to label if canvas not available
                    self.video_label.config(image=photo, text="")
                    self.video_label.image = photo
                
                time.sleep(0.01)  # ~100 FPS display - ultra smooth, reduced lag
                
            except Exception as e:
                print(f"Display error: {e}")
                time.sleep(0.1)
    
    def draw_face_detections(self, frame, detections):
        """Draw face detection bounding boxes and recognition info - Shows ALL faces"""
        try:
            for det in detections:
                bbox = det.get('bbox')
                if bbox is None:
                    continue
                
                x1, y1, x2, y2 = map(int, bbox)
                person_type = det.get('person_type', 'unknown')
                person_id = det.get('person_id')
                rec_confidence = det.get('recognition_confidence', 0.0)
                det_confidence = det.get('confidence', 0.0)
                
                # Draw bounding box - ALWAYS draw for ALL detected faces (matching image style)
                # Use bright blue box like in the image (BGR: Blue=255, Green=144, Red=30)
                color = (255, 144, 30)  # Bright blue matching image
                box_thickness = 3
                
                # Draw bounding box with blue color - thick box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, box_thickness)
                
                # Semi-transparent blue overlay for visibility
                overlay = frame.copy()
                cv2.rectangle(overlay, (x1-2, y1-2), (x2+2, y2+2), color, -1)
                cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
                
                # Text ABOVE face - Always show these labels matching image
                text_y = max(50, y1)
                text_color = (255, 255, 255)  # White text for visibility
                
                # Draw labels above face (matching image)
                cv2.putText(frame, 'FACIAL RECOGNITION', (x1, text_y - 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.85, text_color, 2)
                cv2.putText(frame, 'HUMAN MOTION DETECTED', (x1, text_y - 18), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.75, text_color, 2)
                
                # Text BELOW face
                cv2.putText(frame, 'MOTION DATA', (x1, y2 + 25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)
                
                # Show recognition status
                if person_type == 'staff' and person_id and rec_confidence >= 0.55:
                    # Staff recognized - show ID and name
                    staff_info = self.db_manager.get_staff_info(person_id)
                    if staff_info:
                        employee_id = self.get_employee_id(person_id)
                        name = staff_info.get('name', 'Unknown')
                        # Show ID above face
                        cv2.putText(frame, f'ID: {employee_id}', (x1, text_y - 2), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        cv2.putText(frame, f'STEP 2', (x1, y2 + 45), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
                else:
                    # Still detecting/unknown - show detection status
                    cv2.putText(frame, f'Detecting... ({det_confidence:.2f})', (x1, text_y - 2), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
                    
        except Exception as e:
            print(f"Draw detections error: {e}")
            import traceback
            traceback.print_exc()
        
        return frame
    
    def load_background_image(self):
        """Load the Vector.png background/logo image"""
        try:
            # Try multiple possible paths
            possible_paths = [
                'assets/icons/Vector.png',
                './assets/icons/Vector.png',
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'icons', 'Vector.png'),
                os.path.join(os.getcwd(), 'assets', 'icons', 'Vector.png')
            ]
            
            image_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    image_path = path
                    break
            
            if image_path and os.path.exists(image_path):
                self.background_image = Image.open(image_path)
                # Convert to RGBA if needed for transparency
                if self.background_image.mode != 'RGBA':
                    self.background_image = self.background_image.convert('RGBA')
                self.background_photo = ImageTk.PhotoImage(self.background_image)
                print(f"✅ Loaded background image from: {image_path}")
            else:
                print(f"⚠️ Background image not found. Searched: {possible_paths}")
                self.background_image = None
                self.background_photo = None
        except Exception as e:
            print(f"⚠️ Error loading background image: {e}")
            self.background_image = None
            self.background_photo = None
    
    def load_employee_icons(self):
        """Load employee card icons from assets/icons folder"""
        try:
            # Icon files to load
            icon_files = {
                'default': 'Group 3.png',
                'placeholder': 'Vector-1.png',
                'profile': 'Vector-2.png'
            }
            
            # Try multiple possible paths
            base_paths = [
                'assets/icons',
                './assets/icons',
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'icons'),
                os.path.join(os.getcwd(), 'assets', 'icons')
            ]
            
            base_path = None
            for path in base_paths:
                if os.path.exists(path):
                    base_path = path
                    break
            
            if base_path:
                for icon_key, icon_file in icon_files.items():
                    icon_path = os.path.join(base_path, icon_file)
                    if os.path.exists(icon_path):
                        try:
                            icon_img = Image.open(icon_path)
                            # Convert to RGBA for transparency support
                            if icon_img.mode != 'RGBA':
                                icon_img = icon_img.convert('RGBA')
                            # Resize to standard size for employee cards (70x70)
                            icon_img = icon_img.resize((70, 70), Image.Resampling.LANCZOS)
                            self.employee_icons[icon_key] = ImageTk.PhotoImage(icon_img)
                            print(f"✅ Loaded icon '{icon_key}' from: {icon_path}")
                        except Exception as e:
                            print(f"⚠️ Error loading icon {icon_file}: {e}")
                    else:
                        print(f"⚠️ Icon file not found: {icon_path}")
            else:
                print(f"⚠️ Icons directory not found. Searched: {base_paths}")
        except Exception as e:
            print(f"⚠️ Error loading employee icons: {e}")
    
    def update_canvas_background(self):
        """Update canvas background with Vector.png image"""
        try:
            if hasattr(self, 'video_canvas') and self.background_photo:
                # Get canvas size
                self.video_canvas.update_idletasks()
                canvas_width = self.video_canvas.winfo_width()
                canvas_height = self.video_canvas.winfo_height()
                
                if canvas_width > 1 and canvas_height > 1 and self.background_image:
                    # Scale background to fit canvas
                    bg_scaled = self.background_image.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                    bg_photo_scaled = ImageTk.PhotoImage(bg_scaled)
                    # Remove old background and add new one
                    self.video_canvas.delete('bg_image')
                    self.video_canvas.create_image(0, 0, anchor='nw', image=bg_photo_scaled, tags='bg_image')
                    self.video_canvas.tag_lower('bg_image')  # Put background at bottom
                    self.video_canvas.bg_image = bg_photo_scaled  # Keep reference
        except Exception as e:
            print(f"Error updating canvas background: {e}")
    
    def add_background_overlay(self, frame):
        """Add background image overlay to video frame"""
        try:
            if self.background_image is None:
                return frame
            
            h, w = frame.shape[:2]
            
            # Convert frame to PIL Image
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_frame = Image.fromarray(frame_rgb)
            
            # Resize background image to frame size
            bg_resized = self.background_image.resize((w, h), Image.Resampling.LANCZOS)
            
            # Create a semi-transparent overlay (adjust alpha as needed)
            # Blend background with frame - adjust alpha for desired transparency
            alpha = 0.1  # 10% opacity - very subtle background
            overlay = Image.blend(pil_frame, bg_resized.convert('RGB'), alpha)
            
            # Convert back to OpenCV format
            overlay_np = np.array(overlay)
            frame_bgr = cv2.cvtColor(overlay_np, cv2.COLOR_RGB2BGR)
            
            return frame_bgr
        except Exception as e:
            print(f"Error adding background overlay: {e}")
            return frame
    
    def add_camera_overlays(self, frame):
        """Add camera overlays matching the image design"""
        h, w = frame.shape[:2]
        
        # Add Vector.png logo overlay in top left (if available)
        if self.background_image:
            try:
                # Resize logo to appropriate size for overlay
                logo_size = (150, 150)  # Adjust size as needed
                logo_resized = self.background_image.resize(logo_size, Image.Resampling.LANCZOS)
                logo_np = np.array(logo_resized)
                
                # Convert RGBA to BGR for OpenCV
                if logo_np.shape[2] == 4:  # Has alpha channel
                    # Extract alpha channel
                    alpha = logo_np[:, :, 3:4] / 255.0
                    logo_rgb = logo_np[:, :, :3]
                    logo_bgr = cv2.cvtColor(logo_rgb, cv2.COLOR_RGB2BGR)
                    
                    # Get position in frame (top left with padding)
                    y1, y2 = 10, 10 + logo_size[1]
                    x1, x2 = 10, 10 + logo_size[0]
                    
                    # Ensure it fits
                    if y2 <= h and x2 <= w:
                        # Blend logo with frame using alpha
                        roi = frame[y1:y2, x1:x2].astype(np.float32)
                        logo_float = logo_bgr.astype(np.float32)
                        alpha_3d = alpha
                        
                        blended = roi * (1 - alpha_3d) + logo_float * alpha_3d
                        frame[y1:y2, x1:x2] = blended.astype(np.uint8)
                else:
                    # No alpha channel, just overlay
                    logo_bgr = cv2.cvtColor(logo_np, cv2.COLOR_RGB2BGR)
                    y1, y2 = 10, 10 + logo_size[1]
                    x1, x2 = 10, 10 + logo_size[0]
                    if y2 <= h and x2 <= w:
                        frame[y1:y2, x1:x2] = logo_bgr
            except Exception as e:
                print(f"Error adding logo overlay: {e}")
        
        # Add "impex" text (top left, next to logo)
        cv2.putText(frame, 'impex', (170, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                   1.2, (0, 0, 255), 3)
        cv2.putText(frame, 'FOV', (170, 80), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.6, (255, 255, 255), 1)
        
        # Add "LIVE" indicator (top right) - red background
        cv2.rectangle(frame, (w-110, 10), (w-10, 45), (0, 0, 255), -1)
        cv2.putText(frame, 'LIVE', (w-95, 35), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.8, (255, 255, 255), 2)
        cv2.putText(frame, 'CAMERA', (w-110, 58), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (255, 255, 255), 1)
        cv2.putText(frame, 'DET', (w-55, 58), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (255, 255, 255), 1)
        
        # Camera settings (bottom left)
        cv2.putText(frame, '0 1/100 F 2.8', (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (255, 255, 255), 1)
        
        # Motion data (bottom center)
        if len(self.current_detections) > 0:
            cv2.putText(frame, f'MOTION DATA - {len(self.current_detections)} DETECTED', 
                       (w//2-150, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        else:
            cv2.putText(frame, 'MOTION DATA', (w//2-80, h-30), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, (255, 255, 255), 1)
        
        # Resolution (bottom right)
        cv2.putText(frame, 'HD 2K', (w-80, h-30), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.6, (255, 255, 255), 1)
        
        return frame
    
    def load_employee_ids(self):
        """Load employee IDs from database"""
        try:
            all_staff = self.db_manager.get_all_staff()
            for staff in all_staff:
                staff_id = staff['staff_id']
                employee_id = staff.get('employee_id')
                
                # Use employee_id from database if available, otherwise extract from staff_id
                if employee_id:
                    self.employee_id_map[staff_id] = employee_id
                else:
                    # Extract ID from staff_id format (e.g., "STAFF_4730" -> "4730")
                    if staff_id.startswith('STAFF_'):
                        self.employee_id_map[staff_id] = staff_id.replace('STAFF_', '')
                    else:
                        self.employee_id_map[staff_id] = staff_id
            
            print(f"✅ Loaded {len(self.employee_id_map)} employee IDs from database")
        except Exception as e:
            print(f"Load employee IDs error: {e}")
            # Initialize empty if error
            if not hasattr(self, 'employee_id_map'):
                self.employee_id_map = {}
    
    def load_fake_employees(self):
        """Load/create fake employees for testing"""
        try:
            # Check if employees exist, if not create fake ones
            all_staff = self.db_manager.get_all_staff()
            if len(all_staff) == 0:
                print("Creating fake employees for testing...")
                self.create_fake_employees()
        except Exception as e:
            print(f"Load fake employees error: {e}")
    
    def create_fake_employees(self):
        """Create fake employees with IDs for testing"""
        fake_employees = [
            {'employee_id': '2484', 'name': 'John Doe', 'department': 'IT'},
            {'employee_id': '2485', 'name': 'Jane Smith', 'department': 'HR'},
            {'employee_id': '2486', 'name': 'Bob Johnson', 'department': 'Finance'},
            {'employee_id': '2487', 'name': 'Alice Brown', 'department': 'Operations'},
            {'employee_id': '2488', 'name': 'Charlie Wilson', 'department': 'IT'},
            {'employee_id': '2489', 'name': 'Diana Davis', 'department': 'HR'},
            {'employee_id': '2490', 'name': 'Edward Miller', 'department': 'Finance'},
            {'employee_id': '2491', 'name': 'Fiona Garcia', 'department': 'Operations'},
            {'employee_id': '2492', 'name': 'George Martinez', 'department': 'IT'},
        ]
        
        # Store employee_id mapping - don't overwrite existing
        if not hasattr(self, 'employee_id_map') or self.employee_id_map is None:
            self.employee_id_map = {}
        
        for emp in fake_employees:
            staff_id = f"STAFF_{emp['employee_id']}"
            # Only add if not already in map
            if staff_id not in self.employee_id_map:
                self.employee_id_map[staff_id] = emp['employee_id']
            
            # Note: This will create staff without photos initially
            # Photos will be captured during auto-registration
            print(f"Created fake employee: {emp['name']} (ID: {emp['employee_id']})")
    
    def get_employee_id(self, staff_id):
        """Get employee ID number for staff_id"""
        # Ensure employee_id_map exists
        if not hasattr(self, 'employee_id_map') or self.employee_id_map is None:
            self.employee_id_map = {}
        
        # Try to get from map first
        if staff_id in self.employee_id_map:
            return self.employee_id_map[staff_id]
        
        # Fallback: extract from staff_id format
        if staff_id.startswith('STAFF_'):
            return staff_id.replace('STAFF_', '')
        
        return staff_id
    
    def get_today_attendance(self):
        """Get today's attendance summary"""
        return self.today_attendance
    
    def load_today_attendance(self):
        """Load today's attendance from database"""
        try:
            today = date.today()
            attendance_records = self.db_manager.get_today_attendance(today)
            
            for record in attendance_records:
                staff_id = record['staff_id']
                # Handle datetime parsing
                check_in = record.get('check_in_time')
                check_out = record.get('check_out_time')
                
                self.today_attendance[staff_id] = {
                    'staff_id': staff_id,
                    'check_in_time': check_in if isinstance(check_in, datetime) else None,
                    'check_out_time': check_out if isinstance(check_out, datetime) else None,
                    'status': record.get('status', 'Present')
                }
            
            print(f"✅ Loaded {len(self.today_attendance)} attendance records")
            
        except Exception as e:
            print(f"Load attendance error: {e}")
            # Initialize empty if error
            self.today_attendance = {}

