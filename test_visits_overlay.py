import numpy as np
import cv2

def draw_visits_text(width, height):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    x1, y1 = 100, 100
    text_pos = (x1, max(40, y1 - 40))
    cv2.putText(frame, "Total Visits: 5", text_pos, cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    region = frame[text_pos[1]-5:text_pos[1]+5, text_pos[0]:text_pos[0]+150]
    return np.any(region > 0)

def test_overlay_legibility_hd_frames():
    assert draw_visits_text(1920, 1080)
    assert draw_visits_text(1980, 1080)
