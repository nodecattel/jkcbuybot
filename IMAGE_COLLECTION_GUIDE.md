# XBT Bot Image Collection Management Guide

## 📁 Image Collection System Overview

The XBT Telegram bot includes a sophisticated image collection system that allows admins to upload multiple alert images for varied visual alerts. The system randomly selects images from the collection for each alert, providing dynamic and engaging notifications.

## 🎯 Current Collection Status

**✅ POPULATED:** The image collection has been pre-populated with 4 Bitcoin Classic (XBT) themed images:

1. **alert_image_1750647001.gif** (1.2MB) - Animated XBT buy alert GIF
2. **alert_image_1750647002.gif** (1.2MB) - Alternative animated XBT GIF  
3. **alert_image_1750647003.jpg** (46KB) - Static XBT resized image
4. **alert_image_1750647005.jpg** (Various) - Backup XBT image

## 🔧 Admin Commands Available

### `/setimage` - Upload New Images
**Purpose:** Add new images to the collection
**Access:** Admin only
**Usage:**
1. Send `/setimage` command to the bot
2. Bot will prompt: "Please send me the image you want to use for alerts"
3. Upload any photo/image (PNG, JPG, JPEG, GIF supported)
4. Bot will save it with timestamp naming: `alert_image_TIMESTAMP.jpg`
5. Image is added to collection for random selection

### `/list_images` - View Collection
**Purpose:** Display all images in the collection with details
**Access:** Admin only
**Usage:**
- Send `/list_images` command
- Bot shows numbered list with filenames and file sizes
- Example output:
```
📁 Image Collection (4 images)

1. alert_image_1750647001.gif (1177.9 KB)
2. alert_image_1750647002.gif (1177.9 KB)
3. alert_image_1750647003.jpg (45.8 KB)
4. alert_image_1750647005.jpg (XX.X KB)

🎲 Images are randomly selected for alerts
```

### `/clear_images` - Reset Collection
**Purpose:** Remove all images from collection
**Access:** Admin only
**Usage:**
- Send `/clear_images` command
- Bot will delete all images in collection
- Default image will be used for alerts until new images are uploaded

## 🎲 Random Selection System

**How it works:**
- Each alert randomly selects an image from the collection
- If collection is empty, falls back to default `xbt_buy_alert.gif`
- Provides visual variety and keeps alerts engaging
- No duplicate prevention - same image can be selected multiple times

## 📋 Supported Image Formats

- **PNG** - High quality static images
- **JPG/JPEG** - Compressed static images (recommended for file size)
- **GIF** - Animated images (automatically detected and sent as animations)

## 🔒 Security Features

- **Admin Only Access:** All image commands require admin permissions
- **File Validation:** Only image files are accepted
- **Size Management:** File sizes are tracked and displayed
- **Safe Storage:** Images stored in isolated directory

## 📱 Step-by-Step Upload Process

### For Telegram Mobile App:
1. Open chat with XBT bot
2. Type `/setimage` and send
3. Bot responds: "Please send me the image..."
4. Tap attachment button (📎)
5. Select "Photo & Video"
6. Choose image from gallery or take new photo
7. Send the image
8. Bot confirms: "✅ Image uploaded successfully..."

### For Telegram Desktop:
1. Open chat with XBT bot
2. Type `/setimage` and send
3. Bot responds: "Please send me the image..."
4. Drag and drop image file into chat, OR
5. Click attachment button and select image file
6. Send the image
7. Bot confirms successful upload

## 🧪 Testing the Collection

### Test Random Selection:
1. Use `/test` command (admin only)
2. Bot will simulate an alert with random image from collection
3. Verify different images appear on multiple test runs

### Verify Collection:
1. Use `/list_images` to see all uploaded images
2. Check file sizes and names are correct
3. Ensure collection shows expected number of images

## 🚨 Alert Integration

**Automatic Usage:**
- All trading alerts automatically use random image selection
- Large trade alerts (above threshold) trigger with random images
- Orderbook sweep detection alerts use random images
- Manual test alerts use random images

**Image Display:**
- GIF files: Sent as animations (preserves animation)
- Static files: Sent as photos
- Proper filename preservation for identification

## 🔧 Troubleshooting

### "Image collection is empty"
- **Solution:** Upload images using `/setimage` command
- **Fallback:** Bot uses default `xbt_buy_alert.gif`

### Upload fails
- **Check:** Ensure you have admin permissions
- **Check:** File is a valid image format (PNG/JPG/JPEG/GIF)
- **Check:** File size is reasonable (under 20MB recommended)

### Images not displaying
- **Check:** Use `/list_images` to verify upload was successful
- **Check:** Test with `/test` command to see if images appear
- **Check:** Ensure bot has proper file permissions

## 📊 Collection Management Best Practices

1. **Variety:** Upload mix of static and animated images
2. **Relevance:** Keep images Bitcoin Classic/XBT themed
3. **Quality:** Use appropriate resolution (not too large/small)
4. **File Size:** Balance quality vs file size for fast loading
5. **Regular Updates:** Refresh collection periodically with new images

## 🎯 Recommended Collection Size

- **Minimum:** 3-5 images for basic variety
- **Optimal:** 8-12 images for good randomization
- **Maximum:** No hard limit, but consider storage and performance

## 🔄 Current Status Commands

- **Check Collection:** `/list_images`
- **Test Alerts:** `/test` 
- **Add Images:** `/setimage`
- **Reset Collection:** `/clear_images`

---

**✅ The image collection system is now fully operational and ready for use!**
