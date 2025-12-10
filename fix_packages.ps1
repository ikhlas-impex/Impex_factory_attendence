# PowerShell script to fix NumPy/OpenCV compatibility issues
Write-Host "🔧 Fixing package installation issues..." -ForegroundColor Cyan
Write-Host "=" * 60

# Step 1: Uninstall conflicting packages
Write-Host "`n📦 Step 1: Removing conflicting packages..." -ForegroundColor Yellow
$packages = @('opencv-python', 'opencv-python-headless', 'numpy')
foreach ($package in $packages) {
    Write-Host "   Removing $package..." -ForegroundColor Gray
    python -m pip uninstall -y $package 2>&1 | Out-Null
}

# Step 2: Install NumPy 1.x
Write-Host "`n📦 Step 2: Installing NumPy 1.x (compatible version)..." -ForegroundColor Yellow
python -m pip install "numpy<2.0,>=1.24.0" --force-reinstall
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ❌ Failed to install NumPy" -ForegroundColor Red
    exit 1
}
Write-Host "   ✓ NumPy installed successfully" -ForegroundColor Green

# Step 3: Install OpenCV packages
Write-Host "`n📦 Step 3: Installing OpenCV packages..." -ForegroundColor Yellow
python -m pip install "opencv-python>=4.8.0,<5.0.0" "opencv-python-headless>=4.9.0.80" --force-reinstall
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ❌ Failed to install OpenCV packages" -ForegroundColor Red
    exit 1
}
Write-Host "   ✓ OpenCV packages installed successfully" -ForegroundColor Green

# Step 4: Install remaining requirements
Write-Host "`n📦 Step 4: Installing remaining requirements..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    python -m pip install -r requirements.txt --upgrade
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ⚠️ Some packages may have failed to install" -ForegroundColor Yellow
    } else {
        Write-Host "   ✓ All requirements installed successfully" -ForegroundColor Green
    }
} else {
    Write-Host "   ⚠️ requirements.txt not found" -ForegroundColor Yellow
}

# Step 5: Verify installation
Write-Host "`n🔍 Step 5: Verifying installation..." -ForegroundColor Yellow
try {
    $numpyVersion = python -c "import numpy; print(numpy.__version__)" 2>&1
    $cv2Version = python -c "import cv2; print(cv2.__version__)" 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✓ NumPy version: $numpyVersion" -ForegroundColor Green
        Write-Host "   ✓ OpenCV version: $cv2Version" -ForegroundColor Green
        Write-Host "   ✓ Import test passed" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Import verification failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   ❌ Error during verification: $_" -ForegroundColor Red
    exit 1
}

# Step 6: Check for dependency conflicts
Write-Host "`n🔍 Step 6: Checking for dependency conflicts..." -ForegroundColor Yellow
python -m pip check
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ No dependency conflicts detected" -ForegroundColor Green
} else {
    Write-Host "   ⚠️ Some dependency conflicts detected (see above)" -ForegroundColor Yellow
}

Write-Host "`n" + ("=" * 60)
Write-Host "✅ Package installation fix completed successfully!" -ForegroundColor Green
Write-Host "=" * 60

