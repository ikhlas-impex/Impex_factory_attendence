# src/ui/network_setup.py - Enhanced for Router-Connected Cameras

import tkinter as tk
from tkinter import ttk, messagebox
import socket
import subprocess
import platform
import threading
import ipaddress
import time
from core.config_manager import ConfigManager

class NetworkSetupWindow:
    def __init__(self, parent):
        self.parent = parent
        self.config = ConfigManager()
        self.discovered_cameras = []
        
        self.window = tk.Toplevel(parent)
        self.window.title("🌐 Network Camera Setup - Router Connection")
        self.window.geometry("700x650")
        self.window.resizable(True, True)
        self.window.transient(parent)
        self.window.grab_set()
        
        self.setup_gui()
        self.load_current_settings()
        
        # Auto-discover cameras on startup
        self.auto_discover_cameras()
        self.auto_discover_and_update_camera()

    def setup_gui(self):
        """Setup GUI for router-connected camera configuration"""
        # Main container
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Router Connection Guide
        guide_frame = ttk.LabelFrame(main_frame, text="📡 Router Connection Setup", padding=10)
        guide_frame.pack(fill=tk.X, pady=(0, 10))
        
        guide_text = """
🔧 SETUP STEPS:
1. Connect camera to router via Ethernet cable
2. Power on camera (PoE or adapter)
3. Click 'Discover Cameras' to find your device
4. Select your camera and configure credentials
5. Test connection and save settings
        """
        
        ttk.Label(guide_frame, text=guide_text, font=('Arial', 9)).pack(anchor=tk.W)
        
        # Camera Discovery Section
        discovery_frame = ttk.LabelFrame(main_frame, text="🔍 Camera Discovery", padding=10)
        discovery_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Discovery controls
        discovery_controls = ttk.Frame(discovery_frame)
        discovery_controls.pack(fill=tk.X, pady=5)
        
        ttk.Button(discovery_controls, text="🔍 Discover Cameras", 
                  command=self.discover_cameras).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(discovery_controls, text="🔄 Scan Network", 
                  command=self.scan_network_range).pack(side=tk.LEFT, padx=5)
        
        # Network range input
        range_frame = ttk.Frame(discovery_controls)
        range_frame.pack(side=tk.RIGHT)
        
        ttk.Label(range_frame, text="Network Range:").pack(side=tk.LEFT, padx=(20,5))
        self.network_range_var = tk.StringVar(value="192.168.1.0/24")
        ttk.Entry(range_frame, textvariable=self.network_range_var, width=15).pack(side=tk.LEFT)
        
        # Discovered cameras list
        ttk.Label(discovery_frame, text="Discovered Cameras:").pack(anchor=tk.W, pady=(10,0))
        
        # Camera list with columns
        columns = ('IP Address', 'Port', 'Status', 'Model')
        self.camera_tree = ttk.Treeview(discovery_frame, columns=columns, show='headings', height=6)
        
        for col in columns:
            self.camera_tree.heading(col, text=col)
            self.camera_tree.column(col, width=120)
        
        # Scrollbar for camera list
        camera_scroll = ttk.Scrollbar(discovery_frame, orient=tk.VERTICAL, command=self.camera_tree.yview)
        self.camera_tree.configure(yscrollcommand=camera_scroll.set)
        
        self.camera_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        camera_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # Bind camera selection
        self.camera_tree.bind('<<TreeviewSelect>>', self.on_camera_selected)

        # Network Interface Settings
        network_frame = ttk.LabelFrame(main_frame, text="🌐 Network Interfaces", padding=10)
        network_frame.pack(fill=tk.X, pady=(0, 10))

        interface_grid = ttk.Frame(network_frame)
        interface_grid.pack(fill=tk.X, pady=5)

        ttk.Label(interface_grid, text="Ethernet IP:").grid(row=0, column=0, sticky=tk.W)
        self.ethernet_ip_var = tk.StringVar(value="192.168.1.100")
        ttk.Entry(interface_grid, textvariable=self.ethernet_ip_var, width=18).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(interface_grid, text="WiFi IP:").grid(row=1, column=0, sticky=tk.W)
        self.wifi_ip_var = tk.StringVar(value="192.168.1.100")
        ttk.Entry(interface_grid, textvariable=self.wifi_ip_var, width=18).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(interface_grid, text="Preferred:").grid(row=0, column=2, padx=(20,5), sticky=tk.W)
        self.connection_type_var = tk.StringVar(value="ethernet")
        pref_combo = ttk.Combobox(interface_grid, textvariable=self.connection_type_var,
                                  values=["ethernet", "wifi"], width=12, state="readonly")
        pref_combo.grid(row=0, column=3, padx=5)

        ttk.Button(network_frame, text="Check Network", command=self.check_network).pack(anchor=tk.E, pady=5)

        # Camera Configuration Section
        config_frame = ttk.LabelFrame(main_frame, text="⚙️ Camera Configuration", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Camera IP
        ip_frame = ttk.Frame(config_frame)
        ip_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(ip_frame, text="Camera IP Address:").pack(side=tk.LEFT)
        self.camera_ip_var = tk.StringVar(value="192.168.1.12")
        ttk.Entry(ip_frame, textvariable=self.camera_ip_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(ip_frame, text="🔍 Test", command=self.test_camera_connection).pack(side=tk.LEFT, padx=5)
        
        # Authentication
        auth_frame = ttk.Frame(config_frame)
        auth_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(auth_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=(0,5))
        self.username_var = tk.StringVar(value="admin")
        ttk.Entry(auth_frame, textvariable=self.username_var, width=15).grid(row=0, column=1, padx=5)
        
        ttk.Label(auth_frame, text="Password:").grid(row=0, column=2, sticky=tk.W, padx=(20,5))
        self.password_var = tk.StringVar(value="Ikhlas@123")
        ttk.Entry(auth_frame, textvariable=self.password_var, show="*", width=15).grid(row=0, column=3, padx=5)
        
        ttk.Label(auth_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, padx=(0,5), pady=(5,0))
        self.port_var = tk.StringVar(value="554")
        ttk.Entry(auth_frame, textvariable=self.port_var, width=8).grid(row=1, column=1, padx=5, pady=(5,0))
        
        # Stream settings
        stream_frame = ttk.Frame(config_frame)
        stream_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(stream_frame, text="Stream Type:").pack(side=tk.LEFT)
        self.stream_var = tk.StringVar(value="main")
        stream_combo = ttk.Combobox(stream_frame, textvariable=self.stream_var, 
                                   values=["main", "sub"], width=10, state="readonly")
        stream_combo.pack(side=tk.LEFT, padx=5)
        
        # Generated RTSP URL display
        url_frame = ttk.Frame(config_frame)
        url_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(url_frame, text="Generated RTSP URL:").pack(anchor=tk.W)
        self.rtsp_url_var = tk.StringVar()
        self.rtsp_url_label = ttk.Label(url_frame, textvariable=self.rtsp_url_var, 
                                       foreground="blue", font=('Arial', 9))
        self.rtsp_url_label.pack(anchor=tk.W, pady=2)
        
        # Update URL when fields change
        for var in [self.camera_ip_var, self.username_var, self.password_var, self.port_var, self.stream_var]:
            var.trace('w', self.update_rtsp_url)
        
        # Connection Status Section
        status_frame = ttk.LabelFrame(main_frame, text="📊 Connection Status", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_text = tk.Text(status_frame, height=8, wrap=tk.WORD, font=("Courier", 9))
        status_scroll = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scroll.set)
        
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        status_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="💾 Save Configuration", command=self.save_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="❌ Cancel", command=self.window.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="📋 Export Config", command=self.export_config).pack(side=tk.LEFT)

    def auto_discover_cameras(self):
        """Automatically discover cameras on startup"""
        self.log_status("🔍 Auto-discovering cameras on network...")
        threading.Thread(target=self.discover_cameras, daemon=True).start()

    def auto_discover_and_update_camera(self):
        """Continuously monitor the camera IP and update configuration if it changes"""
        def monitor_camera():
            while True:
                settings = self.config.get_camera_settings()
                ip, port = self.extract_ip_from_url(settings.get('rtsp_url', ''))

                if ip and not self.test_camera_port(ip, port):
                    self.log_status("📡 Camera not reachable, scanning for new IP...")
                    found = self.scan_for_cameras(self.network_range_var.get())
                    if found:
                        new_ip = found[0]['ip']
                        self.config.update_camera_ip(new_ip)
                time.sleep(30)

        threading.Thread(target=monitor_camera, daemon=True).start()

    def scan_for_cameras(self, network_range):
        """Scan the network range and return discovered cameras"""
        try:
            network = ipaddress.IPv4Network(network_range, strict=False)
        except Exception:
            network = ipaddress.IPv4Network("192.168.1.0/24", strict=False)

        found_cameras = []
        for ip in network.hosts():
            ip_str = str(ip)
            for port in [554, 8554, 80, 8080]:
                if self.test_camera_port(ip_str, port):
                    camera_info = self.get_camera_info(ip_str, port)
                    found_cameras.append(camera_info)
                    break
        return found_cameras

    def discover_cameras(self):
        """Discover cameras on the network"""
        try:
            self.log_status("🔍 Starting camera discovery...")

            # Clear existing entries
            for item in self.camera_tree.get_children():
                self.camera_tree.delete(item)
            network_range = self.network_range_var.get()
            found_cameras = self.scan_for_cameras(network_range)
            self.discovered_cameras = found_cameras

            for camera_info in found_cameras:
                self.camera_tree.insert('', 'end', values=(
                    camera_info['ip'],
                    camera_info['port'],
                    camera_info['status'],
                    camera_info['model']
                ))
                self.log_status(f"📹 Found camera at {camera_info['ip']}:{camera_info['port']}")

            if found_cameras:
                self.log_status(f"✅ Discovery complete. Found {len(found_cameras)} cameras")

                # Auto-select first camera
                if len(found_cameras) > 0:
                    first_item = self.camera_tree.get_children()[0]
                    self.camera_tree.selection_set(first_item)
                    self.on_camera_selected(None)
            else:
                self.log_status("❌ No cameras found. Check connections and power.")
                
        except Exception as e:
            self.log_status(f"❌ Discovery error: {e}")

    def test_camera_port(self, ip, port):
        """Test if camera responds on specific port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)  # Quick timeout for scanning
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False

    def extract_ip_from_url(self, url):
        """Extract IP and port from an RTSP URL"""
        try:
            if '://' in url and '@' in url:
                after_auth = url.split('://', 1)[1].split('@', 1)[1]
                host_part = after_auth.split('/', 1)[0]
                if ':' in host_part:
                    ip, port = host_part.split(':', 1)
                    return ip, int(port)
                return host_part, 554
        except Exception:
            pass
        return '', 554

    def get_camera_info(self, ip, port):
        """Get camera information"""
        camera_info = {
            'ip': ip,
            'port': port,
            'status': 'Online',
            'model': 'Unknown'
        }
        
        # Try to identify camera model
        if port == 554:
            camera_info['model'] = 'RTSP Camera'
        elif port == 8554:
            camera_info['model'] = 'RTSP Camera (Alt)'
        elif port in [80, 8080]:
            camera_info['model'] = 'Web Camera'
        
        return camera_info

    def on_camera_selected(self, event):
        """Handle camera selection from list"""
        try:
            selection = self.camera_tree.selection()
            if selection:
                item = selection[0]
                values = self.camera_tree.item(item, 'values')
                if values:
                    ip, port, status, model = values
                    self.camera_ip_var.set(ip)
                    self.port_var.set(port)
                    
                    self.log_status(f"📹 Selected camera: {ip}:{port} ({model})")
                    
                    # Auto-update RTSP URL
                    self.update_rtsp_url()
        except Exception as e:
            print(f"Selection error: {e}")

    def update_rtsp_url(self, *args):
        """Update RTSP URL based on current settings"""
        try:
            ip = self.camera_ip_var.get()
            username = self.username_var.get()
            password = self.password_var.get()
            port = self.port_var.get()
            stream = self.stream_var.get()
            
            # Generate RTSP URL based on stream type
            if stream == "main":
                stream_path = "/Streaming/Channels/101"
            else:
                stream_path = "/Streaming/Channels/102"
            
            rtsp_url = f"rtsp://{username}:{password}@{ip}:{port}{stream_path}"
            self.rtsp_url_var.set(rtsp_url)
            
        except Exception as e:
            self.rtsp_url_var.set("Invalid configuration")

    def check_network(self):
        """Ping the selected network IP"""
        try:
            ip = self.ethernet_ip_var.get() if self.connection_type_var.get() == "ethernet" else self.wifi_ip_var.get()
            if not ip:
                messagebox.showwarning("Network Test", "No IP address specified.")
                return

            param = "-n" if platform.system().lower() == "windows" else "-c"
            result = subprocess.run(["ping", param, "1", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                self.log_status(f"✅ Network reachable: {ip}")
                messagebox.showinfo("Network Test", f"✅ {ip} is reachable")
            else:
                self.log_status(f"❌ Network unreachable: {ip}")
                messagebox.showerror("Network Test", f"❌ {ip} is unreachable")
        except Exception as e:
            self.log_status(f"❌ Network test error: {e}")
            messagebox.showerror("Network Test", f"❌ Test failed: {e}")

    def test_camera_connection(self):
        """Test camera connection with current settings"""
        try:
            self.log_status("🔍 Testing camera connection...")
            
            ip = self.camera_ip_var.get()
            port = int(self.port_var.get())
            username = self.username_var.get()
            password = self.password_var.get()
            
            # Test basic connectivity
            if not self.test_camera_port(ip, port):
                self.log_status(f"❌ Cannot reach {ip}:{port}")
                messagebox.showerror("Connection Test", f"❌ Cannot reach camera at {ip}:{port}")
                return False
            
            # Test RTSP stream
            rtsp_url = self.rtsp_url_var.get()
            self.log_status(f"📡 Testing RTSP stream: {rtsp_url}")
            
            import cv2
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    height, width = frame.shape[:2]
                    self.log_status(f"✅ Connection successful! Resolution: {width}x{height}")
                    messagebox.showinfo("Connection Test", 
                                      f"✅ Camera connection successful!\n\n"
                                      f"Resolution: {width}x{height}\n"
                                      f"RTSP URL: {rtsp_url}")
                    cap.release()
                    return True
                else:
                    self.log_status("❌ Cannot read from camera stream")
                    messagebox.showerror("Connection Test", "❌ Camera connected but cannot read stream")
            else:
                self.log_status("❌ Cannot open RTSP stream")
                messagebox.showerror("Connection Test", "❌ Cannot open RTSP stream. Check credentials.")
            
            cap.release()
            return False
            
        except Exception as e:
            self.log_status(f"❌ Connection test error: {e}")
            messagebox.showerror("Connection Test", f"❌ Test failed: {e}")
            return False

    def scan_network_range(self):
        """Scan specific network range"""
        try:
            # Get custom network range from user
            range_dialog = tk.Toplevel(self.window)
            range_dialog.title("Network Range")
            range_dialog.geometry("400x200")
            range_dialog.transient(self.window)
            range_dialog.grab_set()
            
            ttk.Label(range_dialog, text="Enter network range to scan:", 
                     font=('Arial', 12, 'bold')).pack(pady=10)
            
            range_var = tk.StringVar(value=self.network_range_var.get())
            range_entry = ttk.Entry(range_dialog, textvariable=range_var, width=20, font=('Arial', 12))
            range_entry.pack(pady=10)
            
            button_frame = ttk.Frame(range_dialog)
            button_frame.pack(pady=10)
            
            def scan_range():
                self.network_range_var.set(range_var.get())
                range_dialog.destroy()
                threading.Thread(target=self.discover_cameras, daemon=True).start()
            
            ttk.Button(button_frame, text="🔍 Scan", command=scan_range).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="❌ Cancel", command=range_dialog.destroy).pack(side=tk.LEFT, padx=5)
            
            # Examples
            examples_frame = ttk.LabelFrame(range_dialog, text="Examples", padding=5)
            examples_frame.pack(fill=tk.X, padx=20, pady=10)
            
            examples = [
                "192.168.1.0/24 (192.168.1.1-254)",
                "192.168.0.0/24 (192.168.0.1-254)",
                "10.0.0.0/24 (10.0.0.1-254)"
            ]
            
            for example in examples:
                ttk.Label(examples_frame, text=f"• {example}", font=('Arial', 9)).pack(anchor=tk.W)
            
        except Exception as e:
            messagebox.showerror("Error", f"Network scan error: {e}")

    def log_status(self, message):
        """Add message to status log"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_message = f"[{timestamp}] {message}\n"
            
            self.status_text.insert(tk.END, log_message)
            self.status_text.see(tk.END)
            self.window.update_idletasks()
            
        except:
            pass

    def load_current_settings(self):
        """Load current network settings"""
        try:
            settings = self.config.get_network_settings()
            self.ethernet_ip_var.set(settings.get('ethernet_ip', ''))
            self.wifi_ip_var.set(settings.get('wifi_ip', ''))
            self.connection_type_var.set(settings.get('preferred_connection', 'ethernet'))

            # Load camera settings
            camera_settings = self.config.get_camera_settings()

            if 'rtsp_url' in camera_settings:
                rtsp_url = camera_settings['rtsp_url']

                # Parse RTSP URL to extract components
                if '://' in rtsp_url and '@' in rtsp_url:
                    try:
                        # Extract from rtsp://username:password@ip:port/path
                        protocol_part = rtsp_url.split('://')[1]
                        if '@' in protocol_part:
                            auth_part, location_part = protocol_part.split('@', 1)
                            if ':' in auth_part:
                                username, password = auth_part.split(':', 1)
                                self.username_var.set(username)
                                self.password_var.set(password)

                            if ':' in location_part:
                                ip_part = location_part.split(':')[0]
                                port_part = location_part.split(':')[1].split('/')[0]
                                self.camera_ip_var.set(ip_part)
                                self.port_var.set(port_part)
                    except:
                        pass

            self.update_rtsp_url()
            
        except Exception as e:
            print(f"❌ Error loading settings: {e}")

    def save_settings(self):
        """Save network settings"""
        try:
            # Test connection first
            if not self.test_camera_connection():
                result = messagebox.askyesno("Connection Failed", 
                                           "Connection test failed. Save anyway?")
                if not result:
                    return
            
            # Prepare network settings
            network_settings = {
                'ethernet_ip': self.ethernet_ip_var.get(),
                'wifi_ip': self.wifi_ip_var.get(),
                'username': self.username_var.get(),
                'password': self.password_var.get(),
                'port': int(self.port_var.get()),
                'auto_switch_enabled': False,  # Not needed for router connection
                'preferred_connection': self.connection_type_var.get(),
                'monitor_interval': 5,
                'failover_timeout': 5
            }
            
            # Prepare camera settings
            camera_settings = {
                'source_type': 'rtsp',
                'rtsp_url': self.rtsp_url_var.get(),
                'resolution': '1920x1080',
                'fps': 25,
                'buffer_size': 1,
                'transport': 'TCP',
                'camera_mac': self.config.get_camera_settings().get('camera_mac')
            }
            
            # Save settings
            self.config.save_network_settings(network_settings)
            self.config.save_camera_settings(camera_settings)
            
            self.log_status("✅ Configuration saved successfully")
            messagebox.showinfo("Success", 
                              "✅ Camera configuration saved successfully!\n\n"
                              f"Camera IP: {self.camera_ip_var.get()}\n"
                              f"RTSP URL: {self.rtsp_url_var.get()}")
            
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
            self.log_status(f"❌ Save error: {e}")

    def export_config(self):
        """Export configuration"""
        try:
            if self.config.export_configuration():
                messagebox.showinfo("Export", "✅ Configuration exported successfully!")
                self.log_status("✅ Configuration exported")
        except Exception as e:
            messagebox.showerror("Export Error", f"Export failed: {e}")
