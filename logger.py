import logging
from logging.handlers import TimedRotatingFileHandler
import json
import os
import sys
from datetime import datetime

class CenteredLevelFormatter(logging.Formatter):
    def format(self, record):
        record.filename = record.filename[:20]  # set filename limit
        record.funcName = record.funcName[:25]  # set funcName limit

        formatted_message = super().format(record)
        parts = formatted_message.split("|")

        widths = [15, 5, 15, 15, 50]  # asctime / levelname / filename + lineno / funcName
        centered_parts = [
            part.strip().center(width) for part, width in zip(parts[:-1], widths[:-1])
        ]
        centered_parts.append(parts[-1])  # msg

        return " | ".join(centered_parts)

class CustomLogger:
    def __init__(self, log_file_prefix):
        self.logger = logging.getLogger("DifySlackBotLogger")
        self.logger.setLevel(logging.INFO)

        save_dir = './logs'
        os.makedirs(save_dir, exist_ok=True)
        
        backup_limit = int(os.getenv("backup_limit", 24))

        if not os.path.exists(save_dir):
            os.mkdir(save_dir)

        log_formatter = CenteredLevelFormatter(
            '%(asctime)s | %(levelname)s | %(filename)s :%(lineno)d | %(funcName)s |  %(message)s')

        handler = TimedRotatingFileHandler(
            filename=os.path.join(save_dir, f"{log_file_prefix}.log"),
            when="H",
            interval=1,
            backupCount=backup_limit,
            encoding="utf-8"
        )
        handler.setFormatter(log_formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)

        self.logger.addHandler(handler)
        self.logger.addHandler(console_handler)

    def log_slack_event(self, event_data):
        formatted_event = {
            #"token": event_data.get('token'),
            "team_id": event_data.get('team_id'),
            "api_app_id": event_data.get('api_app_id'),
            "user": event_data['event'].get('user'),
            "type": event_data['event'].get('type'),
            "ts": event_data['event'].get('ts'),
            "thread_ts": event_data['event'].get('thread_ts'),
            "channel": event_data['event'].get('channel'),
            "parent_user_id": event_data['event'].get('parent_user_id'),
            "event_time": event_data.get('event_time'),
            "text": event_data['event'].get('text'),
        }
        self.logger.info(f"Slack chat: {json.dumps(formatted_event, ensure_ascii=False)}")

    def log_llm_response(self, response_data):
        formatted_response = {
            "event": response_data.get('event'),
            "task_id": response_data.get('task_id'),
            "id": response_data.get('id'),
            "message_id": response_data.get('message_id'),
            "conversation_id": response_data.get('conversation_id'),
            "mode": response_data.get('mode'),
            "created_at": datetime.utcfromtimestamp(response_data.get('created_at')).strftime('%Y-%m-%d %H:%M:%S'),
            "answer": response_data.get('answer'),
        }
        self.logger.info(f"LLM BOT: {json.dumps(formatted_response, ensure_ascii=False)}\n\n")
    
    
    def log_api_status(self, end_point, method, response, error=None):
        
        self.logger.error(f"{end_point} {method} {response.status_code} - {error}")

# Usage example
if __name__ == "__main__":
    logger = CustomLogger("dify_slack_bot")
    slack_event = {
        'token': 'PHDiTbTU4Ir0W0Dfu0rL2HCW',
        'team_id': 'T088YBL1AGP',
        'api_app_id': 'A089RJDC3LZ',
        'event': {
            'user': 'U089A2N776Z',
            'type': 'app_mention',
            'ts': '1737510538.910639',
            'text': '<@U08969B98GN> 오늘 코스피 지수',
            'channel': 'C089C3M877Y',
            'thread_ts': '1737510407.233349',
            'parent_user_id': 'U089A2N776Z'
        },
        'event_time': 1737510538
    }
    llm_response = {
        'event': 'message',
        'task_id': '8e35f9de-a0dd-4830-91c5-3899a556d595',
        'id': 'ea3867f8-8dd4-4702-966a-5c6107a0aeda',
        'message_id': 'ea3867f8-8dd4-4702-966a-5c6107a0aeda',
        'conversation_id': 'c6b27f49-45ba-4d1d-8d9a-6ec8e2484e1a',
        'mode': 'advanced-chat',
        'answer': '좋은 아침입니다! 어떻게 도와드릴까요? 오늘 하루 잘 보내시고 계시길 바랍니다. 혹시 특별히 궁금한 사항이 있으신가요?',
        'created_at': 1737510408
    }
    api_error = {
        'error': 'Timeout',
        'status_code': 504,
        'url': 'https://api.example.com/data',
        'method': 'POST',
        'response': 'Gateway Timeout'
    }
    logger.log_slack_event(slack_event)
    logger.log_llm_response(llm_response)
    logger.log_api_error(api_error)
    
'''
    Slack chat:{'token': 'PHDiTbTU4Ir0W0Dfu0rL2HCW', 'team_id': 'T088YBL1AGP', 'api_app_id': 'A089RJDC3LZ', 'event': {'user': 'U089A2N776Z', 'type': 'app_mention', 'ts': '1737511608.616579', 'client_msg_id': '05059c6a-b81f-46ab-830a-9e219b752b8d', 'text': '<@U08969B98GN> 안녕', 'team': 'T088YBL1AGP', 'thread_ts': '1737510407.233349', 'parent_user_id': 'U089A2N776Z', 'blocks': [{'type': 'rich_text', 'block_id': 'VHY7A', 'elements': [{'type': 'rich_text_section', 'elements': [{'type': 'user', 'user_id': 'U08969B98GN'}, {'type': 'text', 'text': ' 안녕'}]}]}], 'channel': 'C089C3M877Y', 'event_ts': '1737511608.616579'}, 'type': 'event_callback', 'event_id': 'Ev089H1L4VU6', 'event_time': 1737511608, 'authorizations': [{'enterprise_id': None, 'team_id': 'T088YBL1AGP', 'user_id': 'U08969B98GN', 'is_bot': True, 'is_enterprise_install': False}], 'is_ext_shared_channel': False, 'event_context': '4-eyJldCI6ImFwcF9tZW50aW9uIiwidGlkIjoiVDA4OFlCTDFBR1AiLCJhaWQiOiJBMDg5UkpEQzNMWiIsImNpZCI6IkMwODlDM004NzdZIn0'}
'''