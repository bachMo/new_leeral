import cv2
import numpy as np

from app.ai.contracts import ImageQuality, QualityIssue
from app.ai.settings import AiSettings


def assess_quality(image: bytes, settings: AiSettings) -> ImageQuality:
    decoded = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if decoded is None:
        return ImageQuality(issue=QualityIssue.UNREADABLE)
    height, width = decoded.shape[:2]
    blur_score = float(cv2.Laplacian(decoded, cv2.CV_64F).var())
    brightness = float(decoded.mean())
    issue: QualityIssue | None = None
    if width < settings.quality_min_width or height < settings.quality_min_height:
        issue = QualityIssue.UNREADABLE
    elif brightness < settings.quality_min_brightness:
        issue = QualityIssue.TOO_DARK
    elif blur_score < settings.quality_blur_threshold:
        issue = QualityIssue.TOO_BLURRY
    return ImageQuality(
        issue=issue, blur_score=blur_score, brightness=brightness, width=width, height=height
    )
