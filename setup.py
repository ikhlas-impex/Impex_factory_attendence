from cx_Freeze import setup, Executable
import sys
import os

# Dependencies
build_exe_options = {
    "packages": [
        "cv2", "numpy", "sklearn", "insightface", "tkinter", 
        "PIL", "pandas", "sqlite3", "threading", "queue"
    ],
    "include_files": [
        ("config/", "config/"),
        ("assets/", "assets/"),
        ("requirements.txt", "requirements.txt")
    ],
    "excludes": ["matplotlib", "scipy"],
    "zip_include_packages": ["encodings", "PySide2"]
}

# Executable configuration
executables = [
    Executable(
        "main.py",
        base="Win32GUI" if sys.platform == "win32" else None,
        target_name="HotelFaceRecognition.exe",
        icon="assets/icons/hotel.ico"
    )
]

setup(
    name="Hotel Face Recognition System",
    version="2.0",
    description="AI-Powered Hotel Customer Recognition System",
    options={"build_exe": build_exe_options},
    executables=executables
)
