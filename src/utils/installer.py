import subprocess
import sys
import os

def check_installed_versions():
    """Check installed package versions using pip (faster than importing)"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--format=json'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return None
        
        import json
        packages = {pkg['name'].lower(): pkg['version'] for pkg in json.loads(result.stdout)}
        return packages
    except:
        return None

def check_package_compatibility():
    """Quick check if NumPy and OpenCV are compatible"""
    # First check installed versions via pip (safer)
    installed = check_installed_versions()
    if installed:
        numpy_version = installed.get('numpy', '')
        opencv_version = installed.get('opencv-python', '') or installed.get('opencv-python-headless', '')
        
        # Check if NumPy 2.x is installed
        if numpy_version and numpy_version.startswith('2.'):
            return False, f"NumPy {numpy_version} is too new (need <2.0)"
        
        # If both are installed, try quick import test
        if numpy_version and opencv_version:
            try:
                import numpy as np
                import cv2
                # Quick compatibility test
                arr = np.array([1, 2, 3])
                _ = cv2.__version__
                return True, "Packages are compatible"
            except ImportError as e:
                return False, f"Import error: {e}"
            except AttributeError as e:
                if "_ARRAY_API" in str(e):
                    return False, "NumPy/OpenCV compatibility issue - _ARRAY_API not found"
                return False, f"Attribute error: {e}"
            except Exception as e:
                return False, f"Compatibility check failed: {e}"
    
    # Fallback: try importing directly (may fail with compatibility error)
    try:
        import numpy as np
        import cv2
        
        # Check NumPy version
        np_version = tuple(map(int, np.__version__.split('.')[:2]))
        if np_version[0] >= 2:
            return False, f"NumPy {np.__version__} is too new (need <2.0)"
        
        # Test basic import and array operations
        arr = np.array([1, 2, 3])
        _ = cv2.__version__
        return True, "Packages are compatible"
    except ImportError as e:
        return False, f"Import error: {e}"
    except AttributeError as e:
        if "_ARRAY_API" in str(e):
            return False, "NumPy/OpenCV compatibility issue - _ARRAY_API not found"
        return False, f"Attribute error: {e}"
    except Exception as e:
        return False, f"Compatibility check failed: {e}"

def check_and_install_requirements():
    """
    Checks if required packages are installed and installs them if missing.
    Handles NumPy/OpenCV compatibility issues by reinstalling OpenCV after NumPy changes.
    Only installs if packages are missing or incompatible.
    """
    requirements_path = os.path.join(os.path.dirname(__file__), '..', '..', 'requirements.txt')
    if not os.path.exists(requirements_path):
        print(f"⚠️ requirements.txt not found at {requirements_path}")
        return True  # Don't fail if requirements.txt is missing
    
    try:
        # Quick compatibility check first (with timeout)
        try:
            is_compatible, message = check_package_compatibility()
        except Exception as e:
            # If check itself fails, assume packages need installation but don't block
            print(f"⚠️ Could not verify package compatibility: {e}")
            print("💡 Continuing without auto-installation. Run 'python fix_packages.py' if needed.")
            return True
        
        if is_compatible:
            print("✅ Package compatibility check passed - no installation needed")
            return True
        
        print(f"⚠️ Compatibility issue detected: {message}")
        print("💡 For faster startup, run 'python fix_packages.py' separately to fix packages.")
        print("📦 Attempting quick fix (this may take a moment)...")
        
        # Check if critical packages exist first
        packages_ok = True
        try:
            import numpy
            import cv2
        except ImportError:
            packages_ok = False
        
        # Only reinstall if there's a compatibility issue
        if not packages_ok or not is_compatible:
            print("📦 Installing/updating packages...")
            print("   (This may take a few minutes. You can interrupt and run 'python fix_packages.py' separately)")
            
            # Check installed versions to see what needs updating
            installed = check_installed_versions()
            numpy_needs_fix = True
            opencv_needs_fix = True
            
            if installed:
                numpy_ver = installed.get('numpy', '')
                opencv_ver = installed.get('opencv-python', '') or installed.get('opencv-python-headless', '')
                
                # Check if NumPy is already 1.x
                if numpy_ver and not numpy_ver.startswith('2.'):
                    numpy_needs_fix = False
                    print(f"   → NumPy {numpy_ver} looks compatible, skipping...")
            
            # Install NumPy first with compatible version (only if needed)
            if numpy_needs_fix:
                print("  → Installing compatible NumPy version...")
                try:
                    result = subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '--upgrade', 'numpy<2.0,>=1.24.0'],
                        timeout=180,  # 3 minute timeout
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        print(f"   ⚠️ NumPy installation had issues")
                except subprocess.TimeoutExpired:
                    print("   ⚠️ NumPy installation timed out")
            
            # Install OpenCV packages (compatible with NumPy 1.x)
            print("  → Installing OpenCV packages...")
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '--upgrade',
                     'opencv-python>=4.8.0,<5.0.0', 'opencv-python-headless>=4.9.0.80'],
                    timeout=300,  # 5 minute timeout for OpenCV
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    print(f"   ⚠️ OpenCV installation had issues")
            except subprocess.TimeoutExpired:
                print("   ⚠️ OpenCV installation timed out")
            
            # Install remaining packages if needed (skip if they're already installed)
            print("  → Checking remaining requirements...")
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '-r', requirements_path],
                    timeout=180,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    print(f"   ⚠️ Some requirements may need manual installation")
            except subprocess.TimeoutExpired:
                print("   ⚠️ Requirements installation timed out")
        
        # Verify installation
        print("🔍 Verifying installation...")
        is_compatible, message = check_package_compatibility()
        
        if is_compatible:
            try:
                import numpy as np
                import cv2
                print(f"✅ NumPy {np.__version__} and OpenCV {cv2.__version__} are compatible")
            except:
                pass
            return True
        else:
            print(f"⚠️ Compatibility issue persists: {message}")
            print("💡 Try running 'python fix_packages.py' manually to fix this")
            # Don't fail - let the app try to continue
            return True
            
    except subprocess.TimeoutExpired:
        print("⚠️ Package installation timed out. This may take longer on slow connections.")
        print("💡 You can install packages manually later. Continuing...")
        return True
    except Exception as e:
        print(f"⚠️ Package check encountered an issue: {e}")
        print("💡 Continuing anyway - packages may need manual installation")
        return True  # Don't fail the app startup
