# 🐳 XBT Bot Docker Deployment Guide

## **🎉 BUILD COMPLETE - READY FOR DEPLOYMENT**

The Docker image has been successfully built and is ready for deployment. However, **a unique Telegram bot token is required** before the container can be deployed.

---

## **⚠️ CRITICAL: TELEGRAM BOT TOKEN REQUIRED**

### **Current Status:**
- ✅ Docker image built: `xbt-telebot:latest` (956MB)
- ✅ All dependencies installed and tested
- ✅ GIF integration ready
- ✅ WebSocket architecture restored
- ❌ **MISSING: Unique Telegram bot token**

### **REQUIRED ACTION:**
**You must create a new Telegram bot token before deployment to avoid conflicts with the JKC bot.**

---

## **STEP 1: CREATE NEW TELEGRAM BOT TOKEN**

### **Quick Setup:**
1. **Open Telegram** and message `@BotFather`
2. **Send:** `/newbot`
3. **Bot Name:** `Bitcoin Classic (XBT) Alert Bot`
4. **Username:** `xbt_alert_bot` (or similar ending in `_bot`)
5. **Copy the token** (format: `XXXXXXXXX:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`)

### **Automated Token Update:**
```bash
# Run the token update script
python3 update_bot_token.py

# Follow the prompts to enter your new token
# The script will validate and update config.json automatically
```

---

## **STEP 2: DEPLOY WITH DOCKER COMPOSE**

### **Option A: Automated Deployment (Recommended)**
```bash
# Run the automated deployment script
./deploy_xbt_bot.sh

# This will:
# - Validate configuration
# - Create necessary directories
# - Deploy the container
# - Run health checks
# - Show status and logs
```

### **Option B: Manual Docker Compose Deployment**
```bash
# Create necessary directories
mkdir -p logs images backups

# Deploy using Docker Compose
docker-compose -f docker-compose.xbt.yml up -d

# Check status
docker ps | grep xbt-telebot
```

### **Option C: Direct Docker Run**
```bash
# Create directories
mkdir -p logs images backups

# Run container with volume mounts
docker run -d \
  --name xbt-telebot-container \
  --restart unless-stopped \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/logs:/app/logs:rw \
  -v $(pwd)/images:/app/images:rw \
  -e TZ=UTC \
  xbt-telebot:latest
```

---

## **STEP 3: VERIFY DEPLOYMENT**

### **Check Container Status:**
```bash
# View running containers
docker ps | grep xbt-telebot

# Check container health
docker inspect xbt-telebot-container | grep Health -A 10

# View recent logs
docker logs --tail 20 xbt-telebot-container
```

### **Monitor Startup:**
```bash
# Follow logs in real-time
docker logs -f xbt-telebot-container

# Look for these success indicators:
# ✅ "Bot started successfully"
# ✅ "Exchange availability monitor started"
# ✅ "WebSocket connections activated"
# ✅ "LiveCoinWatch API working"
```

---

## **STEP 4: TEST BOT FUNCTIONALITY**

### **Basic Tests:**
1. **Start bot in Telegram:**
   - Find your bot: `@xbt_alert_bot` (or your chosen username)
   - Send: `/start`
   - Expected: Welcome message with XBT branding

2. **Test GIF alerts:**
   - Send: `/test` (admin only)
   - Expected: Animated GIF alert displays

3. **Test price data:**
   - Send: `/price`
   - Expected: Current XBT price from LiveCoinWatch

4. **Test commands:**
   - Send: `/help`
   - Expected: List of available commands

### **Advanced Tests:**
```bash
# Test configuration loading in container
docker exec xbt-telebot-container python3 -c "import json; print('Config:', json.load(open('config.json'))['image_path'])"

# Test GIF file accessibility
docker exec xbt-telebot-container ls -la xbt_buy_alert.gif

# Test WebSocket availability detection
docker exec xbt-telebot-container python3 -c "from telebot_fixed import check_exchange_availability; import asyncio; print(asyncio.run(check_exchange_availability()))"
```

---

## **STEP 5: PRODUCTION MONITORING**

### **Container Management:**
```bash
# Stop container
docker stop xbt-telebot-container

# Start container
docker start xbt-telebot-container

# Restart container
docker restart xbt-telebot-container

# View resource usage
docker stats xbt-telebot-container
```

### **Log Management:**
```bash
# View logs
docker logs xbt-telebot-container

# Follow logs
docker logs -f xbt-telebot-container

# View specific log files
ls -la logs/xbt_telebot_*.log
tail -f logs/xbt_telebot_*.log
```

### **Health Monitoring:**
```bash
# Check health status
docker inspect xbt-telebot-container | grep -A 5 '"Health"'

# Manual health check
docker exec xbt-telebot-container python3 -c "import requests; print('Health:', requests.get('https://api.telegram.org/bot$(cat config.json | grep bot_token | cut -d'\"' -f4)/getMe').status_code)"
```

---

## **TROUBLESHOOTING**

### **Common Issues:**

1. **Container won't start:**
   ```bash
   # Check logs for errors
   docker logs xbt-telebot-container
   
   # Verify config.json has valid token
   cat config.json | grep bot_token
   ```

2. **Bot not responding in Telegram:**
   ```bash
   # Check if bot process is running
   docker exec xbt-telebot-container pgrep -f "python3 telebot_fixed.py"
   
   # Test token validity
   docker exec xbt-telebot-container python3 update_bot_token.py
   ```

3. **GIF not displaying:**
   ```bash
   # Verify GIF file exists
   docker exec xbt-telebot-container ls -la xbt_buy_alert.gif
   
   # Check file permissions
   docker exec xbt-telebot-container stat xbt_buy_alert.gif
   ```

### **Rollback Procedure:**
```bash
# Stop container
docker stop xbt-telebot-container

# Remove container
docker rm xbt-telebot-container

# Restore backup config
cp config.json.backup config.json

# Redeploy with corrected configuration
./deploy_xbt_bot.sh
```

---

## **ISOLATION VERIFICATION**

### **Confirm No Conflicts with JKC Bot:**
```bash
# Check running containers
docker ps | grep -E "(jkc|xbt)"

# Verify different networks
docker network ls | grep -E "(jkc|xbt)"

# Check port usage (should be none for both bots)
docker port xbt-telebot-container
```

### **Resource Usage:**
```bash
# Monitor memory usage
docker stats --no-stream xbt-telebot-container

# Check disk usage
docker system df
```

---

## **SUCCESS CRITERIA**

### **Deployment is successful when:**
- ✅ Container starts without errors
- ✅ Health check passes
- ✅ Bot responds to `/start` in Telegram
- ✅ `/test` command sends animated GIF
- ✅ `/price` command shows current XBT price
- ✅ Logs show WebSocket connections activating
- ✅ No conflicts with JKC bot (if running)

---

## **NEXT STEPS AFTER DEPLOYMENT**

1. **Configure Bot Settings:**
   - Set bot description and commands via @BotFather
   - Upload bot profile picture (use `xbt_buy_alert.gif`)
   - Configure webhook URL if needed

2. **User Onboarding:**
   - Share bot username with users
   - Provide usage instructions
   - Set up admin permissions

3. **Monitoring Setup:**
   - Set up log rotation
   - Configure alerting for container health
   - Monitor API rate limits

---

## **DEPLOYMENT COMMANDS SUMMARY**

```bash
# 1. Update bot token (REQUIRED)
python3 update_bot_token.py

# 2. Deploy container
./deploy_xbt_bot.sh

# 3. Monitor deployment
docker logs -f xbt-telebot-container

# 4. Test in Telegram
# Send /start to your new XBT bot

# 5. Verify GIF alerts
# Send /test command (admin only)
```

**🚀 Ready for deployment once the Telegram bot token is configured!**
