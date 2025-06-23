# 🚀 XBT Trading Alert Bot - Deployment Guide

## 📋 Overview

The `deploy.sh` script provides a complete one-command solution to rebuild and redeploy the XBT trading alert bot with all latest enhancements, including the GIF animation fixes we implemented.

---

## 🎬 Features Included

### **Latest Enhancements**
- ✅ **GIF Animation Support** - MP4 files sent as animations in alerts
- ✅ **Price Calculation Validation** - Mathematical accuracy ensured
- ✅ **Enhanced Debug Logging** - Comprehensive trade information
- ✅ **Image Management System** - Full `/list_images` functionality
- ✅ **Random Image Selection** - Seamless alert integration
- ✅ **Error Handling** - Robust edge case management

### **System Features**
- ✅ **Health Checks** - Automatic container health monitoring
- ✅ **Restart Policy** - Automatic restart on failure
- ✅ **Volume Persistence** - Logs, images, and config preserved
- ✅ **Clean Deployment** - Complete rebuild with latest code

---

## 🔧 Usage

### **Simple Deployment**
```bash
cd /home/n3k0h1m3/xbttelebot
./deploy.sh
```

### **What the Script Does**
1. **🛑 Cleanup**: Stops and removes existing container
2. **🔨 Build**: Creates fresh Docker image with latest code
3. **🚀 Deploy**: Starts container with full configuration
4. **✅ Verify**: Confirms deployment success and tests features
5. **📊 Report**: Provides comprehensive status summary

---

## 📊 Script Output

The script provides detailed, color-coded output showing:

- **🔵 Info Messages**: General information and progress
- **🟢 Success Messages**: Completed operations
- **🟡 Warning Messages**: Non-critical issues
- **🔴 Error Messages**: Critical failures (script will exit)

### **Example Output**
```
================================================================================
🎬 XBT TRADING ALERT BOT - COMPLETE DEPLOYMENT SCRIPT
================================================================================
🔧 Features: GIF Animation Support, Price Validation, Enhanced Logging
📅 Version: 2.0 - Animation Fixes Included
📂 Directory: /home/n3k0h1m3/xbttelebot
================================================================================

[2025-06-23 19:01:21] 🛑 STEP 1: Stopping and cleaning up existing container...
[2025-06-23 19:01:21] ✅ Container stopped successfully
[2025-06-23 19:01:21] ✅ Container removed successfully
[2025-06-23 19:01:21] ✅ Container cleanup verified

[2025-06-23 19:01:21] 🔨 STEP 2: Building fresh Docker image...
[2025-06-23 19:01:21] ✅ Docker image built successfully: xbt-telebot:latest

[2025-06-23 19:01:21] 🚀 STEP 3: Deploying container...
[2025-06-23 19:01:21] ✅ Container deployed successfully

[2025-06-23 19:01:21] ✅ STEP 4: Verifying deployment...
[2025-06-23 19:01:21] ✅ Container is running and healthy
[2025-06-23 19:01:21] ✅ GIF animation fix verified active

================================================================================
✅ DEPLOYMENT COMPLETED SUCCESSFULLY!
================================================================================
```

---

## 🔍 Verification Features

### **Automatic Checks**
- **Container Status**: Verifies container is running and healthy
- **Health Monitoring**: Confirms health checks are passing
- **Animation Fix**: Tests GIF animation detection functionality
- **Bot Initialization**: Confirms bot startup messages
- **WebSocket Connections**: Verifies real-time data connections

### **Manual Verification Commands**
```bash
# Check container status
docker ps | grep xbt-telebot-container

# View recent logs
docker logs xbt-telebot-container --tail 20

# Follow live logs
docker logs xbt-telebot-container -f

# Check health status
docker inspect --format='{{.State.Health.Status}}' xbt-telebot-container
```

---

## 📁 File Structure

### **Required Files**
- `telebot_fixed.py` - Main bot code with animation fixes
- `config.json` - Bot configuration
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container build instructions
- `deploy.sh` - This deployment script

### **Volume Mounts**
- `./logs:/app/logs` - Persistent logging
- `./images:/app/images` - Image collection storage
- `./config.json:/app/config.json` - Configuration file

---

## ⚠️ Prerequisites

### **System Requirements**
- Docker installed and running
- Bash shell (Linux/macOS)
- Sufficient disk space for Docker image (~500MB)
- Network access for Docker image pulls

### **File Permissions**
```bash
# Make script executable (if not already)
chmod +x deploy.sh

# Verify permissions
ls -la deploy.sh
# Should show: -rwxrwxr-x
```

---

## 🛠️ Troubleshooting

### **Common Issues**

#### **Permission Denied**
```bash
# Fix script permissions
chmod +x deploy.sh
```

#### **Docker Not Running**
```bash
# Start Docker service
sudo systemctl start docker
```

#### **Container Build Fails**
```bash
# Check Docker space
docker system df

# Clean up if needed
docker system prune
```

#### **Container Won't Start**
```bash
# Check logs for errors
docker logs xbt-telebot-container

# Verify config file exists
ls -la config.json
```

### **Manual Recovery**
If the script fails, you can manually run individual steps:

```bash
# Stop container
docker stop xbt-telebot-container

# Remove container
docker rm xbt-telebot-container

# Build image
docker build -t xbt-telebot:latest .

# Run container
docker run -d \
  --name xbt-telebot-container \
  --restart unless-stopped \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/images:/app/images" \
  -v "$(pwd)/config.json:/app/config.json" \
  --health-cmd="python3 -c 'import sys; sys.exit(0)'" \
  --health-interval=60s \
  --health-timeout=10s \
  --health-start-period=30s \
  --health-retries=3 \
  xbt-telebot:latest
```

---

## 📈 Post-Deployment

### **Immediate Actions**
1. **Monitor Logs**: Watch for successful initialization
2. **Test Commands**: Try `/list_images` to verify animation support
3. **Check Alerts**: Verify animations work when threshold is triggered
4. **Validate Calculations**: Monitor price calculation validation in logs

### **Ongoing Monitoring**
```bash
# Monitor container health
watch 'docker ps | grep xbt-telebot-container'

# Track resource usage
docker stats xbt-telebot-container

# Monitor log file growth
ls -lh logs/
```

---

## 🎯 Success Indicators

### **Deployment Success**
- ✅ Script completes without errors
- ✅ Container shows "healthy" status
- ✅ Bot reports "ready to receive commands"
- ✅ Animation fix verification passes
- ✅ WebSocket connections established

### **Runtime Success**
- ✅ `/list_images` command works with animations
- ✅ Price calculation validation active in logs
- ✅ Real-time trade processing visible
- ✅ Alert system delivers animated content

---

## 📞 Support

### **Log Locations**
- **Container Logs**: `docker logs xbt-telebot-container`
- **Persistent Logs**: `./logs/xbt_telebot_*.log`
- **Build Logs**: Displayed during script execution

### **Key Commands**
```bash
# Quick status check
./deploy.sh && docker ps | grep xbt-telebot

# Full system check
docker logs xbt-telebot-container --tail 50 | grep -E "(Bot started|Animation|ERROR)"

# Restart if needed
docker restart xbt-telebot-container
```

---

**The deployment script ensures a reliable, repeatable process for deploying the XBT trading alert bot with all latest enhancements and fixes.** 🎉
