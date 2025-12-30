// Admin Panel JavaScript

let currentTab = 'dashboard';
let staffList = [];
let attendanceList = [];
let realtimeInterval = null;

// Initialize admin panel
document.addEventListener('DOMContentLoaded', function() {
    initAdmin();
});

function initAdmin() {
    updateDateTime();
    setInterval(updateDateTime, 1000);
    
    // Setup tab navigation
    setupTabs();
    
    // Load initial data
    loadDashboardStats();
    loadStaffList();
    loadAttendance();
    loadCameraConfig();
    startRealtimeUpdates();
    
    // Initialize date pickers
    const attendanceDate = document.getElementById('attendanceDate');
    const unknownEntriesDate = document.getElementById('unknownEntriesDate');
    if (attendanceDate && !attendanceDate.value) {
        attendanceDate.value = new Date().toISOString().split('T')[0];
    }
    if (unknownEntriesDate && !unknownEntriesDate.value) {
        unknownEntriesDate.value = new Date().toISOString().split('T')[0];
    }
    
    // Setup form handlers
    setupFormHandlers();
}

// Date and Time
function updateDateTime() {
    const now = new Date();
    const dateStr = now.toLocaleDateString('en-GB', { 
        day: '2-digit', 
        month: '2-digit', 
        year: 'numeric' 
    }).replace(/\//g, '.');
    const timeStr = now.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit',
        hour12: true 
    });
    
    const dateEl = document.getElementById('currentDate');
    const timeEl = document.getElementById('currentTime');
    if (dateEl) dateEl.textContent = dateStr;
    if (timeEl) timeEl.textContent = timeStr;
}

// Tab Navigation
function setupTabs() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    currentTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`tab-${tabName}`).classList.add('active');
    
    // Load tab-specific data
    if (tabName === 'dashboard') {
        loadDashboardStats();
    } else if (tabName === 'staff') {
        loadStaffList();
    } else if (tabName === 'attendance') {
        loadAttendance();
    } else if (tabName === 'realtime') {
        startRealtimeUpdates();
    } else if (tabName === 'unknown') {
        loadUnknownEntries();
        loadUnknownEntriesStats();
    }
}

// Dashboard Stats
async function loadDashboardStats() {
    try {
        const response = await fetch('/api/admin/statistics/dashboard');
        const data = await response.json();
        
        if (data.success) {
            const stats = data.stats;
            document.getElementById('stat-total-staff').textContent = stats.total_staff;
            document.getElementById('stat-present').textContent = stats.present_today;
            document.getElementById('stat-absent').textContent = stats.absent_today;
            document.getElementById('stat-checked-out').textContent = stats.checked_out_today;
            document.getElementById('stat-late').textContent = stats.late_today;
            document.getElementById('stat-rate').textContent = stats.attendance_rate.toFixed(1) + '%';
            
            // Update weekly chart if needed
            updateWeeklyChart(stats.week_attendance);
        }
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
    }
}

function updateWeeklyChart(weekData) {
    // Simple chart implementation (can be enhanced with Chart.js)
    const canvas = document.getElementById('weeklyChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.offsetWidth;
    const height = canvas.height = 200;
    
    ctx.clearRect(0, 0, width, height);
    
    if (weekData && weekData.length > 0) {
        const maxValue = Math.max(...weekData.map(d => d.present), 1);
        const barWidth = width / weekData.length - 10;
        const barSpacing = 10;
        
        weekData.forEach((day, index) => {
            const barHeight = (day.present / maxValue) * (height - 40);
            const x = index * (barWidth + barSpacing) + 5;
            const y = height - barHeight - 20;
            
            ctx.fillStyle = '#667eea';
            ctx.fillRect(x, y, barWidth, barHeight);
            
            ctx.fillStyle = '#333';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(day.present, x + barWidth / 2, y - 5);
        });
    }
}

// Staff Management
async function loadStaffList() {
    try {
        const response = await fetch('/api/admin/staff/all');
        const data = await response.json();
        
        if (data.success) {
            staffList = data.staff;
            renderStaffTable(staffList);
        }
    } catch (error) {
        console.error('Error loading staff list:', error);
    }
}

function renderStaffTable(staff) {
    const tbody = document.getElementById('staffTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    staff.forEach(member => {
        const row = document.createElement('tr');
        
        const photoUrl = `/api/admin/staff/${member.staff_id}/photo`;
        const statusClass = member.today_status === 'Present' ? 'present' : 
                          member.today_status === 'Late' ? 'late' : 'absent';
        
        row.innerHTML = `
            <td><img src="${photoUrl}" alt="${member.name}" class="staff-photo" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27200%27 height=%27200%27%3E%3Crect fill=%27%23ddd%27 width=%27200%27 height=%27200%27/%3E%3Ctext fill=%27%23999%27 font-family=%27sans-serif%27 font-size=%2730%27 dy=%2710.5%27 font-weight=%27bold%27 x=%2750%25%27 y=%2750%25%27 text-anchor=%27middle%27%3ENo Photo%3C/text%3E%3C/svg%3E'"></td>
            <td>${member.employee_id || member.staff_id}</td>
            <td>${member.name}</td>
            <td>${member.department || '-'}</td>
            <td><span class="status-badge ${statusClass}">${member.today_status}</span></td>
            <td>${member.today_check_in ? new Date(member.today_check_in).toLocaleTimeString() : '-'}</td>
            <td>${member.today_check_out ? new Date(member.today_check_out).toLocaleTimeString() : '-'}</td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="editStaff('${member.staff_id}')">✏️ Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deleteStaff('${member.staff_id}')">🗑️ Delete</button>
            </td>
        `;
        
        tbody.appendChild(row);
    });
}

function openAddStaffModal() {
    document.getElementById('modalTitle').textContent = 'Add Staff Member';
    document.getElementById('staffForm').reset();
    document.getElementById('editStaffId').value = '';
    document.getElementById('staffId').disabled = false;
    document.getElementById('photoPreview').innerHTML = '<span>Click to upload photo or capture from camera</span>';
    document.getElementById('showcasePhotoPreview').innerHTML = '<span>Click to upload showcase photo</span>';
    document.getElementById('staffModal').style.display = 'block';
}

function closeStaffModal() {
    document.getElementById('staffModal').style.display = 'none';
}

async function editStaff(staffId) {
    const staff = staffList.find(s => s.staff_id === staffId);
    if (!staff) return;
    
    document.getElementById('modalTitle').textContent = 'Edit Staff Member';
    document.getElementById('editStaffId').value = staff.staff_id;
    document.getElementById('staffId').value = staff.staff_id;
    document.getElementById('staffId').disabled = true;
    document.getElementById('staffName').value = staff.name;
    document.getElementById('staffDepartment').value = staff.department || '';
    
    // Load photo
    const photoUrl = `/api/admin/staff/${staff.staff_id}/photo`;
    document.getElementById('photoPreview').innerHTML = `<img src="${photoUrl}" alt="Staff Photo" style="width: 100%; height: 100%; object-fit: cover;">`;
    
    // Load showcase photo
    const showcasePhotoUrl = `/api/admin/staff/${staff.staff_id}/showcase-photo`;
    const showcasePreview = document.getElementById('showcasePhotoPreview');
    showcasePreview.innerHTML = `<img src="${showcasePhotoUrl}" alt="Showcase Photo" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.parentElement.innerHTML='<span>Click to upload showcase photo</span>'">`;
    
    document.getElementById('staffModal').style.display = 'block';
}

function previewPhoto(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('photoPreview');
            preview.innerHTML = `<img src="${e.target.result}" alt="Preview" style="width: 100%; height: 100%; object-fit: cover;">`;
        };
        reader.readAsDataURL(file);
    }
}

function previewShowcasePhoto(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('showcasePhotoPreview');
            preview.innerHTML = `<img src="${e.target.result}" alt="Showcase Preview" style="width: 100%; height: 100%; object-fit: cover;">`;
        };
        reader.readAsDataURL(file);
    }
}

function clearShowcasePhoto() {
    const preview = document.getElementById('showcasePhotoPreview');
    preview.innerHTML = '<span>Click to upload showcase photo</span>';
    document.getElementById('staffShowcasePhoto').value = '';
}

function setupFormHandlers() {
    const staffForm = document.getElementById('staffForm');
    if (staffForm) {
        staffForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            await saveStaff();
        });
    }
}

async function saveStaff() {
    try {
        const formData = {
            staff_id: document.getElementById('staffId').value.trim(),
            name: document.getElementById('staffName').value.trim(),
            department: document.getElementById('staffDepartment').value.trim(),
        };
        
        // Check if multiple photos were captured from camera
        const photoPreview = document.getElementById('photoPreview');
        const capturedPhotosData = photoPreview.dataset.capturedPhotos;
        const photoImg = photoPreview.querySelector('img');
        const photoFile = document.getElementById('staffPhoto').files[0];
        
        // Get showcase photo
        const showcasePhotoFile = document.getElementById('staffShowcasePhoto').files[0];
        const showcasePhotoPreview = document.getElementById('showcasePhotoPreview');
        const showcasePhotoImg = showcasePhotoPreview.querySelector('img');
        
        if (showcasePhotoFile) {
            const reader = new FileReader();
            reader.onload = async function(e) {
                formData.showcase_photo = e.target.result;
                await processMainPhoto(formData);
            };
            reader.readAsDataURL(showcasePhotoFile);
            return;
        } else if (showcasePhotoImg && showcasePhotoImg.src && !showcasePhotoImg.src.includes('/api/admin/staff/')) {
            // Showcase photo was already loaded from file (not from server)
            formData.showcase_photo = showcasePhotoImg.src;
        }
        
        await processMainPhoto(formData);
    } catch (error) {
        console.error('Error saving staff:', error);
        alert('Error saving staff: ' + error.message);
    }
}

async function processMainPhoto(formData) {
    try {
        // Check if multiple photos were captured from camera
        const photoPreview = document.getElementById('photoPreview');
        const capturedPhotosData = photoPreview.dataset.capturedPhotos;
        const photoImg = photoPreview.querySelector('img');
        const photoFile = document.getElementById('staffPhoto').files[0];
        
        // Get photos from captured images or file
        if (capturedPhotosData) {
            // Multiple photos were captured from camera
            try {
                const photos = JSON.parse(capturedPhotosData);
                if (photos && photos.length >= 3) {
                    formData.photos = photos; // Send array of photos
                    await submitStaffForm(formData);
                    return;
                }
            } catch (e) {
                console.error('Error parsing captured photos:', e);
            }
        }
        
        if (photoImg && photoImg.src && photoImg.src.startsWith('data:image')) {
            // Single photo was captured from camera
            formData.photo = photoImg.src;
        } else if (photoFile) {
            // Photo was uploaded from file
            const reader = new FileReader();
            reader.onload = async function(e) {
                formData.photo = e.target.result;
                await submitStaffForm(formData);
            };
            reader.readAsDataURL(photoFile);
            return;
        } else if (!document.getElementById('editStaffId').value) {
            alert('Please capture or upload a photo');
            return;
        }
        
        await submitStaffForm(formData);
    } catch (error) {
        console.error('Error saving staff:', error);
        alert('Error saving staff: ' + error.message);
    }
}

async function submitStaffForm(formData) {
    try {
        const editId = document.getElementById('editStaffId').value;
        const url = editId ? '/api/admin/staff/update' : '/api/admin/staff/add';
        
        if (editId) {
            formData.staff_id = editId;
        }
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            // If showcase photo was provided, update it separately
            if (formData.showcase_photo && editId) {
                await updateShowcasePhoto(editId, formData.showcase_photo);
            }
            
            alert(data.message || 'Staff saved successfully');
            closeStaffModal();
            loadStaffList();
            loadDashboardStats();
        } else {
            alert('Error: ' + (data.error || 'Failed to save staff'));
        }
    } catch (error) {
        console.error('Error submitting staff form:', error);
        alert('Error: ' + error.message);
    }
}

async function updateShowcasePhoto(staffId, photoData) {
    try {
        const response = await fetch(`/api/admin/staff/${staffId}/showcase-photo`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ photo: photoData })
        });
        
        const data = await response.json();
        if (!data.success) {
            console.error('Failed to update showcase photo:', data.error);
        }
    } catch (error) {
        console.error('Error updating showcase photo:', error);
    }
}

async function deleteStaff(staffId) {
    if (!confirm('Are you sure you want to delete this staff member?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/admin/staff/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ staff_id: staffId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Staff member deleted successfully');
            loadStaffList();
            loadDashboardStats();
        } else {
            alert('Error: ' + (data.error || 'Failed to delete staff'));
        }
    } catch (error) {
        console.error('Error deleting staff:', error);
        alert('Error: ' + error.message);
    }
}

// Attendance Management
async function loadAttendance() {
    try {
        const dateInput = document.getElementById('attendanceDate');
        const date = dateInput ? dateInput.value : new Date().toISOString().split('T')[0];
        
        if (!dateInput) {
            const today = new Date().toISOString().split('T')[0];
            if (dateInput) dateInput.value = today;
        }
        
        const response = await fetch(`/api/admin/attendance/today?date=${date}`);
        const data = await response.json();
        
        if (data.success) {
            attendanceList = data.attendance;
            renderAttendanceTable(attendanceList);
        }
    } catch (error) {
        console.error('Error loading attendance:', error);
    }
}

function renderAttendanceTable(attendance) {
    const tbody = document.getElementById('attendanceTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (attendance.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">No attendance records for this date</td></tr>';
        return;
    }
    
    attendance.forEach(record => {
        const row = document.createElement('tr');
        const statusClass = record.status === 'Present' ? 'present' : 
                          record.status === 'Late' ? 'late' : 'absent';
        
        row.innerHTML = `
            <td>${record.employee_id || record.staff_id}</td>
            <td>${record.name}</td>
            <td>${record.department || '-'}</td>
            <td>${record.check_in_time ? new Date(record.check_in_time).toLocaleTimeString() : '-'}</td>
            <td>${record.check_out_time ? new Date(record.check_out_time).toLocaleTimeString() : '-'}</td>
            <td><span class="status-badge ${statusClass}">${record.status}</span></td>
            <td>${(record.confidence * 100).toFixed(1)}%</td>
        `;
        
        tbody.appendChild(row);
    });
}

function filterAttendance() {
    const search = document.getElementById('attendanceSearch').value.toLowerCase();
    const filter = document.getElementById('attendanceFilter').value;
    
    let filtered = attendanceList.filter(record => {
        const matchSearch = !search || 
            record.name.toLowerCase().includes(search) ||
            (record.employee_id && record.employee_id.toLowerCase().includes(search));
        
        const matchFilter = filter === 'all' || 
            (filter === 'present' && record.status === 'Present') ||
            (filter === 'absent' && record.status === 'Absent') ||
            (filter === 'late' && record.status === 'Late');
        
        return matchSearch && matchFilter;
    });
    
    renderAttendanceTable(filtered);
}

async function exportAttendance() {
    try {
        const dateInput = document.getElementById('attendanceDate');
        const date = dateInput ? dateInput.value : new Date().toISOString().split('T')[0];
        
        const url = `/api/admin/attendance/export?start_date=${date}&end_date=${date}`;
        window.open(url, '_blank');
    } catch (error) {
        console.error('Error exporting attendance:', error);
        alert('Error exporting attendance');
    }
}

// Camera Configuration
async function loadCameraConfig() {
    try {
        const response = await fetch('/api/admin/camera/config');
        const data = await response.json();
        
        if (data.success && data.config) {
            const config = data.config;
            document.getElementById('cameraSourceType').value = config.source_type || 'usb';
            document.getElementById('usbIndex').value = config.usb_index || 0;
            document.getElementById('rtspUrl').value = config.rtsp_url || '';
            document.getElementById('cameraResolution').value = config.resolution || '1920x1080';
            document.getElementById('cameraFPS').value = config.fps || 30;
            document.getElementById('cameraBuffer').value = config.buffer_size || 1;
            document.getElementById('cameraTransport').value = config.transport || 'TCP';
            
            toggleCameraFields();
        }
    } catch (error) {
        console.error('Error loading camera config:', error);
    }
}

function toggleCameraFields() {
    const sourceType = document.getElementById('cameraSourceType').value;
    const usbFields = document.getElementById('usbCameraFields');
    const rtspFields = document.getElementById('rtspCameraFields');
    
    if (sourceType === 'usb') {
        usbFields.style.display = 'block';
        rtspFields.style.display = 'none';
    } else {
        usbFields.style.display = 'none';
        rtspFields.style.display = 'block';
    }
}

async function saveCameraConfig() {
    try {
        const sourceType = document.getElementById('cameraSourceType').value;
        const config = {
            source_type: sourceType,
            resolution: document.getElementById('cameraResolution').value,
            fps: parseInt(document.getElementById('cameraFPS').value),
            buffer_size: parseInt(document.getElementById('cameraBuffer').value),
            transport: document.getElementById('cameraTransport').value
        };
        
        if (sourceType === 'usb') {
            config.usb_index = parseInt(document.getElementById('usbIndex').value);
        } else {
            config.rtsp_url = document.getElementById('rtspUrl').value;
        }
        
        const response = await fetch('/api/admin/camera/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Camera configuration saved successfully');
        } else {
            alert('Error: ' + (data.error || 'Failed to save configuration'));
        }
    } catch (error) {
        console.error('Error saving camera config:', error);
        alert('Error: ' + error.message);
    }
}

async function testCamera() {
    try {
        const sourceType = document.getElementById('cameraSourceType').value;
        const cameraSource = sourceType === 'usb' ? 
            document.getElementById('usbIndex').value : 
            document.getElementById('rtspUrl').value;
        
        const response = await fetch('/api/admin/camera/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                source_type: sourceType,
                camera_source: cameraSource
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Camera connection test successful!');
        } else {
            alert('Camera connection test failed: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error testing camera:', error);
        alert('Error: ' + error.message);
    }
}

function detectCameras() {
    alert('Camera detection feature - Please check available camera indices manually (usually 0, 1, 2...)');
}

// Real-Time Updates
function startRealtimeUpdates() {
    if (realtimeInterval) {
        clearInterval(realtimeInterval);
    }
    
    loadRealtimeData();
    realtimeInterval = setInterval(loadRealtimeData, 5000); // Update every 5 seconds
}

async function loadRealtimeData() {
    try {
        const response = await fetch('/api/admin/realtime/attendance');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('realtimePresent').textContent = data.total_present;
            document.getElementById('lastUpdate').textContent = 'Last update: ' + new Date(data.timestamp).toLocaleTimeString();
            
            // Update recent check-ins
            const checkinsList = document.getElementById('recentCheckinsList');
            if (checkinsList) {
                checkinsList.innerHTML = '';
                
                if (data.recent_checkins.length === 0) {
                    checkinsList.innerHTML = '<div style="text-align: center; padding: 20px; color: #999;">No recent check-ins</div>';
                } else {
                    data.recent_checkins.forEach(checkin => {
                        const item = document.createElement('div');
                        item.className = 'checkin-item';
                        const statusClass = checkin.status === 'Late' ? 'late' : 'present';
                        item.innerHTML = `
                            <div class="checkin-info">
                                <div class="checkin-name">${checkin.name} (${checkin.employee_id || checkin.staff_id})</div>
                                <div class="checkin-time">${checkin.check_time}</div>
                            </div>
                            <div>
                                <span class="checkin-status ${statusClass}">${checkin.status}${checkin.late_minutes > 0 ? ' (' + checkin.late_minutes + ' min)' : ''}</span>
                            </div>
                        `;
                        checkinsList.appendChild(item);
                    });
                }
            }
        }
    } catch (error) {
        console.error('Error loading realtime data:', error);
    }
}

// Reports
async function generateReport() {
    try {
        const startDate = document.getElementById('reportStartDate').value;
        const endDate = document.getElementById('reportEndDate').value;
        
        if (!startDate || !endDate) {
            alert('Please select both start and end dates');
            return;
        }
        
        const url = `/api/admin/attendance/export?start_date=${startDate}&end_date=${endDate}`;
        window.open(url, '_blank');
    } catch (error) {
        console.error('Error generating report:', error);
        alert('Error generating report');
    }
}

// Unknown Entries Management
let unknownEntriesList = [];

async function loadUnknownEntries() {
    try {
        const dateInput = document.getElementById('unknownEntriesDate');
        const date = dateInput ? dateInput.value : new Date().toISOString().split('T')[0];
        
        if (!dateInput) {
            const today = new Date().toISOString().split('T')[0];
            if (dateInput) dateInput.value = today;
        }
        
        console.log(`Loading unknown entries for date: ${date}`);
        const response = await fetch(`/api/admin/unknown-entries?date=${date}&limit=1000`);
        const data = await response.json();
        
        console.log('Unknown entries API response:', data);
        
        if (data.success) {
            unknownEntriesList = (data.entries || []);
            console.log(`Loaded ${unknownEntriesList.length} unknown entries from database`);

            // Show ALL entries, not just deduplicated ones
            // This ensures all unknown person captures are visible in the dashboard
            // Sort by detection_time (most recent first)
            const sortedEntries = unknownEntriesList.sort((a, b) => {
                const timeA = a.detection_time || a.time || '';
                const timeB = b.detection_time || b.time || '';
                return timeB.localeCompare(timeA);
            });

            console.log(`Rendering ${sortedEntries.length} unknown entries (all entries, sorted by time)`);

            renderUnknownEntries(sortedEntries);
        } else {
            console.error('Failed to load unknown entries:', data.error);
        }
    } catch (error) {
        console.error('Error loading unknown entries:', error);
    }
}

async function loadUnknownEntriesStats() {
    try {
        const dateInput = document.getElementById('unknownEntriesDate');
        const date = dateInput ? dateInput.value : new Date().toISOString().split('T')[0];
        
        const response = await fetch(`/api/admin/unknown-entries/stats?date=${date}`);
        const data = await response.json();
        
        if (data.success) {
            const stats = data.stats;
            document.getElementById('stat-unknown-total').textContent = stats.total_today;
            document.getElementById('stat-unknown-person').textContent = stats.unknown_person;
            document.getElementById('stat-covered-face').textContent = stats.covered_face;
            document.getElementById('stat-no-face').textContent = stats.no_face;
        }
    } catch (error) {
        console.error('Error loading unknown entries stats:', error);
    }
}

function renderUnknownEntries(entries) {
    const grid = document.getElementById('unknownEntriesGrid');
    const emptyState = document.getElementById('unknownEntriesEmpty');
    const selectAllCheckbox = document.getElementById('unknownSelectAll');
    
    console.log(`Rendering ${entries.length} unknown entries`);
    
    if (!grid) {
        console.error('Unknown entries grid element not found!');
        return;
    }

    // Reset "Select All" state whenever we re-render the list
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = false;
    }
    
    if (entries.length === 0) {
        console.log('No entries to display, showing empty state');
        grid.innerHTML = '';
        if (emptyState) emptyState.style.display = 'block';
        return;
    }
    
    if (emptyState) emptyState.style.display = 'none';
    
    grid.innerHTML = '';
    console.log(`Creating cards for ${entries.length} entries...`);
    
    entries.forEach(entry => {
        const card = document.createElement('div');
        card.className = 'unknown-entry-card';
        card.dataset.entryId = entry.id;
        card.dataset.entryType = entry.entry_type;
        card.dataset.processed = entry.is_processed;
        
        const typeLabels = {
            'unknown_person': 'Unknown Person',
            'covered_face': 'Covered Face',
            'no_face': 'No Face Detected'
        };
        
        const typeIcons = {
            'unknown_person': '❓',
            'covered_face': '🎭',
            'no_face': '🚫'
        };
        
        const modeLabels = {
            'checkin': 'Check-In',
            'checkout': 'Check-Out'
        };
        
        const processedBadge = entry.is_processed ? 
            '<span class="badge badge-success">Processed</span>' : 
            '<span class="badge badge-warning">Unprocessed</span>';
        
        card.innerHTML = `
            <div class="unknown-entry-select-row">
                <label style="display: inline-flex; align-items: center; gap: 4px; font-size: 13px; cursor: pointer;">
                    <input type="checkbox" class="unknown-entry-select" value="${entry.id}">
                    <span>Select</span>
                </label>
            </div>
            <div class="unknown-entry-image">
                <img src="${entry.image_url}" alt="Unknown Entry"
                     onclick="openUnknownImageModal('${entry.image_url}')"
                     onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27400%27 height=%27600%27%3E%3Crect fill=%27%23ddd%27 width=%27400%27 height=%27600%27/%3E%3Ctext fill=%27%23999%27 font-family=%27sans-serif%27 font-size=%2720%27 dy=%2710.5%27 font-weight=%27bold%27 x=%2750%25%27 y=%2750%25%27 text-anchor=%27middle%27%3ENo Image%3C/text%3E%3C/svg%3E'">
            </div>
            <div class="unknown-entry-info">
                <div class="unknown-entry-header">
                    <span class="entry-type-icon">${typeIcons[entry.entry_type] || '👤'}</span>
                    <span class="entry-type-label">${typeLabels[entry.entry_type] || entry.entry_type}</span>
                    ${processedBadge}
                </div>
                <div class="unknown-entry-details">
                    <div class="detail-row">
                        <span class="detail-label">Time:</span>
                        <span class="detail-value">${entry.time}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Date:</span>
                        <span class="detail-value">${entry.date}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Mode:</span>
                        <span class="detail-value">${modeLabels[entry.system_mode] || entry.system_mode}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Track ID:</span>
                        <span class="detail-value">#${entry.track_id}</span>
                    </div>
                    ${entry.face_detected ? `
                    <div class="detail-row">
                        <span class="detail-label">Face Confidence:</span>
                        <span class="detail-value">${(entry.face_confidence * 100).toFixed(1)}%</span>
                    </div>
                    ` : ''}
                    ${entry.recognition_confidence > 0 ? `
                    <div class="detail-row">
                        <span class="detail-label">Recognition:</span>
                        <span class="detail-value">${(entry.recognition_confidence * 100).toFixed(1)}%</span>
                    </div>
                    ` : ''}
                    ${entry.reason ? `
                    <div class="detail-row reason-row">
                        <span class="detail-label">Reason:</span>
                        <span class="detail-value">${entry.reason}</span>
                    </div>
                    ` : ''}
                </div>
                <div class="unknown-entry-actions">
                    ${!entry.is_processed ? `
                    <button class="btn btn-sm btn-primary" onclick="markEntryProcessed(${entry.id})">
                        ✓ Mark Processed
                    </button>
                    ` : ''}
                    <button class="btn btn-sm btn-secondary" onclick="recheckUnknownEntryAsStaff(${entry.id})">
                        🔍 Recheck as Staff
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteUnknownEntry(${entry.id})">
                        🗑️ Delete
                    </button>
                </div>
            </div>
        `;
        
        grid.appendChild(card);
    });
}

function filterUnknownEntries() {
    const search = document.getElementById('unknownEntriesSearch').value.toLowerCase();
    const typeFilter = document.getElementById('unknownEntriesFilter').value;
    const statusFilter = document.getElementById('unknownEntriesStatusFilter').value;
    
    let filtered = unknownEntriesList.filter(entry => {
        const matchSearch = !search || 
            entry.reason.toLowerCase().includes(search) ||
            entry.entry_type.toLowerCase().includes(search) ||
            entry.track_id.toString().includes(search);
        
        const matchType = typeFilter === 'all' || entry.entry_type === typeFilter;
        
        const matchStatus = statusFilter === 'all' || 
            (statusFilter === 'processed' && entry.is_processed) ||
            (statusFilter === 'unprocessed' && !entry.is_processed);
        
        return matchSearch && matchType && matchStatus;
    });
    
    renderUnknownEntries(filtered);
}

function getSelectedUnknownEntryIds() {
    const checkboxes = document.querySelectorAll('.unknown-entry-select');
    const ids = [];
    checkboxes.forEach(cb => {
        if (cb.checked) {
            const id = parseInt(cb.value, 10);
            if (!isNaN(id)) {
                ids.push(id);
            }
        }
    });
    return ids;
}

function toggleSelectAllUnknownEntries(masterCheckbox) {
    const checkboxes = document.querySelectorAll('.unknown-entry-select');
    checkboxes.forEach(cb => {
        cb.checked = masterCheckbox.checked;
    });
}

async function bulkDeleteSelectedUnknownEntries() {
    const ids = getSelectedUnknownEntryIds();
    if (!ids.length) {
        alert('Please select at least one unknown entry to delete.');
        return;
    }

    if (!confirm(`Are you sure you want to delete ${ids.length} selected entr${ids.length === 1 ? 'y' : 'ies'}? This action cannot be undone.`)) {
        return;
    }

    try {
        const deletePromises = ids.map(id =>
            fetch(`/api/admin/unknown-entries/${id}`, {
                method: 'DELETE'
            }).then(r => r.json())
        );

        const results = await Promise.all(deletePromises);
        const failed = results.filter(r => !r || !r.success);

        if (failed.length === 0) {
            alert(`Successfully deleted ${ids.length} entr${ids.length === 1 ? 'y' : 'ies'}.`);
        } else {
            alert(`Some entries could not be deleted (${failed.length} failed).`);
        }

        loadUnknownEntries();
        loadUnknownEntriesStats();
    } catch (error) {
        console.error('Error bulk deleting unknown entries:', error);
        alert('Error bulk deleting entries: ' + error.message);
    }
}

async function markEntryProcessed(entryId) {
    if (!confirm('Mark this entry as processed?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/unknown-entries/${entryId}/mark-processed`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Entry marked as processed');
            loadUnknownEntries();
            loadUnknownEntriesStats();
        } else {
            alert('Error: ' + (data.error || 'Failed to mark entry as processed'));
        }
    } catch (error) {
        console.error('Error marking entry as processed:', error);
        alert('Error: ' + error.message);
    }
}

async function deleteUnknownEntry(entryId) {
    if (!confirm('Are you sure you want to delete this entry? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/unknown-entries/${entryId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Entry deleted successfully');
            loadUnknownEntries();
            loadUnknownEntriesStats();
        } else {
            alert('Error: ' + (data.error || 'Failed to delete entry'));
        }
    } catch (error) {
        console.error('Error deleting entry:', error);
        alert('Error: ' + error.message);
    }
}

function refreshUnknownEntries() {
    loadUnknownEntries();
    loadUnknownEntriesStats();
}

// Unknown entry image preview
function openUnknownImageModal(imageUrl) {
    const modal = document.getElementById('unknownImageModal');
    const img = document.getElementById('unknownImageModalImg');
    if (!modal || !img) return;

    // Add cache-busting query param so updates are visible immediately
    const separator = imageUrl.includes('?') ? '&' : '?';
    img.src = imageUrl + separator + 'ts=' + Date.now();
    modal.style.display = 'block';
}

function closeUnknownImageModal() {
    const modal = document.getElementById('unknownImageModal');
    const img = document.getElementById('unknownImageModalImg');
    if (modal) modal.style.display = 'none';
    if (img) img.src = '';
}

// Re-check unknown entry image against staff database
async function recheckUnknownEntryAsStaff(entryId) {
    if (!confirm('Recheck this image against the staff database?\nIf a staff member is found, the entry will be marked as processed.')) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/unknown-entries/${entryId}/recheck-staff`, {
            method: 'POST'
        });

        const data = await response.json();

        if (!data.success) {
            const reason = data.error || 'No matching staff found or error occurred.';
            alert('Recheck result: ' + reason);
            return;
        }

        const msgParts = [];
        msgParts.push(`Matched Staff ID: ${data.staff_id}`);
        msgParts.push(`Recognition Confidence: ${(data.recognition_confidence * 100).toFixed(1)}%`);

        if (data.already_captured) {
            msgParts.push('Status: Staff was already captured recently. No new check-in created.');
        } else if (data.check_in_created) {
            msgParts.push(`Status: New ${data.system_mode === 'checkout' ? 'check-out' : 'check-in'} recorded.`);
        } else {
            msgParts.push('Status: Could not create attendance record.');
        }

        alert(msgParts.join('\n'));

        // Refresh lists to reflect processed state / new attendance
        loadUnknownEntries();
        loadUnknownEntriesStats();
        loadAttendance();
        loadDashboardStats();

    } catch (error) {
        console.error('Error rechecking unknown entry as staff:', error);
        alert('Error rechecking entry: ' + error.message);
    }
}

// Camera Capture Functions
let cameraStreamInterval = null;
let capturedPhotos = [];
let captureInstructions = [
    "Position yourself in front of the camera and look straight ahead",
    "Excellent! Now turn your head slightly to the right →",
    "Perfect! Now turn your head slightly to the left ←",
    "Great! Now tilt your head up slightly ↑",
    "Amazing! Now look down slightly ↓",
    "Perfect! All 5 photos captured successfully! ✅"
];

function openCameraCapture() {
    const cameraModal = document.getElementById('cameraModal');
    const cameraStream = document.getElementById('cameraStream');
    
    // Reset capture state
    capturedPhotos = [];
    updateCaptureUI();
    
    if (cameraModal) {
        cameraModal.style.display = 'block';
        // Reload the stream to start it
        const streamUrl = '/api/admin/camera/stream?' + new Date().getTime();
        cameraStream.src = streamUrl;
        document.getElementById('captureStatus').textContent = 'Camera stream started. Position yourself in front of the camera.';
        document.getElementById('captureInstructions').textContent = captureInstructions[0];
    }
}

function closeCameraModal() {
    const cameraModal = document.getElementById('cameraModal');
    const cameraStream = document.getElementById('cameraStream');
    
    if (cameraModal) {
        cameraModal.style.display = 'none';
        // Stop the stream
        cameraStream.src = '';
        
        // Stop camera on backend
        fetch('/api/admin/camera/stop', {
            method: 'POST'
        }).catch(err => console.error('Error stopping camera:', err));
        
        document.getElementById('captureStatus').textContent = '';
        capturedPhotos = [];
        updateCaptureUI();
    }
}

function updateCaptureUI() {
    const photoCount = capturedPhotos.length;
    document.getElementById('photoCount').textContent = photoCount;
    
    const captureBtn = document.getElementById('captureBtn');
    const clearBtn = document.getElementById('clearBtn');
    const finishBtn = document.getElementById('finishBtn');
    const instructions = document.getElementById('captureInstructions');
    const preview = document.getElementById('capturedPhotosPreview');
    
    if (photoCount === 0) {
        captureBtn.textContent = '📸 Capture Photo 1/5';
        captureBtn.disabled = false;
        clearBtn.style.display = 'none';
        finishBtn.style.display = 'none';
        instructions.textContent = captureInstructions[0];
        preview.innerHTML = '';
    } else if (photoCount < 5) {
        captureBtn.textContent = `📸 Capture Photo ${photoCount + 1}/5`;
        captureBtn.disabled = false;
        clearBtn.style.display = 'inline-block';
        finishBtn.style.display = photoCount >= 3 ? 'inline-block' : 'none';
        instructions.textContent = captureInstructions[photoCount];
    } else {
        captureBtn.textContent = '📸 All Photos Captured';
        captureBtn.disabled = true;
        clearBtn.style.display = 'inline-block';
        finishBtn.style.display = 'inline-block';
        instructions.textContent = captureInstructions[5];
    }
    
    // Update preview thumbnails
    preview.innerHTML = '';
    capturedPhotos.forEach((photo, index) => {
        const thumb = document.createElement('div');
        thumb.style.cssText = 'position: relative; width: 80px; height: 80px; border: 2px solid #667eea; border-radius: 4px; overflow: hidden;';
        thumb.innerHTML = `
            <img src="${photo}" alt="Photo ${index + 1}" style="width: 100%; height: 100%; object-fit: cover;">
            <div style="position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.7); color: white; text-align: center; font-size: 10px; padding: 2px;">
                ${index + 1}
            </div>
        `;
        preview.appendChild(thumb);
    });
}

async function capturePhoto() {
    if (capturedPhotos.length >= 5) {
        document.getElementById('captureStatus').textContent = 'All 5 photos already captured!';
        document.getElementById('captureStatus').style.color = '#f44336';
        return;
    }
    
    try {
        document.getElementById('captureStatus').textContent = 'Capturing photo...';
        document.getElementById('captureStatus').style.color = '#666';
        
        const response = await fetch('/api/admin/camera/capture', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success && data.image) {
            // Add to captured photos array
            capturedPhotos.push(data.image);
            updateCaptureUI();
            
            document.getElementById('captureStatus').textContent = `Photo ${capturedPhotos.length}/5 captured successfully!`;
            document.getElementById('captureStatus').style.color = '#4CAF50';
            
            if (capturedPhotos.length >= 5) {
                setTimeout(() => {
                    document.getElementById('captureStatus').textContent = 'All photos captured! Click "Finish" to use them.';
                }, 1500);
            }
        } else {
            document.getElementById('captureStatus').textContent = 'Error: ' + (data.error || 'Failed to capture photo');
            document.getElementById('captureStatus').style.color = '#f44336';
        }
    } catch (error) {
        console.error('Error capturing photo:', error);
        document.getElementById('captureStatus').textContent = 'Error: ' + error.message;
        document.getElementById('captureStatus').style.color = '#f44336';
    }
}

function clearCapturedPhotos() {
    if (capturedPhotos.length === 0) return;
    
    if (confirm(`Are you sure you want to clear all ${capturedPhotos.length} captured photos?`)) {
        capturedPhotos = [];
        updateCaptureUI();
        document.getElementById('captureStatus').textContent = 'All photos cleared. Ready to capture again.';
        document.getElementById('captureStatus').style.color = '#666';
    }
}

function finishCapture() {
    if (capturedPhotos.length < 3) {
        alert('Please capture at least 3 photos for better recognition.\nCurrently captured: ' + capturedPhotos.length);
        return;
    }
    
    // Use the first photo as the preview (or average them visually)
    const photoPreview = document.getElementById('photoPreview');
    photoPreview.innerHTML = `<img src="${capturedPhotos[0]}" alt="Captured Photos" style="width: 100%; height: 100%; object-fit: cover;">`;
    
    // Store all captured photos in a hidden field or data attribute
    document.getElementById('photoPreview').dataset.capturedPhotos = JSON.stringify(capturedPhotos);
    
    // Clear file input
    document.getElementById('staffPhoto').value = '';
    
    document.getElementById('captureStatus').textContent = `${capturedPhotos.length} photos ready to use!`;
    document.getElementById('captureStatus').style.color = '#4CAF50';
    
    // Close camera modal
    setTimeout(() => {
        closeCameraModal();
    }, 1000);
}

// Close modal when clicking outside
window.onclick = function(event) {
    const staffModal = document.getElementById('staffModal');
    const cameraModal = document.getElementById('cameraModal');
    const unknownImageModal = document.getElementById('unknownImageModal');
    
    if (event.target === staffModal) {
        closeStaffModal();
    }
    
    if (event.target === cameraModal) {
        closeCameraModal();
    }

    if (event.target === unknownImageModal) {
        closeUnknownImageModal();
    }
}

