import os
import re
import json
import time
import threading
from flask import Flask, request, g
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

from config import *
from utils import debug_print
from dify_process import DifyClient
from slack_process import SlackProcess
from db_handler import ConversationDB, UserDB

class SlackBotServer:
    def __init__(self):
        self.app = Flask(__name__)
        self.conv_db = ConversationDB(
            host=redis_host,
            port=redis_port,
            db=redis_conv_db,
            pw=redis_password
        )
        self.user_db = UserDB(
            host=redis_host,
            port=redis_port,
            db=redis_user_db,
            pw=redis_password
        )
        
        @self.app.route("/slack/events", methods=["POST"])
        def handle_slack_events():
            bot = SlackBot(self.user_db, self.conv_db)
            debug_print(f"SlackBot created")
            return bot.handle_request(request)
            
    def run(self, port=web_port):
        self.app.run(port=port, debug=False)

class SlackBot:
    """각 요청을 처리하는 Slack 봇 인스턴스입니다. 각 요청마다 새로운 인스턴스가 생성됩니다."""

    def __init__(self, user_db, conv_db):
        self.bolt_app = App(
            token=slack_OAuth_token,
            signing_secret=slack_signing_secret
        )
        
        self.handler = SlackRequestHandler(self.bolt_app)
        
        self.user_db = user_db
        self.conv_db = conv_db
        self.dify_client = DifyClient()
        self.slack = SlackProcess(self.bolt_app)
        
        # 타이핑 
        self.typing_dots = ["", ".", "..", "..."]
        # 앱 멘션 이벤트 리스너 (일반 채널용)
        self.bolt_app.event("app_mention")(self.handle_mention)
        # DM 메시지 이벤트 리스너
        self.bolt_app.message()(self.handle_dm)
        # 슬래시 커맨드 등록
        self.bolt_app.command("/bot-settings")(self.handle_settings_command)
        
    def handle_request(self,request):
        return self.handler.handle(request)
    
    def handle_mention(self, event, say):
        """일반 채널에서의 멘션 처리"""
        self._process_message(event, say)
    
    def handle_dm(self, message, say):
        """DM 채널에서의 메시지 처리"""
        if message.get('bot_id') or message.get('channel_type') != 'im':
            return
            
        self._process_message(message, say)
    
    def _process_message(self, event, say):
        """메시지 처리 로직"""
        if event.get('bot_id'):
            return
        
        if event.get('command'):
            channel_id = event['channel_id']
            
            
        channel_id = event['channel']
        thread_ts = event.get('thread_ts', event['ts'])
        user_query = re.sub(r'^<@[^>]+>\s*', '', event['text'])
        user_id = event.get('user')
        
        # load user models and prompts
        user_model = self.user_db.get_current_model(user_id)
        user_prompt = self.user_db.get_current_prompt(user_id)
        
        if not user_model:
            user_model = "gpt-3.5-turbo"
            self.user_db.set_user_model(user_id, user_model)
        if not user_prompt:
            user_prompt = "test"
            self.user_db.set_user_prompt(user_id, user_prompt)
        
        user_query = f"Model:{user_model} Prompt:{user_prompt}" + user_query
        
        # thread_ts에 해당하는 DifyClient 가져오기
        conversation_id = self.conv_db.get_conversation(str(thread_ts))
    
         # conversation_id가 없으면 새로 생성
        if not conversation_id:
            conversation_id = self.dify_client.create_conversation(user_id)
            self.conv_db.save_conversation(str(thread_ts), conversation_id)
            debug_print(f"Created new conversation: {conversation_id} for thread: {thread_ts}")
        else:
            self.dify_client.set_conversation_id(conversation_id)
            debug_print(f"Get conversation_id from redis: {conversation_id} for thread: {thread_ts}")
                    
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
            
            self._process_dify_response(
                user_query,
                event.get('user', ''),
                channel_id,
                tmp_ts,
            )
            
        except Exception as e:
            debug_print(f"Error in conversation handling: {e}")
            self.slack.chat_update(channel_id, "처리 중 오류가 발생했습니다.", tmp_ts)
    
    def _show_waiting_animation(self, channel_id, tmp_ts):
        start_time = time.time()
        idx = 0
        while time.time() - start_time < 3:
            current_text = f"잠시만 기다려주세요{self.typing_dots[idx]}..🤔⏳"
            self.slack.chat_update(channel_id, current_text, tmp_ts)
            idx = (idx + 1) % len(self.typing_dots)
            time.sleep(0.5)
    
    def _process_dify_response(self, user_query, user_id, channel_id, tmp_ts):
        
        response = self.dify_client.chat_messages_stream(
            user_query,
            user_id,
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
                    tmp_ts
                )
            except json.JSONDecodeError as e:
                debug_print(f"JSON decode error: {e}")
        
        time.sleep(0.5)
        final_text = self.accumulated_response if self.is_complete else f"{self.accumulated_response} ⏳ ..."
        final_text += "\n더 필요하신 부분이 있으면 말씀해주세요."
        self.slack.chat_update(channel_id, final_text, tmp_ts)

    def _handle_stream_line(self, line, channel_id, tmp_ts):
        if line.startswith('data: '):
            data = json.loads(line[6:])
            
            if 'event' in data and data['event'] == 'message':
                message_chunk = data.get('answer', '')
                self.accumulated_response += message_chunk
                
                current_time = time.time()
                if current_time - self.last_update_time >= self.update_interval:
                    self.slack.chat_update(
                        channel_id, 
                        f"{self.accumulated_response} ⏳ ...", 
                        tmp_ts
                    )
                    self.last_update_time = current_time
                
            elif 'event' in data and data['event'] == 'message_end':
                self.is_complete = True
                time.sleep(0.5)
                self.slack.chat_update(channel_id, self.accumulated_response, tmp_ts)
                    
    
    def run(self, port=web_port):
        self.app.run(port=port, debug=False)

    def handle_settings_command(self, ack, body, client):
        """설정 메인 메뉴 모달"""
        ack()
        
        try:
            user_id = body['user_id']
            channel_id = body['channel_id']
            
            # DB에서 현재 모델과 프롬프트 가져오기
            current_model = self.user_db.get_current_model(user_id)
            current_prompt = self.user_db.get_current_prompt(user_id)
            available_models = ["gpt-3.5-turbo", "gpt-4", "claude-2"]  # 예시 모델 목록
            
            # 모달 열기
            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "settings_modal",
                    "title": {"type": "plain_text", "text": "Bot 설정"},
                    "submit": {"type": "plain_text", "text": "저장"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "*모델 설정*"},
                            "accessory": {
                                "type": "static_select",
                                "placeholder": {"type": "plain_text", "text": "모델 선택"},
                                "options": [
                                    {
                                        "text": {"type": "plain_text", "text": model},
                                        "value": model
                                    } for model in available_models
                                ],
                                "initial_option": {
                                    "text": {"type": "plain_text", "text": current_model},
                                    "value": current_model
                                },
                                "action_id": "model_select"
                            }
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "*현재 프롬프트*"},
                        },
                        {
                            "type": "input",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "prompt_input",
                                "initial_value": current_prompt
                            },
                            "label": {
                                "type": "plain_text",
                                "text": "프롬프트 수정"
                            }
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "프롬프트 수정"},
                                    "action_id": "prompt_edit"
                                }
                            ]
                        }
                    ]
                }
            )
        except Exception as e:
            debug_print(f"Error in handle_settings_command: {e}")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="설정을 불러오는 중 오류가 발생했습니다."
            )

if __name__ == '__main__':
    server = SlackBotServer()
    server.run()