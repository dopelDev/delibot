# bot_main.py

import os
from pathlib import Path
import discord
from discord.ext import commands
from dotenv import load_dotenv
from app.utils.path import get_project_root

ROOT_DIR = get_project_root()
