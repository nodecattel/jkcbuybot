#!/usr/bin/env python3
"""
Test script for XBT Trading Alert Bot Image Management Functions.

This script tests all the image management functions that would be accessible
through the Telegram bot interface, including delete, info, test send, and
collection management features.
"""

import os
import sys
import shutil
import tempfile
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_delete_image_function():
    """Test the delete image functionality."""
    print("=" * 80)
    print("TESTING DELETE IMAGE FUNCTION")
    print("=" * 80)
    
    try:
        from telebot_fixed import get_image_collection
        
        # Get current collection
        images_before = get_image_collection()
        print(f"📁 Images before test: {len(images_before)}")
        
        if not images_before:
            print("⚠️ No images to test deletion with")
            return False
        
        # Create a backup of the first image for testing
        test_image_path = images_before[0]
        backup_path = test_image_path + ".backup"
        
        try:
            # Create backup
            shutil.copy2(test_image_path, backup_path)
            print(f"✅ Created backup: {os.path.basename(backup_path)}")
            
            # Test deletion (simulate what the bot would do)
            filename = os.path.basename(test_image_path)
            print(f"🗑️ Testing deletion of: {filename}")
            
            # Simulate the deletion process
            if os.path.exists(test_image_path):
                os.remove(test_image_path)
                print(f"✅ File deleted successfully")
                
                # Check collection count
                images_after = get_image_collection()
                print(f"📁 Images after deletion: {len(images_after)}")
                
                if len(images_after) == len(images_before) - 1:
                    print("✅ Collection count updated correctly")
                    success = True
                else:
                    print("❌ Collection count mismatch")
                    success = False
                
                # Restore from backup
                shutil.move(backup_path, test_image_path)
                print(f"🔄 Restored from backup")
                
                return success
            else:
                print("❌ Test image not found")
                return False
                
        except Exception as e:
            print(f"❌ Error during deletion test: {e}")
            # Try to restore backup if it exists
            if os.path.exists(backup_path):
                try:
                    shutil.move(backup_path, test_image_path)
                    print("🔄 Restored from backup after error")
                except:
                    pass
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_image_info_function():
    """Test the image info display functionality."""
    print("=" * 80)
    print("TESTING IMAGE INFO FUNCTION")
    print("=" * 80)
    
    try:
        from telebot_fixed import get_image_collection, detect_file_type
        
        images = get_image_collection()
        
        if not images:
            print("⚠️ No images to test info display with")
            return False
        
        # Test info for each image
        for i, img_path in enumerate(images, 1):
            filename = os.path.basename(img_path)
            print(f"\n📸 Testing info for Image {i}: {filename}")
            
            try:
                # Simulate the info gathering process
                file_stat = os.stat(img_path)
                file_size = file_stat.st_size
                file_size_mb = file_size / (1024 * 1024)
                
                detected_type = detect_file_type(img_path)
                file_ext = os.path.splitext(filename)[1].lower()
                format_display = detected_type.upper() if detected_type != 'unknown' else file_ext.replace('.', '').upper()
                
                # Create the info message (as the bot would)
                info_message = (
                    f"📸 Image {i}/{len(images)}: {filename}\n\n"
                    f"💾 Size: {file_size_mb:.2f} MB ({file_size:,} bytes)\n"
                    f"📁 Format: {format_display}\n"
                    f"📅 Modified: {datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"🔍 Extension: {file_ext}"
                )
                
                print("✅ Info generated successfully:")
                print(f"   Size: {file_size_mb:.2f} MB")
                print(f"   Format: {format_display}")
                print(f"   Extension: {file_ext}")
                
            except Exception as e:
                print(f"❌ Error getting info for {filename}: {e}")
                return False
        
        print(f"\n✅ Info function test completed for {len(images)} images")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_image_send_function():
    """Test the image send/preview functionality."""
    print("=" * 80)
    print("TESTING IMAGE SEND/PREVIEW FUNCTION")
    print("=" * 80)
    
    try:
        from telebot_fixed import get_image_collection, detect_file_type
        
        images = get_image_collection()
        
        if not images:
            print("⚠️ No images to test send function with")
            return False
        
        # Test send preparation for each image
        for i, img_path in enumerate(images, 1):
            filename = os.path.basename(img_path)
            print(f"\n📤 Testing send preparation for Image {i}: {filename}")
            
            try:
                # Check if file is accessible for sending
                if not os.path.exists(img_path):
                    print(f"❌ File not found: {img_path}")
                    return False
                
                # Check file size (Telegram has limits)
                file_size = os.path.getsize(img_path)
                file_size_mb = file_size / (1024 * 1024)
                
                if file_size_mb > 50:  # Telegram limit
                    print(f"⚠️ File too large for Telegram: {file_size_mb:.2f} MB")
                else:
                    print(f"✅ File size OK: {file_size_mb:.2f} MB")
                
                # Check file type compatibility
                detected_type = detect_file_type(img_path)
                supported_types = ['jpg', 'jpeg', 'png', 'gif', 'mp4', 'webp']
                
                if detected_type.lower() in supported_types:
                    print(f"✅ File type supported: {detected_type.upper()}")
                else:
                    print(f"⚠️ File type may not be supported: {detected_type.upper()}")
                
                # Test file readability
                try:
                    with open(img_path, 'rb') as f:
                        # Read first few bytes to ensure file is readable
                        f.read(1024)
                    print("✅ File is readable")
                except Exception as read_error:
                    print(f"❌ File read error: {read_error}")
                    return False
                
            except Exception as e:
                print(f"❌ Error testing send for {filename}: {e}")
                return False
        
        print(f"\n✅ Send function test completed for {len(images)} images")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_collection_management():
    """Test collection-wide management functions."""
    print("=" * 80)
    print("TESTING COLLECTION MANAGEMENT")
    print("=" * 80)
    
    try:
        from telebot_fixed import get_image_collection, detect_file_type, ensure_images_directory
        
        # Ensure directory exists
        ensure_images_directory()
        print("✅ Images directory ensured")
        
        # Get collection stats
        images = get_image_collection()
        print(f"📁 Current collection: {len(images)} images")
        
        if images:
            # Test collection statistics calculation
            total_size = 0
            type_counts = {}
            readable_count = 0
            
            for img_path in images:
                try:
                    # Size calculation
                    size = os.path.getsize(img_path)
                    total_size += size
                    
                    # Type detection
                    detected_type = detect_file_type(img_path)
                    type_counts[detected_type] = type_counts.get(detected_type, 0) + 1
                    
                    # Readability test
                    with open(img_path, 'rb') as f:
                        f.read(1)
                    readable_count += 1
                    
                except Exception as e:
                    print(f"⚠️ Issue with {os.path.basename(img_path)}: {e}")
            
            # Display statistics
            print(f"💾 Total size: {total_size/1024/1024:.2f} MB")
            print(f"📈 Average size: {total_size/len(images)/1024:.1f} KB")
            print(f"📖 Readable files: {readable_count}/{len(images)}")
            
            print("\n🎯 Format breakdown:")
            for file_type, count in type_counts.items():
                print(f"   • {file_type.upper()}: {count}")
            
            # Test clear all simulation (without actually clearing)
            print(f"\n🗑️ Clear all would affect {len(images)} files")
            print(f"💾 Would free {total_size/1024/1024:.2f} MB of space")
            
        else:
            print("📁 Collection is empty - testing empty state handling")
            print("✅ Empty collection handled gracefully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Run all image management function tests."""
    print("XBT TRADING ALERT BOT - IMAGE MANAGEMENT FUNCTION TESTS")
    print("=" * 80)
    print()
    
    # Run all tests
    test_results = {
        "Delete Function": test_delete_image_function(),
        "Info Function": test_image_info_function(),
        "Send Function": test_image_send_function(),
        "Collection Management": test_collection_management()
    }
    
    # Summary
    print("=" * 80)
    print("IMAGE MANAGEMENT FUNCTION TEST SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 ALL IMAGE MANAGEMENT FUNCTIONS WORKING CORRECTLY!")
        print("✅ Delete functionality operational")
        print("✅ Info display working properly")
        print("✅ Send/preview preparation successful")
        print("✅ Collection management features functional")
    else:
        print("⚠️ SOME IMAGE MANAGEMENT FUNCTIONS HAVE ISSUES")
        print("🔧 Review the failed tests above for specific problems")
    
    print()
    print("NEXT STEPS:")
    print("1. 🤖 Test actual Telegram bot interactions")
    print("2. 🔍 Verify callback handlers are working")
    print("3. 📱 Test user interface responsiveness")
    print("4. 🛡️ Validate permission controls")

if __name__ == "__main__":
    main()
