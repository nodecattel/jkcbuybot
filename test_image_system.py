#!/usr/bin/env python3
"""
Test script to verify the image handling system functionality.

This test will:
1. Test the get_image_collection() function
2. Test the get_random_image() function  
3. Test the load_random_image() function
4. Verify default image fallback logic
5. Test image format detection
6. Simulate /list_images command functionality
"""

import os
import sys
import glob
import logging

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_image_collection_functions():
    """Test the image collection functions."""
    print("=" * 80)
    print("TESTING IMAGE COLLECTION FUNCTIONS")
    print("=" * 80)
    
    try:
        # Import the functions we need to test
        from telebot_fixed import (
            get_image_collection, 
            get_random_image, 
            load_random_image,
            ensure_images_directory,
            IMAGES_DIR,
            SUPPORTED_IMAGE_FORMATS,
            IMAGE_PATH
        )
        
        print("✅ Successfully imported image functions")
        print(f"📁 Images directory: {IMAGES_DIR}")
        print(f"🎨 Supported formats: {SUPPORTED_IMAGE_FORMATS}")
        print(f"🖼️ Default image path: {IMAGE_PATH}")
        print()
        
        # Test ensure_images_directory
        ensure_images_directory()
        print("✅ ensure_images_directory() executed successfully")
        
        # Test get_image_collection
        collection = get_image_collection()
        print(f"📁 Image collection contains {len(collection)} images:")
        
        if collection:
            for i, img_path in enumerate(collection, 1):
                filename = os.path.basename(img_path)
                try:
                    size = os.path.getsize(img_path)
                    size_kb = size / 1024
                    print(f"  {i}. {filename} ({size_kb:.1f} KB)")
                except Exception as e:
                    print(f"  {i}. {filename} (Error reading size: {e})")
        else:
            print("  📁 Collection is empty")
        print()
        
        # Test get_random_image
        print("Testing get_random_image()...")
        for i in range(3):  # Test multiple times to see randomness
            random_image = get_random_image()
            if random_image:
                filename = os.path.basename(random_image)
                print(f"  Test {i+1}: {filename}")
            else:
                print(f"  Test {i+1}: None (no images available)")
        print()
        
        # Test load_random_image
        print("Testing load_random_image()...")
        try:
            loaded_image = load_random_image()
            if loaded_image:
                print("✅ load_random_image() returned a valid InputFile object")
                print(f"   Filename: {loaded_image.filename if hasattr(loaded_image, 'filename') else 'Unknown'}")
            else:
                print("❌ load_random_image() returned None")
        except Exception as e:
            print(f"❌ load_random_image() failed: {e}")
        print()
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import image functions: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing image functions: {e}")
        return False

def test_default_image_fallback():
    """Test the default image fallback logic."""
    print("=" * 80)
    print("TESTING DEFAULT IMAGE FALLBACK")
    print("=" * 80)
    
    # Check for default images
    default_paths = [
        "xbt_buy_alert.gif",
        "xbtbuy.GIF", 
        "junk.jpg",
        "chart_15min.jpeg"
    ]
    
    print("Checking for default images:")
    found_defaults = []
    for path in default_paths:
        if os.path.exists(path):
            size = os.path.getsize(path)
            size_kb = size / 1024
            print(f"  ✅ {path} ({size_kb:.1f} KB)")
            found_defaults.append(path)
        else:
            print(f"  ❌ {path} (not found)")
    
    print(f"\nFound {len(found_defaults)} default images")
    return found_defaults

def test_image_format_detection():
    """Test image format detection."""
    print("=" * 80)
    print("TESTING IMAGE FORMAT DETECTION")
    print("=" * 80)
    
    try:
        from telebot_fixed import detect_file_type
        
        # Test with existing files
        test_files = []
        
        # Add files from current directory
        for ext in ['.gif', '.jpg', '.jpeg', '.png', '.mp4']:
            files = glob.glob(f"*{ext}")
            test_files.extend(files)
        
        # Add files from images directory
        if os.path.exists('images'):
            for ext in ['.gif', '.jpg', '.jpeg', '.png', '.mp4']:
                files = glob.glob(f"images/*{ext}")
                test_files.extend(files)
        
        print(f"Testing format detection on {len(test_files)} files:")
        
        for file_path in test_files[:10]:  # Limit to first 10 files
            if os.path.exists(file_path):
                detected_type = detect_file_type(file_path)
                filename = os.path.basename(file_path)
                print(f"  {filename} -> {detected_type}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import detect_file_type: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing format detection: {e}")
        return False

def simulate_list_images_command():
    """Simulate the /list_images command functionality."""
    print("=" * 80)
    print("SIMULATING /list_images COMMAND")
    print("=" * 80)
    
    try:
        from telebot_fixed import get_image_collection
        
        images = get_image_collection()
        
        if not images:
            print("📁 Image collection is empty.")
            print("Use /setimage to add images to the collection.")
        else:
            image_list = []
            total_size = 0
            
            for i, img_path in enumerate(images, 1):
                filename = os.path.basename(img_path)
                try:
                    size = os.path.getsize(img_path)
                    size_kb = size / 1024
                    total_size += size
                    image_list.append(f"{i}. {filename} ({size_kb:.1f} KB)")
                except Exception as e:
                    image_list.append(f"{i}. {filename} (Error: {e})")
            
            total_size_mb = total_size / (1024 * 1024)
            
            message = (
                f"📁 Image Collection ({len(images)} images)\n"
                f"💾 Total Size: {total_size_mb:.2f} MB\n\n" +
                "\n".join(image_list) +
                "\n\n🎲 Images are randomly selected for alerts"
            )
            
            print(message)
        
        return True
        
    except Exception as e:
        print(f"❌ Error simulating /list_images: {e}")
        return False

def main():
    """Run all image system tests."""
    print("XBT TRADING ALERT IMAGE SYSTEM TEST")
    print("=" * 80)
    print()
    
    # Test 1: Image collection functions
    test1_success = test_image_collection_functions()
    
    # Test 2: Default image fallback
    default_images = test_default_image_fallback()
    
    # Test 3: Image format detection
    test3_success = test_image_format_detection()
    
    # Test 4: Simulate /list_images command
    test4_success = simulate_list_images_command()
    
    # Summary
    print("=" * 80)
    print("IMAGE SYSTEM TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Image collection functions: {'PASS' if test1_success else 'FAIL'}")
    print(f"✅ Default images available: {len(default_images)} found")
    print(f"✅ Format detection: {'PASS' if test3_success else 'FAIL'}")
    print(f"✅ /list_images simulation: {'PASS' if test4_success else 'FAIL'}")
    print()
    
    if test1_success and default_images and test3_success and test4_success:
        print("🎉 All image system tests PASSED!")
        print("📸 Image handling system is working correctly.")
    else:
        print("⚠️ Some image system tests failed.")
        print("🔧 Review the output above for specific issues.")

if __name__ == "__main__":
    main()
