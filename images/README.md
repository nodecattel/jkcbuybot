# JKC Alert Images Directory

This directory contains images and GIFs used for JKC trading alerts.

## Current Images
- `alert_image_*.mp4` - Video alert files (if any)

## Recommended JKC Images
To enhance the JKC branding, consider adding:
- JKC logo images (PNG/JPG)
- JKC-themed trading GIFs
- JunkCoin promotional images
- Custom alert animations

## Image Requirements
- **Format**: PNG, JPG, GIF, MP4
- **Size**: Recommended max 10MB per file
- **Dimensions**: 512x512 or 1024x1024 for best Telegram display
- **Content**: JKC/JunkCoin themed content

## Usage
The bot will randomly select from available images in this directory for alerts.
If no images are found, it will fall back to the default `jkc_buy_alert.gif`.

## Adding New Images
1. Copy image files to this directory
2. Restart the bot container: `docker restart jkc-telebot-container`
3. Images will be automatically detected and used

## JKC Branding Guidelines
- Use JKC logo and colors
- Include "$JKC" ticker symbol
- Maintain professional appearance
- Avoid non-JKC references
