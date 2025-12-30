// IMPEX Attendance Dashboard - JavaScript

let systemMode = 'checkin';
let isSystemRunning = false;
let attendanceRefreshInterval = null;
let systemStatusInterval = null;
let allStaff = [];
let activeCards = new Map(); // staff_id -> { cardElement, timerId, displayTime }
const CARD_DISPLAY_DURATION = 30 * 60 * 1000; // 30 minutes in milliseconds

// Initialize dashboard
function initDashboard() {
    updateDateTime();
    setInterval(updateDateTime, 1000); // Update every second
    
    // Load staff list once
    loadStaffList();
    
    // Load existing attendance cards on page load
    loadExistingAttendanceCards();
    
    // Check system status every 5 seconds
    systemStatusInterval = setInterval(checkSystemStatus, 5000);
    
    // Listen for new detections via WebSocket or polling (using polling for now)
    // Poll for new detections every 1 second (lighter than full refresh)
    attendanceRefreshInterval = setInterval(checkForNewDetections, 1000);
    
    // Update card times every 5 seconds to keep them current
    setInterval(updateAllCardTimes, 5000);
    
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
            // Clear all cards when system stops
            clearAllCards();
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
            // Cards are now shown dynamically on detection, no need to refresh
            checkForNewDetections();
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

// Load existing attendance cards on page initialization
async function loadExistingAttendanceCards() {
    try {
        const response = await fetch('/api/attendance/today');
        const data = await response.json();
        
        if (response.ok) {
            const checkins = data.checkins || [];
            
            if (checkins.length > 0) {
                // Sort by time (most recent first)
                const sortedCheckins = [...checkins].sort((a, b) => {
                    const timeA = a.check_time || a.check_in_time || '';
                    const timeB = b.check_time || b.check_in_time || '';
                    return timeB.localeCompare(timeA);
                });
                
                // Show cards for all existing check-ins (within 30-minute window)
                sortedCheckins.forEach(checkin => {
                    const staffId = checkin.staff_id;
                    if (staffId) {
                        // Check if check-in is within 30-minute window
                        const checkTimeStr = checkin.check_time || checkin.check_in_time;
                        if (checkTimeStr) {
                            try {
                                const checkTime = new Date(checkTimeStr);
                                const now = new Date();
                                const elapsed = now - checkTime;
                                
                                // Only show if within 30-minute window
                                if (elapsed <= CARD_DISPLAY_DURATION) {
                                    showDetectionCard(checkin, data.mode || systemMode, true); // true = isExisting
                                }
                            } catch (e) {
                                // If time parsing fails, show the card anyway
                                showDetectionCard(checkin, data.mode || systemMode, true);
                            }
                        } else {
                            showDetectionCard(checkin, data.mode || systemMode, true);
                        }
                    }
                });
            }
        } else {
            console.error('Error loading existing attendance:', data.error);
        }
    } catch (error) {
        console.error('Error loading existing attendance cards:', error);
    }
}

// Refresh attendance cards
// Check for new detections and show cards dynamically
async function checkForNewDetections() {
    try {
        const response = await fetch('/api/attendance/today');
        const data = await response.json();
        
        if (response.ok) {
            const checkins = data.checkins || [];
            const attendance = data.attendance || [];
            
            // Process all checkins to update existing cards or add new ones
            if (checkins.length > 0) {
                // Get the most recent check-in per staff_id
                const latestByStaff = {};
                checkins.forEach(checkin => {
                    const staffId = checkin.staff_id;
                    if (!staffId) return;
                    
                    const checkTime = checkin.check_time || checkin.check_in_time || '';
                    const existing = latestByStaff[staffId];
                    
                    if (!existing || checkTime.localeCompare(existing.check_time || existing.check_in_time || '') > 0) {
                        latestByStaff[staffId] = checkin;
                    }
                });
                
                // Update or create cards
                Object.values(latestByStaff).forEach(checkin => {
                    const staffId = checkin.staff_id;
                    if (staffId) {
                        if (activeCards.has(staffId)) {
                            // Update existing card time
                            updateCardTime(staffId, checkin);
                        } else {
                            // New detection - show card
                            showDetectionCard(checkin, data.mode || systemMode, false);
                        }
                    }
                });
            }
            
            // Clean up expired cards
            cleanupExpiredCards();
        } else {
            console.error('Error loading attendance:', data.error);
        }
    } catch (error) {
        console.error('Error checking for new detections:', error);
    }
}

// Show card for a detected staff member
function showDetectionCard(item, mode, isExisting = false) {
    const checkedContainer = document.getElementById('checkedOutContainer');
    if (!checkedContainer) return;
    
    const staffId = item.staff_id;
    if (!staffId) return;
    
    // Remove existing card if any (shouldn't happen, but safety check)
    if (activeCards.has(staffId)) {
        removeCard(staffId);
    }
    
    // Create and add card
    const card = createEmployeeCard(item, mode);
    card.dataset.staffId = staffId;
    
    // Set display time based on check-in time or now
    const checkTimeStr = item.check_time || item.check_in_time;
    let displayTime = Date.now();
    if (checkTimeStr && isExisting) {
        try {
            const checkTime = new Date(checkTimeStr);
            displayTime = checkTime.getTime();
        } catch (e) {
            displayTime = Date.now();
        }
    }
    card.dataset.displayTime = displayTime;
    
    // Calculate remaining time for timer
    const elapsed = Date.now() - displayTime;
    const remainingTime = Math.max(0, CARD_DISPLAY_DURATION - elapsed);
    
    // Add card to container (at the beginning for most recent first)
    checkedContainer.insertBefore(card, checkedContainer.firstChild);
    
    // Set timer to remove card after remaining duration
    const timerId = setTimeout(() => {
        removeCard(staffId);
    }, remainingTime);
    
    // Track active card
    activeCards.set(staffId, {
        cardElement: card,
        timerId: timerId,
        displayTime: displayTime,
        lastUpdateTime: Date.now()
    });
    
    console.log(`✅ ${isExisting ? 'Loaded' : 'Showing'} card for ${item.name || staffId}`);
}

// Update card time display
function updateCardTime(staffId, item) {
    if (!activeCards.has(staffId)) return;
    
    const cardData = activeCards.get(staffId);
    const card = cardData.cardElement;
    if (!card) return;
    
    // Update time label in the card
    const timeLabel = card.querySelector('.employee-time');
    if (timeLabel) {
        const checkTimeStr = item.check_time || item.check_in_time;
        if (checkTimeStr) {
            timeLabel.textContent = formatTime(checkTimeStr);
        }
    }
    
    // Update status/late minutes if needed
    const statusLabel = card.querySelector('.employee-status');
    if (statusLabel) {
        const checkTimeStr = item.check_time || item.check_in_time;
        let showLate = false;
        let lateMinutes = 0;
        
        if (typeof item.late_minutes === 'number' && item.late_minutes > 0 && checkTimeStr) {
            try {
                const checkTime = new Date(checkTimeStr);
                const hours = checkTime.getHours();
                const minutes = checkTime.getMinutes();
                const totalMinutes = hours * 60 + minutes;
                const startMinutes = 9 * 60; // 9:00 AM
                const endMinutes = 9 * 60 + 20; // 9:20 AM
                
                if (totalMinutes > startMinutes && totalMinutes <= endMinutes) {
                    showLate = true;
                    lateMinutes = item.late_minutes;
                }
            } catch (e) {
                if (item.late_minutes > 0) {
                    showLate = true;
                    lateMinutes = item.late_minutes;
                }
            }
        }
        
        if (showLate && lateMinutes > 0) {
            statusLabel.textContent = `${lateMinutes} min Late`;
            statusLabel.classList.remove('on-time');
        } else {
            statusLabel.textContent = item.status && !item.status.toLowerCase().includes('late') 
                ? item.status 
                : 'Present';
            if (!showLate) {
                statusLabel.classList.add('on-time');
            }
        }
    }
    
    // Update last update time
    cardData.lastUpdateTime = Date.now();
    
    console.log(`🔄 Updated card time for ${item.name || staffId}`);
}

// Remove card for a staff member
function removeCard(staffId) {
    if (!activeCards.has(staffId)) return;
    
    const cardData = activeCards.get(staffId);
    if (cardData.cardElement && cardData.cardElement.parentNode) {
        cardData.cardElement.parentNode.removeChild(cardData.cardElement);
    }
    if (cardData.timerId) {
        clearTimeout(cardData.timerId);
    }
    activeCards.delete(staffId);
    console.log(`🗑️ Removed card for ${staffId}`);
}

// Clean up expired cards
function cleanupExpiredCards() {
    const now = Date.now();
    for (const [staffId, cardData] of activeCards.entries()) {
        const elapsed = now - cardData.displayTime;
        if (elapsed >= CARD_DISPLAY_DURATION) {
            removeCard(staffId);
        }
    }
}

// Update all card times periodically
async function updateAllCardTimes() {
    try {
        const response = await fetch('/api/attendance/today');
        const data = await response.json();
        
        if (response.ok) {
            const checkins = data.checkins || [];
            
            // Create a map of staff_id -> latest checkin
            const latestByStaff = {};
            checkins.forEach(checkin => {
                const staffId = checkin.staff_id;
                if (!staffId) return;
                
                const checkTime = checkin.check_time || checkin.check_in_time || '';
                const existing = latestByStaff[staffId];
                
                if (!existing || checkTime.localeCompare(existing.check_time || existing.check_in_time || '') > 0) {
                    latestByStaff[staffId] = checkin;
                }
            });
            
            // Update times for all active cards
            for (const [staffId, cardData] of activeCards.entries()) {
                if (latestByStaff[staffId]) {
                    updateCardTime(staffId, latestByStaff[staffId]);
                }
            }
        }
    } catch (error) {
        console.error('Error updating card times:', error);
    }
}

// Clear all active cards
function clearAllCards() {
    for (const staffId of Array.from(activeCards.keys())) {
        removeCard(staffId);
    }
}

// Legacy function kept for compatibility (but not used for auto-refresh)
async function refreshAttendanceCards() {
    // This function is kept for compatibility but auto-refresh is disabled
    // Cards are now shown dynamically on detection
    checkForNewDetections();
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
    
    // Use showcase photo URL if available, otherwise fallback to captured photo or placeholder
    if (item.photo_url) {
        const img = document.createElement('img');
        img.src = item.photo_url + '?t=' + Date.now(); // Add timestamp to prevent caching
        img.alt = 'Employee Photo';
        img.onerror = function() {
            // Fallback to placeholder if showcase photo fails to load
            this.src = '/static/icons/Clip path group.png';
            this.className = 'photo-placeholder-icon';
        };
        photoContainer.appendChild(img);
    } else if (item.photo) {
        // Fallback to captured photo if showcase photo URL not available
        const img = document.createElement('img');
        img.src = 'data:image/jpeg;base64,' + item.photo;
        img.alt = 'Employee Photo';
        photoContainer.appendChild(img);
    } else {
        const placeholderImg = document.createElement('img');
        placeholderImg.src = '/static/icons/Clip path group.png';
        placeholderImg.alt = 'User Icon';
        placeholderImg.className = 'photo-placeholder-icon';
        photoContainer.appendChild(placeholderImg);
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
    
    // Status (Late time for check-in - only show if between 9:00 AM and 9:20 AM)
    const statusLabel = document.createElement('div');
    statusLabel.className = 'employee-status';
    
    if (viewMode === 'checkout') {
        // Do not show late/present status on checkout cards
        statusLabel.textContent = '';
    } else {
        // Only show late status if check-in is between 9:00 AM and 9:20 AM
        const checkTimeStr = item.check_time || item.check_in_time;
        let showLate = false;
        let lateMinutes = 0;
        
        if (typeof item.late_minutes === 'number' && item.late_minutes > 0 && checkTimeStr) {
            // Verify the time is actually between 9:00 AM and 9:20 AM
            try {
                const checkTime = new Date(checkTimeStr);
                const hours = checkTime.getHours();
                const minutes = checkTime.getMinutes();
                const totalMinutes = hours * 60 + minutes;
                const startMinutes = 9 * 60; // 9:00 AM
                const endMinutes = 9 * 60 + 20; // 9:20 AM
                
                if (totalMinutes > startMinutes && totalMinutes <= endMinutes) {
                    showLate = true;
                    lateMinutes = item.late_minutes;
                }
            } catch (e) {
                // If parsing fails, use the provided late_minutes if > 0
                if (item.late_minutes > 0) {
                    showLate = true;
                    lateMinutes = item.late_minutes;
                }
            }
        }
        
        if (showLate && lateMinutes > 0) {
            statusLabel.textContent = `${lateMinutes} min Late`;
        } else if (item.status && !item.status.toLowerCase().includes('late')) {
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

