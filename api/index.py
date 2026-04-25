"""Vercel serverless function entry point."""
import sys
import os

# Add the project root to the Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
