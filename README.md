# JunkCoin (JKC) Telegram Alert Bot 🤖⛵️

A sophisticated Telegram bot that monitors JunkCoin (JKC) transactions and sends real-time alerts for significant trades. Features include sweep detection, trade aggregation, dynamic thresholds, and animated alert images.

## 🎯 **Bot Information**
- **Bot Username**: Configure your own bot with @BotFather
- **Bot Token**: Set in config.json (get from @BotFather)
- **Admin User**: Configure your Telegram user ID
- **Trading Pair**: JKC/USDT only
- **Default Threshold**: 300 USDT

## 🌟 Features

### 📊 **Multi-Exchange Monitoring**
- **NonKYC Exchange** - Real-time orderbook monitoring with sweep detection
- **CoinEx Exchange** - Live trade monitoring via WebSocket
- **AscendEX Exchange** - Trade monitoring with API support
- **Komodo DEX** - Decentralized exchange support

### 🚨 **Smart Alert System**
- **Dynamic Thresholds** - Automatically adjusts based on JKC trading volume
- **Trade Aggregation** - Groups related trades within 3-second windows
- **Sweep Detection** - Identifies large orderbook sweeps in real-time
- **Magnitude Indicators** - Visual representation of trade size with emoji scaling

### 🎨 **Image Collection System**
- **Random Image Selection** - Each alert uses a different JKC image from your collection
- **Multiple Formats** - Supports PNG, JPG, JPEG, and GIF files
- **Easy Management** - Add, list, and clear images via commands
- **JKC Branding** - Default JKC-branded alert images included

### ⚙️ **Advanced Configuration**
- **Admin Controls** - Comprehensive permission system for configured admin user
- **Real-time Configuration** - Change settings without restarting
- **Multiple Chat Support** - Deploy across multiple Telegram groups
- **API Integration** - Optional exchange API keys for enhanced features

## 🔗 **JunkCoin Resources**

### Official Links
- **Website**: https://junk-coin.com/
- **Explorer**: https://jkc-explorer.dedoo.xyz/
- **Wallets**: https://junk-coin.com/wallets/
- **History**: https://jkchistory.vercel.app/
- **Supply Tracker**: https://jkcsupply.vercel.app/

### Market Data
- **CoinGecko**: https://www.coingecko.com/en/coins/junkcoin
- **CoinMarketCap**: https://coinmarketcap.com/currencies/junkcoin/

### Trading Exchanges
- **NonKYC**: https://nonkyc.io/market/JKC_USDT
- **CoinEx**: https://www.coinex.com/en/exchange/jkc-usdt
- **AscendEX**: https://ascendex.com/en/cashtrade-spottrading/usdt/jkc
- **Komodo DEX**: https://app.komodoplatform.com/wallet

## 🚀 Installation

### Prerequisites
- Docker and Docker Compose
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Linux server or VPS

### 1. Clone the Repository
```bash
git clone https://github.com/nodecattel/jkcbuybot.git
cd jkcbuybot
```

### 2. Configure the Bot
Edit the `config.json` file with your settings:

```json
{
  "bot_token": "YOUR_BOT_TOKEN_HERE",
  "value_require": 300,
  "active_chat_ids": [],
  "bot_owner": YOUR_TELEGRAM_USER_ID,
  "by_pass": 0,
  "image_path": "jkc_buy_alert.gif",
  "dynamic_threshold": {
    "enabled": true,
    "base_value": 300,
    "volume_multiplier": 0.05,
    "price_check_interval": 3600,
    "min_threshold": 100,
    "max_threshold": 1000
  },
  "trade_aggregation": {
    "enabled": true,
    "window_seconds": 3
  },
  "coinex_access_id": "",
  "coinex_secret_key": "",
  "ascendex_access_id": "",
  "ascendex_secret_key": ""
}
```

#### Configuration Parameters:
- **`bot_token`** - Your Telegram bot token from BotFather
- **`value_require`** - Minimum transaction value in USDT to trigger alerts
- **`bot_owner`** - Your Telegram user ID (get from [@userinfobot](https://t.me/userinfobot))
- **`by_pass`** - Additional admin user ID (optional)
- **`active_chat_ids`** - Will be populated automatically when you start the bot

### 3. Build and Deploy
```bash
# Use the automated deployment script
chmod +x deploy_jkc_bot.sh
./deploy_jkc_bot.sh

# Or manually with Docker Compose
docker-compose -f docker-compose.jkc.yml up -d

# Check logs
docker logs jkc-telebot-container
```

### 4. Get Your Telegram User ID
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. Copy your user ID and update `bot_owner` in `config.json`
3. Rebuild and restart: `./deploy_jkc_bot.sh`

## 🎮 Bot Operation

### Initial Setup
1. **Start the bot** in your Telegram chat: `/start`
2. **Verify admin status**: `/debug`
3. **Configure settings**: `/config`

### Basic Commands

#### 📊 **Information Commands**
- `/price` - Check current JKC price and market cap
- `/chart` - Generate and send a price chart
- `/help` - Show all available commands
- `/debug` - Show user ID, chat info, and admin status

#### 🛑 **Control Commands**
- `/start` - Start receiving alerts in the current chat
- `/stop` - Stop receiving alerts in the current chat

### Admin Commands

#### ⚙️ **Configuration**
- `/config` - Access interactive configuration menu
- `/setmin <value>` - Set minimum transaction value (e.g., `/setmin 300`)
- `/toggle_aggregation` - Enable/disable trade aggregation

#### 🎨 **Image Management**
- `/setimage` - Add an image to the collection (send image after command)
- `/list_images` - View all images in your collection
- `/clear_images` - Remove all images from collection

#### 🔐 **Advanced (Owner Only)**
- `/setapikey` or `/setapikeys` - Configure exchange API keys
- `/ipwan` - Get server's public IP address

## 📱 Using the Bot

### Setting Up Alerts
1. **Add the bot** to your Telegram group or use in private chat
2. **Make yourself admin** of the group (if using in a group)
3. **Start monitoring**: `/start`
4. **Configure threshold**: `/setmin 300` (sets minimum to 300 USDT)
5. **Add alert images**: `/setimage` (send multiple images for variety)

### Understanding Alerts
The bot sends different types of alerts based on transaction size:

- 🚨 **Standard Alert** - Regular transactions above threshold
- 💥 **Significant Alert** - 2x threshold value
- 🔥 **Major Alert** - 3x threshold value
- 🔥🔥 **Huge Alert** - 5x threshold value
- 🐋🐋🐋 **Whale Alert** - 10x+ threshold value

Each alert includes:
- **Visual magnitude indicator** (green squares showing relative size)
- **Transaction details** (amount, price, total value)
- **Exchange information** with direct trading link
- **Timestamp** in your timezone
- **Random image** from your collection

### Advanced Features

#### Dynamic Thresholds
The bot can automatically adjust alert thresholds based on trading volume:
- **Enable**: Use `/config` → Dynamic Threshold Settings
- **Automatic scaling** based on 24h volume
- **Min/max limits** to prevent extreme values

#### Trade Aggregation
Groups related trades to detect coordinated buying:
- **Time window** - Groups trades within 3-second windows
- **Sweep detection** - Identifies large coordinated purchases
- **Reduces spam** - Combines small trades into meaningful alerts

## 🔧 Maintenance

### Updating the Bot
```bash
# Pull latest changes
git pull origin main

# Use the deployment script
./deploy_jkc_bot.sh

# Or manually rebuild and restart
docker-compose -f docker-compose.jkc.yml down
docker-compose -f docker-compose.jkc.yml up -d
```

### Viewing Logs
```bash
# Real-time logs
docker logs -f jkc-telebot-container

# Last 50 lines
docker logs jkc-telebot-container --tail 50
```

### Backup Configuration
```bash
# Backup your config and images
cp config.json config.json.backup
tar -czf images_backup.tar.gz images/
```

## 🛠️ Troubleshooting

### Common Issues

#### Bot Not Responding
1. Check if container is running: `docker ps`
2. Check logs: `docker logs jkc-telebot-container`
3. Verify bot token in `config.json`
4. Restart: `docker-compose -f docker-compose.jkc.yml restart`

#### Admin Commands Not Working
1. Verify your user ID: `/debug`
2. Check `bot_owner` in `config.json`
3. Ensure you're admin in group chats
4. Rebuild after config changes: `./deploy_jkc_bot.sh`

#### No Alerts Received
1. Check if bot is started: `/start`
2. Verify threshold setting: `/config`
3. Check active chats: `/debug`
4. Monitor logs for trade processing

#### Image Issues
1. Ensure images directory exists: `mkdir -p images`
2. Check supported formats: PNG, JPG, JPEG, GIF
3. Verify file permissions
4. Use `/list_images` to check collection

### Getting Help
- Check logs: `docker logs jkc-telebot-container`
- Verify configuration: `/debug` command
- Test with lower threshold temporarily
- Ensure proper permissions and admin status

## 📈 Performance Tips

### Optimal Settings
- **Threshold**: Start with 300-500 USDT, adjust based on activity
- **Aggregation**: Keep enabled for better sweep detection
- **Dynamic threshold**: Enable for automatic scaling
- **Image collection**: 5-10 varied images for best experience

### Resource Usage
- **CPU**: Low usage, spikes during high trading activity
- **Memory**: ~100-200MB typical usage
- **Network**: Minimal bandwidth for WebSocket connections
- **Storage**: Logs and images, typically <1GB

## 🔒 Security Notes

- **API Keys**: Only bot owner can set exchange API keys
- **Permissions**: Admin commands require proper authorization
- **Private Data**: API keys are automatically deleted from chat after input
- **Logs**: Monitor logs for unauthorized access attempts

## 📄 License

This project is open source. Please check the repository for license details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

---

**Happy Trading! ⛵️🚀**
