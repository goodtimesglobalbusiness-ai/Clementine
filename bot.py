"""
Clementine Discord Bot - Entry Point

This module serves as the main entry point for the Clementine bot.
It imports and starts the bot defined in clem2_0.py.
"""

import sys
import os

# Add the current directory to the path to ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and start the bot
from clem2_0 import bot, __name__ as bot_module_name

if __name__ == "__main__":
    # The bot is already configured in clem2_0.py and will run from here
    pass
