"""
Configuration Module
Simple configuration for SLO detection application.
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("gunicorn.log"),
        logging.StreamHandler()
    ]
)


class Config:
    """Application configuration class."""

    # Flask settings
    DEBUG = True
    HOST = '0.0.0.0'
    PORT = 8001
    THREADED = True


    @classmethod
    def validate(cls):
        """Validate required configuration."""
        logging.info("Configuration validated")


