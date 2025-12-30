# Unknown Entry Capture Fixes

## Issues Fixed

### 1. Quality Checks Blocking Unknown Person Detection
**Problem**: Unknown persons moving through the camera were not being captured because strict quality checks (blur/brightness) were filtering out frames before face detection could occur.

**Solution**:
- Added dual quality check system: `strict=True` for staff recognition, `strict=False` for unknown detection
- **Strict mode** (staff recognition):
  - Brightness threshold: 30 (unchanged)
  - Blur threshold: 50 (unchanged)
- **Lenient mode** (unknown detection):
  - Brightness threshold: 15 (reduced from 30) - allows darker frames
  - Blur threshold: 20 (reduced from 50) - allows blurrier frames
- Both quality checks are evaluated, and frames that pass lenient checks are processed for unknown detection even if they fail strict checks

### 2. Unknown Entries Not Showing in Dashboard
**Problem**: The JavaScript was deduplicating entries by `track_id`, showing only the latest entry per track. This meant if the same person was captured multiple times, only one entry was visible.

**Solution**:
- Removed aggressive deduplication in `static/js/admin.js`
- Now shows ALL unknown entries, sorted by detection time (most recent first)
- This ensures every capture of an unknown person is visible in the dashboard

## Code Changes

### File: `src/ui/attendance_dashboard.py`

1. **Enhanced `_is_good_frame()` method**:
   ```python
   def _is_good_frame(self, frame, strict=True):
       # strict=True: For staff recognition (needs good quality)
       # strict=False: For unknown detection (more lenient)
   ```

2. **Dual quality processing**:
   - `is_good_quality`: Strict check for staff recognition
   - `is_acceptable_quality`: Lenient check for unknown detection
   - Both checks run, and frames passing either check are processed

3. **Improved unknown detection**:
   - Unknown persons are detected even on lenient quality frames
   - Lower confidence threshold (0.50) used for staff verification on lenient frames
   - Better logging to track when lenient quality frames are processed

### File: `static/js/admin.js`

1. **Removed deduplication**:
   - Changed from showing only latest entry per track_id
   - Now shows all entries sorted by detection time
   - Ensures all unknown person captures are visible

## How It Works Now

1. **Frame Processing**:
   - Every frame is checked with both strict and lenient quality criteria
   - Frames passing strict checks: Processed normally (staff + unknown detection)
   - Frames passing only lenient checks: Processed for unknown detection only
   - This ensures moving/blurry unknown persons are still captured

2. **Unknown Person Detection**:
   - Face detection runs on all acceptable quality frames
   - Staff verification happens first (with appropriate threshold based on quality)
   - If not confirmed staff → marked as unknown and captured
   - Captured immediately when detected (not waiting for entry/exit)

3. **Dashboard Display**:
   - All unknown entries are loaded from database
   - Sorted by detection time (most recent first)
   - All entries visible (no deduplication)
   - Can filter by type, status, date, etc.

## Benefits

1. **Better Coverage**: Unknown persons are captured even when moving quickly or in poor lighting
2. **No Misses**: Lenient quality checks ensure we don't miss unknown persons due to blur/brightness
3. **Complete Visibility**: All unknown entries are visible in dashboard (not just one per track)
4. **Better Tracking**: Can see all captures of the same person, not just the latest

## Testing

To verify the fixes work:

1. **Test with moving person**:
   - Have someone walk quickly past the camera
   - Should see multiple captures in unknown entries dashboard
   - All captures should be visible (not deduplicated)

2. **Test with poor lighting**:
   - Test in dim lighting conditions
   - Unknown persons should still be captured (lenient quality check)

3. **Test with blurry frames**:
   - Test with person moving quickly (causes motion blur)
   - Should still capture unknown persons

4. **Check dashboard**:
   - Go to Admin Panel → Unknown Entries tab
   - Should see all unknown entries, not just one per track_id
   - Entries should be sorted by time (most recent first)

## Configuration

Quality thresholds can be adjusted in `_is_good_frame()`:
- **Strict mode** (staff): `brightness >= 30`, `blur >= 50`
- **Lenient mode** (unknown): `brightness >= 15`, `blur >= 20`

Lower thresholds = more captures but potentially lower quality images.





