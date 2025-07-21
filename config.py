"""
Configuration Management Module for JKC Trading Bot

This module handles all configuration loading, validation, and persistence
for the JKC trading bot. It maintains backward compatibility with the existing
config.json structure while providing a clean interface for other modules.
"""

import json
import os
import logging
from typing import Dict, Any, Optional

# Set up module logger
logger = logging.getLogger(__name__)

# Global configuration storage
_CONFIG: Optional[Dict[str, Any]] = None

def load_config() -> Dict[str, Any]:
    """
    Load configuration from file with comprehensive validation.
    Creates default config if file doesn't exist.
    
    Returns:
        Dict containing the loaded configuration
    """
    config_path = "config.json"
    if not os.path.exists(config_path):
        # Create default config if it doesn't exist
        default_config = {
            "bot_token": "YOUR_BOT_TOKEN",
            "value_require": 300,
            "active_chat_ids": [],
            "bot_owner": 0,
            "by_pass": 0,
            "image_path": "jkc_buy_alert.gif",
            "dynamic_threshold": {
                "enabled": True,
                "base_value": 300,
                "volume_multiplier": 0.05,
                "price_check_interval": 3600,
                "min_threshold": 100,
                "max_threshold": 1000
            },
            "coinex_access_id": "",
            "coinex_secret_key": "",
            "ascendex_access_id": "",
            "ascendex_secret_key": ""
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        logger.info("Created default configuration file")
        return default_config
    
    with open(config_path, 'r') as f:
        config_data = json.load(f)
    
    logger.info("Configuration loaded from config.json")
    return config_data

def save_config(config_data: Dict[str, Any]) -> bool:
    """
    Save configuration to file with error handling.
    
    Args:
        config_data: Configuration dictionary to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        config_path = "config.json"
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        logger.info("Configuration saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        return False

def validate_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize configuration data.
    Adds missing fields with defaults and validates critical settings.
    
    Args:
        config_data: Raw configuration data
        
    Returns:
        Dict: Validated and normalized configuration
        
    Raises:
        ValueError: If critical validation fails
    """
    # Validate critical fields
    required_fields = ['bot_token', 'bot_owner', 'value_require', 'active_chat_ids', 'by_pass', 'image_path']
    for field in required_fields:
        if field not in config_data:
            raise ValueError(f"Missing required field: {field}")

    # Validate optional but important nested configurations
    if 'dynamic_threshold' not in config_data:
        config_data['dynamic_threshold'] = {
            "enabled": False,
            "base_value": 300,
            "volume_multiplier": 0.05,
            "price_check_interval": 3600,
            "min_threshold": 100,
            "max_threshold": 1000
        }

    if 'trade_aggregation' not in config_data:
        config_data['trade_aggregation'] = {
            "enabled": True,
            "window_seconds": 8
        }

    if 'sweep_orders' not in config_data:
        config_data['sweep_orders'] = {
            "enabled": True,
            "min_value": 80,
            "check_interval": 2,
            "min_orders_filled": 2
        }

    # Validate bot_token format
    bot_token = config_data.get('bot_token', '')
    if not bot_token or bot_token == "YOUR_BOT_TOKEN":
        raise ValueError("bot_token must be set to a valid Telegram bot token")
    if not bot_token.count(':') == 1 or len(bot_token.split(':')[0]) < 8:
        raise ValueError("bot_token format appears invalid (should be like '123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11')")

    # Validate bot_owner
    bot_owner = config_data.get('bot_owner', 0)
    if not isinstance(bot_owner, int) or bot_owner <= 0:
        raise ValueError("bot_owner must be a positive integer (Telegram user ID)")

    # Validate value_require
    value_require = config_data.get('value_require', 0)
    if not isinstance(value_require, (int, float)) or value_require <= 0:
        raise ValueError("value_require must be a positive number")

    # Validate active_chat_ids
    active_chat_ids = config_data.get('active_chat_ids', [])
    if not isinstance(active_chat_ids, list):
        raise ValueError("active_chat_ids must be a list")

    # Validate by_pass
    by_pass = config_data.get('by_pass', 0)
    if not isinstance(by_pass, int):
        raise ValueError("by_pass must be an integer")

    # Validate image_path
    image_path = config_data.get('image_path', '')
    if not isinstance(image_path, str) or not image_path:
        raise ValueError("image_path must be a non-empty string")

    logger.info("Configuration validation completed successfully")
    return config_data

def get_config() -> Dict[str, Any]:
    """
    Get the current configuration, loading it if necessary.
    
    Returns:
        Dict: Current configuration
    """
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = validate_config(load_config())
    return _CONFIG

def update_config(updates: Dict[str, Any]) -> bool:
    """
    Update configuration with new values and save to file.
    
    Args:
        updates: Dictionary of configuration updates
        
    Returns:
        bool: True if successful, False otherwise
    """
    global _CONFIG
    config = get_config()
    config.update(updates)
    
    try:
        validated_config = validate_config(config)
        if save_config(validated_config):
            _CONFIG = validated_config
            return True
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
    
    return False

def get_config_value(key: str, default: Any = None) -> Any:
    """
    Get a specific configuration value.
    
    Args:
        key: Configuration key (supports dot notation for nested values)
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    config = get_config()
    
    # Support dot notation for nested values
    if '.' in key:
        keys = key.split('.')
        value = config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    return config.get(key, default)

# Configuration constants for backward compatibility
def get_bot_token() -> str:
    """Get bot token from configuration."""
    return get_config_value('bot_token', '')

def get_value_require() -> float:
    """Get value requirement threshold from configuration."""
    return float(get_config_value('value_require', 300))

def get_active_chat_ids() -> list:
    """Get active chat IDs from configuration."""
    return get_config_value('active_chat_ids', [])

def get_bot_owner() -> int:
    """Get bot owner ID from configuration."""
    return int(get_config_value('bot_owner', 0))

def get_by_pass() -> int:
    """Get bypass user ID from configuration."""
    return int(get_config_value('by_pass', 0))

def get_image_path() -> str:
    """Get image path from configuration."""
    return get_config_value('image_path', 'jkc_buy_alert.gif')
