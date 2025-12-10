// IMPEX Attendance Dashboard - JavaScript

let systemMode = 'checkin';
let isSystemRunning = false;
let attendanceRefreshInterval = null;
let systemStatusInterval = null;
let allStaff = [];

// Initialize dashboard
function initDashboard() {
    updateDateTime();
    setInterval(updateDateTime, 1000); // Update every second
    
    // Load staff list once
    loadStaffList();
    
    // Load attendance cards
    refreshAttendanceCards();
    
    // Refresh attendance every 2 seconds
    attendanceRefreshInterval = setInterval(refreshAttendanceCards, 2000);
    
    // Check system status every 5 seconds
    systemStatusInterval = setInterval(checkSystemStatus, 5000);
    
    // Set initial mode
    if (typeof SYSTEM_MODE !== 'undefined') {
        systemMode = SYSTEM_MODE;
        updateModeButtons();
    }
}

// Update date and time
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
        hour12: true 
    });
    
    const dateLabel = document.getElementById('dateLabel');
    const timeLabel = document.getElementById('timeLabel');
    
    if (dateLabel) dateLabel.textContent = dateStr;
    if (timeLabel) timeLabel.textContent = timeStr;
}

// Start system
async function startSystem() {
    try {
        const response = await fetch('/api/system/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ mode: (typeof PAGE_MODE !== 'undefined' && PAGE_MODE) ? PAGE_MODE : systemMode })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            isSystemRunning = true;
            updateButtonStates();
            console.log('System started:', data);
        } else {
            alert('Error starting system: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error starting system:', error);
        alert('Failed to start system. Please check console for details.');
    }
}

// Stop system
async function stopSystem() {
    try {
        const response = await fetch('/api/system/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            isSystemRunning = false;
            updateButtonStates();
            console.log('System stopped:', data);
        } else {
            alert('Error stopping system: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error stopping system:', error);
        alert('Failed to stop system. Please check console for details.');
    }
}

// Set mode
async function setMode(mode) {
    if (typeof IS_LOCKED !== 'undefined' && IS_LOCKED) {
        return; // Mode switching is locked
    }
    
    try {
        const response = await fetch('/api/system/mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ mode: mode })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            systemMode = mode;
            updateModeButtons();
            const titleImage = document.getElementById('titleLabel');
            if (titleImage && titleImage.tagName === 'IMG') {
                const titleSrc = mode === 'checkin' 
                    ? '/static/icons/Check%20In.png' 
                    : '/static/icons/Check%20Out.png';
                titleImage.src = titleSrc;
                titleImage.alt = mode === 'checkin' ? 'Check In' : 'Check Out';
            }
            refreshAttendanceCards();
        } else {
            alert('Error setting mode: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error setting mode:', error);
    }
}

// Update mode buttons
function updateModeButtons() {
    const buttons = document.querySelectorAll('.mode-btn');
    buttons.forEach(btn => {
        const btnMode = btn.textContent.toLowerCase().replace(' ', '');
        if (btnMode === systemMode) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

// Update button states
function updateButtonStates() {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    
    if (startBtn) {
        startBtn.disabled = isSystemRunning;
    }
    if (stopBtn) {
        stopBtn.disabled = !isSystemRunning;
    }
}

// Check system status
async function checkSystemStatus() {
    try {
        const response = await fetch('/api/system/status');
        const data = await response.json();
        
        if (data.running !== isSystemRunning) {
            isSystemRunning = data.running;
            updateButtonStates();
        }
        
        // Update camera status
        const statusLabel = document.getElementById('cameraStatus');
        if (statusLabel) {
            if (data.camera_connected && data.running) {
                statusLabel.textContent = 'Camera Connected - Running';
                statusLabel.style.color = '#44ff44';
            } else if (data.camera_connected) {
                statusLabel.textContent = 'Camera Connected - Stopped';
                statusLabel.style.color = '#ffff44';
            } else {
                statusLabel.textContent = 'Camera Disconnected';
                statusLabel.style.color = '#ff4444';
            }
        }
    } catch (error) {
        console.error('Error checking system status:', error);
    }
}

// Refresh attendance cards
async function refreshAttendanceCards() {
    try {
        const response = await fetch('/api/attendance/today');
        const data = await response.json();
        
        if (response.ok) {
            const checkins = data.checkins || [];
            const attendance = data.attendance || [];
            displayAttendanceCards(checkins, attendance, data.mode || systemMode);
        } else {
            console.error('Error loading attendance:', data.error);
        }
    } catch (error) {
        console.error('Error refreshing attendance cards:', error);
    }
}

// Display attendance cards (checked vs remaining)
function displayAttendanceCards(checkinList, attendanceList, mode) {
    const checkedContainer = document.getElementById('checkedOutContainer');
    const remainingContainer = document.getElementById('remainingContainer');
    const remainingCountLabel = document.getElementById('remainingCount');
    const remainingSection = document.querySelector('.remaining-section');
    if (!checkedContainer || !remainingContainer || !remainingCountLabel) return;
    
    // Determine view mode: honor page intent first (e.g., /checkin), then API/system
    const viewMode = (typeof PAGE_MODE !== 'undefined' && PAGE_MODE) ? PAGE_MODE : (mode || systemMode);
    const effectiveMode = mode || systemMode;

    if (viewMode === 'checkout') {
        // For checkout: use attendance records
        // If system is not running, show everyone who checked in today in remaining
        // If system is running, show checked-out people above and remaining below
        
        // Remaining: people with check_in_time (regardless of check_out_time if system not running)
        // OR people with check_in_time but NO check_out_time (if system is running)
        const allCheckedIn = (attendanceList || []).filter(att => att.check_in_time);
        
        let checkedOut = [];
        let remaining = [];
        
        if (!isSystemRunning) {
            // System not running: show everyone who checked in today in remaining
            remaining = allCheckedIn;
            checkedOut = [];
        } else {
            // System running: separate checked-out from remaining
            checkedOut = allCheckedIn.filter(att => att.check_out_time);
            remaining = allCheckedIn.filter(att => !att.check_out_time);
        }
        
        // Sort checked out by time (most recent first)
        const sortedCheckedOut = checkedOut.sort((a, b) => {
            const timeA = a.check_out_time || '';
            const timeB = b.check_out_time || '';
            return timeB.localeCompare(timeA);
        });
        
        // Display checked out cards
        checkedContainer.innerHTML = '';
        if (sortedCheckedOut.length === 0) {
            createPlaceholderCards(checkedContainer, effectiveMode);
        } else {
            sortedCheckedOut.forEach(item => {
                const card = createEmployeeCard(item, effectiveMode);
                checkedContainer.appendChild(card);
            });
        }
        
        // Display remaining cards with photos
        remainingCountLabel.textContent = `REMAINING : ${remaining.length}`;
        remainingContainer.innerHTML = '';
        if (remaining.length === 0) {
            createPlaceholderCards(remainingContainer, effectiveMode);
        } else {
            remaining.forEach(item => {
                const card = createEmployeeCard(item, effectiveMode);
                remainingContainer.appendChild(card);
            });
        }
        
        // Show remaining section
        if (remainingSection) {
            remainingSection.style.display = 'block';
        }
    } else {
        // For checkin: use checkin events
        // Dedupe to latest per staff_id
        const latestByStaff = {};
        (checkinList || []).forEach(ev => {
            const t = ev.check_time || ev.check_in_time || ev.check_out_time || '';
            const prev = latestByStaff[ev.staff_id];
            if (!prev || t.localeCompare(prev.check_time || prev.check_in_time || prev.check_out_time || '') > 0) {
                latestByStaff[ev.staff_id] = ev;
            }
        });
        const deduped = Object.values(latestByStaff);

        // Sort by time (most recent first)
        const sortedAtt = deduped.sort((a, b) => {
            const timeA = a.check_time || a.check_in_time || a.check_out_time || '';
            const timeB = b.check_time || b.check_in_time || b.check_out_time || '';
            return timeB.localeCompare(timeA);
        });
        
        // Display checkin cards
        checkedContainer.innerHTML = '';
        const maxCards = 20;
        const displayItems = sortedAtt.slice(0, maxCards);
        if (displayItems.length === 0) {
            createPlaceholderCards(checkedContainer, effectiveMode);
        } else {
            displayItems.forEach(item => {
                const card = createEmployeeCard(item, effectiveMode);
                checkedContainer.appendChild(card);
            });
        }
        
        // Hide remaining section for checkin
        if (remainingSection) {
            remainingSection.style.display = 'none';
        }
    }
}

// Create employee card
function createEmployeeCard(item, mode) {
    const card = document.createElement('div');
    card.className = 'employee-card';
    const viewMode = (typeof PAGE_MODE !== 'undefined' && PAGE_MODE) ? PAGE_MODE : mode;
    
    // Photo container (white top section)
    const photoContainer = document.createElement('div');
    photoContainer.className = 'photo-container';
    
    if (item.photo) {
        const img = document.createElement('img');
        img.src = 'data:image/jpeg;base64,' + item.photo;
        img.alt = 'Employee Photo';
        photoContainer.appendChild(img);
    } else {
        const placeholder = document.createElement('div');
        placeholder.className = 'photo-placeholder';
        photoContainer.appendChild(placeholder);
    }
    
    // Info container (dark brown bottom section)
    const infoContainer = document.createElement('div');
    infoContainer.className = 'employee-card-info';
    
    // Employee ID
    const idLabel = document.createElement('div');
    idLabel.className = 'employee-id';
    idLabel.textContent = `ID : ${item.employee_id || item.staff_id}`;
    
    // Time
    const timeLabel = document.createElement('div');
    timeLabel.className = 'employee-time';
    
    if (item.check_time) {
        timeLabel.textContent = formatTime(item.check_time);
    } else if (viewMode === 'checkout') {
        // For checkout: show check_out_time if available (checked out), otherwise check_in_time (remaining)
        timeLabel.textContent = item.check_out_time 
            ? formatTime(item.check_out_time) 
            : (item.check_in_time ? formatTime(item.check_in_time) : '--:--');
    } else {
        // For checkin: show check_in_time
        timeLabel.textContent = item.check_in_time 
            ? formatTime(item.check_in_time) 
            : '--:--';
    }
    
    // Status (Late time for check-in)
    const statusLabel = document.createElement('div');
    statusLabel.className = 'employee-status';
    
    if (viewMode === 'checkout') {
        // Do not show late/present status on checkout cards
        statusLabel.textContent = '';
    } else {
        if (typeof item.late_minutes === 'number' && item.late_minutes > 0) {
            statusLabel.textContent = `${item.late_minutes} min Late`;
        } else if (item.status) {
            statusLabel.textContent = item.status;
            if (item.status.toLowerCase().includes('on time') || item.status.toLowerCase().includes('present')) {
                statusLabel.classList.add('on-time');
            }
        } else if (item.check_time || item.check_in_time) {
            statusLabel.textContent = 'Present';
            statusLabel.classList.add('on-time');
        }
    }
    
    // Assemble info container
    infoContainer.appendChild(idLabel);
    infoContainer.appendChild(timeLabel);
    if (statusLabel.textContent) {
        infoContainer.appendChild(statusLabel);
    }
    
    // Assemble card
    card.appendChild(photoContainer);
    card.appendChild(infoContainer);
    
    return card;
}

// Create placeholder cards when no attendance data
function createPlaceholderCards(container, mode) {
    const placeholderCount = 12;
    for (let i = 0; i < placeholderCount; i++) {
        const placeholderItem = {
            employee_id: '----',
            staff_id: '----',
            status: 'Waiting',
            check_in_time: null,
            check_out_time: null,
            photo: null
        };
        const card = createEmployeeCard(placeholderItem, mode);
        container.appendChild(card);
    }
}

// Load all staff list once
async function loadStaffList() {
    try {
        const response = await fetch('/api/staff/all');
        const data = await response.json();
        if (response.ok && data.staff) {
            allStaff = data.staff;
        }
    } catch (error) {
        console.error('Error loading staff list:', error);
    }
}

// Format time from ISO string
function formatTime(isoString) {
    try {
        const date = new Date(isoString);
        if (isNaN(date.getTime())) return '--:--';
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: true 
        });
    } catch (error) {
        return '--:--';
    }
}

