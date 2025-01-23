from config import *
from utils import debug_print
import time

# https://api.slack.com/methods

class SlackProcess:
    def __init__(self, bolt_app):
        self.client = bolt_app.client
    
    def chat_update(self, channel_id, text, ts, retry_count=3):
        """메시지 업데이트"""
        for attempt in range(retry_count):
            try:
                response = self.client.chat_update(
                    channel=channel_id,
                    ts=ts,
                    text=text
                )
                return response
            except Exception as e:
                if attempt == retry_count - 1:
                    debug_print(f"Failed to update message after {retry_count} attempts: {e}")
                    raise e
                time.sleep(0.5)
    
    def post_message(self, channel_id, text, thread_ts=None):
        """새 메시지 전송"""
        try:
            return self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts
            )
        except Exception as e:
            debug_print(f"Failed to post message: {e}")
            raise e
    
    def get_thread_messages(self, channel_id, thread_ts):
        """스레드의 메시지 조회"""
        try:
            return self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
        except Exception as e:
            debug_print(f"Failed to get thread messages: {e}")
            raise e


#TODO - Sending messages using incoming webhooks
# def webhook_post(message):
#     '''
#     https://api.slack.com/messaging/webhooks
#     '''
#     slack_response = requests.post(slack_web_hook, json={"text": message})
#     pass

#TODO - Send or schedule a message
# def schedule_message():
#     '''
#     예약메시지
#     https://api.slack.com/messaging/sending#scheduling
#     '''
