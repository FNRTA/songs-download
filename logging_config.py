import logging
import os
from datetime import datetime

# Create a logs directory if it doesn't exist
if not os.path.exists("logs"):
    os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Log format
    handlers=[
        logging.FileHandler(f"logs/app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),  # Log to a file
        logging.StreamHandler()  # Log to the console
    ]
)

# Create a logger instance
logger = logging.getLogger(__name__)
