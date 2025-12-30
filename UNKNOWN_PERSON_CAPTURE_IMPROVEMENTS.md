# Unknown Person Capture Efficiency Improvements

## Overview
This document describes the improvements made to enhance the efficiency of capturing unknown people who pass while the camera is on, while ensuring proper staff verification.

## Key Improvements

### 1. Enhanced Staff Verification
- **Location**: `src/core/face_engine.py` - `identify_person()` method
- **Changes**:
  - Lowered staff recognition threshold from 0.65 to 0.60 to catch more staff members while maintaining accuracy
  - Added additional verification to ensure staff_id exists in database before returning staff match
  - Improved error handling and logging
  - Staff checking is done FIRST before marking anyone as unknown

- **Location**: `src/ui/attendance_dashboard.py` - `process_video()` method
- **Changes**:
  - Added double-check verification: after `identify_person()` returns staff, we verify the staff_id exists in database
  - Only marks person as unknown if they are NOT confirmed staff
  - Enhanced logging to show when staff is confirmed

### 2. Improved Unknown Person Capture Efficiency
- **Location**: `src/ui/attendance_dashboard.py` - `process_video()` method
- **Changes**:
  - **Immediate Capture**: Unknown persons are now captured immediately when detected, not just on entry/exit
  - **Continuous Capture**: If an unknown person stays in frame, they are captured again every 2 seconds (configurable via `UNKNOWN_CAPTURE_INTERVAL`)
  - **Better Tracking**: Improved tracking system to avoid duplicate captures while ensuring all unique persons are captured
  - **Enhanced Logging**: Better console output showing when unknown persons are detected and captured

### 3. Reduced Frame Skipping
- **Location**: `src/ui/attendance_dashboard.py` - `process_video()` method
- **Changes**:
  - Reduced `FRAME_SKIP_INTERVAL` from 3 to 2 (process every 2nd frame instead of every 3rd)
  - Reduced `MIN_PROCESS_INTERVAL` from 0.1s to 0.05s (20 FPS max detection rate instead of 10 FPS)
  - This allows the system to detect and capture unknown persons more frequently

### 4. Enhanced Unknown Entry Processing
- **Location**: `src/ui/attendance_dashboard.py` - `process_unknown_entries()` method
- **Changes**:
  - Better reason determination based on detection confidence and person type
  - Distinguishes between customers and truly unknown persons
  - More detailed logging for debugging

## Technical Details

### Staff Verification Flow
1. Face is detected in frame
2. Embedding is extracted
3. `identify_person()` is called:
   - First checks staff database (priority)
   - If staff match found with confidence >= 0.60, returns staff
   - Then checks customer database
   - If no match, returns unknown
4. Additional verification in `process_video()`:
   - If staff match found, verify staff_id exists in database
   - Only mark as unknown if NOT confirmed staff

### Unknown Person Capture Flow
1. Person detected in frame
2. Staff verification performed (as above)
3. If NOT confirmed staff:
   - Check if this is first time seeing this person (new entry)
   - OR check if enough time has passed since last capture (2 seconds)
   - If either condition true, capture immediately
   - Save to database with full body image
   - Show on screen for 3 seconds

### Configuration Parameters
- `FRAME_SKIP_INTERVAL = 2`: Process every 2nd frame
- `MIN_PROCESS_INTERVAL = 0.05`: Minimum 0.05s between detections (20 FPS max)
- `UNKNOWN_CAPTURE_INTERVAL = 2.0`: Capture same unknown person every 2 seconds if still in frame
- Staff recognition threshold: 0.60 (in face_engine.py)

## Benefits

1. **Better Coverage**: Every unknown person who passes is captured, not just on entry/exit
2. **Accurate Staff Detection**: Enhanced verification ensures staff members are properly recognized before marking as unknown
3. **Reduced Misses**: Lower frame skipping means more opportunities to detect and capture
4. **Continuous Monitoring**: Unknown persons are captured repeatedly if they stay in frame, ensuring no one is missed
5. **Better Logging**: Enhanced console output helps with debugging and monitoring

## Database Storage

All unknown person captures are stored in the `unknown_entries` table with:
- Track ID (unique identifier for the person)
- Entry type (unknown_person, customer, covered_face, no_face)
- Full body image
- Face bounding box
- Person bounding box
- Detection confidence
- Recognition confidence
- Reason for unknown entry
- System mode (checkin/checkout)
- Timestamp

## Testing Recommendations

1. Test with known staff members - should NOT be captured as unknown
2. Test with unknown persons - should be captured immediately when detected
3. Test with persons staying in frame - should be captured every 2 seconds
4. Test with multiple unknown persons - all should be captured
5. Monitor console output for detection and capture logs

## Future Enhancements

Potential improvements for future consideration:
- Configurable capture intervals via settings file
- Face quality filtering to avoid capturing very blurry faces
- Automatic cleanup of old unknown entries
- Dashboard to view and manage unknown entries
- Option to manually mark unknown entries as staff members

