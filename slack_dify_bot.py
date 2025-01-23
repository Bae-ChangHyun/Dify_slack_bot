import os
import re
import json
import time
import threading
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

from config import *
from utils import debug_print
from dify_process import chat_messages_stream
from slack_process import chat_update

class SlackBot:
    # 클래스 변수로 선언하여 인스턴스 간에 공유
    conversation_mapper = dict()
    
    def __init__(self):
        self.bolt_app = App(
            token=slack_OAuth_token,
            signing_secret=slack_signing_secret
        )
        self.app = Flask(__name__)
        self.handler = SlackRequestHandler(self.bolt_app)
        self.typing_dots = ["", ".", "..", "..."]
        
        # 앱 멘션 이벤트 리스너 (일반 채널용)
        self.bolt_app.event("app_mention")(self.handle_mention)
        # DM 메시지 이벤트 리스너
        self.bolt_app.message()(self.handle_dm)
        
        # Flask 라우트 설정
        self.app.route("/slack/events", methods=["POST"])(self.handle_slack_events)
    
    def handle_slack_events(self):
        return self.handler.handle(request)
    
    def handle_mention(self, event, say):
        """일반 채널에서의 멘션 처리"""
        self._process_message(event, say)
    
    def handle_dm(self, message, say):
        """DM 채널에서의 메시지 처리"""
        # 봇 자신의 메시지는 무시
        if message.get('bot_id'):
            return
            
        # DM 채널인지 확인
        if message.get('channel_type') == 'im':
            self._process_message(message, say)
    
    def _process_message(self, event, say):
        """메시지 처리 로직"""
        if event.get('bot_id'):
            return
            
        channel_id = event['channel']
        thread_ts = event.get('thread_ts', event['ts'])
        user_query = re.sub(r'^<@[^>]+>\s*', '', event['text'])
        
        debug_print(f"Current conversation_mapper: {self.conversation_mapper}")
        debug_print(f"Thread TS: {thread_ts}")
        debug_print(f"Conversation ID for this thread: {self.conversation_mapper.get(str(thread_ts))}")
        
        # 임시 메시지 전송
        response = say(
            text="잠시만 기다려주세요...🤔",
            thread_ts=thread_ts
        )
        tmp_ts = response['ts']
        
        # 처리 스레드 시작
        threading.Thread(
            target=self._handle_conversation,
            args=(event, tmp_ts, user_query, channel_id, thread_ts)
        ).start()
    
    def _handle_conversation(self, event, tmp_ts, user_query, channel_id, thread_ts):
        try:
            self._show_waiting_animation(channel_id, tmp_ts)
            
            dify_conversation_id = self.conversation_mapper.get(str(thread_ts), '')
            
            self._process_dify_response(
                user_query,
                event.get('user', ''),
                channel_id,
                tmp_ts,
                thread_ts,
                dify_conversation_id
            )
            
        except Exception as e:
            debug_print(f"Error in conversation handling: {e}")
            chat_update(channel_id, "처리 중 오류가 발생했습니다.", tmp_ts)
    
    def _show_waiting_animation(self, channel_id, tmp_ts):
        start_time = time.time()
        idx = 0
        while time.time() - start_time < 3:
            current_text = f"잠시만 기다려주세요{self.typing_dots[idx]}🤔..⏳"
            chat_update(channel_id, current_text, tmp_ts)
            idx = (idx + 1) % len(self.typing_dots)
            time.sleep(0.5)
    
    def _process_dify_response(self, user_query, user_id, channel_id, tmp_ts, thread_ts, dify_conversation_id):
        response = chat_messages_stream(
            user_query,
            user_id,
            dify_conversation_id
        )
        
        self.accumulated_response = ""
        self.last_update_time = time.time()
        self.update_interval = 0.9
        self.is_complete = False
        
        for line in response.iter_lines():
            if not line:
                continue   
            try:
                line_text = line.decode('utf-8')
                self._handle_stream_line(
                    line_text,
                    channel_id,
                    tmp_ts,
                    thread_ts
                )
            except json.JSONDecodeError as e:
                debug_print(f"JSON decode error: {e}")
        
        time.sleep(0.5)
        final_text = self.accumulated_response if self.is_complete else f"{self.accumulated_response} ⏳ ..."
        final_text += "\n더 필요하신 부분이 있으면 말씀해주세요."
        chat_update(channel_id, final_text, tmp_ts)

    def _handle_stream_line(self, line, channel_id, tmp_ts, thread_ts):
        if line.startswith('data: '):
            data = json.loads(line[6:])
            
            if 'event' in data and data['event'] == 'message':
                message_chunk = data.get('answer', '')
                self.accumulated_response += message_chunk
                
                current_time = time.time()
                if current_time - self.last_update_time >= self.update_interval:
                    chat_update(
                        channel_id, 
                        f"{self.accumulated_response} ⏳ ...", 
                        tmp_ts
                    )
                    self.last_update_time = current_time
                
            elif 'event' in data and data['event'] == 'message_end':
                conversation_id = data.get('conversation_id')
                self.is_complete = True
                time.sleep(0.5)
                chat_update(channel_id, self.accumulated_response, tmp_ts)
                
                if conversation_id:
                    self.conversation_mapper[str(thread_ts)] = conversation_id
    
    def run(self, port=web_port):
        self.app.run(port=port, debug=False)

if __name__ == '__main__':
    bot = SlackBot()
    bot.run()