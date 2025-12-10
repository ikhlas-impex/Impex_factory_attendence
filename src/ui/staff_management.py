import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import time
from core.database_manager import DatabaseManager
from core.face_engine import FaceRecognitionEngine
from core.config_manager import ConfigManager


def find_working_camera_index():
    """Find the first working camera index with backend selection"""
    # Set environment to disable OBSENSOR
    import os
    os.environ['OPENCV_VIDEOIO_PRIORITY_OBSENSOR'] = '0'
    os.environ['OPENCV_VIDEOIO_PRIORITY_DIRECTSHOW'] = '1000'

    backends_to_try = [cv2.CAP_DSHOW, cv2.CAP_V4L2, cv2.CAP_ANY]

    for backend in backends_to_try:
        print(f"Testing backend: {backend}")
        for index in range(5):  # Test first 5 indices
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


class StaffManagementWindow:
    def __init__(self, parent):
        self.parent = parent
        self.db_manager = DatabaseManager()

        self.window = tk.Toplevel(parent)
        self.window.title("Staff Management")
        self.window.geometry("800x600")
        self.window.transient(parent)

        self.setup_gui()
        self.load_staff_list()

    def setup_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Staff list frame
        list_frame = ttk.LabelFrame(main_frame, text="Staff Members", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Staff treeview
        columns = ('ID', 'Name', 'Department', 'Added Date')
        self.staff_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.staff_tree.heading(col, text=col)
            self.staff_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.staff_tree.yview)
        self.staff_tree.configure(yscrollcommand=scrollbar.set)

        self.staff_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add Staff", command=self.add_staff).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Edit Staff", command=self.edit_staff).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Staff", command=self.delete_staff).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_staff_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

    def load_staff_list(self):
        """Load staff list into treeview"""
        # Clear existing items
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)

        # Load staff from database
        staff_members = self.db_manager.get_all_staff()
        for staff in staff_members:
            self.staff_tree.insert('', tk.END, values=(
                staff['staff_id'],
                staff['name'],
                staff['department'] or 'N/A',
                staff['added_date']
            ))

    def add_staff(self):
        """Add new staff member"""
        AddEditStaffDialog(self.window, self.db_manager, callback=self.load_staff_list)

    def edit_staff(self):
        """Edit selected staff member"""
        selection = self.staff_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a staff member to edit")
            return

        item = self.staff_tree.item(selection[0])
        staff_id = item['values'][0]
        AddEditStaffDialog(self.window, self.db_manager, staff_id=staff_id, callback=self.load_staff_list)

    def delete_staff(self):
        """Delete the selected staff member from the database and refresh the list."""
        try:
            selection = self.staff_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a staff member to delete.")
                return

            staff_id = self.staff_tree.item(selection[0])["values"][0]
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete staff '{staff_id}'?"
            )
            if not confirm:
                return

            # Remove from database
            success = self.db_manager.delete_staff_member(staff_id)
            if not success:
                messagebox.showerror("Error", "Failed to delete staff from database.")
                return

            # Remove from UI
            self.staff_tree.delete(selection[0])
            messagebox.showinfo("Deleted", f"Staff '{staff_id}' has been deleted.")
        except Exception as e:
            messagebox.showerror("Error", f"Error deleting staff: {e}")


class AddEditStaffDialog:
    def __init__(self, parent, db_manager, staff_id=None, callback=None):
        self.db_manager = db_manager
        self.staff_id = staff_id
        self.callback = callback
        self.photo_data = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Staff" if staff_id is None else "Edit Staff")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.setup_gui()

        if staff_id:
            self.load_staff_data()

    def setup_gui(self):
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Staff ID
        ttk.Label(frame, text="Staff ID:").pack(anchor=tk.W, pady=2)
        self.staff_id_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.staff_id_var, width=30).pack(fill=tk.X, pady=2)

        # Name
        ttk.Label(frame, text="Full Name:").pack(anchor=tk.W, pady=(10, 2))
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=30).pack(fill=tk.X, pady=2)

        # Department
        ttk.Label(frame, text="Department:").pack(anchor=tk.W, pady=(10, 2))
        self.department_var = tk.StringVar()
        department_combo = ttk.Combobox(frame, textvariable=self.department_var,
                                        values=["Reception", "Housekeeping", "Security", "Management", "Kitchen",
                                                "Maintenance"])
        department_combo.pack(fill=tk.X, pady=2)

        # Photo section
        photo_frame = ttk.LabelFrame(frame, text="Photo", padding=10)
        photo_frame.pack(fill=tk.X, pady=10)

        self.photo_label = tk.Label(photo_frame, text="No photo selected", bg='lightgray', width=30, height=10)
        self.photo_label.pack(pady=5)

        photo_button_frame = ttk.Frame(photo_frame)
        photo_button_frame.pack(fill=tk.X)

        ttk.Button(photo_button_frame, text="Browse Photo", command=self.browse_photo).pack(side=tk.LEFT, padx=5)
        ttk.Button(photo_button_frame, text="Take Photo", command=self.take_photo).pack(side=tk.LEFT, padx=5)

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save_staff).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def browse_photo(self):
        """Browse for photo file"""
        file_path = filedialog.askopenfilename(
            title="Select Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")]
        )

        if file_path:
            try:
                # Load and display photo
                image = Image.open(file_path)
                image.thumbnail((200, 200))
                photo = ImageTk.PhotoImage(image)

                self.photo_label.config(image=photo, text="")
                self.photo_label.image = photo

                # Store photo data
                self.photo_data = cv2.imread(file_path)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {e}")

    def take_photo(self):
        """Take photo using camera"""
        PhotoCaptureDialog(self.dialog, callback=self.set_photo_data)

    def set_photo_data(self, photo_data):
        """Set photo data from camera capture with proper data validation"""
        try:
            # Handle both single photo and multiple photo data structures
            if isinstance(photo_data, dict):
                # Multiple photos captured
                if 'photos' in photo_data and photo_data['photos']:
                    # Use the first photo for display and main storage
                    self.photo_data = photo_data['photos'][0]
                    self.multiple_photos = photo_data['photos']
                    self.photo_embeddings = photo_data.get('embeddings', [])

                    # Convert and display the first photo
                    rgb_image = cv2.cvtColor(self.photo_data, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_image)
                    pil_image.thumbnail((200, 200))
                    photo = ImageTk.PhotoImage(pil_image)

                    self.photo_label.config(image=photo, text="")
                    self.photo_label.image = photo

                    print(f"✅ Received {len(self.multiple_photos)} photos for staff registration")
            else:
                # Single photo (legacy support)
                if photo_data is not None and isinstance(photo_data, np.ndarray):
                    self.photo_data = photo_data

                    # Convert and display
                    rgb_image = cv2.cvtColor(photo_data, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_image)
                    pil_image.thumbnail((200, 200))
                    photo = ImageTk.PhotoImage(pil_image)

                    self.photo_label.config(image=photo, text="")
                    self.photo_label.image = photo
                else:
                    print("❌ Invalid photo data received")
                    messagebox.showerror("Error", "Invalid photo data received from camera")

        except Exception as e:
            print(f"❌ Photo data processing error: {e}")
            messagebox.showerror("Error", f"Failed to process photo data: {e}")

    def load_staff_data(self):
        """Load existing staff data for editing"""
        staff_info = self.db_manager.get_staff_info(self.staff_id)
        if staff_info:
            self.staff_id_var.set(staff_info['staff_id'])
            self.name_var.set(staff_info['name'])
            self.department_var.set(staff_info['department'] or '')

    def save_staff(self):
        """Save staff member"""
        staff_id = self.staff_id_var.get().strip()
        name = self.name_var.get().strip()
        department = self.department_var.get().strip()

        if not staff_id or not name:
            messagebox.showerror("Error", "Please fill in Staff ID and Name")
            return

        if self.photo_data is None:
            messagebox.showerror("Error", "Please provide a photo")
            return

        try:
            # Extract face embedding
            face_engine = FaceRecognitionEngine()
            detections = face_engine.detect_faces(self.photo_data)

            if not detections:
                messagebox.showerror("Error", "No face detected in the photo. Please use a clear face photo.")
                return

            if len(detections) > 1:
                messagebox.showerror("Error", "Multiple faces detected. Please use a photo with only one face.")
                return

            embedding = detections[0]['embedding']

            # Save to database
            success = self.db_manager.add_staff_member(staff_id, name, department, embedding, self.photo_data)

            if success:
                messagebox.showinfo("Success", "Staff member saved successfully!")
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to save staff member")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process photo: {e}")


class PhotoCaptureDialog:
    def __init__(self, parent, callback=None):
        self.callback = callback
        self.cap = None
        self.running = False

        # Initialize photo storage
        self.captured_photos = []
        self.photo_embeddings = []

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Capture Photo")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.setup_gui()
        self.start_camera()

    def setup_gui(self):
        """Setup enhanced camera capture GUI with larger display"""
        # Make dialog larger for better photo capture
        self.dialog.geometry("900x700")

        # Video frame with larger size
        self.video_frame = tk.Frame(self.dialog, bg='black')
        self.video_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Larger video label for better preview
        self.video_label = tk.Label(self.video_frame, bg='black', text="Connecting to camera...",
                                    font=('Arial', 14), fg='white')
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # Photo collection frame for multiple images
        photo_collection_frame = tk.Frame(self.dialog)
        photo_collection_frame.pack(fill=tk.X, padx=10, pady=5)

        # Show captured images count
        self.photo_count_label = tk.Label(photo_collection_frame,
                                          text="Photos Captured: 0/5",
                                          font=('Arial', 12, 'bold'))
        self.photo_count_label.pack(side=tk.LEFT)

        # Instructions
        instruction_label = tk.Label(photo_collection_frame,
                                     text="Capture 5 photos from different angles for better recognition",
                                     font=('Arial', 10), fg='blue')
        instruction_label.pack(side=tk.RIGHT)

        # Button frame
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Enhanced buttons
        self.capture_btn = tk.Button(button_frame, text="📸 Capture Photo",
                                     command=self.capture_multiple_photos,
                                     font=('Arial', 14, 'bold'), bg='green', fg='white',
                                     height=2, width=15)
        self.capture_btn.pack(side=tk.LEFT, padx=10)

        self.retake_btn = tk.Button(button_frame, text="🔄 Clear All Photos",
                                    command=self.clear_photos,
                                    font=('Arial', 12), bg='orange', fg='white',
                                    height=2, width=12, state=tk.DISABLED)
        self.retake_btn.pack(side=tk.LEFT, padx=10)

        self.finish_btn = tk.Button(button_frame, text="✅ Finish Capture",
                                    command=self.finish_capture,
                                    font=('Arial', 14, 'bold'), bg='blue', fg='white',
                                    height=2, width=15, state=tk.DISABLED)
        self.finish_btn.pack(side=tk.LEFT, padx=10)

        tk.Button(button_frame, text="❌ Cancel", command=self.close_dialog,
                  font=('Arial', 12), height=2, width=10).pack(side=tk.RIGHT, padx=10)

        # Initialize photo storage
        self.captured_photos = []
        self.photo_embeddings = []

    def capture_multiple_photos(self):
        """Enhanced multi-photo capture with better validation"""
        if hasattr(self, 'current_frame') and self.current_frame is not None:
            # Validate frame is a proper numpy array
            if not isinstance(self.current_frame, np.ndarray):
                messagebox.showerror("Error", "Invalid frame data - not a numpy array")
                return

            if self.current_frame.size == 0:
                messagebox.showerror("Error", "Empty frame captured")
                return

            # Store the photo
            photo_copy = self.current_frame.copy()
            self.captured_photos.append(photo_copy)

            # Extract face embedding for each photo
            try:
                from core.face_engine import FaceRecognitionEngine
                face_engine = FaceRecognitionEngine()
                detections = face_engine.detect_faces(photo_copy)

                if detections:
                    # Store embedding for this photo
                    self.photo_embeddings.append(detections[0]['embedding'])

                    # Update UI
                    photo_count = len(self.captured_photos)
                    self.photo_count_label.config(text=f"Photos Captured: {photo_count}/5")

                    # Enhanced capture instructions
                    instructions = [
                        "Excellent! Now turn your head slightly right →",
                        "Perfect! Now turn your head slightly left ←",
                        "Great! Now tilt your head up slightly ↑",
                        "Amazing! Now look down slightly ↓",
                        "Perfect! All photos captured successfully! ✅"
                    ]

                    if photo_count <= 5:
                        instruction = instructions[min(photo_count - 1, 4)]
                        messagebox.showinfo("Photo Captured",
                                            f"Photo {photo_count}/5 captured successfully!\n\n{instruction}")

                    # Enable/disable buttons based on photo count
                    if photo_count >= 3:  # Minimum 3 photos required
                        self.finish_btn.config(state=tk.NORMAL, bg='blue')

                    if photo_count >= 5:  # Maximum 5 photos
                        self.capture_btn.config(state=tk.DISABLED, bg='gray')
                        messagebox.showinfo("Complete",
                                            "All 5 photos captured successfully!\n"
                                            "Click 'Finish Capture' to save and continue.")

                    self.retake_btn.config(state=tk.NORMAL, bg='orange')

                else:
                    messagebox.showerror("No Face Detected",
                                         "No clear face detected in the photo.\n"
                                         "Please ensure:\n"
                                         "• Your face is clearly visible\n"
                                         "• Good lighting conditions\n"
                                         "• Face is not too close or far from camera")

            except Exception as e:
                print(f"Face processing error: {e}")
                messagebox.showerror("Error", f"Failed to process photo: {e}")
        else:
            messagebox.showwarning("Warning", "No frame available to capture")

    def clear_photos(self):
        """Clear all captured photos and reset the capture interface"""
        if len(self.captured_photos) > 0:
            # Ask for confirmation if photos exist
            if messagebox.askyesno("Clear Photos",
                                   f"Are you sure you want to clear all {len(self.captured_photos)} captured photos?"):
                # Clear photo arrays
                self.captured_photos.clear()
                self.photo_embeddings.clear()

                # Reset UI elements
                self.photo_count_label.config(text="Photos Captured: 0/5")
                self.capture_btn.config(state=tk.NORMAL, bg='green', text="📸 Capture Photo")
                self.retake_btn.config(state=tk.DISABLED, bg='gray')
                self.finish_btn.config(state=tk.DISABLED, bg='gray')

                messagebox.showinfo("Cleared",
                                    "All photos cleared successfully!\n"
                                    "Ready to capture new photos.")

                print(f"✅ Cleared all captured photos")
        else:
            messagebox.showinfo("No Photos", "No photos to clear.")

    def finish_capture(self):
        """Finish photo capture with proper data validation"""
        if len(self.captured_photos) >= 3:
            # Validate all photos are proper numpy arrays
            valid_photos = []
            valid_embeddings = []

            for i, photo in enumerate(self.captured_photos):
                if isinstance(photo, np.ndarray) and photo.size > 0:
                    valid_photos.append(photo)
                    if i < len(self.photo_embeddings):
                        valid_embeddings.append(self.photo_embeddings[i])

            if valid_photos:
                if self.callback:
                    # Return properly structured data
                    callback_data = {
                        'photos': valid_photos,
                        'embeddings': valid_embeddings,
                        'count': len(valid_photos)
                    }
                    self.callback(callback_data)
                self.close_dialog()
            else:
                messagebox.showerror("Error", "No valid photos to save")
        else:
            messagebox.showwarning("Insufficient Photos",
                                   f"Please capture at least 3 photos for better recognition.\n"
                                   f"Currently captured: {len(self.captured_photos)} photos")

    def update_video(self):
        """Enhanced video display with larger frame"""
        if not self.running or not self.cap or not self.cap.isOpened():
            return

        try:
            ret, frame = self.cap.read()
            if ret:
                # Convert to RGB for display
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Resize to larger display - enhanced size
                height, width = frame_rgb.shape[:2]
                max_width = 800  # Increased from 600
                max_height = 600  # Increased from 400

                scale = min(max_width / width, max_height / height)
                new_width = int(width * scale)
                new_height = int(height * scale)

                frame_resized = cv2.resize(frame_rgb, (new_width, new_height))

                # Convert to PhotoImage
                image = Image.fromarray(frame_resized)
                photo = ImageTk.PhotoImage(image)

                # Update label
                self.video_label.configure(image=photo, text="")
                self.video_label.image = photo  # Keep reference

                # Store current frame
                self.current_frame = frame

        except Exception as e:
            print(f"Video update error: {e}")

        # Schedule next update
        if self.running:
            self.dialog.after(30, self.update_video)  # ~30 FPS

    def start_camera(self):
        """Start camera with ultra-low latency configuration"""
        try:
            config = ConfigManager()
            camera_settings = config.get_camera_settings()

            print(f"📷 Staff photo capture - Camera settings: {camera_settings}")

            # Get transport protocol from camera_settings.json
            transport = camera_settings.get('transport', 'TCP').upper()
            rtsp_transport = 'udp' if transport == 'UDP' else 'tcp'
            
            # Ultra-low latency environment settings based on camera_settings.json
            import os
            rtsp_options = (
                f'rtsp_transport;{rtsp_transport}|'
                'rtsp_flags;prefer_tcp|'
                'fflags;nobuffer|'
                'flags;low_delay|'
                'fflags;flush_packets'
            )
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = rtsp_options
            print(f"🔧 Using RTSP transport: {rtsp_transport} (from camera_settings.json)")

            if camera_settings.get('source_type') in ['rtsp', 'ip']:
                camera_source = camera_settings.get('rtsp_url')
                print(f"📹 Using RTSP camera with ultra-low latency: {camera_source}")

                # Connect with FFmpeg backend and ultra-low latency settings
                self.cap = cv2.VideoCapture(camera_source, cv2.CAP_FFMPEG)

                if self.cap.isOpened():
                    # Get settings from camera_settings.json
                    buffer_size = camera_settings.get('buffer_size', 1)
                    target_fps = camera_settings.get('fps', 25)
                    
                    # Apply settings from camera_settings.json
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
                    self.cap.set(cv2.CAP_PROP_FPS, target_fps)
                    print(f"🔧 Camera buffer_size: {buffer_size}, fps: {target_fps} (from camera_settings.json)")

                    # Additional latency reduction settings
                    self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))

                    # Test connection with timeout
                    import time
                    start_time = time.time()

                    for attempt in range(3):  # Reduced attempts for faster response
                        ret, frame = self.cap.read()
                        if ret and frame is not None:
                            connection_time = time.time() - start_time
                            print(f"✅ Ultra-low latency RTSP connected in {connection_time:.2f}s")
                            self.running = True
                            self.update_video()
                            return
                        time.sleep(0.5)  # Shorter wait between attempts

                    self.cap.release()
                    print("❌ RTSP camera: Cannot read frames with low latency")
                else:
                    print("❌ Failed to open RTSP camera")

            # USB fallback with low latency settings
            print("📷 Trying USB cameras with low latency settings...")

            backends_to_try = [cv2.CAP_DSHOW, cv2.CAP_V4L2]

            for backend in backends_to_try:
                for index in range(3):
                    try:
                        self.cap = cv2.VideoCapture(index, backend)

                        if self.cap.isOpened():
                            # Use settings from camera_settings.json
                            buffer_size = camera_settings.get('buffer_size', 1)
                            target_fps = camera_settings.get('fps', 25)
                            
                            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
                            self.cap.set(cv2.CAP_PROP_FPS, target_fps)
                            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Lower resolution
                            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # for less latency

                            ret, frame = self.cap.read()
                            if ret and frame is not None:
                                print(f"✅ Low-latency USB camera: index {index}, backend {backend}")
                                self.running = True
                                self.update_video()
                                return
                            else:
                                self.cap.release()

                    except Exception as e:
                        if self.cap:
                            self.cap.release()
                        continue

            # Enhanced error message
            transport = camera_settings.get('transport', 'TCP')
            messagebox.showerror("Camera Error",
                                 f"Cannot access camera for photo capture.\n\n"
                                 f"Camera Configuration (from camera_settings.json):\n"
                                 f"• Type: {camera_settings.get('source_type', 'Unknown')}\n"
                                 f"• URL: {camera_settings.get('rtsp_url', 'Not configured')}\n"
                                 f"• Transport: {transport}\n\n"
                                 f"Troubleshooting:\n"
                                 f"• Ensure stable network connection to IP camera\n"
                                 f"• Close other applications using the camera\n"
                                 f"• Check camera supports {transport} transport\n"
                                 f"• Verify firewall allows RTSP traffic on port 554\n"
                                 f"• Review camera_settings.json configuration")
            self.dialog.destroy()

        except Exception as e:
            print(f"❌ Camera initialization error: {e}")
            messagebox.showerror("Camera Error", f"Failed to initialize camera: {e}")
            self.dialog.destroy()

    def update_video(self):
        """Ultra-optimized video display with minimal latency"""
        if not self.running or not self.cap or not self.cap.isOpened():
            return

        try:
            # Skip old frames to reduce latency
            frames_to_skip = 2  # Skip 2 frames to get latest
            for _ in range(frames_to_skip):
                ret, _ = self.cap.read()
                if not ret:
                    break

            # Get the latest frame
            ret, frame = self.cap.read()
            if ret and frame is not None:
                # Optimize frame processing for speed
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Dynamic resizing based on dialog size
                dialog_width = self.dialog.winfo_width()
                dialog_height = self.dialog.winfo_height()

                if dialog_width > 100 and dialog_height > 100:
                    # Use dialog proportions for better fit
                    max_width = min(dialog_width - 50, 800)
                    max_height = min(dialog_height - 150, 600)
                else:
                    # Default large size
                    max_width, max_height = 800, 600

                # Efficient resizing
                h, w = frame_rgb.shape[:2]
                scale = min(max_width / w, max_height / h)
                new_w, new_h = int(w * scale), int(h * scale)

                frame_resized = cv2.resize(frame_rgb, (new_w, new_h))

                # Fast PhotoImage conversion
                image = Image.fromarray(frame_resized)
                photo = ImageTk.PhotoImage(image)

                # Update display
                self.video_label.configure(image=photo, text="")
                self.video_label.image = photo

                # Store current frame
                self.current_frame = frame

            else:
                print("⚠️ Failed to capture frame")

        except Exception as e:
            print(f"❌ Video update error: {e}")

        # Schedule next update with minimal delay for responsiveness
        if self.running:
            self.dialog.after(16, self.update_video)  # ~60 FPS for smooth display

    def capture_photo(self):
        """Capture current frame"""
        if hasattr(self, 'current_frame') and self.current_frame is not None:
            if self.callback:
                self.callback(self.current_frame)
            self.close_dialog()
        else:
            messagebox.showwarning("Warning", "No frame available to capture")

    def close_dialog(self):
        """Close the dialog and cleanup"""
        self.running = False
        if self.cap:
            self.cap.release()
        self.dialog.destroy()
