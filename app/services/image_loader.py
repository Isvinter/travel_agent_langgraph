from pathlib import Path
from app.state import ImageData


def load_images_from_directory(directory: str) -> list[ImageData]:
    image_data_list = []
    for image_path in Path(directory).glob('*.*'):
        if image_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
            image_data = ImageData(path=str(image_path))
            image_data_list.append(image_data)
    return image_data_list