import numpy as np
# Use SciPy's Hungarian implementation for robust linear assignment
from scipy.optimize import linear_sum_assignment


def linear_assignment(cost_matrix: np.ndarray) -> np.ndarray:
    """Solve linear assignment problem using Hungarian algorithm.

    This function finds the optimal assignment between two sets of items given a
    cost matrix, where a lower cost indicates a better match. It's a critical
    component for associating new detections with existing tracks.

    Parameters
    ----------
    cost_matrix : np.ndarray
        Matrix of shape (num_tracks, num_detections) containing association
        costs.

    Returns
    -------
    np.ndarray
        An array of (track_index, detection_index) pairs representing the
        optimal assignment. Returns an empty array if either tracks or
        detections are empty.
    """
    if cost_matrix.size == 0:
        return np.empty((0, 2), dtype=int)

    # The Hungarian algorithm implementation in SciPy returns optimal indices
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    # Combine the row and column indices into a single array of pairs
    return np.asarray(list(zip(row_ind, col_ind)), dtype=int)


def tlbr_to_xyah(tlbr):
    """Convert bounding box from [x1, y1, x2, y2] to [cx, cy, a, h].

    This format, where 'cx' and 'cy' are the center coordinates, 'a' is the
    aspect ratio, and 'h' is the height, is used by the Kalman filter.
    """
    x1, y1, x2, y2 = tlbr
    w = x2 - x1
    h = y2 - y1
    cx = x1 + w / 2.0
    cy = y1 + h / 2.0
    a = w / (h + 1e-6)  # Add epsilon to avoid division by zero
    return np.array([cx, cy, a, h])


def xyah_to_tlbr(xyah):
    """Convert bounding box from [cx, cy, a, h] back to [x1, y1, x2, y2]."""
    cx, cy, a, h = xyah
    w = a * h
    x1 = cx - w / 2.0
    y1 = cy - h / 2.0
    x2 = cx + w / 2.0
    y2 = cy + h / 2.0
    return np.array([x1, y1, x2, y2])


class Detection:
    """A lightweight container for detection results.

    This class stores the bounding box and its associated feature vector, which
    is used for matching detections with tracks.
    """

    def __init__(self, bbox, feature):
        self.tlbr = np.asarray(bbox, dtype=float)
        self.bbox = tlbr_to_xyah(self.tlbr)
        # Normalize the feature vector for stable cosine similarity calculations
        feature = np.asarray(feature, dtype=float)
        self.feature = feature / (np.linalg.norm(feature) + 1e-6)


class KalmanFilter:
    """A simple Kalman filter for tracking bounding box movement.

    This filter predicts the next state of a track based on its current motion
    and corrects its prediction using new measurements (detections).
    """

    def __init__(self):
        ndim, dt = 4, 1.0  # 4D state space, unit time step
        # Motion model matrix (constant velocity)
        self._motion_mat = np.eye(2 * ndim)
        for i in range(ndim):
            self._motion_mat[i, ndim + i] = dt
        # Measurement matrix (we only measure position)
        self._update_mat = np.eye(ndim, 2 * ndim)

        # Noise parameters tuned for pedestrian tracking
        self._std_weight_position = 1.0 / 20
        self._std_weight_velocity = 1.0 / 160

    def initiate(self, measurement):
        """Initialize a new track's state."""
        mean_pos = measurement
        mean_vel = np.zeros_like(mean_pos)
        mean = np.r_[mean_pos, mean_vel]

        # Initialize covariance with high uncertainty for velocity
        covariance = np.eye(8)
        covariance[4:, 4:] *= 1000.0  # High uncertainty for velocity
        covariance *= 10.0
        return mean, covariance

    def predict(self, mean, covariance):
        """Predict the next state (mean and covariance)."""
        # Calculate motion noise
        std_pos = self._std_weight_position * mean[3]
        std_vel = self._std_weight_velocity * mean[3]
        motion_cov = np.diag([std_pos**2, std_pos**2, 1e-2, std_pos**2,
                                std_vel**2, std_vel**2, 1e-4, std_vel**2])

        # Predict the next state
        mean = np.dot(self._motion_mat, mean)
        covariance = (
            self._motion_mat @ covariance @ self._motion_mat.T + motion_cov
        )
        return mean, covariance

    def project(self, mean, covariance):
        """Project state into measurement space."""
        # Calculate measurement noise
        std = self._std_weight_position * mean[3]
        innovation_cov = np.diag([std**2, std**2, 1e-2, std**2])

        # Project the state
        mean = self._update_mat @ mean
        covariance = (
            self._update_mat @ covariance @ self._update_mat.T
        )
        return mean, covariance + innovation_cov

    def update(self, mean, covariance, measurement):
        """Update the state with a new measurement."""
        proj_mean, proj_cov = self.project(mean, covariance)
        kalman_gain = covariance @ self._update_mat.T @ np.linalg.inv(proj_cov)
        innovation = measurement - proj_mean
        new_mean = mean + kalman_gain @ innovation
        new_cov = covariance - kalman_gain @ proj_cov @ kalman_gain.T
        return new_mean, new_cov


class Track:
    """Represents a single tracked object within the DeepSort algorithm."""

    def __init__(self, mean, covariance, track_id, feature):
        self.mean = mean
        self.covariance = covariance
        self.track_id = track_id
        self.features = [feature]  # Store a gallery of features
        self.time_since_update = 0
        self.hits = 1  # Number of consecutive successful updates

    def predict(self, kf):
        """Advance the track's state and increase its age."""
        self.mean, self.covariance = kf.predict(self.mean, self.covariance)
        self.time_since_update += 1

    def update(self, kf, detection):
        """Update the track with a new detection."""
        self.mean, self.covariance = kf.update(
            self.mean, self.covariance, detection.bbox
        )
        self.features.append(detection.feature)
        self.time_since_update = 0
        self.hits += 1

    def to_tlbr(self):
        """Get the current bounding box in [x1, y1, x2, y2] format."""
        return xyah_to_tlbr(self.mean[:4])

    @property
    def feature(self):
        """Return the most recent feature for this track."""
        return self.features[-1]


class DeepSort:
    """An optimized DeepSort tracker for real-time face recognition."""

    def __init__(self, max_age=30, n_init=3, max_cosine_distance=0.2):
        self.max_age = max_age  # Max frames to keep a track without updates
        self.n_init = n_init  # Min hits to consider a track confirmed
        self.max_cosine_distance = max_cosine_distance

        self.tracks = []
        self._next_id = 1
        self.kf = KalmanFilter()

    def _cosine_distance(self, tracks, detections):
        """Calculate cosine distance between track features and detection features."""
        if len(tracks) == 0 or len(detections) == 0:
            return np.empty((len(tracks), len(detections)))
        track_features = np.array([t.feature for t in tracks])
        det_features = np.array([d.feature for d in detections])
        # Cosine similarity is dot product of normalized vectors
        cost = 1.0 - np.dot(track_features, det_features.T)
        return cost

    def _match(self, detections):
        """Associate detections with existing tracks."""
        cost_matrix = self._cosine_distance(self.tracks, detections)
        if cost_matrix.size == 0:
            return [], list(range(len(self.tracks))), list(range(len(detections)))

        # Use Hungarian algorithm for optimal assignment
        matches_indices = linear_assignment(cost_matrix)

        # Separate matches from unmatched items
        unmatched_tracks = list(range(len(self.tracks)))
        unmatched_dets = list(range(len(detections)))
        for t, d in matches_indices:
            unmatched_tracks.remove(t)
            unmatched_dets.remove(d)

        # Filter out poor matches based on cosine distance threshold
        good_matches = []
        for t, d in matches_indices:
            if cost_matrix[t, d] > self.max_cosine_distance:
                unmatched_tracks.append(t)
                unmatched_dets.append(d)
            else:
                good_matches.append((t, d))

        return good_matches, unmatched_tracks, unmatched_dets

    def update(self, detections):
        """Run a full update cycle for the tracker."""
        # 1. Predict new locations for all existing tracks
        for track in self.tracks:
            track.predict(self.kf)

        # 2. Associate new detections with predicted tracks
        matches, unmatched_tracks, unmatched_dets = self._match(detections)

        # 3. Update tracks that were successfully matched
        for track_idx, det_idx in matches:
            self.tracks[track_idx].update(self.kf, detections[det_idx])

        # 4. Create new tracks for detections that couldn't be matched
        for det_idx in unmatched_dets:
            det = detections[det_idx]
            mean, cov = self.kf.initiate(det.bbox)
            track = Track(mean, cov, self._next_id, det.feature)
            self.tracks.append(track)
            self._next_id += 1

        # 5. Clean up old, un-updated tracks
        self.tracks = [
            t for t in self.tracks if t.time_since_update <= self.max_age
        ]

        # 6. Return only the confirmed tracks
        outputs = []
        for track in self.tracks:
            # A track is confirmed if it has been updated consistently
            if track.hits >= self.n_init and track.time_since_update == 0:
                outputs.append(
                    (track.track_id, track.to_tlbr(), track.feature)
                )
        return outputs