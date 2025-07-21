"""
Permissions and Security Module for JKC Trading Bot

This module handles all permission checking, user authentication, and access control
for the JKC trading bot. It provides a clean interface for verifying user permissions
across different command types and chat contexts.
"""

import logging
from typing import Optional

try:
    from telegram import Update
    from telegram.ext import CallbackContext
    TELEGRAM_AVAILABLE = True
except ImportError:
    # Handle missing telegram dependency gracefully
    Update = None
    CallbackContext = None
    TELEGRAM_AVAILABLE = False

from config import get_bot_owner, get_by_pass

# Set up module logger
logger = logging.getLogger(__name__)

async def is_admin(update: Update, context: CallbackContext) -> bool:
    """
    Check if the user is an admin or bot owner.
    
    This function checks multiple permission levels:
    1. Bot owner (highest permission)
    2. Bypass user (special permission)
    3. Group chat administrator (context-dependent)
    
    Args:
        update: Telegram update object
        context: Telegram callback context
        
    Returns:
        bool: True if user has admin permissions, False otherwise
    """
    # Get user ID with multiple fallback methods to ensure we get the correct one
    user_id = None

    # Try different methods to get the user ID, prioritizing message.from_user
    if update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id
    elif update.effective_user:
        user_id = update.effective_user.id

    if user_id is None:
        logger.error("Could not extract user ID from update")
        return False

    # Get chat ID for context
    chat_id = None
    if update.message:
        chat_id = update.message.chat_id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat_id
    elif update.effective_chat:
        chat_id = update.effective_chat.id

    logger.info(f"Checking admin permissions for user {user_id} in chat {chat_id}")

    # Check if user is bot owner (highest permission level)
    bot_owner = get_bot_owner()
    if int(user_id) == int(bot_owner):
        logger.info(f"User {user_id} is bot owner - admin access granted")
        return True

    # Check if user is bypass user (special permission)
    by_pass = get_by_pass()
    if by_pass and int(user_id) == int(by_pass):
        logger.info(f"User {user_id} is bypass user - admin access granted")
        return True

    # For group chats, check if user is an admin
    if chat_id and chat_id < 0:  # Group chat IDs are negative
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            is_admin_status = chat_member.status in ["administrator", "creator"]
            logger.info(f"User {user_id} in group {chat_id} has status: {chat_member.status}, is_admin: {is_admin_status}")
            return is_admin_status
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
    else:
        # For private chats, only bot owner and bypass user have admin rights
        logger.info(f"Private chat {chat_id} - User {user_id} is not bot owner or bypass user")

    return False

async def is_owner_only(update: Update, context: CallbackContext) -> bool:
    """
    Check if the user is the bot owner (stricter than admin check).
    
    This is used for commands that should only be available to the bot owner,
    not to group administrators or bypass users.
    
    Args:
        update: Telegram update object
        context: Telegram callback context
        
    Returns:
        bool: True if user is the bot owner, False otherwise
    """
    user_id = None

    if update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id
    elif update.effective_user:
        user_id = update.effective_user.id

    if user_id is None:
        return False

    bot_owner = get_bot_owner()
    is_owner = int(user_id) == int(bot_owner)
    
    if is_owner:
        logger.info(f"User {user_id} verified as bot owner")
    else:
        logger.info(f"User {user_id} is not bot owner (owner: {bot_owner})")
    
    return is_owner

async def can_use_public_commands(update: Update, context: CallbackContext) -> bool:
    """
    Check if user can use public commands (always true for basic info commands).
    
    Public commands like /help, /price, /chart are available to everyone.
    This function exists for consistency and future extensibility.
    
    Args:
        update: Telegram update object
        context: Telegram callback context
        
    Returns:
        bool: Always True for public commands
    """
    # Public commands like /help, /price, /chart are available to everyone
    return True

async def can_use_admin_commands(update: Update, context: CallbackContext) -> bool:
    """
    Check if user can use admin commands with special handling for public supergroup.
    
    This function implements special logic for the public supergroup where
    admin commands are restricted to the owner only, while other chats
    use standard admin permissions.
    
    Args:
        update: Telegram update object
        context: Telegram callback context
        
    Returns:
        bool: True if user can use admin commands, False otherwise
    """
    # Get chat ID for context-specific permission checking
    chat_id = None
    if update.message:
        chat_id = update.message.chat_id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat_id
    elif update.effective_chat:
        chat_id = update.effective_chat.id

    # Get user ID for logging
    user_id = None
    if update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id
    elif update.effective_user:
        user_id = update.effective_user.id

    # For public supergroups, restrict admin commands to owner only
    public_supergroups = config.get("public_supergroups", [])
    if chat_id in public_supergroups:
        logger.info(f"Public supergroup access: User {user_id} requesting admin command - checking owner status")
        return await is_owner_only(update, context)

    # For other chats, use standard admin check
    return await is_admin(update, context)

async def get_user_id(update: Update) -> Optional[int]:
    """
    Extract user ID from update object with multiple fallback methods.
    
    Args:
        update: Telegram update object
        
    Returns:
        Optional[int]: User ID if found, None otherwise
    """
    if update.message and update.message.from_user:
        return update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    elif update.effective_user:
        return update.effective_user.id
    
    return None

async def get_chat_id(update: Update) -> Optional[int]:
    """
    Extract chat ID from update object with multiple fallback methods.
    
    Args:
        update: Telegram update object
        
    Returns:
        Optional[int]: Chat ID if found, None otherwise
    """
    if update.message:
        return update.message.chat_id
    elif update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat_id
    elif update.effective_chat:
        return update.effective_chat.id
    
    return None

async def log_permission_check(update: Update, command: str, permission_granted: bool) -> None:
    """
    Log permission check results for audit purposes.
    
    Args:
        update: Telegram update object
        command: Command being checked
        permission_granted: Whether permission was granted
    """
    user_id = await get_user_id(update)
    chat_id = await get_chat_id(update)
    
    status = "GRANTED" if permission_granted else "DENIED"
    logger.info(f"Permission {status}: User {user_id} in chat {chat_id} for command '{command}'")

def is_group_chat(chat_id: Optional[int]) -> bool:
    """
    Check if the chat ID represents a group chat.
    
    Args:
        chat_id: Chat ID to check
        
    Returns:
        bool: True if group chat, False otherwise
    """
    return chat_id is not None and chat_id < 0

def is_private_chat(chat_id: Optional[int]) -> bool:
    """
    Check if the chat ID represents a private chat.
    
    Args:
        chat_id: Chat ID to check
        
    Returns:
        bool: True if private chat, False otherwise
    """
    return chat_id is not None and chat_id > 0
