"""Pré-processamento conservador de fotos de fichas manuscritas.

O original nunca é substituído. O resultado é um derivado usado para análise,
com alertas de qualidade para orientar o reenvio da foto quando necessário.
"""

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps


@dataclass
class PreprocessedImage:
    data: bytes
    mime_type: str
    quality_score: float
    warnings: list[str]
    rotation_degrees: float = 0.0
    perspective_corrected: bool = False


def preprocess_image(data: bytes, mime_type: str, *, max_dimension: int = 2600) -> PreprocessedImage:
    """Corrige somente problemas seguros: orientação EXIF, escala, rotação leve e contraste moderado."""
    image = Image.open(BytesIO(data))
    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) > max_dimension:
        ratio = max_dimension / max(image.size)
        image = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))), Image.Resampling.LANCZOS)
    cv2 = _load_cv2()
    if cv2 is None:
        return _encode(image, mime_type, _quality_fallback(image), ["OpenCV indisponível; apenas orientação e escala foram aplicadas."])

    import numpy as np

    array = np.array(image)
    gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    warnings = []
    score = _quality_score(gray, cv2)
    if score < 0.35:
        warnings.append("A imagem tem baixa nitidez ou iluminação irregular; revise com atenção.")
    if min(image.size) < 900:
        warnings.append("A menor dimensão da imagem é baixa para leitura manuscrita.")

    rotated, degrees = _deskew(array, gray, cv2)
    warped, corrected = _perspective(array if rotated is None else rotated, cv2)
    working = warped if corrected else (rotated if rotated is not None else array)
    working_gray = cv2.cvtColor(working, cv2.COLOR_RGB2GRAY)
    # CLAHE moderado mantém traços de lápis; não binariza nem remove detalhes finos.
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(working_gray)
    output = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
    return _encode(Image.fromarray(output), mime_type, score, warnings, degrees, corrected)


def crop_region(data: bytes, region: dict):
    """Recorta uma região normalizada (0..1) para conferência visual."""
    image = Image.open(BytesIO(data)).convert("RGB")
    x = max(0, min(image.width, int(float(region.get("x", 0)) * image.width)))
    y = max(0, min(image.height, int(float(region.get("y", 0)) * image.height)))
    right = max(x + 1, min(image.width, int((float(region.get("x", 0)) + float(region.get("width", 1))) * image.width)))
    bottom = max(y + 1, min(image.height, int((float(region.get("y", 0)) + float(region.get("height", 1))) * image.height)))
    output = BytesIO()
    image.crop((x, y, right, bottom)).save(output, format="PNG", optimize=True)
    return output.getvalue()


def _load_cv2():
    try:
        import cv2

        return cv2
    except ImportError:
        return None


def _quality_fallback(image):
    return min(1.0, max(0.0, min(image.size) / 1800))


def _quality_score(gray, cv2):
    sharpness = min(1.0, float(cv2.Laplacian(gray, cv2.CV_64F).var()) / 500.0)
    brightness = float(gray.mean()) / 255.0
    exposure = max(0.0, 1.0 - abs(brightness - 0.58) / 0.58)
    return round(max(0.0, min(1.0, 0.7 * sharpness + 0.3 * exposure)), 4)


def _deskew(array, gray, cv2):
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, 3.14159 / 180, threshold=100, minLineLength=max(100, gray.shape[1] // 4), maxLineGap=20)
    if lines is None:
        return None, 0.0
    angles = []
    for line in lines.reshape(-1, 4):
        x1, y1, x2, y2 = line
        angle = __import__("math").degrees(__import__("math").atan2(y2 - y1, x2 - x1))
        if -15 < angle < 15:
            angles.append(angle)
    if not angles:
        return None, 0.0
    angle = sum(angles) / len(angles)
    if abs(angle) < 0.8:
        return None, 0.0
    center = (array.shape[1] / 2, array.shape[0] / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(array, matrix, (array.shape[1], array.shape[0]), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, round(angle, 2)


def _perspective(array, cv2):
    gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    area = array.shape[0] * array.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) != 4 or cv2.contourArea(polygon) < area * 0.45:
            continue
        points = _order_points(polygon.reshape(4, 2))
        width = int(max(__import__("numpy").linalg.norm(points[0] - points[1]), __import__("numpy").linalg.norm(points[2] - points[3])))
        height = int(max(__import__("numpy").linalg.norm(points[0] - points[3]), __import__("numpy").linalg.norm(points[1] - points[2])))
        destination = __import__("numpy").array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
        matrix = cv2.getPerspectiveTransform(points.astype("float32"), destination)
        return cv2.warpPerspective(array, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE), True
    return array, False


def _order_points(points):
    import numpy as np

    ordered = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(sums)]
    ordered[2] = points[np.argmax(sums)]
    ordered[1] = points[np.argmin(diffs)]
    ordered[3] = points[np.argmax(diffs)]
    return ordered


def _encode(image, mime_type, score, warnings, degrees=0.0, corrected=False):
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return PreprocessedImage(output.getvalue(), "image/png", round(score, 4), warnings, degrees, corrected)
