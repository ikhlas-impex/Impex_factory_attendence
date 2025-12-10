# src/core/face_engine.py - Ultra-Optimized Implementation
import cv2
import numpy as np
from insightface.app import FaceAnalysis
from sklearn.metrics.pairwise import cosine_similarity
import sqlite3
import threading
import time
from datetime import datetime
from core.database_manager import DatabaseManager
from core.config_manager import ConfigManager
import logging
import pickle


class FaceRecognitionEngine:
    def __init__(self, gpu_mode=True):
        self.gpu_mode = gpu_mode
        self.config = ConfigManager()
        self.db_manager = DatabaseManager()

        # Research-backed threshold settings
        # MODIFIED: Lowered thresholds for better real-world detection
        self.min_face_size = 60  # Changed from 80
        # Allow configurable match threshold; default tuned for balanced
        # precision/recall. Users can adjust via ConfigManager settings.json.
        self.confidence_threshold = self.config.get_setting(
            "confidence_threshold", 0.55
        )
        self.detection_threshold = 0.6  # Changed from 0.65
        self.quality_threshold = 0.7

        # Enhanced processing settings
        self.processing_resolution = (640, 480)  # Better balance of speed vs accuracy

        # Initialize InsightFace with optimal settings
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if gpu_mode else ['CPUExecutionProvider']

        try:
            self.app = FaceAnalysis(
                allowed_modules=['detection', 'recognition'],
                providers=providers
            )

            # Optimal detection size for accuracy[75]
            # Adjust detection size for better compatibility with various camera resolutions
            det_size = (960, 960) if gpu_mode else (640, 640)
            self.app.prepare(ctx_id=0 if gpu_mode else -1, det_size=det_size, det_thresh=0.5)

            print(f"✅ Enhanced face recognition initialized in {'GPU' if gpu_mode else 'CPU'} mode")

        except Exception as e:
            print(f"Failed to initialize face recognition: {e}")
            raise

        # Load databases with performance optimization
        self.customer_database = {}
        self.staff_database = {}
        self.load_databases()

        # Performance optimization
        self.face_cache = {}
        self.last_cache_clear = time.time()

    def load_databases(self):
        """Load customer and staff databases with ultra-optimization"""
        try:
            # Load customers with performance limit
            customers = self.db_manager.get_all_customers()
            self.customer_database = {}
            loaded_customers = 0

            # Limit loading to most recent 1000 customers for performance
            recent_customers = sorted(customers, key=lambda x: x.get('last_visit', ''), reverse=True)[:1000]

            for customer in recent_customers:
                if customer['embedding'] is not None:
                    try:
                        # Embeddings are stored using pickle to preserve dtype/shape
                        embedding = pickle.loads(customer['embedding'])
                        self.customer_database[customer['customer_id']] = embedding
                        loaded_customers += 1
                    except Exception as e:
                        print(f"Error loading customer {customer['customer_id']}: {e}")

            # Load staff - FIXED to handle both pickle and buffer formats
            staff_members = self.db_manager.get_all_staff()
            self.staff_database = {}
            loaded_staff = 0

            for staff in staff_members:
                if staff['embedding'] is not None:
                    try:
                        embedding_blob = staff['embedding']
                        
                        # Try pickle first (most common format)
                        try:
                            embedding = pickle.loads(embedding_blob)
                            if isinstance(embedding, np.ndarray):
                                # Normalize embedding
                                if np.linalg.norm(embedding) > 0:
                                    embedding = embedding / np.linalg.norm(embedding)
                                self.staff_database[staff['staff_id']] = embedding
                                loaded_staff += 1
                                continue
                        except:
                            pass
                        
                        # Try frombuffer as fallback
                        try:
                            embedding = np.frombuffer(embedding_blob, dtype=np.float32)
                            if embedding.size > 0:
                                # Normalize embedding
                                if np.linalg.norm(embedding) > 0:
                                    embedding = embedding / np.linalg.norm(embedding)
                                self.staff_database[staff['staff_id']] = embedding
                                loaded_staff += 1
                        except Exception as e2:
                            print(f"Error loading staff {staff['staff_id']}: {e2}")
                    except Exception as e:
                        print(f"Error loading staff {staff['staff_id']}: {e}")

            print(f"✅ Loaded {loaded_customers} customers and {loaded_staff} staff members (ultra-optimized)")

        except Exception as e:
            print(f"❌ Error loading databases: {e}")
            self.customer_database = {}
            self.staff_database = {}

    def ultra_optimized_face_detection(self, frame):
        """Ultra-optimized face detection with proper threshold"""
        try:
            if frame is None:
                return []

            # Process frame with optimal resolution
            height, width = frame.shape[:2]
            scale_factor = min(self.processing_resolution[0] / width, self.processing_resolution[1] / height)

            if scale_factor < 1.0:
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                processed_frame = cv2.resize(frame, (new_width, new_height))
            else:
                processed_frame = frame
                scale_factor = 1.0

            # InsightFace expects BGR images
            faces = self.app.get(processed_frame)

            detections = []
            for face in faces:
                # OPTIMIZED: Lower detection threshold for better face visibility
                if face.det_score < 0.25:  # Lowered threshold to detect more faces
                    continue

                # Scale coordinates back to original image
                bbox = face.bbox / scale_factor
                x1, y1, x2, y2 = bbox.astype(int)

                # OPTIMIZED: Reduced minimum face size for better detection
                face_width = x2 - x1
                face_height = y2 - y1
                if min(face_width, face_height) < 30:  # Even smaller minimum for better detection
                    continue

                # More lenient aspect ratio
                aspect_ratio = face_width / face_height
                if aspect_ratio < 0.5 or aspect_ratio > 2.0:  # More lenient range
                    continue

                # Normalize embedding
                embedding = face.embedding
                if np.linalg.norm(embedding) > 0:
                    embedding = embedding / np.linalg.norm(embedding)
                else:
                    continue

                # Calculate quality score
                face_area = face_width * face_height
                quality_score = face.det_score * min(1.0, face_area / 5000)  # Lowered threshold

                detection = {
                    'bbox': [x1, y1, x2, y2],
                    'confidence': float(face.det_score),
                    'embedding': embedding,
                    'landmarks': face.kps if hasattr(face, 'kps') else None,
                    'quality_score': quality_score,
                    'face_area': face_area
                }

                detections.append(detection)

            # Return all detections for visibility
            detections = sorted(detections, key=lambda x: x['quality_score'], reverse=True)
            return detections  # Return all detections, not just top 2

        except Exception as e:
            print(f"Face detection error: {e}")
            return []

    def monitor_detection_quality(self, detections):
        """Monitor and log detection quality metrics"""
        try:
            if not detections:
                return

            total_detections = len(detections)
            high_quality_detections = len([d for d in detections if d['quality_score'] > 0.8])
            avg_confidence = sum(d['confidence'] for d in detections) / total_detections

            print(f"📊 Detection Quality: {high_quality_detections}/{total_detections} high-quality, "
                  f"Avg confidence: {avg_confidence:.3f}")

            # Log poor quality detections for debugging
            for i, det in enumerate(detections):
                if det['quality_score'] < 0.7:
                    print(f"⚠️ Low quality detection {i}: confidence={det['confidence']:.3f}, "
                          f"quality={det['quality_score']:.3f}, area={det['face_area']}")

        except Exception as e:
            print(f"Quality monitoring error: {e}")

    def _validate_human_face_landmarks(self, landmarks, bbox):
        """Validate landmarks to ensure detection is a human face"""
        try:
            if landmarks is None or len(landmarks) < 5:
                return False

            x1, y1, x2, y2 = bbox
            face_width = x2 - x1
            face_height = y2 - y1

            # Extract key facial landmarks
            left_eye = landmarks[0]
            right_eye = landmarks[1]
            nose = landmarks[2] if len(landmarks) > 2 else None
            left_mouth = landmarks[3] if len(landmarks) > 3 else None
            right_mouth = landmarks[4] if len(landmarks) > 4 else None

            # Validate landmarks are within bounding box
            for point in landmarks:
                x, y = point[0], point[1]
                if x < x1 or x > x2 or y < y1 or y > y2:
                    return False

            # Validate facial structure proportions
            eye_distance = abs(right_eye[0] - left_eye[0])

            # Eyes should be reasonably spaced (15-50% of face width)
            if eye_distance < face_width * 0.15 or eye_distance > face_width * 0.5:
                return False

            # Eyes should be in upper half of face
            eye_avg_y = (left_eye[1] + right_eye[1]) / 2
            if eye_avg_y > y1 + face_height * 0.6:
                return False

            # Validate mouth position if available
            if left_mouth is not None and right_mouth is not None:
                mouth_avg_y = (left_mouth[1] + right_mouth[1]) / 2

                # Mouth should be below eyes
                if mouth_avg_y <= eye_avg_y:
                    return False

                # Mouth should be in lower half of face
                if mouth_avg_y < y1 + face_height * 0.4:
                    return False

            # Validate nose position if available
            if nose is not None:
                # Nose should be between eyes vertically
                if nose[1] < eye_avg_y or nose[1] > y1 + face_height * 0.75:
                    return False

            return True

        except Exception as e:
            print(f"Landmark validation error: {e}")
            return True  # Default to accepting if validation fails

    def detect_faces(self, frame):
        """Main face detection method using ultra-optimization"""
        return self.ultra_optimized_face_detection(frame)

    def lightning_fast_customer_identification(self, face_embedding):
        """Ultra-fast customer identification with dot product optimization"""
        if face_embedding is None or len(self.customer_database) == 0:
            return None, 0.0

        try:
            best_match_id = None
            best_similarity = 0.0
            
            # Normalize embedding once outside the loop
            embedding_norm = np.linalg.norm(face_embedding)
            if embedding_norm == 0:
                return None, 0.0
            face_embedding_normalized = face_embedding / embedding_norm

            # Process only top 50 most recent customers for speed
            customer_items = list(self.customer_database.items())[:50]

            for customer_id, stored_embedding in customer_items:
                try:
                    # Fast dot product instead of cosine_similarity
                    stored_norm = np.linalg.norm(stored_embedding)
                    if stored_norm == 0:
                        continue
                        
                    stored_normalized = stored_embedding / stored_norm
                    similarity = float(np.dot(face_embedding_normalized, stored_normalized))

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match_id = customer_id

                    # Early exit for very high confidence (CRITICAL for speed)
                    if similarity > 0.90:
                        print(f"⚡ Fast match found: {customer_id} ({similarity:.3f})")
                        break

                except Exception as e:
                    continue

            return best_match_id, best_similarity

        except Exception as e:
            print(f"Customer identification error: {e}")
            return None, 0.0

    def identify_person(self, embedding):
        """Identify if person is customer or staff with ultra-optimization"""
        try:
            # Check staff first (higher priority)
            staff_match = self._match_against_database(embedding, self.staff_database)
            if staff_match[1] > 0.65:  # Higher threshold for staff
                return 'staff', staff_match[0], staff_match[1]

            # Check customers with lightning-fast method
            customer_id, confidence = self.lightning_fast_customer_identification(embedding)
            if customer_id and confidence > self.confidence_threshold:
                return 'customer', customer_id, confidence

            return 'unknown', None, 0.0

        except Exception as e:
            print(f"Identification error: {e}")
            return 'unknown', None, 0.0

    def _match_against_database(self, embedding, database):
        """Match embedding against database with optimization"""
        if not database or embedding is None:
            return None, 0.0

        best_match = None
        best_similarity = 0.0

        try:
            embedding_reshaped = embedding.reshape(1, -1)

            for person_id, stored_embedding in database.items():
                if stored_embedding is None:
                    continue

                stored_reshaped = stored_embedding.reshape(1, -1)
                similarity = cosine_similarity(embedding_reshaped, stored_reshaped)[0][0]

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = person_id

            return best_match, best_similarity

        except Exception as e:
            print(f"Matching error: {e}")
            return None, 0.0

    def register_new_customer(self, embedding, image=None, min_quality_score=0.6):
        """Register a new customer with enhanced validation and database verification"""
        try:
            # Validate embedding quality
            if embedding is None or np.linalg.norm(embedding) == 0:
                print("❌ Invalid embedding for customer registration")
                return None

            # Check for duplicate embeddings in existing database
            if self._is_duplicate_customer(embedding):
                print("⚠️ Similar customer already exists, skipping registration")
                return None

            # Register in database with verification
            customer_id = self.db_manager.register_new_customer(embedding, image)

            if customer_id:
                # Verify the registration was successful by trying to retrieve it
                customer_info = self.db_manager.get_customer_info(customer_id)
                if customer_info:
                    # Add to local database immediately for speed
                    self.customer_database[customer_id] = embedding
                    print(f"✅ Customer registered and verified: {customer_id}")

                    # Log the registration
                    self._log_customer_registration(customer_id, embedding)
                    return customer_id
                else:
                    print(f"❌ Customer registration verification failed for {customer_id}")
                    return None
            else:
                print("❌ Database registration failed")
                return None

        except Exception as e:
            print(f"❌ Customer registration error: {e}")
            return None

    def _is_duplicate_customer(self, new_embedding, similarity_threshold=0.85):
        """Check if customer already exists with high similarity"""
        try:
            if len(self.customer_database) == 0:
                return False

            new_embedding_reshaped = new_embedding.reshape(1, -1)

            for customer_id, existing_embedding in self.customer_database.items():
                try:
                    existing_reshaped = existing_embedding.reshape(1, -1)
                    similarity = cosine_similarity(new_embedding_reshaped, existing_reshaped)[0][0]

                    if similarity > similarity_threshold:
                        print(f"Found similar customer {customer_id} with similarity {similarity:.3f}")
                        return True

                except Exception as e:
                    continue

            return False

        except Exception as e:
            print(f"Duplicate check error: {e}")
            return False

    def _log_customer_registration(self, customer_id, embedding):
        """Log customer registration for debugging"""
        try:
            # Log to database system logs
            log_message = f"New customer registered: {customer_id}, embedding norm: {np.linalg.norm(embedding):.3f}"

            # You can add this to your database_manager if you have a logging table
            print(f"📝 Registration Log: {log_message}")

        except Exception as e:
            print(f"Logging error: {e}")

    def add_staff_member(self, staff_id, name, department, embedding, image=None):
        """Add a staff member"""
        try:
            success = self.db_manager.add_staff_member(staff_id, name, department, embedding, image)

            if success:
                self.staff_database[staff_id] = embedding
                print(f"✅ Staff member added: {staff_id} - {name}")

            return success

        except Exception as e:
            print(f"Staff addition error: {e}")
            return False
    def load_staff(self):
        """Load all active staff and their embeddings - FIXED MISSING METHOD"""
        try:
            staff_members = self.db_manager.get_all_staff()
            staff_list = []
            loaded_staff = 0
            
            for staff in staff_members:
                if staff['embedding'] is not None:
                    try:
                        # CONSISTENT: Use pickle.loads like customers
                        embedding = pickle.loads(staff['embedding'])
                        if isinstance(embedding, np.ndarray) and embedding.size > 0:
                            staff_list.append({'id': staff['staff_id'], 'embedding': embedding})
                            loaded_staff += 1
                    except Exception as e:
                        print(f"⚠️ Error loading embedding for staff {staff['staff_id']}: {e}")
                        continue
            
            print(f"✅ Loaded {loaded_staff} staff members")
            return staff_list
            
        except Exception as e:
            print(f"❌ Error loading staff: {e}")
            return []

    def get_statistics(self):
        """Get system statistics"""
        return {
            'total_customers': len(self.customer_database),
            'total_staff': len(self.staff_database),
            'gpu_mode': self.gpu_mode,
            'detection_resolution': self.processing_resolution
        }

    def debug_face_detection(self, frame):
        """Debug version of face detection with detailed output"""
        try:
            print(f"🔍 Debug: Starting face detection on frame {frame.shape}")

            # Process frame
            height, width = frame.shape[:2]
            print(f"  📐 Original frame size: {width}x{height}")

            # Resize for processing
            scale_factor = min(self.processing_resolution[0] / width, self.processing_resolution[1] / height)
            if scale_factor < 1.0:
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                processed_frame = cv2.resize(frame, (new_width, new_height))
                print(f"  📏 Resized to: {new_width}x{new_height} (scale: {scale_factor:.3f})")
            else:
                processed_frame = frame
                scale_factor = 1.0
                print(f"  📏 No resize needed")

            # InsightFace expects BGR input
            print(f"  🎨 Using BGR frame for detection")

            # Detect faces
            faces = self.app.get(processed_frame)
            print(f"  👤 Raw detections: {len(faces)}")

            detections = []
            for i, face in enumerate(faces):
                print(f"    Face {i + 1}: confidence={face.det_score:.3f}")

                if face.det_score < 0.3:  # Debug threshold
                    print(f"      ❌ Rejected: Low confidence ({face.det_score:.3f} < 0.3)")
                    continue

                # Scale coordinates back
                bbox = face.bbox / scale_factor
                x1, y1, x2, y2 = bbox.astype(int)
                face_width = x2 - x1
                face_height = y2 - y1

                print(f"      📦 BBox: ({x1},{y1}) to ({x2},{y2}), size: {face_width}x{face_height}")

                if min(face_width, face_height) < self.min_face_size:
                    print(f"      ❌ Rejected: Too small ({min(face_width, face_height)} < {self.min_face_size})")
                    continue

                embedding = face.embedding
                if np.linalg.norm(embedding) > 0:
                    embedding = embedding / np.linalg.norm(embedding)
                    print(f"      ✅ Accepted: embedding norm={np.linalg.norm(embedding):.3f}")

                    detection = {
                        'bbox': [x1, y1, x2, y2],
                        'confidence': float(face.det_score),
                        'embedding': embedding,
                        'landmarks': face.kps if hasattr(face, 'kps') else None,
                        'quality_score': face.det_score,
                        'face_area': face_width * face_height
                    }
                    detections.append(detection)
                else:
                    print(f"      ❌ Rejected: Invalid embedding")

            print(f"  ✅ Final detections: {len(detections)}")
            return detections

        except Exception as e:
            print(f"❌ Debug face detection error: {e}")
            import traceback
            traceback.print_exc()
            return []
