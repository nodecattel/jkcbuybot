#!/usr/bin/env python3
"""
Test script to verify the /setimage command fixes
"""

import asyncio
import json
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

# Add the current directory to the path so we can import the bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the bot functions we need to test
from telebot_fixed import (
    set_image_command, 
    set_image_input, 
    get_random_image,
    get_image_collection,
    ensure_images_directory,
    INPUT_IMAGE_SETIMAGE,
    IMAGES_DIR
)

async def test_setimage_command():
    """Test the /setimage command response"""
    print("🧪 Testing /setimage command...")
    
    # Mock update and context
    update = MagicMock()
    update.effective_user.id = 1145064309  # Bot owner ID from config
    update.message.reply_text = AsyncMock()
    
    context = MagicMock()
    
    # Test the command
    result = await set_image_command(update, context)
    
    # Verify the response
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    
    assert "Please send the image you want to use for alerts" in call_args
    assert result == INPUT_IMAGE_SETIMAGE
    
    print("✅ /setimage command test passed!")
    return True

async def test_image_upload_processing():
    """Test image upload processing with different file types"""
    print("🧪 Testing image upload processing...")
    
    # Ensure images directory exists
    ensure_images_directory()
    
    # Test cases for different image types
    test_cases = [
        {
            "name": "Photo upload",
            "has_photo": True,
            "has_document": False,
            "has_animation": False,
            "expected_extension": ".jpg"
        },
        {
            "name": "Document upload (PNG)",
            "has_photo": False,
            "has_document": True,
            "has_animation": False,
            "document_name": "test.png",
            "expected_extension": ".png"
        },
        {
            "name": "Animation upload (GIF)",
            "has_photo": False,
            "has_document": False,
            "has_animation": True,
            "expected_extension": ".gif"
        }
    ]
    
    for test_case in test_cases:
        print(f"  Testing: {test_case['name']}")
        
        # Mock update and context
        update = MagicMock()
        update.effective_user.id = 1145064309
        update.message.reply_text = AsyncMock()
        
        # Mock the file objects
        mock_file = AsyncMock()
        mock_file.file_id = "test_file_id"
        mock_file.file_size = 12345
        mock_file.download_as_bytearray = AsyncMock(return_value=b"fake_image_data")
        
        # Set up the message based on test case
        if test_case["has_photo"]:
            photo_mock = MagicMock()
            photo_mock.get_file = AsyncMock(return_value=mock_file)
            update.message.photo = [photo_mock]  # List with one photo
            update.message.document = None
            update.message.animation = None
        elif test_case["has_document"]:
            document_mock = MagicMock()
            document_mock.get_file = AsyncMock(return_value=mock_file)
            document_mock.file_name = test_case.get("document_name", "test.jpg")
            update.message.photo = None
            update.message.document = document_mock
            update.message.animation = None
        elif test_case["has_animation"]:
            animation_mock = MagicMock()
            animation_mock.get_file = AsyncMock(return_value=mock_file)
            update.message.photo = None
            update.message.document = None
            update.message.animation = animation_mock
        
        context = MagicMock()
        
        # Test the function
        try:
            result = await set_image_input(update, context)
            
            # Verify success response
            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "✅" in call_args or "successfully" in call_args.lower()
            
            print(f"    ✅ {test_case['name']} test passed!")
            
        except Exception as e:
            print(f"    ❌ {test_case['name']} test failed: {e}")
            return False
    
    print("✅ Image upload processing tests passed!")
    return True

def test_default_image_fallback():
    """Test the default image fallback logic"""
    print("🧪 Testing default image fallback...")
    
    # Test when no images in collection
    default_image = get_random_image()
    
    if default_image:
        print(f"  Default image found: {default_image}")
        assert os.path.exists(default_image), f"Default image file doesn't exist: {default_image}"
        print("✅ Default image fallback test passed!")
        return True
    else:
        print("❌ No default image found!")
        return False

def test_image_collection():
    """Test image collection functionality"""
    print("🧪 Testing image collection...")
    
    # Get current collection
    images = get_image_collection()
    print(f"  Current image collection: {len(images)} images")
    
    for img in images:
        print(f"    - {img}")
        assert os.path.exists(img), f"Image file doesn't exist: {img}"
    
    print("✅ Image collection test passed!")
    return True

def test_images_directory():
    """Test images directory setup"""
    print("🧪 Testing images directory...")
    
    # Ensure directory exists
    ensure_images_directory()
    
    assert os.path.exists(IMAGES_DIR), f"Images directory doesn't exist: {IMAGES_DIR}"
    assert os.path.isdir(IMAGES_DIR), f"Images path is not a directory: {IMAGES_DIR}"
    
    # Check permissions
    assert os.access(IMAGES_DIR, os.W_OK), f"Images directory is not writable: {IMAGES_DIR}"
    
    print(f"  Images directory: {IMAGES_DIR}")
    print("✅ Images directory test passed!")
    return True

async def main():
    """Run all tests"""
    print("🚀 Starting /setimage functionality tests...\n")
    
    tests = [
        ("Images Directory Setup", test_images_directory),
        ("Default Image Fallback", test_default_image_fallback),
        ("Image Collection", test_image_collection),
        ("/setimage Command", test_setimage_command),
        ("Image Upload Processing", test_image_upload_processing),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
                
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print(f"\n{'='*50}")
    print(f"TEST SUMMARY: {passed}/{total} tests passed")
    print('='*50)
    
    if passed == total:
        print("🎉 All tests passed! The /setimage fixes are working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
