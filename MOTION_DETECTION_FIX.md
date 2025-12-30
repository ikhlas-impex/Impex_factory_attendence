# Motion Detection for Fast-Moving Unknown Persons

## Problem Solved

When an unknown person walks fast through the camera:
- The tracker loses them because they move too quickly
- Face detection fails or is too slow
- They are not recognized and not shown in unknown entries
- Even when they're not showing (not in frame), the image is not captured

## Solution Implemented

Added **motion detection** to catch fast-moving persons even when face detection fails or tracker loses them.

### Key Features

1. **Motion Detection Using Background Subtraction**
   - Uses MOG2 (Mixture of Gaussians) background subtractor
   - Detects moving objects (persons) even when face detection fails
   - Runs on every 5th frame to balance performance and detection

2. **Smart Person Detection**
   - Filters by size (person-sized objects: 1-50% of frame area)
   - Minimum size: 50x100 pixels (ensures it's a person, not noise)
   - Skips objects that are already detected by face detection

3. **Staff Verification**
   - Even for motion detections, tries to detect face in the motion region
   - If face found, attempts to identify if person is staff
   - Only captures as unknown if NOT confirmed as staff
   - Uses lower confidence threshold (0.50) for motion-based detections

4. **Complete Capture**
   - Captures full body image (motion detection provides full body bbox)
   - Saves to unknown entries database
   - Appears in unknown entries dashboard
   - Entry type: `no_face` (if no face detected) or `unknown_person` (if face found but not staff)

## How It Works

1. **Motion Detection Process**:
   ```
   Frame → Background Subtraction → Contour Detection → 
   Size Filtering → Staff Check → Unknown Entry Capture
   ```

2. **Detection Flow**:
   - Motion detected (person moving)
   - Check if already handled by face detection (skip if yes)
   - Try face detection in motion region (might be blurry)
   - If face found: try to identify as staff
   - If NOT staff: capture as unknown entry
   - Save full body image to database

3. **Entry Types**:
   - `no_face`: Fast-moving person, no face detected
   - `unknown_person`: Fast-moving person, face found but not recognized as staff

## Code Changes

### File: `src/ui/attendance_dashboard.py`

1. **Initialization** (lines 77-82):
   - Added motion detection variables
   - `motion_detection_enabled = True`
   - `background_subtractor = None` (initialized in `start_recognition`)

2. **Motion Detection Initialization** (lines 416-427):
   - Initializes MOG2 background subtractor when recognition starts
   - Handles initialization errors gracefully

3. **Motion Detection Method** (lines 925-1055):
   - `detect_and_capture_motion()`: Main motion detection logic
   - Detects moving objects, filters by size, checks for staff, captures unknown

4. **Motion Detection Call** (lines 819-822):
   - Called every 5 frames during video processing
   - Runs alongside face detection to catch fast-moving persons

5. **Enhanced `process_unknown_entries()`** (lines 1063-1181):
   - Handles both face-based and motion-based detections
   - Properly processes motion detections with full body bbox
   - Sets appropriate entry type and reason

## Configuration

- **Motion Capture Interval**: 1.0 second (capture same motion every 1 second)
- **Motion Detection Frequency**: Every 5 frames
- **Minimum Person Size**: 50x100 pixels
- **Area Filter**: 1-50% of frame area
- **Staff Confidence Threshold**: 0.50 (for motion detections)

## Benefits

1. **Catches Fast-Moving Persons**: Even when face detection fails
2. **No Misses**: Motion detection works independently of face detection
3. **Staff Verification**: Still checks if person is staff before marking as unknown
4. **Complete Images**: Captures full body, not just face
5. **Dashboard Visibility**: All captures appear in unknown entries dashboard

## Testing

To verify it works:

1. **Fast Movement Test**:
   - Have someone walk quickly past camera
   - Should see motion-based unknown entries in dashboard
   - Entry type should be `no_face` or `unknown_person`

2. **Check Dashboard**:
   - Go to Admin Panel → Unknown Entries
   - Should see entries with reason: "Fast-moving person detected (motion-based)..."
   - Images should show full body

3. **Staff Verification**:
   - Fast-moving staff should NOT appear in unknown entries
   - System still verifies if person is staff

## Console Output

You should see messages like:
```
🏃 Motion detected (no face/fast-moving): motion_id=12345, has_face=False, person_type=unknown, conf=0.00
📸 Capturing 1 motion-based unknown entry/entries...
💾 Attempting to record unknown entry: Track ID 12345, Type: no_face, Motion: True
✅ Unknown entry SUCCESSFULLY recorded in database: Entry ID 123, Track ID 12345, Type: no_face
```

## Notes

- Motion detection runs every 5 frames to balance performance
- Only captures if person is NOT confirmed as staff
- Full body images are captured (not just face region)
- All entries appear in unknown entries dashboard
- Motion detection is independent of face detection tracking





