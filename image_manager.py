"""
Image Management Module for JKC Trading Bot

This module handles all image-related functionality including image collection management,
random image selection, file type detection, and image processing for alert messages.
"""

import os
import io
import glob
import random
import logging
from typing import Optional, List

try:
    from telegram import InputFile
    TELEGRAM_AVAILABLE = True
except ImportError:
    # Handle missing telegram dependency gracefully
    InputFile = None
    TELEGRAM_AVAILABLE = False

from config import get_image_path

# Set up module logger
logger = logging.getLogger(__name__)

# Image collection constants
IMAGES_DIR = "images"
SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webp"]

def ensure_images_directory() -> None:
    """
    Ensure the images directory exists, create it if it doesn't.
    """
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)
        logger.info(f"Created images directory: {IMAGES_DIR}")

def detect_file_type(file_path: str) -> str:
    """
    Detect file type based on file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: File type/extension without the dot
    """
    if not os.path.exists(file_path):
        return 'unknown'
    
    ext = os.path.splitext(file_path)[1].lower()
    return ext.replace('.', '') if ext else 'unknown'

def get_image_collection() -> List[str]:
    """
    Get list of all images in the collection.
    
    Returns:
        List[str]: List of image file paths
    """
    ensure_images_directory()
    images = []
    
    for ext in SUPPORTED_IMAGE_FORMATS:
        pattern = os.path.join(IMAGES_DIR, f"*{ext}")
        images.extend(glob.glob(pattern))
        # Also check uppercase extensions
        pattern = os.path.join(IMAGES_DIR, f"*{ext.upper()}")
        images.extend(glob.glob(pattern))
    
    # Remove duplicates and sort
    images = sorted(list(set(images)))
    logger.debug(f"Found {len(images)} images in collection")
    
    return images

def get_random_image() -> Optional[str]:
    """
    Get a random image from the collection.
    
    Returns:
        Optional[str]: Path to random image or None if no images available
    """
    images = get_image_collection()

    # If no images in collection, try to use the default image
    if not images:
        # Try multiple possible default image paths
        default_paths = [
            get_image_path(),  # From config
            "jkcbuy.GIF",  # Actual file name
            "jkc_buy_alert.gif",  # Config file name
            os.path.join(os.getcwd(), "jkcbuy.GIF"),  # Full path
        ]

        for path in default_paths:
            if os.path.exists(path):
                logger.info(f"Using default image: {path}")
                return path

        logger.warning("No images found in collection and no default image exists")
        return None

    # Return random image from collection
    selected_image = random.choice(images)
    logger.debug(f"Selected random image: {selected_image}")
    return selected_image

def load_random_image() -> Optional[InputFile]:
    """
    Load a random image as InputFile for Telegram.
    
    Returns:
        Optional[InputFile]: Telegram InputFile object or None if no images available
    """
    image_path = get_random_image()
    if not image_path:
        return None

    try:
        with open(image_path, 'rb') as photo:
            img = photo.read()
            filename = os.path.basename(image_path)
            return InputFile(io.BytesIO(img), filename=filename)
    except Exception as e:
        logger.error(f"Error loading image {image_path}: {e}")
        return None

def is_animation(file_path: str) -> bool:
    """
    Check if a file is an animation (GIF or MP4).
    
    Args:
        file_path: Path to the file
        
    Returns:
        bool: True if file is an animation, False otherwise
    """
    if not os.path.exists(file_path):
        return False
    
    filename = os.path.basename(file_path).lower()
    detected_type = detect_file_type(file_path)
    
    return filename.endswith(('.gif', '.mp4')) or detected_type == 'mp4'

def get_image_stats() -> dict:
    """
    Get statistics about the image collection.
    
    Returns:
        dict: Statistics including count, total size, and type breakdown
    """
    images = get_image_collection()
    
    if not images:
        return {
            'count': 0,
            'total_size': 0,
            'total_size_mb': 0.0,
            'type_counts': {},
            'animations': 0
        }
    
    total_size = 0
    type_counts = {}
    animations = 0
    
    for img_path in images:
        try:
            size = os.path.getsize(img_path)
            total_size += size
            
            detected_type = detect_file_type(img_path)
            type_counts[detected_type] = type_counts.get(detected_type, 0) + 1
            
            if is_animation(img_path):
                animations += 1
                
        except Exception as e:
            logger.warning(f"Error analyzing {img_path}: {e}")
    
    return {
        'count': len(images),
        'total_size': total_size,
        'total_size_mb': total_size / (1024 * 1024),
        'type_counts': type_counts,
        'animations': animations
    }

def save_image_to_collection(image_data: bytes, filename: str) -> str:
    """
    Save image data to the collection directory.
    
    Args:
        image_data: Raw image data
        filename: Filename for the image
        
    Returns:
        str: Path to the saved image
        
    Raises:
        Exception: If saving fails
    """
    ensure_images_directory()
    
    image_path = os.path.join(IMAGES_DIR, filename)
    
    with open(image_path, 'wb') as f:
        f.write(image_data)
    
    logger.info(f"Successfully saved image to: {image_path}")
    return image_path

def delete_image_from_collection(image_path: str) -> bool:
    """
    Delete an image from the collection.
    
    Args:
        image_path: Path to the image to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
            logger.info(f"Deleted image: {image_path}")
            return True
        else:
            logger.warning(f"Image not found for deletion: {image_path}")
            return False
    except Exception as e:
        logger.error(f"Error deleting image {image_path}: {e}")
        return False

def clear_image_collection() -> int:
    """
    Clear all images from the collection.
    
    Returns:
        int: Number of images deleted
    """
    images = get_image_collection()
    deleted_count = 0
    
    for image_path in images:
        if delete_image_from_collection(image_path):
            deleted_count += 1
    
    logger.info(f"Cleared {deleted_count} images from collection")
    return deleted_count

def get_image_info(image_path: str) -> dict:
    """
    Get detailed information about an image file.
    
    Args:
        image_path: Path to the image
        
    Returns:
        dict: Image information including size, type, etc.
    """
    if not os.path.exists(image_path):
        return {'exists': False}
    
    try:
        stat = os.stat(image_path)
        return {
            'exists': True,
            'path': image_path,
            'filename': os.path.basename(image_path),
            'size': stat.st_size,
            'size_mb': stat.st_size / (1024 * 1024),
            'modified': stat.st_mtime,
            'type': detect_file_type(image_path),
            'is_animation': is_animation(image_path)
        }
    except Exception as e:
        logger.error(f"Error getting image info for {image_path}: {e}")
        return {'exists': False, 'error': str(e)}

def validate_image_format(filename: str) -> bool:
    """
    Validate if a filename has a supported image format.
    
    Args:
        filename: Filename to validate
        
    Returns:
        bool: True if format is supported, False otherwise
    """
    ext = os.path.splitext(filename.lower())[1]
    return ext in SUPPORTED_IMAGE_FORMATS

def generate_unique_filename(base_name: str, extension: str) -> str:
    """
    Generate a unique filename with timestamp.
    
    Args:
        base_name: Base name for the file
        extension: File extension (with or without dot)
        
    Returns:
        str: Unique filename
    """
    import time
    
    if not extension.startswith('.'):
        extension = '.' + extension
    
    timestamp = int(time.time())
    return f"{base_name}_{timestamp}{extension}"
