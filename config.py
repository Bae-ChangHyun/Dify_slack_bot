import os
from logger import CustomLogger  
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variables
web_port = os.getenv('web_port')
debug = os.getenv('debug_mode', 'False').lower() in ('true', '1', 't')

# Dify variables
dify_api_key = os.getenv('dify_api_key')
dify_base_url = os.getenv('dify_base_url')

# Slack variables
slack_base_url = os.getenv('slack_base_url')
slack_web_hook = os.getenv('slack_web_hook')
slack_signing_secret = os.getenv('slack_signing_secret')
slack_app_token = os.getenv('slack_app_token')
slack_OAuth_token = os.getenv('slack_OAuth_token')

# Redis variables
redis_host = os.getenv('redis_host')
redis_port = os.getenv('redis_port')
redis_conv_db = os.getenv('redis_conv_db')
redis_user_db = os.getenv('redis_user_db')
redis_password = os.getenv('redis_password')

logger = CustomLogger("chat_log")
