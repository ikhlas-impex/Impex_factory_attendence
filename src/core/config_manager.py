# src/core/config_manager.py
import json
import os
import shutil
from typing import Dict, Any, Callable
from urllib.parse import urlparse

class ConfigManager:
    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self.settings_file = os.path.join(config_dir, "settings.json")
        self.camera_file = os.path.join(config_dir, "camera_settings.json")
        self.network_file = os.path.join(config_dir, "network_settings.json")
        self.system_file = os.path.join(config_dir, "system_config.json")
        
        # Ensure config directory exists
        os.makedirs(config_dir, exist_ok=True)
        
        # Load or create default settings
        self.settings = self.load_settings()
        self.system_config = self.load_system_config()

        # Callbacks for camera IP changes
        self.ip_change_callbacks = []

        print(f"ConfigManager initialized with camera file: {self.camera_file}")
        
    def load_settings(self) -> Dict[str, Any]:
        """Load application settings"""
        default_settings = {
            "app_version": "2.0",
            "auto_save_reports": True,
            "report_generation_time": "23:55",
            "max_detection_distance": 0.6,
            "min_face_size": 50,
            "gpu_enabled": True,
            "language": "english",
            "theme": "default",
            # Adjustable face recognition match threshold. Lower values increase
            # matches but may introduce false positives. Recommended range:
            # 0.55-0.7 based on environment.
            "confidence_threshold": 0.55,
        }
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults
                    default_settings.update(loaded_settings)
            except Exception as e:
                print(f"Error loading settings: {e}")
        
        return default_settings
    
    def load_system_config(self) -> Dict[str, Any]:
        """Load system configuration (check-in/check-out mode)"""
        default_config = {
            "system_mode": "checkin",
            "system_name": "IMPEX Attendance System",
            "database_path": "data/factory_attendance.db",
            "allow_mode_switch": True,
            "locked_mode": False
        }
        
        if os.path.exists(self.system_file):
            try:
                with open(self.system_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults
                    default_config.update(loaded_config)
            except Exception as e:
                print(f"Error loading system config: {e}")
        else:
            # Create default system config file
            try:
                with open(self.system_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Error creating system config: {e}")
        
        return default_config
    
    def save_settings(self, settings: Dict[str, Any] = None):
        """Save application settings"""
        if settings:
            self.settings.update(settings)
        
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def get_setting(self, key: str, default=None):
        """Get a specific setting"""
        return self.settings.get(key, default)
    
    def set_setting(self, key: str, value):
        """Set a specific setting"""
        self.settings[key] = value
        self.save_settings()
    
    def get_camera_settings(self) -> Dict[str, Any]:
        """Get camera settings - CRITICAL METHOD"""
        print(f"Loading camera settings from: {self.camera_file}")
        
        if os.path.exists(self.camera_file):
            try:
                with open(self.camera_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    print(f"Loaded camera settings: {settings}")
                    return settings
            except Exception as e:
                print(f"Error loading camera settings: {e}")
        
        # Return default camera settings if file doesn't exist
        default_settings = {
            "source_type": "usb",
            "rtsp_url": "rtsp://admin:password@192.168.1.100:554/stream1",
            "usb_index": 0,
            "resolution": "1920x1080",
            "fps": 30,  # Optimized FPS for smooth video with low latency
            "buffer_size": 1,  # Minimum buffer for lowest latency
            "transport": "TCP",
            "camera_mac": None,
        }
        print(f"Using default camera settings: {default_settings}")
        return default_settings
    
    def save_camera_settings(self, settings: Dict[str, Any]):
        """Save camera settings"""
        print(f"Saving camera settings to: {self.camera_file}")
        print(f"Settings to save: {settings}")
        
        try:
            with open(self.camera_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            print("Camera settings saved successfully!")
        except Exception as e:
            print(f"Error saving camera settings: {e}")

    def update_camera_ip(self, new_ip: str):
        """Update the IP address portion of the stored RTSP URL"""
        try:
            settings = self.get_camera_settings()
            rtsp_url = settings.get("rtsp_url", "")
            if not rtsp_url:
                return

            parsed = urlparse(rtsp_url)
            username = parsed.username or ""
            password = parsed.password or ""
            port = parsed.port or 554
            path = parsed.path or ""

            if username and password:
                auth_part = f"{username}:{password}@"
            elif username:
                auth_part = f"{username}@"
            else:
                auth_part = ""

            new_url = f"rtsp://{auth_part}{new_ip}:{port}{path}"
            settings["rtsp_url"] = new_url
            self.save_camera_settings(settings)
            self._notify_ip_change(new_ip)
        except Exception as e:
            print(f"Error updating camera IP: {e}")

    def register_ip_change_callback(self, callback: Callable[[str], None]):
        """Register a callback for camera IP changes"""
        if callback not in self.ip_change_callbacks:
            self.ip_change_callbacks.append(callback)

    def _notify_ip_change(self, new_ip: str):
        for cb in self.ip_change_callbacks:
            try:
                cb(new_ip)
            except Exception as e:
                print(f"IP change callback error: {e}")

    def get_network_settings(self) -> Dict[str, Any]:
        """Load network configuration"""
        print(f"Loading network settings from: {self.network_file}")

        default_settings = {
            "ethernet_ip": "192.168.1.100",
            "wifi_ip": "192.168.1.100",
            "username": "admin",
            "password": "admin",
            "port": 554,
            "auto_switch_enabled": False,
            "preferred_connection": "ethernet",
            "monitor_interval": 5,
            "failover_timeout": 5,
        }

        if os.path.exists(self.network_file):
            try:
                with open(self.network_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    if isinstance(loaded_settings, dict):
                        default_settings.update(loaded_settings)
                    else:
                        print("Network settings file is malformed; using defaults")
            except Exception as e:
                print(f"Error loading network settings: {e}")

        print(f"Using network settings: {default_settings}")
        return default_settings

    def save_network_settings(self, settings: Dict[str, Any]):
        """Persist network configuration"""
        print(f"Saving network settings to: {self.network_file}")
        print(f"Settings to save: {settings}")

        try:
            with open(self.network_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            print("Network settings saved successfully!")
        except Exception as e:
            print(f"Error saving network settings: {e}")

    def get_system_config(self) -> Dict[str, Any]:
        """Get system configuration"""
        return self.system_config
    
    def save_system_config(self, config: Dict[str, Any] = None):
        """Save system configuration"""
        if config:
            self.system_config.update(config)
        
        try:
            with open(self.system_file, 'w', encoding='utf-8') as f:
                json.dump(self.system_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving system config: {e}")
    
    def get_system_mode(self) -> str:
        """Get current system mode: 'checkin' or 'checkout'"""
        return self.system_config.get('system_mode', 'checkin')
    
    def is_locked_mode(self) -> bool:
        """Check if system is in locked mode (no mode switching allowed)"""
        return self.system_config.get('locked_mode', False)
    
    def get_database_path(self) -> str:
        """Get database path from system config"""
        return self.system_config.get('database_path', 'data/factory_attendance.db')
    
    def export_configuration(self, export_path: str):
        """Export configuration files to a specified directory"""
        print(f"Exporting configuration to: {export_path}")
        os.makedirs(export_path, exist_ok=True)

        files = [self.settings_file, self.camera_file, self.network_file, self.system_file]

        for file_path in files:
            if os.path.exists(file_path):
                try:
                    shutil.copy(file_path, export_path)
                    print(f"Copied {file_path} to {export_path}")
                except Exception as e:
                    print(f"Error copying {file_path}: {e}")
            else:
                print(f"File {file_path} does not exist, skipping")
    
    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        self.settings = self.load_settings()
        self.save_settings()
        
        # Remove camera settings file to reset to defaults
        if os.path.exists(self.camera_file):
            try:
                os.remove(self.camera_file)
                print("Camera settings reset to defaults")
            except Exception as e:
                print(f"Error resetting camera settings: {e}")
