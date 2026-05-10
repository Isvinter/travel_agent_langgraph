from pathlib import Path
import logging
from app.state import ImageData

logger = logging.getLogger(__name__)


def load_images_from_directory(directory: str) -> list[ImageData]:
    image_data_list = []
    dir_path = Path(directory)
    if not dir_path.is_dir():
        logger.warning("Bildverzeichnis existiert nicht: %s", directory)
        return image_data_list
    for image_path in dir_path.glob('*.*'):
        if image_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
            image_data = ImageData(path=str(image_path))
            image_data_list.append(image_data)
    return image_data_list