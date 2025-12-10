# src/ui/dashboard.py - Enhanced Implementation with Fixed Message Flow and Fullscreen

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import threading
import time
from datetime import datetime, date
import numpy as np
import os
import sqlite3

# Import optimized modules
from core.face_engine import FaceRecognitionEngine
from core.tracking_manager import TrackingManager
from utils.camera_utils import CameraManager
from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager

class FactoryAttendanceDashboard:
    def __init__(self, root, gpu_available=False):
        self.parent = root
        self.gpu_available = gpu_available
        self.running = False
        self.config = ConfigManager()
        self.config.register_ip_change_callback(self.on_camera_ip_change)
        self.db_manager = DatabaseManager()
        
        # Initialize fullscreen variables FIRST
        self.fullscreen_window = None
        self.fullscreen_label = None
        self.fullscreen_active = False
        
        # Frame capture system with thread safety
        self.current_frame = None
        self.current_detections = []
        self.current_tracks = []
        self.capture_lock = threading.RLock()
        self.captured_photos = []
        self.auto_capture_enabled = False
        
        # Visit tracking system
        # ✅ ENHANCED: Separate counters for customer types
        self.visit_counts = {
            'total_today': 0,
            'new_customers': 0,           # First-time visitors
            'returning_customers': 0,     # Known customers with new visits
            'returning_already_counted': 0, # Known customers already counted today
            'staff_checkins': 0
        }
        
        # **CRITICAL MESSAGE SYSTEM - WORKING IMPLEMENTATION**
        self.face_messages = {}  # bbox_key -> message_data
        self.message_timers = {}  # bbox_key -> timer_info
        self.processed_faces = {}  # bbox_key -> processing_status
        
        # Track customers counted for the current day
        self.current_date = date.today()
        self.customers_today = set()
        self.staff_today = set()
        
        # Performance tracking
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.current_fps = 0
        self.frame_count = 0
        # Manual tracking structures removed in favor of DeepSort persistent IDs
        
        # Ultra-optimization settings
        self.process_every_n_frames = 2
        self.checking_duration = 2.0
        self.display_duration = 5.0
        self.auto_register_delay = 3.0
        
        # Detection statistics
        self.detection_stats = {
            'total_detections': 0,
            'known_customers': 0,
            'unknown_persons': 0,
            'staff_detections': 0
        }
        
        self.setup_gui()
        self.setup_engines()

    def setup_gui(self):
        """Setup enhanced GUI maintaining original layout"""
        # Create main paned window
        paned = ttk.PanedWindow(self.parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel for video and controls
        left_panel = ttk.Frame(paned)
        paned.add(left_panel, weight=3)
        
        # Right panel for statistics and logs
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=1)
        
        # Enhanced Video Frame
        video_frame = ttk.LabelFrame(left_panel, text="🏭 Factory Attendance - Live Camera Feed", padding=10)
        video_frame.pack(fill=tk.BOTH, expand=True)
        
        self.video_label = tk.Label(video_frame, bg='black', text="Camera Disconnected")
        self.video_label.pack(fill=tk.BOTH, expand=True)
        
        # Enhanced Controls Frame
        control_frame = ttk.LabelFrame(left_panel, text="🎮 System Controls", padding=10)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Main control buttons
        main_buttons = ttk.Frame(control_frame)
        main_buttons.pack(fill=tk.X, pady=5)
        
        self.start_btn = ttk.Button(main_buttons, text="▶ Start Attendance Recognition",
                                   command=self.start_enhanced_recognition)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(main_buttons, text="⏹ Stop Recognition",
                                  command=self.stop_recognition, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Photo capture controls
        capture_buttons = ttk.Frame(control_frame)
        capture_buttons.pack(fill=tk.X, pady=5)
        
        self.capture_btn = ttk.Button(capture_buttons, text="📸 Capture Photo",
                                     command=self.capture_current_frame, state=tk.DISABLED)
        self.capture_btn.pack(side=tk.LEFT, padx=5)
        
        self.auto_capture_var = tk.BooleanVar()
        self.auto_capture_check = ttk.Checkbutton(capture_buttons, text="🔄 Auto Capture",
                                                 variable=self.auto_capture_var,
                                                 command=self.toggle_auto_capture)
        self.auto_capture_check.pack(side=tk.LEFT, padx=5)
        
        self.fullscreen_btn = ttk.Button(capture_buttons, text="🔳 Fullscreen",
                                        command=self.toggle_fullscreen_camera)
        self.fullscreen_btn.pack(side=tk.LEFT, padx=5)
        
        # Debug controls
        debug_buttons = ttk.Frame(control_frame)
        debug_buttons.pack(fill=tk.X, pady=5)
        
        self.reset_stats_btn = ttk.Button(debug_buttons, text="🔄 Reset Stats",
                                         command=self.reset_visit_stats)
        self.reset_stats_btn.pack(side=tk.LEFT, padx=5)
        
        # Detection threshold control
        threshold_frame = ttk.Frame(debug_buttons)
        threshold_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(threshold_frame, text="Threshold:").pack(side=tk.LEFT)
        self.threshold_var = tk.DoubleVar(value=0.5)
        threshold_scale = ttk.Scale(threshold_frame, from_=0.3, to=0.9, 
                                   orient=tk.HORIZONTAL, variable=self.threshold_var,
                                   length=100, command=self.update_detection_threshold)
        threshold_scale.pack(side=tk.LEFT, padx=5)
        
        self.threshold_label = ttk.Label(threshold_frame, text="0.5")
        self.threshold_label.pack(side=tk.LEFT, padx=2)
        
        # Mode selection
        mode_frame = ttk.Frame(debug_buttons)
        mode_frame.pack(side=tk.RIGHT)
        
        ttk.Label(mode_frame, text="Mode:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="GPU" if self.gpu_available else "CPU")
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.mode_var,
                                 values=["GPU", "CPU"] if self.gpu_available else ["CPU"],
                                 state="readonly", width=8)
        mode_combo.pack(side=tk.LEFT, padx=5)
        
        # Enhanced status display
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=5)

        self.camera_status = ttk.Label(status_frame, text="📹 Camera: Disconnected", foreground="red")
        self.camera_status.pack(side=tk.LEFT)

        self.camera_ip_label = ttk.Label(status_frame, text=f"IP: {self._get_current_camera_ip()}")
        self.camera_ip_label.pack(side=tk.LEFT, padx=(10, 0))

        self.processing_status = ttk.Label(status_frame, text="🧠 Processing: Stopped", foreground="red")
        self.processing_status.pack(side=tk.RIGHT)
        
        # Setup enhanced right panel
        self.setup_enhanced_right_panel(right_panel)

    def setup_enhanced_right_panel(self, right_panel):
        """Setup enhanced right panel maintaining original layout"""
        # Real-time System Statistics
        stats_frame = ttk.LabelFrame(right_panel, text="📊 Live Performance Stats", padding=10)
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.fps_label = ttk.Label(stats_frame, text="FPS: 0", font=("Arial", 10, "bold"))
        self.fps_label.pack(anchor=tk.W)
        
        self.detections_label = ttk.Label(stats_frame, text="Face Detections: 0", font=("Arial", 10))
        self.detections_label.pack(anchor=tk.W)
        
        self.tracks_label = ttk.Label(stats_frame, text="Active Tracks: 0", font=("Arial", 10))
        self.tracks_label.pack(anchor=tk.W)
        
        self.staff_label = ttk.Label(stats_frame, text="Total Staff Members: 0", font=("Arial", 10))
        self.staff_label.pack(anchor=tk.W)
        
        # Factory Attendance Counts Display
        visits_frame = ttk.LabelFrame(right_panel, text="🏭 Today's Attendance", padding=10)
        visits_frame.pack(fill=tk.X, pady=5)
        
        self.staff_checkins_label = ttk.Label(visits_frame, text="Staff Check-ins Today: 0",
                                           font=("Arial", 12, "bold"), foreground="green")
        self.staff_checkins_label.pack(anchor=tk.W)
        
        self.staff_present_count_label = ttk.Label(visits_frame, text="Present: 0", font=("Arial", 10), foreground="green")
        self.staff_present_count_label.pack(anchor=tk.W)
        
        self.staff_absent_count_label = ttk.Label(visits_frame, text="Absent: 0", font=("Arial", 10), foreground="red")
        self.staff_absent_count_label.pack(anchor=tk.W)
        
        self.staff_late_count_label = ttk.Label(visits_frame, text="Late: 0", font=("Arial", 10), foreground="orange")
        self.staff_late_count_label.pack(anchor=tk.W)
        
        # Factory Staff Detections
        detections_frame = ttk.LabelFrame(right_panel, text="👥 Staff Detections", padding=5)
        detections_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ('Time', 'Type', 'ID', 'Status', 'Confidence', 'Action')
        self.recent_tree = ttk.Treeview(detections_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            width = 80 if col != 'Status' else 100
            self.recent_tree.heading(col, text=col)
            self.recent_tree.column(col, width=width)
        
        detection_scrollbar = ttk.Scrollbar(detections_frame, orient=tk.VERTICAL, command=self.recent_tree.yview)
        self.recent_tree.configure(yscrollcommand=detection_scrollbar.set)
        
        self.recent_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detection_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Staff Attendance Summary
        attendance_frame = ttk.LabelFrame(right_panel, text="⏰ Factory Attendance Status", padding=5)
        attendance_frame.pack(fill=tk.X, pady=5)

        self.staff_present_label = ttk.Label(attendance_frame, text="Present: 0", font=("Arial", 10))
        self.staff_present_label.pack(anchor=tk.W)

        self.staff_absent_label = ttk.Label(attendance_frame, text="Absent: 0", font=("Arial", 10))
        self.staff_absent_label.pack(anchor=tk.W)

        self.staff_late_label = ttk.Label(attendance_frame, text="Late: 0", font=("Arial", 10))
        self.staff_late_label.pack(anchor=tk.W)

        ttk.Button(
            attendance_frame,
            text="📋 Manage Attendance",
            command=self.open_staff_attendance,
        ).pack(anchor=tk.E, pady=2)

        # Start periodic attendance updates
        self.update_staff_attendance()
        
        # Factory Messages
        messages_frame = ttk.LabelFrame(right_panel, text="📢 Factory Attendance Log", padding=5)
        messages_frame.pack(fill=tk.X, pady=5)
        
        self.welcome_text = tk.Text(messages_frame, height=6, wrap=tk.WORD, font=("Arial", 9))
        welcome_scrollbar = ttk.Scrollbar(messages_frame, orient=tk.VERTICAL, command=self.welcome_text.yview)
        self.welcome_text.configure(yscrollcommand=welcome_scrollbar.set)
        
        self.welcome_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        welcome_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_engines(self):
        """Initialize recognition engines"""
        self.face_engine = None
        self.tracking_manager = None
        self.camera_manager = CameraManager()

    def _get_current_camera_ip(self):
        """Fetch current camera IP from configuration"""
        try:
            settings = self.config.get_camera_settings()
            url = settings.get('rtsp_url', '')
            if '://' in url and '@' in url:
                after_auth = url.split('://', 1)[1].split('@', 1)[1]
                return after_auth.split(':')[0]
        except Exception:
            pass
        return 'Unknown'

    def on_camera_ip_change(self, new_ip):
        """Callback when camera IP changes"""
        try:
            self.parent.after(0, lambda: self._handle_ip_change(new_ip))
        except Exception as e:
            print(f"IP change callback error: {e}")

    def _handle_ip_change(self, new_ip):
        self.camera_ip_label.config(text=f"IP: {new_ip}")
        messagebox.showinfo("Camera IP Updated", f"Camera IP changed to {new_ip}")
        print(f"Camera IP updated to {new_ip}")

    def start_enhanced_recognition(self):
        """Start enhanced face recognition system with working message flow"""
        try:
            print("🏭 Starting Elkitch Factory Attendance Recognition System...")
            
            # Initialize engines
            gpu_mode = self.mode_var.get() == "GPU" and self.gpu_available
            self.face_engine = FaceRecognitionEngine(gpu_mode=gpu_mode)
            self.db_manager = self.face_engine.db_manager
            
            # **CRITICAL: Fix database schema**
            self.fix_database_schema()
            
            self.tracking_manager = TrackingManager(gpu_mode=gpu_mode)
            
            # Start camera
            if not self.camera_manager.start_camera():
                messagebox.showerror("Camera Error", "Failed to start camera")
                return
            
            self.running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.capture_btn.config(state=tk.NORMAL)
            
            # Update status
            self.camera_status.config(text="📹 Camera: Connected", foreground="green")
            self.processing_status.config(text="🧠 Processing: Active", foreground="green")
            
            # Start processing thread
            self.process_thread = threading.Thread(target=self.enhanced_message_processing, daemon=True)
            self.process_thread.start()
            
            # Start statistics update loop
            self.stats_thread = threading.Thread(target=self.update_statistics_loop, daemon=True)
            self.stats_thread.start()
            
            print("✅ Factory attendance recognition system started successfully")
            
        except Exception as e:
            print(f"❌ Start recognition error: {e}")
            messagebox.showerror("Error", f"Failed to start recognition: {e}")

    def fix_database_schema(self):
        """Fix database schema to include visit_date column"""
        try:
            if hasattr(self.db_manager, 'db_path'):
                conn = sqlite3.connect(self.db_manager.db_path)
                cursor = conn.cursor()
                
                # Check if visits table exists and has visit_date column
                cursor.execute("PRAGMA table_info(visits)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'visit_date' not in columns:
                    print("🔧 Adding missing visit_date column to visits table...")
                    cursor.execute("ALTER TABLE visits ADD COLUMN visit_date DATE DEFAULT CURRENT_DATE")
                    conn.commit()
                    print("✅ Database schema fixed")
                
                conn.close()
                
        except Exception as e:
            print(f"❌ Database schema fix error: {e}")
    def get_face_location_key(self, bbox):
        """Get location-based key for face tracking"""
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        # Round to nearest location zone
        zone_x = round(center_x / self.location_threshold) * self.location_threshold
        zone_y = round(center_y / self.location_threshold) * self.location_threshold
        return f"zone_{zone_x}_{zone_y}"

    def has_moved_significantly(self, bbox_key, bbox):
        """Check if face has moved significantly from last known position"""
        try:
            if bbox_key not in self.location_tracker:
                return True  # First time seeing this face
            
            old_location = self.location_tracker[bbox_key]
            new_location = self.get_face_location_key(bbox)
            
            return old_location != new_location
            
        except Exception as e:
            print(f"❌ Movement check error: {e}")
            return True
    def get_face_tracking_id(self, bbox):
        """Get or create a tracking ID for a face based on position"""
        try:
            x1, y1, x2, y2 = bbox
            face_center_x = (x1 + x2) / 2
            face_center_y = (y1 + y2) / 2
            
            # Check if this face matches any existing tracked face
            for tracking_id, tracked_info in self.face_tracking_ids.items():
                old_center_x, old_center_y = tracked_info['center']
                
                # Calculate distance from previous position
                distance = ((face_center_x - old_center_x)**2 + (face_center_y - old_center_y)**2)**0.5
                
                if distance < self.face_movement_threshold:
                    # Update position for this tracking ID
                    self.face_tracking_ids[tracking_id]['center'] = (face_center_x, face_center_y)
                    self.face_tracking_ids[tracking_id]['last_seen'] = time.time()
                    return tracking_id
            
            # Create new tracking ID for new face
            tracking_id = f"track_{self.next_tracking_id}"
            self.next_tracking_id += 1
            
            self.face_tracking_ids[tracking_id] = {
                'center': (face_center_x, face_center_y),
                'last_seen': time.time(),
                'bbox': bbox
            }
            
            return tracking_id
            
        except Exception as e:
            print(f"❌ Face tracking ID error: {e}")
            return f"track_{self.next_tracking_id}"

    def set_persistent_identification(self, bbox_key, customer_id, customer_type, message, color):
        """Set a persistent identification that stays until customer moves significantly"""
        current_time = time.time()
        
        self.persistent_identifications[bbox_key] = {
            'customer_id': customer_id,
            'customer_type': customer_type,  # 'customer', 'staff', 'new_customer'
            'message': message,
            'color': color,
            'timestamp': current_time,
            'locked_until': current_time + self.identification_lock_time
        }
        
        self.last_identification_time[bbox_key] = current_time
        print(f"🔒 Set persistent identification for {bbox_key}: {customer_id} ({customer_type})")
    def set_persistent_message(self, tracking_id, message, color, customer_id=None):
        """Set a persistent message that stays with the tracked face"""
        current_time = time.time()
        
        self.persistent_messages[tracking_id] = {
            'message': message,
            'color': color,
            'customer_id': customer_id,
            'start_time': current_time,
            'expire_time': current_time + self.message_persistence_time,
            'active': True
        }
        
        print(f"🔒 Set persistent message for {tracking_id}: {message} (will show for {self.message_persistence_time}s)")
        
    def get_persistent_message_for_face(self, bbox):
        """Get persistent message for a face based on its tracking"""
        try:
            tracking_id = self.get_face_tracking_id(bbox)
            current_time = time.time()
            
            if tracking_id in self.persistent_messages:
                msg_data = self.persistent_messages[tracking_id]
                
                # Check if message is still valid
                if current_time < msg_data['expire_time'] and msg_data['active']:
                    return msg_data['message'], msg_data['color'], tracking_id
                else:
                    # Message expired, remove it
                    del self.persistent_messages[tracking_id]
            
            return None, None, tracking_id
            
        except Exception as e:
            print(f"❌ Get persistent message error: {e}")
            return None, None, None

    def cleanup_expired_tracking(self):
        """Clean up expired face tracking data"""
        try:
            current_time = time.time()
            expired_ids = []
            
            # Clean up expired persistent messages
            for tracking_id, msg_data in self.persistent_messages.items():
                if current_time > msg_data['expire_time']:
                    expired_ids.append(tracking_id)
            
            for tracking_id in expired_ids:
                del self.persistent_messages[tracking_id]
                if tracking_id in self.face_tracking_ids:
                    del self.face_tracking_ids[tracking_id]
            
            # Clean up old tracking IDs (not seen for 20 seconds)
            expired_tracking = []
            for tracking_id, track_data in self.face_tracking_ids.items():
                if current_time - track_data['last_seen'] > 20.0:
                    expired_tracking.append(tracking_id)
            
            for tracking_id in expired_tracking:
                del self.face_tracking_ids[tracking_id]
                if tracking_id in self.persistent_messages:
                    del self.persistent_messages[tracking_id]
                    
        except Exception as e:
            print(f"❌ Cleanup tracking error: {e}")

    def process_staff_member_working_with_persistence(self, bbox_key, staff_id, confidence, current_time):
        """Process staff member with persistent messages using face tracking"""
        try:
            # Get the actual bbox from the processed faces
            if bbox_key in self.processed_faces:
                bbox = self.processed_faces[bbox_key]['detection'].get('bbox')
                if bbox:
                    # Check if we already have a persistent message for this face
                    existing_message, existing_color, tracking_id = self.get_persistent_message_for_face(bbox)
                    
                    if existing_message:
                        # Already has persistent message, keep showing it
                        self.set_face_message(bbox_key, existing_message, existing_color, duration=999.0)
                        return
                    
                    # Create new persistent message
                    staff_info = self.db_manager.get_staff_info(staff_id)
                    staff_name = staff_info.get('name', staff_id) if staff_info else staff_id
                    
                    if staff_id in self.staff_today:
                        # Already counted
                        message = f"Staff: {staff_name}\nID: {staff_id}\nAttendance: Already taken\nWelcome back!"
                        color = (255, 165, 0)  # Orange
                    else:
                        # New attendance
                        self.staff_today.add(staff_id)
                        self.increment_visit_counter('staff_checkin')
                        
                        message = f"Staff: {staff_name}\nID: {staff_id}\nAttendance: Recorded\nWelcome!"
                        color = (0, 255, 0)  # Green
                    
                    # Set persistent message with face tracking
                    self.set_persistent_message(tracking_id, message, color, staff_id)
                    self.set_face_message(bbox_key, message, color, duration=999.0)
                    
                    # Set visits message
                    total_visits = self.get_staff_total_visits(staff_id)
                    self.set_visits_message(bbox_key, f"Total Visits: {total_visits}")
                    
                    # Mark as processed
                    self.processed_faces[bbox_key]['processed'] = True
                    self.processed_faces[bbox_key]['is_staff'] = True
                    self.processed_faces[bbox_key]['customer_id'] = staff_id
                    
                    print(f"✅ Staff processed with persistence: {staff_id} (tracking: {tracking_id})")
            
        except Exception as e:
            print(f"❌ Staff persistence processing error: {e}")

    def process_existing_customer_working_with_persistence(self, bbox_key, customer_id, confidence, current_time):
        """Process existing customer with persistent messages using face tracking"""
        try:
            # Get the actual bbox from the processed faces
            if bbox_key in self.processed_faces:
                bbox = self.processed_faces[bbox_key]['detection'].get('bbox')
                if bbox:
                    # Check if we already have a persistent message for this face
                    existing_message, existing_color, tracking_id = self.get_persistent_message_for_face(bbox)
                    
                    if existing_message:
                        # Already has persistent message, keep showing it
                        self.set_face_message(bbox_key, existing_message, existing_color, duration=999.0)
                        return
                    
                    # Create new persistent message
                    visit_status = self.db_manager.check_daily_visit_status(customer_id)
                    
                    if visit_status['visited_today']:
                        # Already visited
                        message = f"Customer: {customer_id}\nStatus: Already counted\nWelcome back!"
                        color = (255, 165, 0)  # Orange
                    else:
                        # Record new visit
                        visit_result = self.db_manager.record_customer_visit(customer_id, confidence)
                        if visit_result['success']:
                            self.customers_today.add(customer_id)
                            
                            if visit_result['total_visits'] == 1:
                                self.increment_visit_counter('new_customer')
                            else:
                                self.increment_visit_counter('known_customer')
                            
                            message = f"Customer: {customer_id}\nVisit: Recorded\nWelcome!"
                            color = (0, 255, 0)  # Green
                        else:
                            message = f"Customer: {customer_id}\nStatus: Processing failed"
                            color = (255, 0, 0)  # Red
                    
                    # Set persistent message with face tracking
                    self.set_persistent_message(tracking_id, message, color, customer_id)
                    self.set_face_message(bbox_key, message, color, duration=999.0)
                    
                    # Set visits message
                    total_visits = visit_status.get('total_visits', visit_result.get('total_visits', 0))
                    self.set_visits_message(bbox_key, f"Total Visits: {total_visits}")
                    
                    # Mark as processed
                    self.processed_faces[bbox_key]['processed'] = True
                    self.processed_faces[bbox_key]['customer_id'] = customer_id
                    
                    print(f"✅ Customer processed with persistence: {customer_id} (tracking: {tracking_id})")
            
        except Exception as e:
            print(f"❌ Customer persistence processing error: {e}")

    def process_new_customer_working_with_persistence(self, bbox_key, embedding, confidence, current_time):
        """Process new customer with persistent messages using face tracking"""
        try:
            # Get the actual bbox from the processed faces
            if bbox_key in self.processed_faces:
                bbox = self.processed_faces[bbox_key]['detection'].get('bbox')
                if bbox:
                    # Check if we already have a persistent message for this face
                    existing_message, existing_color, tracking_id = self.get_persistent_message_for_face(bbox)
                    
                    if existing_message:
                        # Already has persistent message, keep showing it
                        self.set_face_message(bbox_key, existing_message, existing_color, duration=999.0)
                        return
                    
                    # Register new customer
                    new_customer_id = self.face_engine.register_new_customer(embedding)
                    
                    if new_customer_id:
                        # Record first visit
                        visit_result = self.db_manager.record_customer_visit(new_customer_id, confidence)
                        
                        if visit_result['success']:
                            self.customers_today.add(new_customer_id)
                            self.increment_visit_counter('new_customer')
                            
                            message = f"New Customer!\nID: {new_customer_id}\nFirst visit recorded\nWelcome!"
                            color = (255, 0, 255)  # Magenta
                            
                            # Set persistent message with face tracking
                            self.set_persistent_message(tracking_id, message, color, new_customer_id)
                            self.set_face_message(bbox_key, message, color, duration=999.0)
                            
                            # Set visits message
                            self.set_visits_message(bbox_key, "Total Visits: 1")
                            
                            # Mark as processed
                            self.processed_faces[bbox_key]['processed'] = True
                            self.processed_faces[bbox_key]['customer_id'] = new_customer_id
                            self.processed_faces[bbox_key]['total_visits'] = 1
                            
                            print(f"✅ New customer processed with persistence: {new_customer_id} (tracking: {tracking_id})")
                        else:
                            self.set_face_message(bbox_key, "Processing failed\nTry again", (255, 0, 0))
                    else:
                        self.set_face_message(bbox_key, "Registration failed\nTry again", (255, 0, 0))
            
        except Exception as e:
            print(f"❌ New customer persistence processing error: {e}")

    def draw_faces_with_tracking_messages(self, frame):
        """
        Draws persistent welcome/already-counted messages for each track using actual tracking IDs,
        not per-frame detections.
        Should be called instead of (or as an enhancement to) your previous draw_faces_with_working_messages.
        """
        try:
            # Get the current active tracks from TrackingManager (you should keep this updated in your main loop)
            current_tracks = []
            if hasattr(self, 'tracking_manager') and self.tracking_manager:
                current_tracks = list(self.tracking_manager.active_tracks.values())

            for track in current_tracks:
                bbox = track.display_bbox if hasattr(track, 'display_bbox') else track.bbox
                x1, y1, x2, y2 = [int(c) for c in bbox]
                color = getattr(track, 'color', (0, 255, 0))
                message = getattr(track, 'display_message', 'Checking...')
                visits_msg = f"Total Visits: {getattr(track, 'total_visits', 0)}" if hasattr(track, 'total_visits') else ""

                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                # Draw main message BELOW face
                if message:
                    lines = message.split('\n')
                    for j, line in enumerate(lines):
                        text_y = y2 + 20 + j * 22
                        cv2.putText(frame, line, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                # Draw visits message ABOVE face
                if visits_msg:
                    cv2.putText(frame, visits_msg, (x1, y1 - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

                # Draw confidence if available
                if hasattr(track, 'display_confidence'):
                    cv2.putText(frame, f"Conf: {track.display_confidence:.2f}", (x1, y1-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
        except Exception as e:
            print(f"❌ Error in draw_faces_with_tracking_messages: {e}")
        return frame

    def cleanup_lost_tracks(self):
        """
        Remove persistent messages and data for tracks that have left the screen (not just moved).
        Call after updating tracks in each processing loop.
        """
        if not hasattr(self, 'tracking_manager'):
            return
        current_ids = set(self.tracking_manager.active_tracks.keys())
        for tid in list(self.face_messages.keys()):
            if tid not in current_ids:
                del self.face_messages[tid]

    def should_show_persistent_message(self, bbox_key):
        """Check if should show persistent identification message"""
        if bbox_key not in self.persistent_identifications:
            return False
        
        identification = self.persistent_identifications[bbox_key]
        current_time = time.time()
        
        # Show persistent message if still within lock time
        return current_time < identification['locked_until']

    def get_persistent_message(self, bbox_key):
        """Get persistent message for face"""
        if bbox_key in self.persistent_identifications:
            identification = self.persistent_identifications[bbox_key]
            return identification['message'], identification['color']
        return None, None
    def enhanced_message_processing(self):
        """Enhanced video processing with WORKING message flow system"""
        print("🎬 Starting enhanced message processing with working flow...")
        
        last_gui_update = 0
        
        while self.running:
            try:
                # Get frame
                frame = self.get_stable_frame()
                if frame is None:
                    time.sleep(0.02)
                    continue
                
                self.frame_count += 1
                current_time = time.time()
                
                tracks = []
                # Process face detection every nth frame
                if self.frame_count % self.process_every_n_frames == 0:
                    # Get detections from face engine
                    detections = self.face_engine.debug_face_detection(frame)

                    if detections:
                        print(f"🔍 Frame {self.frame_count}: Found {len(detections)} faces")

                    # Update DeepSort tracks
                    tracks = self.tracking_manager.update_tracks(detections)

                # Clean up messages for lost tracks and draw persistent tracking messages
                self.cleanup_lost_tracks()
                frame = self.draw_faces_with_tracking_messages(frame)

                # Thread-safe frame update
                with self.capture_lock:
                    self.current_frame = frame.copy()
                    self.current_detections = detections if 'detections' in locals() else []
                    self.current_tracks = tracks
                
                # GUI update - increased to 60 FPS for smoother display
                if current_time - last_gui_update >= 0.016:  # 60 FPS for smooth video
                    self.parent.after_idle(self.update_display_thread_safe, frame.copy())
                    last_gui_update = current_time
                
                # Update FPS
                self.update_fps()
                
                # Sleep for stability
                time.sleep(0.02)
                
            except Exception as e:
                print(f"❌ Enhanced processing error: {e}")
                time.sleep(0.1)

    def get_bbox_key(self, bbox):
        """Generate unique key for bounding box"""
        x1, y1, x2, y2 = [int(coord) for coord in bbox]
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        return f"face_{center_x}_{center_y}"

    def process_detection_with_working_flow(self, detection, detection_index, current_time):
        """Process detection with WORKING message flow system"""
        try:
            bbox = detection.get('bbox')
            if bbox is None:
                return

            bbox_key = self.get_bbox_key(bbox)

            # Always update tracking and check for existing persistent message
            persistent_msg, persistent_color, _ = self.get_persistent_message_for_face(bbox)

            # Initialize face processing if not exists
            if bbox_key not in self.processed_faces:
                if persistent_msg:
                    # Use existing persistent message without showing "Checking..."
                    self.processed_faces[bbox_key] = {
                        'status': 'identified',
                        'start_time': current_time,
                        'customer_id': None,
                        'is_staff': False,
                        'total_visits': 0,
                        'processed': True,
                        'detection': detection,
                        'persistent': True
                    }
                    self.set_face_message(bbox_key, persistent_msg, persistent_color)
                    return
                else:
                    self.processed_faces[bbox_key] = {
                        'status': 'checking',
                        'start_time': current_time,
                        'customer_id': None,
                        'is_staff': False,
                        'total_visits': 0,
                        'processed': False,
                        'detection': detection
                    }

                    # Set initial "Checking..." message
                    self.set_face_message(bbox_key, "Checking...", (255, 255, 0))  # Yellow
                    print(f"🔍 Started checking {bbox_key}")
                    return

            face_data = self.processed_faces[bbox_key]

            # If a persistent message appears after initialization, apply it
            if persistent_msg and not face_data.get('processed'):
                self.set_face_message(bbox_key, persistent_msg, persistent_color)
                face_data['processed'] = True
                face_data['persistent'] = True
                return

            # Skip if already processed
            if face_data.get('processed'):
                return

            # Get embedding from detection
            embedding = detection.get('embedding')
            if embedding is None:
                return

            # Process after checking duration (2 seconds)
            if current_time - face_data['start_time'] >= self.checking_duration:
                self.identify_and_process_person_working(bbox_key, embedding, current_time)
                
        except Exception as e:
            print(f"❌ Detection processing error: {e}")

    def identify_and_process_person_working(self, bbox_key, embedding, current_time):
        """Identify staff member for factory attendance - Staff only mode"""
        try:
            # Only identify staff members for factory attendance
            person_type, person_id, confidence = self.face_engine.identify_person(embedding)
            
            if person_type == 'staff' and person_id:
                self.process_staff_member_working(bbox_key, person_id, confidence, current_time)
            elif person_type == 'unknown':
                # Unknown person - show message but don't register
                message = "Unknown Staff\nPlease register first"
                self.set_face_message(bbox_key, message, (255, 0, 0))  # Red
                self.add_recent_detection("Unknown", person_id or "Unknown", "Not Registered", confidence)
            # Ignore customers - factory attendance only tracks staff
                
        except Exception as e:
            print(f"❌ Staff identification error: {e}")

    def process_staff_member_working(self, bbox_key, staff_id, confidence, current_time):
        """Process staff member with WORKING message flow and counter updates"""
        try:
            staff_info = self.db_manager.get_staff_info(staff_id)
            staff_name = staff_info.get('name', staff_id) if staff_info else staff_id
            
            # Check if already counted today
            if staff_id in self.staff_today:
                # Already counted - show welcome back message
                message = f"Staff ID: {staff_id}\nAttendance: Already taken\nWelcome back!"
                self.set_face_message(bbox_key, message, (255, 165, 0))  # Orange
                
                # Schedule "already counted" message after 3 seconds
                self.schedule_message_update(bbox_key, current_time + 3.0, 
                                           "Already counted\nfor today", (255, 100, 100))
                
                total_visits = self.get_staff_total_visits(staff_id)
                self.set_visits_message(bbox_key, f"Total Visits: {total_visits}")
                
                self.add_recent_detection("Staff", staff_id, "Already Counted", confidence)
                
            else:
                # New staff attendance
                self.staff_today.add(staff_id)
                
                # **CRITICAL: Increment counter for real-time stats**
                self.increment_visit_counter('staff_checkin')
                
                # Get total visits for this staff
                total_visits = self.get_staff_total_visits(staff_id) + 1
                
                # Show attendance taken message
                message = f"Staff ID: {staff_id}\nAttendance taken for today\nWelcome {staff_name}!"
                self.set_face_message(bbox_key, message, (0, 255, 0))  # Green
                
                # Schedule "already counted" message after 3 seconds
                self.schedule_message_update(bbox_key, current_time + 3.0, 
                                           "Already counted\nfor today", (255, 100, 100))
                
                # Add total visits below
                self.set_visits_message(bbox_key, f"Total Visits: {total_visits}")
                
                self.add_recent_detection("Staff", staff_id, "Attendance Taken", confidence)
                
                # Log staff attendance
                staff_msg = f"👨‍💼 STAFF ATTENDANCE\n"
                staff_msg += f"Staff ID: {staff_id}\n"
                staff_msg += f"Name: {staff_name}\n"
                staff_msg += f"Time: {datetime.now().strftime('%H:%M:%S')}\n"
                staff_msg += f"Total Visits: {total_visits}\n"
                staff_msg += "=" * 30 + "\n\n"
                self.display_system_message(staff_msg)
                
                print(f"✅ Staff attendance recorded: {staff_id}")
            
            # Mark as processed
            self.processed_faces[bbox_key]['processed'] = True
            self.processed_faces[bbox_key]['is_staff'] = True
            self.processed_faces[bbox_key]['customer_id'] = staff_id
            self.processed_faces[bbox_key]['persistent'] = True
            
        except Exception as e:
            print(f"❌ Staff processing error: {e}")

    def process_existing_customer_working(self, bbox_key, customer_id, confidence, current_time):
        """Process existing customer with WORKING message flow and counter updates"""
        try:
            visit_status = self.db_manager.check_daily_visit_status(customer_id)
            
            if visit_status['visited_today']:
                # Already visited today
                message = f"Welcome back!\nCustomer: {customer_id}\nAlready counted today"
                self.set_face_message(bbox_key, message, (255, 165, 0))  # Orange
                
                # Schedule "already counted" message after 3 seconds
                self.schedule_message_update(bbox_key, current_time + 3.0, 
                                           "Already counted\nfor today", (255, 100, 100))
                
                # Add total visits below
                self.set_visits_message(bbox_key, f"Total Visits: {visit_status['total_visits']}")
                
                self.add_recent_detection("Customer", customer_id, "Already Counted", confidence)
                
            else:
                # Record new visit
                visit_result = self.db_manager.record_customer_visit(customer_id, confidence)
                if visit_result['success']:
                    self.customers_today.add(customer_id)
                    
                    # **CRITICAL: Increment counter for real-time stats**
                    if visit_result['total_visits'] == 1:
                        self.increment_visit_counter('new_customer')
                    else:
                        self.increment_visit_counter('known_customer')
                    
                    message = f"Welcome!\nCustomer: {customer_id}\nVisit recorded!"
                    self.set_face_message(bbox_key, message, (0, 255, 0))  # Green
                    
                    # Schedule "already counted" message after 3 seconds
                    self.schedule_message_update(bbox_key, current_time + 3.0, 
                                               "Already counted\nfor today", (255, 100, 100))
                    
                    # Add total visits below
                    self.set_visits_message(bbox_key, f"Total Visits: {visit_result['total_visits']}")
                    
                    self.add_recent_detection("Customer", customer_id, "Visit Recorded", confidence)
                    
                    print(f"✅ Customer visit recorded: {customer_id}")
            
            # Mark as processed
            self.processed_faces[bbox_key]['processed'] = True
            self.processed_faces[bbox_key]['customer_id'] = customer_id
            self.processed_faces[bbox_key]['persistent'] = True
            
        except Exception as e:
            print(f"❌ Customer processing error: {e}")

    def process_new_customer_working(self, bbox_key, embedding, confidence, current_time):
        """Process new customer with auto ID generation, WORKING message flow and counter updates"""
        try:
            # Auto-generate new customer ID
            new_customer_id = self.face_engine.register_new_customer(embedding)
            
            if new_customer_id:
                # Record first visit
                visit_result = self.db_manager.record_customer_visit(new_customer_id, confidence)
                
                if visit_result['success']:
                    self.customers_today.add(new_customer_id)
                    
                    # **CRITICAL: Increment counter for real-time stats**
                    self.increment_visit_counter('new_customer')
                    
                    # Show "Welcome new customer added!" message
                    message = f"Welcome new customer!\nID: {new_customer_id}\nAdded successfully!"
                    self.set_face_message(bbox_key, message, (255, 0, 255))  # Magenta
                    
                    # Schedule "already counted" message after 3 seconds
                    self.schedule_message_update(bbox_key, current_time + 3.0, 
                                               "Already counted\nfor today", (255, 100, 100))
                    
                    # Add total visits below (first visit = 1)
                    self.set_visits_message(bbox_key, "Total Visits: 1")
                    
                    self.add_recent_detection("New Customer", new_customer_id, "Registered", confidence)
                    
                    print(f"✅ New customer registered: {new_customer_id}")
                    
                    # Mark as processed
                    self.processed_faces[bbox_key]['processed'] = True
                    self.processed_faces[bbox_key]['customer_id'] = new_customer_id
                    self.processed_faces[bbox_key]['total_visits'] = 1
                    self.processed_faces[bbox_key]['persistent'] = True
                else:
                    self.set_face_message(bbox_key, "Processing failed\nTry again", (255, 0, 0))
            else:
                self.set_face_message(bbox_key, "Registration failed\nTry again", (255, 0, 0))
                
        except Exception as e:
            print(f"❌ New customer processing error: {e}")

    def set_face_message(self, bbox_key, message, color):
        """Set message for a specific face"""
        current_time = time.time()
        self.face_messages[bbox_key] = {
            'message': message,
            'color': color,
            'timestamp': current_time,
            'visits_message': self.face_messages.get(bbox_key, {}).get('visits_message', '')
        }

    def set_visits_message(self, bbox_key, visits_message):
        """Set visits message for a specific face"""
        if bbox_key in self.face_messages:
            self.face_messages[bbox_key]['visits_message'] = visits_message
        else:
            self.face_messages[bbox_key] = {
                'message': '',
                'color': (255, 255, 255),
                'timestamp': time.time(),
                'visits_message': visits_message
            }

    def schedule_message_update(self, bbox_key, update_time, new_message, new_color):
        """Schedule a message update for future time"""
        self.message_timers[bbox_key] = {
            'update_time': update_time,
            'message': new_message,
            'color': new_color
        }

    def cleanup_message_timers(self):
        """Clean up message timers and update messages"""
        current_time = time.time()

        # Check for scheduled message updates
        for bbox_key, timer_data in list(self.message_timers.items()):
            if current_time >= timer_data['update_time']:
                # Update the message
                self.set_face_message(bbox_key, timer_data['message'], timer_data['color'])
                # Remove the timer
                del self.message_timers[bbox_key]
                print(f"🔄 Updated message for {bbox_key}")

        # Clean up old messages, but respect the 'persistent' flag
        for bbox_key in list(self.face_messages.keys()):
            # **** NEW LOGIC HERE ****
            # If the face has a persistent message, don't clear it.
            if self.processed_faces.get(bbox_key, {}).get('persistent', False):
                continue  # Skip cleanup for this message

            # Original cleanup logic for non-persistent messages
            if current_time - self.face_messages[bbox_key]['timestamp'] > 30:
                del self.face_messages[bbox_key]
                if bbox_key in self.processed_faces:
                    del self.processed_faces[bbox_key]


    def get_stable_frame(self):
        """Get stable frame with error handling"""
        try:
            for attempt in range(3):
                frame = self.camera_manager.get_frame()
                if frame is not None and frame.size > 0:
                    return frame
                time.sleep(0.01)
            return None
        except Exception as e:
            print(f"❌ Frame acquisition error: {e}")
            return None

    def get_staff_total_visits(self, staff_id):
        """Get total visits for staff member"""
        try:
            return len([s for s in self.staff_today if s == staff_id])
        except:
            return 0

    def update_detection_threshold(self, value):
        """Update detection threshold"""
        threshold = float(value)
        self.threshold_label.config(text=f"{threshold:.2f}")
        
        if hasattr(self, 'face_engine') and self.face_engine:
            self.face_engine.detection_threshold = threshold
            print(f"🎯 Detection threshold updated to {threshold:.2f}")

    def add_recent_detection(self, person_type, person_id, status, confidence=0.0):
        """Add recent detection to the tree"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            confidence_str = f"{confidence:.3f}" if confidence > 0 else "N/A"
            
            # Insert new detection
            new_item = self.recent_tree.insert('', 0, values=(
                timestamp, person_type, person_id, status, confidence_str, "Active"
            ))
            
            # Limit entries
            children = self.recent_tree.get_children()
            if len(children) > 50:
                for item in children[49:]:
                    self.recent_tree.delete(item)
                    
        except Exception as e:
            print(f"❌ Recent detection error: {e}")

    def display_system_message(self, message):
        """Display system message with thread safety"""
        try:
            self.welcome_text.config(state='normal')
            self.welcome_text.insert(tk.END, message)
            self.welcome_text.see(tk.END)
            
            # Limit message history
            num_lines = int(self.welcome_text.index('end-1c').split('.')[0])
            if num_lines > 200:
                self.welcome_text.delete('1.0', f'{num_lines - 200}.0')
            
            self.welcome_text.config(state='disabled')
            self.welcome_text.update_idletasks()
            
        except Exception as e:
            print(f"❌ System message error: {e}")

    # **ENHANCED FULLSCREEN IMPLEMENTATION**
    def toggle_fullscreen_camera(self):
        """Toggle fullscreen camera display - FIXED IMPLEMENTATION"""
        try:
            if hasattr(self, 'fullscreen_active') and self.fullscreen_active:
                self.exit_fullscreen()
            else:
                self.enter_fullscreen()
        except Exception as e:
            print(f"❌ Fullscreen toggle error: {e}")
            messagebox.showerror("Fullscreen Error", f"Failed to toggle: {e}")

    def enter_fullscreen(self):
        """Enter fullscreen mode - FIXED IMPLEMENTATION"""
        try:
            if not self.running:
                messagebox.showwarning("Warning", "Start recognition first")
                return
            
            # Create fullscreen window
            self.fullscreen_window = tk.Toplevel(self.parent)
            self.fullscreen_window.title("Elkitch Factory Attendance - Fullscreen")
            
            # **CRITICAL: Set fullscreen attributes properly**
            self.fullscreen_window.attributes('-fullscreen', True)
            self.fullscreen_window.configure(bg='black')
            self.fullscreen_window.focus_set()
            
            # **CRITICAL: Bind multiple exit methods**
            self.fullscreen_window.bind('<Escape>', lambda e: self.exit_fullscreen())
            self.fullscreen_window.bind('<F11>', lambda e: self.exit_fullscreen())
            self.fullscreen_window.bind('<Double-Button-1>', lambda e: self.exit_fullscreen())
            self.fullscreen_window.bind('<q>', lambda e: self.exit_fullscreen())
            
            # Create fullscreen label
            self.fullscreen_label = tk.Label(self.fullscreen_window, bg='black')
            self.fullscreen_label.pack(fill=tk.BOTH, expand=True)
            
            # Add instructions
            instruction_label = tk.Label(
                self.fullscreen_window,
                text="Press ESC, F11, Q, or Double-click to exit fullscreen • Factory Attendance Active",
                bg='black', fg='white', font=('Arial', 12)
            )
            instruction_label.place(relx=0.5, rely=0.95, anchor='center')
            
            self.fullscreen_active = True
            self.fullscreen_video_loop()
            
            print("✅ Entered fullscreen mode")
            
        except Exception as e:
            print(f"❌ Fullscreen enter error: {e}")

    def exit_fullscreen(self):
        """Exit fullscreen mode - FIXED IMPLEMENTATION"""
        try:
            self.fullscreen_active = False
            if hasattr(self, 'fullscreen_window') and self.fullscreen_window:
                self.fullscreen_window.destroy()
                self.fullscreen_window = None
                self.fullscreen_label = None
            print("✅ Exited fullscreen mode")
        except Exception as e:
            print(f"❌ Fullscreen exit error: {e}")

    def fullscreen_video_loop(self):
        """Fullscreen video display loop - FIXED IMPLEMENTATION"""
        try:
            if not self.fullscreen_active or not self.fullscreen_window:
                return
            
            with self.capture_lock:
                if self.current_frame is not None:
                    frame = self.current_frame.copy()
                    
                    # Get screen dimensions
                    screen_width = self.fullscreen_window.winfo_screenwidth()
                    screen_height = self.fullscreen_window.winfo_screenheight()
                    
                    # Resize for fullscreen
                    h, w = frame.shape[:2]
                    aspect_ratio = w / h
                    
                    if screen_width / screen_height > aspect_ratio:
                        new_height = screen_height
                        new_width = int(new_height * aspect_ratio)
                    else:
                        new_width = screen_width
                        new_height = int(new_width / aspect_ratio)
                    
                    frame_resized = cv2.resize(frame, (new_width, new_height))
                    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)
                    photo = ImageTk.PhotoImage(pil_image)
                    
                    if self.fullscreen_label:
                        self.fullscreen_label.image = photo
                        self.fullscreen_label.configure(image=photo)
            
            # Schedule next update - 60 FPS for smooth fullscreen display
            if self.fullscreen_active and self.fullscreen_window:
                self.fullscreen_window.after(16, self.fullscreen_video_loop)  # ~60 FPS
                
        except Exception as e:
            print(f"❌ Fullscreen video error: {e}")
            if self.fullscreen_active:
                self.fullscreen_window.after(100, self.fullscreen_video_loop)

    # **IMPLEMENT OTHER REQUIRED METHODS**
    def capture_current_frame(self):
        """Capture current frame"""
        try:
            with self.capture_lock:
                if self.current_frame is not None:
                    timestamp = datetime.now()
                    photo_data = {
                        'timestamp': timestamp,
                        'frame': self.current_frame.copy(),
                        'filename': f"capture_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                    }
                    
                    self.captured_photos.append(photo_data)

                    return True
                    
        except Exception as e:
            print(f"❌ Photo capture error: {e}")
            return False

    def toggle_auto_capture(self):
        """Toggle auto-capture mode"""
        self.auto_capture_enabled = self.auto_capture_var.get()
        status = "enabled" if self.auto_capture_enabled else "disabled"
        print(f"✅ Auto-capture {status}")

    def open_staff_attendance(self):
        """Open the staff attendance window"""
        try:
            from ui.staff_attendance import StaffAttendanceWindow
            StaffAttendanceWindow(self.parent)
        except Exception as e:
            print(f"❌ Staff attendance window error: {e}")

    def update_staff_attendance(self):
        """Refresh staff attendance summary on the dashboard."""
        try:
            if not self.db_manager:
                self.db_manager = DatabaseManager()

            with self.db_manager.lock:
                conn = sqlite3.connect(self.db_manager.db_path)
                cursor = conn.cursor()

                today = date.today()
                cursor.execute(
                    "SELECT status, COUNT(*) FROM staff_attendance WHERE date = ? GROUP BY status",
                    (today,),
                )
                counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Total active staff
                cursor.execute("SELECT COUNT(*) FROM staff WHERE is_active = 1")
                total_staff = cursor.fetchone()[0]
                conn.close()

            present = counts.get("Present", 0)
            late = counts.get("Late", 0)
            absent = max(total_staff - present - late, 0)

            self.staff_present_label.config(text=f"Present: {present}")
            self.staff_absent_label.config(text=f"Absent: {absent}")
            self.staff_late_label.config(text=f"Late: {late}")
        except Exception as e:
            print(f"❌ Attendance summary update error: {e}")
        finally:
            # Schedule next update
            self.parent.after(60000, self.update_staff_attendance)

    def update_display_thread_safe(self, frame):
        """Thread-safe display update"""
        try:
            if frame is None or frame.size == 0:
                return
            
            # Get label dimensions
            label_width = self.video_label.winfo_width()
            label_height = self.video_label.winfo_height()
            
            if label_width < 50 or label_height < 50:
                return
            
            # Resize frame
            h, w = frame.shape[:2]
            aspect_ratio = w / h
            label_aspect_ratio = label_width / label_height
            
            if label_aspect_ratio > aspect_ratio:
                new_height = label_height
                new_width = int(new_height * aspect_ratio)
            else:
                new_width = label_width
                new_height = int(new_width / aspect_ratio)
            
            frame_resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            photo = ImageTk.PhotoImage(pil_image)
            
            # Update display
            self.video_label.image = photo
            self.video_label.configure(image=photo)
            
        except Exception as e:
            print(f"❌ Display update error: {e}")

    def update_fps(self):
        """Enhanced FPS counter with performance indicators"""
        self.fps_counter += 1
        current_time = time.time()
        
        if current_time - self.fps_start_time >= 1.0:
            # Calculate FPS
            self.current_fps = self.fps_counter / (current_time - self.fps_start_time)
            self.fps_counter = 0
            self.fps_start_time = current_time
            
            # Update performance indicators - optimized for 60 FPS target
            if hasattr(self, 'fps_label'):
                fps_text = f"FPS: {self.current_fps:.1f}"
                if self.current_fps >= 50:
                    color = "green"
                    status = "Excellent"
                elif self.current_fps >= 30:
                    color = "blue"
                    status = "Good"
                elif self.current_fps >= 20:
                    color = "orange"
                    status = "Fair"
                else:
                    color = "red"
                    status = "Low"
                
                # Update with performance status
                self.fps_label.config(text=f"{fps_text} ({status})", foreground=color)

    def reset_visit_stats(self):
        """Reset daily visit statistics"""
        try:
            # Reset counters
            self.visit_counts = {
                'total_today': 0,
                'known_customers': 0,
                'new_customers': 0,
                'staff_checkins': 0
            }
            
            # Clear tracking data
            self.customers_today.clear()
            self.staff_today.clear()
            self.face_messages.clear()
            self.message_timers.clear()
            self.processed_faces.clear()
            
            print("✅ Daily statistics reset successfully")
            
        except Exception as e:
            print(f"❌ Reset stats error: {e}")

    def update_statistics_loop(self):
        """Statistics update loop - WORKING IMPLEMENTATION"""
        while self.running:
            try:
                # Update GUI statistics safely
                self.parent.after_idle(self.update_live_performance_stats)
                self.parent.after_idle(self.update_todays_activity)
                self.parent.after_idle(self.update_database_counts)
                
                time.sleep(2)  # Update every 2 seconds
            except Exception as e:
                print(f"❌ Statistics loop error: {e}")
                time.sleep(5)

    def update_live_performance_stats(self):
        """Update Live Performance Stats section with real-time data"""
        try:
            # Update FPS - optimized for 60 FPS target
            fps_text = f"FPS: {self.current_fps:.1f}"
            if self.current_fps >= 50:
                self.fps_label.config(text=fps_text, foreground="green")
            elif self.current_fps >= 30:
                self.fps_label.config(text=fps_text, foreground="blue")
            elif self.current_fps >= 20:
                self.fps_label.config(text=fps_text, foreground="orange")
            else:
                self.fps_label.config(text=fps_text, foreground="red")
            
            # Update Face Detections
            detection_count = len(self.current_detections) if hasattr(self, 'current_detections') else 0
            self.detections_label.config(text=f"Face Detections: {detection_count}")
            
            # Update Active Tracks
            track_count = len(self.current_tracks) if hasattr(self, 'current_tracks') else 0
            self.tracks_label.config(text=f"Active Tracks: {track_count}")
            
            # Update processing status indicator
            if self.running:
                status_color = "green" if detection_count > 0 else "orange"
                self.processing_status.config(
                    text=f"🧠 Processing: Active ({detection_count} faces)", 
                    foreground=status_color
                )
            
            print(f"📊 Stats Updated - FPS: {self.current_fps:.1f}, Detections: {detection_count}, Tracks: {track_count}")
            
        except Exception as e:
            print(f"❌ Live performance stats update error: {e}")

    def update_todays_activity(self):
        """ENHANCED: Display separate new vs returning customer counts"""
        try:
            total_today = self.visit_counts.get('total_today', 0)
            new_customers = self.visit_counts.get('new_customers', 0)
            returning_customers = self.visit_counts.get('returning_customers', 0)
            staff_checkins = self.visit_counts.get('staff_checkins', 0)

            # ✅ ENHANCED: Clear distinction between customer types
            self.visits_today_label.config(
                text=f"Total Visits: {total_today}",
                foreground="blue" if total_today > 0 else "gray"
            )
            
            # 🆕 NEW CUSTOMERS (first-time visitors)
            self.new_customers_label.config(
                text=f"🆕 New Customers: {new_customers}",
                foreground="purple" if new_customers > 0 else "gray"
            )
            
            # 🔄 RETURNING CUSTOMERS (known customers with new visits)
            self.known_customers_label.config(
                text=f"🔄 Returning Visits: {returning_customers}",
                foreground="green" if returning_customers > 0 else "gray"
            )
            
            self.staff_checkins_label.config(
                text=f"Staff Check-ins: {staff_checkins}",
                foreground="orange" if staff_checkins > 0 else "gray"
            )

            print(f"🎯 ENHANCED Activity - Total: {total_today}, 🆕 New: {new_customers}, 🔄 Returning: {returning_customers}, Staff: {staff_checkins}")
            
        except Exception as e:
            print(f"❌ Today's activity update error: {e}")

    def update_database_counts(self):
        """Update database-driven statistics"""
        try:
            if hasattr(self, 'face_engine') and self.face_engine:
                # Get customer count from database
                customers = self.face_engine.db_manager.load_customers()
                customer_count = len(customers) if customers else 0
                
                # Get staff count from database  
                staff = self.face_engine.load_staff()
                staff_count = len(staff) if staff else 0
                
                # Update labels
                self.customers_label.config(
                    text=f"Total Customers: {customer_count}",
                    foreground="blue" if customer_count > 0 else "gray"
                )
                
                self.staff_label.config(
                    text=f"Staff Members: {staff_count}",
                    foreground="green" if staff_count > 0 else "gray"
                )
                
                print(f"💾 DB Counts Updated - Customers: {customer_count}, Staff: {staff_count}")
            
            else:
                # Fallback to zero counts
                self.customers_label.config(text="Total Customers: 0", foreground="gray")
                self.staff_label.config(text="Staff Members: 0", foreground="gray")
                
        except Exception as e:
            print(f"❌ Database counts update error: {e}")

    def increment_visit_counter(self, visit_type):
        """ENHANCED: Increment visit counters with proper categorization"""
        try:
            current_time = datetime.now()
            
            # Check if it's a new day
            if current_time.date() != self.current_date:
                self.reset_daily_counters()
                self.current_date = current_time.date()

            # ✅ ENHANCED: Proper customer type counting
            if visit_type == 'new_customer':
                self.visit_counts['new_customers'] += 1
                self.visit_counts['total_today'] += 1
                print(f"🆕 NEW CUSTOMER counted! Total new today: {self.visit_counts['new_customers']}")
                
            elif visit_type == 'returning_new_visit':
                self.visit_counts['returning_customers'] += 1
                self.visit_counts['total_today'] += 1
                print(f"🔄 RETURNING CUSTOMER (new visit) counted! Total returning: {self.visit_counts['returning_customers']}")
                
            elif visit_type == 'returning_already_counted':
                # Don't increment total_today since already counted
                print(f"🔒 RETURNING CUSTOMER (already counted today) - no count increment")
                
            elif visit_type == 'staff_checkin':
                self.visit_counts['staff_checkins'] += 1

            # Trigger immediate stats update
            self.parent.after_idle(self.update_todays_activity)
            
        except Exception as e:
            print(f"❌ Visit counter increment error: {e}")

    def reset_daily_counters(self):
        """Reset daily counters for new day"""
        try:
            self.visit_counts = {
                'total_today': 0,
                'known_customers': 0,
                'new_customers': 0,
                'staff_checkins': 0
            }
            
            # Clear tracking sets
            self.customers_today.clear()
            self.staff_today.clear()
            
            print(f"🔄 Daily counters reset for new day: {datetime.now().date()}")
            
        except Exception as e:
            print(f"❌ Daily counter reset error: {e}")

    def get_real_time_stats(self):
        """Get comprehensive real-time statistics"""
        try:
            stats = {
                'performance': {
                    'fps': self.current_fps,
                    'detections': len(self.current_detections) if hasattr(self, 'current_detections') else 0,
                    'tracks': len(self.current_tracks) if hasattr(self, 'current_tracks') else 0,
                    'active_messages': len(self.face_messages) if hasattr(self, 'face_messages') else 0
                },
                'activity': {
                    'total_visits': self.visit_counts.get('total_today', 0),
                    'known_customers': self.visit_counts.get('known_customers', 0),
                    'new_customers': self.visit_counts.get('new_customers', 0),
                    'staff_checkins': self.visit_counts.get('staff_checkins', 0)
                },
                'database': {
                    'total_customers': 0,
                    'staff_members': 0
                }
            }
            
            # Get database counts
            if hasattr(self, 'face_engine') and self.face_engine:
                customers = self.face_engine.load_customers()
                staff = self.face_engine.load_staff()
                stats['database']['total_customers'] = len(customers) if customers else 0
                stats['database']['staff_members'] = len(staff) if staff else 0
            
            return stats
            
        except Exception as e:
            print(f"❌ Get real-time stats error: {e}")
            return {}

    def show_detailed_stats(self):
        """Show detailed statistics window"""
        try:
            stats_window = tk.Toplevel(self.parent)
            stats_window.title("📊 Detailed System Statistics")
            stats_window.geometry("800x600")
            stats_window.transient(self.parent)
            
            # Create notebook for tabs
            notebook = ttk.Notebook(stats_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Performance tab
            perf_frame = ttk.Frame(notebook)
            notebook.add(perf_frame, text="🚀 Performance")
            
            perf_text = tk.Text(perf_frame, wrap=tk.WORD, font=('Courier', 10))
            perf_scroll = ttk.Scrollbar(perf_frame, orient=tk.VERTICAL, command=perf_text.yview)
            perf_text.configure(yscrollcommand=perf_scroll.set)
            
            stats = self.get_real_time_stats()
            perf_content = f"""
📊 REAL-TIME PERFORMANCE STATISTICS
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🚀 PROCESSING PERFORMANCE:
• Current FPS: {stats['performance']['fps']:.2f}
• Active Face Detections: {stats['performance']['detections']}
• Active Tracks: {stats['performance']['tracks']}
• Active Messages: {stats['performance']['active_messages']}

🎯 TODAY'S ACTIVITY:
• Total Visits: {stats['activity']['total_visits']}
• Known Customers: {stats['activity']['known_customers']}
• New Customers: {stats['activity']['new_customers']}
• Staff Check-ins: {stats['activity']['staff_checkins']}

💾 DATABASE STATISTICS:
• Total Customers: {stats['database']['total_customers']}
• Staff Members: {stats['database']['staff_members']}

⏰ SYSTEM STATUS:
• Running: {'Yes' if self.running else 'No'}
• Camera Connected: {'Yes' if hasattr(self, 'camera_manager') and self.camera_manager else 'No'}
• Recognition Active: {'Yes' if self.running else 'No'}
"""
            
            perf_text.insert('1.0', perf_content)
            perf_text.config(state=tk.DISABLED)
            
            perf_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            perf_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Activity tab
            activity_frame = ttk.Frame(notebook)
            notebook.add(activity_frame, text="📈 Activity")
            
            # Add refresh button
            refresh_btn = ttk.Button(stats_window, text="🔄 Refresh", 
                                    command=lambda: self.refresh_detailed_stats(perf_text))
            refresh_btn.pack(side=tk.BOTTOM, pady=5)
            
        except Exception as e:
            print(f"❌ Detailed stats window error: {e}")

    def refresh_detailed_stats(self, text_widget):
        """Refresh detailed statistics display"""
        try:
            stats = self.get_real_time_stats()
            
            content = f"""
📊 REAL-TIME PERFORMANCE STATISTICS
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🚀 PROCESSING PERFORMANCE:
• Current FPS: {stats['performance']['fps']:.2f}
• Active Face Detections: {stats['performance']['detections']}
• Active Tracks: {stats['performance']['tracks']}
• Active Messages: {stats['performance']['active_messages']}

🎯 TODAY'S ACTIVITY:
• Total Visits: {stats['activity']['total_visits']}
• Known Customers: {stats['activity']['known_customers']}
• New Customers: {stats['activity']['new_customers']}
• Staff Check-ins: {stats['activity']['staff_checkins']}

💾 DATABASE STATISTICS:
• Total Customers: {stats['database']['total_customers']}
• Staff Members: {stats['database']['staff_members']}

⏰ SYSTEM STATUS:
• Running: {'Yes' if self.running else 'No'}
• Camera Connected: {'Yes' if hasattr(self, 'camera_manager') and self.camera_manager else 'No'}
• Recognition Active: {'Yes' if self.running else 'No'}
• Last Update: {datetime.now().strftime('%H:%M:%S')}
"""
            
            text_widget.config(state='normal')
            text_widget.delete('1.0', tk.END)
            text_widget.insert('1.0', content)
            text_widget.config(state='disabled')
            
            print("✅ Detailed stats refreshed")
            
        except Exception as e:
            print(f"❌ Stats refresh error: {e}")

    def stop_recognition(self):
        """Stop recognition system"""
        try:
            print("🛑 Stopping Enhanced Recognition System...")
            
            # Exit fullscreen if active
            if hasattr(self, 'fullscreen_active') and self.fullscreen_active:
                self.exit_fullscreen()
            
            self.running = False
            
            # Stop camera
            if hasattr(self, 'camera_manager'):
                self.camera_manager.stop_camera()
            
            # Update GUI
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.capture_btn.config(state=tk.DISABLED)
            
            # Update status
            self.camera_status.config(text="📹 Camera: Disconnected", foreground="red")
            self.processing_status.config(text="🧠 Processing: Stopped", foreground="red")
            
            # Clear display
            self.video_label.config(image='', text="Camera Disconnected")
            
            # Clear message system
            self.face_messages.clear()
            self.message_timers.clear()
            self.processed_faces.clear()
            
            print("✅ Enhanced system stopped successfully")
            
        except Exception as e:
            print(f"❌ Stop recognition error: {e}")
