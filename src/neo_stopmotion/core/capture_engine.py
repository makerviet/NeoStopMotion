from __future__ import annotations
import glob
import os
import time
import cv2
import numpy as np
from loguru import logger


class CaptureError(RuntimeError):
    pass


class CaptureEngine:
    """Read frames from a USB webcam via OpenCV."""

    def __init__(
        self,
        webcam_index: int = 0,
        resolution: tuple[int, int] = (1280, 720),
        retry_count: int = 3,
        retry_delay_seconds: float = 1.0,
        onion_opacity: float = 0.30,
    ) -> None:
        self.webcam_index = webcam_index
        self.resolution = resolution
        self.retry_count = retry_count
        self.retry_delay_seconds = retry_delay_seconds
        self.onion_opacity = onion_opacity
        self._cap: cv2.VideoCapture | None = None
        self._last_frame: np.ndarray | None = None

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def _candidate_indexes(self) -> list[int]:
        """Webcam index cần thử: env NEO_STOPMOTION_WEBCAM_INDEX > index cấu hình +
        các /dev/video* CÓ THẬT. Trên Linux camera thật thường không ở index 0 (các node
        phụ như metadata/obsensor mở index 0 thất bại) nên cần dò."""
        env = os.environ.get("NEO_STOPMOTION_WEBCAM_INDEX", "")
        if env.strip().lstrip("-").isdigit():
            return [int(env)]
        others: list[int] = []
        for path in sorted(glob.glob("/dev/video*")):
            digits = "".join(filter(str.isdigit, os.path.basename(path)))
            if digits.isdigit() and int(digits) != self.webcam_index:
                others.append(int(digits))
        return [self.webcam_index] + others

    def open(self) -> None:
        # Ép backend V4L2 trên Linux: mở nhanh + tránh backend dò chậm (obsensor) gây
        # treo vài giây mỗi index. Nền khác (vd 0) dùng backend mặc định.
        backend = getattr(cv2, "CAP_V4L2", 0)
        candidates = self._candidate_indexes()
        last_err: Exception | None = None
        for attempt in range(1, self.retry_count + 1):
            for index in candidates:
                try:
                    cap = cv2.VideoCapture(index, backend) if backend else cv2.VideoCapture(index)
                    if cap.isOpened():
                        ok, _ = cap.read()      # xác nhận đọc được frame, không chỉ mở
                        if ok:
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                            self._cap = cap
                            self.webcam_index = index
                            logger.info(f"Webcam opened (index={index}, attempt={attempt})")
                            return
                    cap.release()
                except Exception as e:  # noqa: BLE001 - thử index kế tiếp
                    last_err = e
            logger.warning(f"Webcam open attempt {attempt} failed (tried {candidates})")
            time.sleep(self.retry_delay_seconds)
        raise CaptureError(
            f"Failed to open webcam (tried {candidates}) after {self.retry_count} retries"
        ) from last_err

    def capture_frame(self) -> np.ndarray:
        if self._cap is None:
            raise CaptureError("Webcam not opened")
        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise CaptureError("Failed to read frame from webcam")
        # IMPORTANT: store a RAW copy as last_frame for next onion skin,
        # but return the RAW frame (no blending) for saving to disk.
        self._last_frame = frame.copy()
        return frame

    def get_live_preview(self) -> np.ndarray | None:
        if self._cap is None:
            return None
        ret, current = self._cap.read()
        if not ret or current is None:
            return None
        if self._last_frame is None:
            return current
        return cv2.addWeighted(
            current, 1.0 - self.onion_opacity,
            self._last_frame, self.onion_opacity,
            0.0,
        )

    def set_last_frame(self, frame: np.ndarray | None) -> None:
        """Used after UNDO to reset onion skin source to the previous saved frame."""
        self._last_frame = frame.copy() if frame is not None else None

    def reset(self) -> None:
        self._last_frame = None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
