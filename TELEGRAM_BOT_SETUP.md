# 🤖 Telegram Bot Setup for XBT Bot

## **CRITICAL: Create New Telegram Bot Token**

⚠️ **REQUIRED BEFORE DEPLOYMENT**: The XBT bot needs its own unique Telegram bot token to avoid conflicts with the JKC bot.

---

## **Step 1: Create New Telegram Bot**

1. **Open Telegram** and search for `@BotFather`
2. **Start conversation** with BotFather
3. **Send command**: `/newbot`
4. **Follow the prompts**:

### **Bot Creation Dialog:**
```
BotFather: Alright, a new bot. How are we going to call it? Please choose a name for your bot.

You: Bitcoin Classic (XBT) Alert Bot

BotFather: Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.

You: xbt_alert_bot
(or: bitcoinclassic_alert_bot, xbt_trading_bot, etc.)

BotFather: Done! Congratulations on your new bot. You will find it at t.me/xbt_alert_bot. You can now add a description, about section and profile picture for your bot, see /help for a list of commands. By the way, when you've finished creating your cool bot, ping our Bot Support if you want a better username.

Use this token to access the HTTP API:
XXXXXXXXX:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
Keep your token secure and store it safely, it can be used by anyone to control your bot.
```

5. **Copy the token** (format: `XXXXXXXXX:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`)

---

## **Step 2: Update Configuration**

### **Update config.json:**
```bash
cd /home/n3k0h1m3/xbttelebot
cp config.json config.json.backup
```

Edit `config.json` and replace the bot_token:
```json
{
  "bot_token": "PASTE_NEW_XBT_BOT_TOKEN_HERE",
  "active_chat_ids": [],
  "value_require": 300.0,
  "image_path": "xbt_buy_alert.gif",
  "bot_owner": 1145064309,
  "by_pass": 1145064309,
  "dynamic_threshold": {
    "enabled": false,
    "base_value": 300,
    "volume_multiplier": 0.1,
    "max_threshold": 1000
  },
  "trade_aggregation": {
    "enabled": true,
    "window_seconds": 8,
    "min_trades": 2
  },
  "coinex_access_id": "",
  "coinex_secret_key": "",
  "ascendex_access_id": "",
  "ascendex_secret_key": ""
}
```

### **Clear Active Chat IDs:**
Make sure `"active_chat_ids": []` is empty to avoid inheriting JKC bot chats.

---

## **Step 3: Validate Configuration**

Run validation tests:
```bash
python3 test_config_loading.py
python3 test_gif_integration.py
```

Both should pass 100% of tests.

---

## **Step 4: Test Bot Token**

Create a simple test script:
```python
import requests

# Replace with your new token
BOT_TOKEN = "PASTE_NEW_XBT_BOT_TOKEN_HERE"

# Test bot info
response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe")
if response.status_code == 200:
    bot_info = response.json()
    print(f"✅ Bot token valid!")
    print(f"Bot name: {bot_info['result']['first_name']}")
    print(f"Bot username: @{bot_info['result']['username']}")
else:
    print(f"❌ Bot token invalid: {response.status_code}")
```

---

## **Step 5: Optional Bot Customization**

### **Set Bot Description:**
Send to @BotFather:
```
/setdescription @xbt_alert_bot
Bitcoin Classic (XBT) trading alert bot. Get real-time notifications for significant XBT transactions with animated alerts and market data.
```

### **Set Bot Commands:**
Send to @BotFather:
```
/setcommands @xbt_alert_bot
start - Start the XBT alert bot
stop - Stop receiving alerts
price - Check current XBT price
help - Show available commands
test - Send test alert (admin only)
config - Bot configuration (admin only)
```

### **Set Bot Profile Picture:**
1. Send `/setuserpic @xbt_alert_bot` to @BotFather
2. Upload the `xbt_buy_alert.gif` or a static XBT logo

---

## **Security Notes**

⚠️ **IMPORTANT**:
- **Never share** your bot token publicly
- **Store securely** in configuration files
- **Use environment variables** in production if possible
- **Regenerate token** if compromised (via @BotFather `/revoke`)

---

## **Verification Checklist**

Before proceeding to Docker deployment:

- [ ] ✅ New Telegram bot created with unique username
- [ ] ✅ Bot token copied and stored securely
- [ ] ✅ `config.json` updated with new token
- [ ] ✅ `active_chat_ids` cleared (empty array)
- [ ] ✅ Configuration validation tests pass
- [ ] ✅ Bot token tested and valid
- [ ] ✅ Bot description and commands set (optional)

---

## **Next Steps**

Once the bot token is configured:
1. Proceed to Docker image build
2. Deploy container with new configuration
3. Test bot functionality in Telegram
4. Start receiving XBT alerts with animated GIFs! 🎬🟡

---

## **Rollback Plan**

If issues occur:
```bash
# Restore original config
cp config.json.backup config.json

# Or manually revert bot_token in config.json
```

**Ready for Docker deployment once token is configured!** 🚀
