# Critical Fixes Needed for Staff Recognition (ID 4730)

## Issues Found in Logs:

1. **"Error loading staff 4237: buffer size must be a multiple of element size"**
   - Staff embeddings are not loading correctly
   - Results in: "✅ Loaded 26 customers and 0 staff members"

2. **"Refresh cards error: 'ImpexAttendanceDashboard' object has no attribute 'employee_id_map'"**
   - employee_id_map is not initialized properly

3. **Staff 4730 not detected**
   - Because no staff members are loading from database

## Fixes Required:

### Fix 1: Staff Embedding Loading (src/core/face_engine.py)
Location: Lines 86-98

**CURRENT (WRONG):**
```python
embedding = np.frombuffer(staff['embedding'], dtype=np.float32)
```

**SHOULD BE:**
```python
# Try pickle first (embeddings stored with pickle.dumps)
try:
    embedding = pickle.loads(staff['embedding'])
    if isinstance(embedding, np.ndarray):
        if np.linalg.norm(embedding) > 0:
            embedding = embedding / np.linalg.norm(embedding)
        self.staff_database[staff['staff_id']] = embedding
        loaded_staff += 1
        continue
except:
    pass

# Fallback to frombuffer
try:
    embedding = np.frombuffer(staff['embedding'], dtype=np.float32)
    if embedding.size > 0:
        if np.linalg.norm(embedding) > 0:
            embedding = embedding / np.linalg.norm(embedding)
        self.staff_database[staff['staff_id']] = embedding
        loaded_staff += 1
except Exception as e2:
    print(f"Error loading staff {staff['staff_id']}: {e2}")
```

### Fix 2: Initialize employee_id_map Early (src/ui/attendance_dashboard.py)
Location: In `__init__` method, after line 54

**ADD:**
```python
# Employee ID mapping - initialized early
self.employee_id_map = {}
```

### Fix 3: Load Employee IDs from Database
Add this method after `get_employee_id`:

```python
def load_employee_ids(self):
    """Load employee IDs from database"""
    try:
        all_staff = self.db_manager.get_all_staff()
        for staff in all_staff:
            staff_id = staff['staff_id']
            employee_id = staff.get('employee_id')
            if employee_id:
                self.employee_id_map[staff_id] = str(employee_id)
            else:
                # Use staff_id as fallback
                self.employee_id_map[staff_id] = staff_id.replace('STAFF_', '')
        print(f"✅ Loaded {len(self.employee_id_map)} employee IDs")
    except Exception as e:
        print(f"Error loading employee IDs: {e}")
```

**CALL IT** in `__init__` after `load_today_attendance()`:
```python
# Load employee IDs from database
self.load_employee_ids()
```

## Summary:

After these fixes:
- Staff embeddings will load correctly (using pickle)
- Staff 4730 should be recognized
- employee_id_map will be populated from database
- No more "0 staff members" error

**PLEASE RESTORE YOUR attendance_dashboard.py FILE FIRST**, then I can apply these fixes properly!

