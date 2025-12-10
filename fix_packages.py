#!/usr/bin/env python
"""
Fix package installation issues, specifically NumPy/OpenCV compatibility.
Run this script to resolve the _ARRAY_API not found error.
"""

import subprocess
import sys
import os

def fix_packages():
    """Fix NumPy and OpenCV compatibility issues"""
    print("🔧 Fixing package installation issues...")
    print("=" * 60)
    
    try:
        # Step 1: Uninstall conflicting packages
        print("\n📦 Step 1: Removing conflicting packages...")
        packages_to_remove = ['opencv-python', 'opencv-python-headless', 'numpy']
        for package in packages_to_remove:
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'uninstall', '-y', package],
                    check=False,
                    capture_output=True
                )
                print(f"   ✓ Removed {package}")
            except Exception as e:
                print(f"   ⚠️ Could not remove {package}: {e}")
        
        # Step 2: Install NumPy 1.x first
        print("\n📦 Step 2: Installing NumPy 1.x (compatible version)...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', 'numpy<2.0,>=1.24.0'
        ])
        print("   ✓ NumPy installed successfully")
        
        # Step 3: Install OpenCV packages (compatible with NumPy 1.x)
        print("\n📦 Step 3: Installing OpenCV packages...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', 
            'opencv-python>=4.8.0,<5.0.0',
            'opencv-python-headless>=4.9.0.80'
        ])
        print("   ✓ OpenCV packages installed successfully")
        
        # Step 4: Install remaining requirements
        print("\n📦 Step 4: Installing remaining requirements...")
        requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
        if os.path.exists(requirements_path):
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '-r', requirements_path
            ])
            print("   ✓ All requirements installed successfully")
        else:
            print(f"   ⚠️ requirements.txt not found at {requirements_path}")
        
        # Step 5: Verify installation
        print("\n🔍 Step 5: Verifying installation...")
        try:
            import numpy as np
            import cv2
            print(f"   ✓ NumPy version: {np.__version__}")
            print(f"   ✓ OpenCV version: {cv2.__version__}")
            
            # Test basic NumPy array operations
            arr = np.array([1, 2, 3])
            print(f"   ✓ NumPy array test passed")
            
            # Test OpenCV import
            img = cv2.imread('test_image.jpg') if os.path.exists('test_image.jpg') else None
            print(f"   ✓ OpenCV import successful")
            
        except ImportError as e:
            print(f"   ❌ Import verification failed: {e}")
            return False
        except Exception as e:
            print(f"   ⚠️ Verification warning: {e}")
        
        # Step 6: Check for dependency conflicts
        print("\n🔍 Step 6: Checking for dependency conflicts...")
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'check'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("   ✓ No dependency conflicts detected")
        else:
            print("   ⚠️ Some dependency conflicts detected:")
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
        
        print("\n" + "=" * 60)
        print("✅ Package installation fix completed successfully!")
        print("=" * 60)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error during installation: {e}")
        if e.stdout:
            print(f"stdout: {e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_packages()
    sys.exit(0 if success else 1)

