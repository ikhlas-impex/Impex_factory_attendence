import cv2
import time
from datetime import datetime, date
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .deepsort_tracker import DeepSort, Detection
from .database_manager import DatabaseManager
from .face_engine import FaceRecognitionEngine


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embedding vectors."""
    a = a.reshape(1, -1)
    b = b.reshape(1, -1)
    return float(cosine_similarity(a, b)[0][0])


class OptimizedFaceTracker:
    def __init__(self, track_id, bbox, embedding):
        self.track_id = track_id
        self.bbox = bbox
        self.embedding = embedding
        
        # Tracking properties
        self.last_seen = time.time()
        self.display_bbox = bbox
        self.display_confidence = 0.0
        self.display_duration = 8.0
        self.message_shown = False
        self.processing_complete = False
        
        # ✅ ADD ALL THESE PERMANENT RECOGNITION FLAGS:
        self.permanently_recognized = False
        self.customer_message_set = False  
        self.final_message = ""
        self.never_recheck = False
        self.recognition_locked = False
        self.persistent_message = False  # CRITICAL: This was missing!
        
        # Stability and recognition
        self.stability_frames = 0
        self.min_stability = 2
        self.state_timer = time.time()
        self.display_message = "Analyzing customer..."
        self.message_time = time.time()
        self.state = "checking"
        
        # Customer retention tracking
        self.customer_id = None
        self.visit_status = None
        self.total_visits = 0
        self.visits_today = 0
        self.is_returning_customer = False
        self.customer_processed = False
        
        # Recognition tracking
        self.recognition_complete = False
        self.database_checked = False
        self.visit_processed = False
        self.fail_count = 0

    def update_customer_info(self, customer_id, visit_status):
        """FIXED: Enhanced customer info update with guaranteed message display"""
        
        print(f"📝 PERMANENT: Setting customer info for {customer_id}")
        self.customer_id = customer_id
        self.visit_status = visit_status
        self.customer_processed = True
        self.permanently_recognized = True
        self.never_recheck = True
        self.recognition_locked = True

        if visit_status:
            self.total_visits = visit_status.get('total_visits', 0)
            self.visits_today = visit_status.get('visits_today', 0)
            self.is_returning_customer = visit_status.get('visited_today', False)

            if visit_status.get('visited_today'):
                # ✅ GUARANTEED PERMANENT MESSAGE for existing visitors
                welcome_msg = f"Welcome back!\nAlready counted today\nTotal visits: {self.total_visits}"
                self.final_message = welcome_msg
                self.display_message = welcome_msg
                self.persistent_message = True
                self.state = "permanently_known"
                print(f"✅ PERMANENT: Already counted message set: {welcome_msg}")
            else:
                # ✅ GUARANTEED PERMANENT MESSAGE for new visits
                new_total = self.total_visits + 1
                welcome_msg = f"Welcome!\nVisit #{new_total} recorded\nThank you for visiting"
                self.final_message = welcome_msg
                self.display_message = welcome_msg
                self.persistent_message = True
                self.state = "permanently_known"
                print(f"✅ PERMANENT: New visit message set: {welcome_msg}")

        # ✅ FORCE message activation
        self.customer_message_set = True
        self.processing_complete = True
        self.message_time = time.time()  # Reset message timer
        
        # ✅ ENSURE message is immediately visible
        self.message_shown = True



    def set_retention_message(self, message, duration=8.0, persistent=False):
        # ✅ CRITICAL: NEVER override permanent recognition messages
        if getattr(self, 'permanently_recognized', False):
            print(f"🔒 PERMANENT customer - blocking message override: '{message}'")
            return  # Block all message changes for permanent customers
            
        # ✅ CRITICAL: Don't override persistent messages with temporary ones
        if getattr(self, 'persistent_message', False) and not persistent:
            print(f"🔒 Persistent message active - blocking temporary override: '{message}'")
            return
            
        # Don't override existing messages with "Analyzing"
        if "Analyzing" in message and self.message_shown and not persistent:
            return

        if hasattr(self, 'display_message') and self.display_message and not persistent:
            if ("Welcome" in self.display_message and "Welcome" not in message and
                "Analyzing" in message):
                return

        self.display_message = message
        self.message_time = time.time()
        self.display_duration = duration
        self.persistent_message = persistent

        if "Analyzing" in message:
            self.message_shown = True

        print(f"📝 Message set: {message} (duration: {duration}s, persistent={persistent})")


    # Compatibility alias
    def set_message(self, message):
        self.set_retention_message(message)
    
    def is_message_active(self):
        # ✅ PERMANENT recognition messages NEVER expire
        if getattr(self, 'permanently_recognized', False):
            return True
            
        # ✅ Persistent messages never expire
        if getattr(self, 'persistent_message', False):
            return True

        current_time = time.time()
        time_elapsed = current_time - getattr(self, 'message_time', 0)
        is_active = time_elapsed < self.display_duration

        if not is_active:
            print(f"⏰ Message expired for track {self.track_id}: {time_elapsed:.1f}s elapsed")

        return is_active

    def force_display_message(self, message, permanent=True):
        """FORCE a message to be displayed immediately and permanently"""
        self.display_message = message
        self.final_message = message
        self.persistent_message = permanent
        self.message_shown = True
        self.message_time = time.time()
        
        if permanent:
            self.display_duration = 999999  # Effectively permanent
            
        print(f"🔥 FORCED MESSAGE: {message} (permanent: {permanent})")

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        if getattr(self, '_state', None) == value:
            return

        self._state = value
        color_map = {
            'checking': (255, 255, 0),
            'verified_unknown': (0, 255, 255),
            'processing_customer': (0, 255, 0),
            'new_visit_recorded': (0, 200, 0),
            'already_counted_today': (255, 165, 0),
            'returning_customer': (0, 150, 255),
            'new_customer_registered': (255, 0, 255),
            # ✅ ADD PERMANENT STATES
            'permanently_known': (0, 255, 0),  # Bright green
            'permanently_registered': (255, 0, 255),  # Magenta
        }
        self.color = color_map.get(value, (128, 128, 128))


class TrackingManager:
    def __init__(self, gpu_mode=True):
        self.gpu_mode = gpu_mode
        self.active_tracks = {}
        self.deepsort = DeepSort()

        self.db_manager = DatabaseManager()
        self.face_engine = FaceRecognitionEngine(gpu_mode=gpu_mode)

        self.max_fail_count = 3
        self.customer_processing_timeout = 5.0

    def process_customer_retention(self, track):
        """ENHANCED: Process with separate new vs returning customer tracking"""
        try:
            # Skip if already processed
            if getattr(track, "permanently_recognized", False):
                print(f"🔒 Track {track.track_id} permanently recognized - skipping processing")
                return

            # Mark as being processed
            track.customer_processed = True
            track.recognition_locked = True
            print(f"🔄 Processing customer for track {track.track_id}")

            # Set initial checking message
            if not track.message_shown:
                track.set_retention_message("Analyzing customer...", duration=3.0, persistent=False)

            # Try to identify existing customer
            best_match_id, best_score = self.face_engine.lightning_fast_customer_identification(track.embedding)

            if best_score >= 0.55 and best_match_id:
                # ✅ RETURNING CUSTOMER (Existing in database)
                print(f"✅ RETURNING CUSTOMER: {best_match_id} (confidence: {best_score:.3f})")
                track.customer_type = "returning"  # 🔑 KEY: Mark as returning
                track.permanently_recognized = True
                track.confidence = best_score

                # Check if already visited today
                visit_status = self.db_manager.check_daily_visit_status(best_match_id)
                
                if visit_status['visited_today']:
                    # Already counted today
                    track.update_customer_info(best_match_id, visit_status)
                    # 📊 Increment returning customer counter (already counted)
                    self._increment_customer_counter("returning_already_counted")
                else:
                    # New visit today for returning customer
                    visit_result = self.db_manager.record_customer_visit(best_match_id, best_score)
                    if visit_result['success']:
                        track.update_customer_info(best_match_id, visit_result)
                        # 📊 Increment returning customer counter (new visit)
                        self._increment_customer_counter("returning_new_visit")

            else:
                # ✅ NEW CUSTOMER (Unknown face - needs registration)
                if track.stability_frames >= track.min_stability:
                    print(f"🆕 NEW CUSTOMER: Unknown face (confidence: {best_score:.3f})")
                    track.customer_type = "new"  # 🔑 KEY: Mark as new
                    
                    # Register new customer
                    new_customer_id = self.face_engine.register_new_customer(track.embedding)
                    if new_customer_id:
                        track.permanently_recognized = True
                        track.customer_id = new_customer_id
                        
                        # Record first visit
                        visit_result = self.db_manager.record_customer_visit(new_customer_id, 0.9)
                        if visit_result['success']:
                            track.update_customer_info(new_customer_id, visit_result)
                            # 📊 Increment NEW customer counter
                            self._increment_customer_counter("new_customer")
                        
                        print(f"🎉 NEW CUSTOMER REGISTERED: {new_customer_id}")
                    else:
                        track.set_retention_message("Welcome visitor!", duration=6.0)
                else:
                    # Still analyzing
                    track.set_retention_message("Analyzing customer...", duration=3.0)

        except Exception as e:
            print(f"❌ Customer retention processing error: {e}")
            track.set_retention_message("Welcome!", duration=6.0)
            track.processing_complete = True

    def _increment_customer_counter(self, counter_type):
        """Increment specific customer counters with proper categorization"""
        try:
            # This should connect to your dashboard counter system
            if hasattr(self, 'dashboard_callback') and self.dashboard_callback:
                self.dashboard_callback(counter_type)
            
            print(f"📈 Customer counter incremented: {counter_type}")
            
        except Exception as e:
            print(f"❌ Counter increment error: {e}")


    def update_tracks(self, detections):
        current_time = time.time()
        try:
            ds_detections = [Detection(d['bbox'], d['embedding']) for d in detections]
            ds_tracks = self.deepsort.update(ds_detections)

            updated_tracks = []
            active_ids = set()

            for track_id, bbox, embedding in ds_tracks:
                active_ids.add(track_id)
                if track_id in self.active_tracks:
                    tracker = self.active_tracks[track_id]
                    tracker.bbox = bbox
                    tracker.display_bbox = bbox
                    tracker.last_seen = current_time
                    tracker.embedding = embedding
                    tracker.stability_frames += 1
                    # Invoke retention logic after stability update
                    self.process_customer_retention(tracker)
                else:
                    tracker = OptimizedFaceTracker(track_id, bbox, embedding)
                    self.active_tracks[track_id] = tracker
                    updated_tracks.append(tracker)
            for tid in list(self.active_tracks.keys()):
                if tid not in active_ids:
                    tracker = self.active_tracks[tid]
                    if hasattr(tracker, "set_retention_message"):
                        tracker.set_retention_message("", duration=0)
                    del self.active_tracks[tid]

            return updated_tracks

        except Exception as e:
            print(f"❌ Tracking update error: {e}")
            return list(self.active_tracks.values())

    def draw_retention_info(self, frame, tracks):
        """FIXED: Enhanced message display with guaranteed permanent message rendering"""
        try:
            current_time = time.time()
            
            for track in tracks:
                # ✅ ALWAYS show permanent customers (no timeout)
                if getattr(track, 'permanently_recognized', False):
                    timeout = 999999  # Effectively permanent
                else:
                    timeout = track.display_duration
                    
                if current_time - track.last_seen > timeout:
                    continue

                if not hasattr(track, 'display_bbox'):
                    continue

                bbox = track.display_bbox
                x1, y1, x2, y2 = [int(coord) for coord in bbox]

                # ✅ ENHANCED color coding for permanent recognition
                if getattr(track, 'permanently_recognized', False):
                    color = (0, 255, 0)  # Bright green for recognized customers
                    status = "RECOGNIZED ✅"
                    cv2.putText(frame, status, (x1, y1 - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                else:
                    color = (255, 255, 0)  # Yellow for analyzing
                    cv2.putText(frame, "Processing...", (x1, y1 - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                # Track ID and confidence
                info = f"ID:{track.track_id}"
                if hasattr(track, 'confidence') and track.confidence > 0:
                    info += f" {track.confidence:.2f}"
                cv2.putText(frame, info, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                # ✅ GUARANTEED MESSAGE DISPLAY for permanent customers
                show_message = False
                
                if getattr(track, 'permanently_recognized', False):
                    # Always show permanent messages
                    show_message = True
                elif hasattr(track, 'is_message_active') and track.is_message_active():
                    # Show temporary messages if active
                    show_message = True
                    
                if show_message and hasattr(track, 'display_message') and track.display_message:
                    lines = track.display_message.split('\n')[:4]
                    for i, line in enumerate(lines):
                        if line.strip():  # Only show non-empty lines
                            cv2.putText(frame, line, (x1, y2 + 20 + (i * 15)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                    print(f"📺 Displaying message for track {track.track_id}: {track.display_message}")

            return frame

        except Exception as e:
            print(f"❌ Drawing error: {e}")
            return frame


    def get_track_count(self):
        return len(self.active_tracks)
