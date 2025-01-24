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
from dify_process import DifyClient
from slack_process import SlackProcess
from db_handler import ConversationDB

class SlackBot:
    # 클래스 변수로 선언하여 인스턴스 간에 공유
    
    def __init__(self):
        self.bolt_app = App(
            token=slack_OAuth_token,
            signing_secret=slack_signing_secret
        )
        self.app = Flask(__name__)
        self.handler = SlackRequestHandler(self.bolt_app)
        
        self.dify_client = DifyClient()
        self.slack = SlackProcess(self.bolt_app)  # SlackProcess 초기화
        self.typing_dots = ["", ".", "..", "..."]
        
        # Redis 핸들러 초기화 (서버 호스트로 변경)
        self.conv_db = ConversationDB(host=redis_host,port=redis_port,db=redis_db,pw=redis_password)
        
        # 앱 멘션 이벤트 리스너 (일반 채널용)
        self.bolt_app.event("app_mention")(self.handle_mention)
        # DM 메시지 이벤트 리스너
        self.bolt_app.message()(self.handle_dm)
        # Flask 라우트 설정
        self.app.route("/slack/events", methods=["POST"])(self.handle_slack_events)
        # 슬래시 커맨드 등록
        self.bolt_app.command("/bot-settings")(self.handle_settings_command)
        # 인터랙션 핸들러 등록
        self.bolt_app.action("model_select")(self.handle_model_select)
        self.bolt_app.action("prompt_edit")(self.handle_prompt_edit)
        self.bolt_app.action("prompt_refresh")(self.handle_prompt_refresh)
        self.bolt_app.view("prompt_edit_modal")(self.handle_prompt_submit)
        
    
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
        
        # Redis에서 conversation_id 조회
        conversation_id = self.conv_db.get_conversation(str(thread_ts))
    
         # conversation_id가 없으면 새로 생성
        if not conversation_id:
            conversation_id = self.dify_client.create_conversation()
            self.conv_db.save_conversation(str(thread_ts), conversation_id)
            debug_print(f"Created new conversation_id and save to redis: {conversation_id} for thread: {thread_ts}")
        else:
            debug_print(f"Get conversation_id from redis: {conversation_id} for thread: {thread_ts}")
            
        self.conversation_id = conversation_id
        
        # DifyClient에 현재 conversation_id 설정
        self.dify_client.set_conversation_id(conversation_id)
        
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
                thread_ts,
                self.conversation_id or ''
            )
            
        except Exception as e:
            debug_print(f"Error in conversation handling: {e}")
            self.slack.chat_update(channel_id, "처리 중 오류가 발생했습니다.", tmp_ts)
    
    def _show_waiting_animation(self, channel_id, tmp_ts):
        start_time = time.time()
        idx = 0
        while time.time() - start_time < 3:
            current_text = f"잠시만 기다려주세요{self.typing_dots[idx]}🤔..⏳"
            self.slack.chat_update(channel_id, current_text, tmp_ts)
            idx = (idx + 1) % len(self.typing_dots)
            time.sleep(0.5)
    
    def _process_dify_response(self, user_query, user_id, channel_id, tmp_ts, thread_ts, dify_conversation_id):
        response = self.dify_client.chat_messages_stream(
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
        self.slack.chat_update(channel_id, final_text, tmp_ts)

    def _handle_stream_line(self, line, channel_id, tmp_ts, thread_ts):
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
                conversation_id = data.get('conversation_id')
                self.is_complete = True
                time.sleep(0.5)
                self.slack.chat_update(channel_id, self.accumulated_response, tmp_ts)
                    
    def handle_settings_command(self, ack, body, client):
        """설정 메인 메뉴 모달"""
        ack()
        
        try:
            current_model = self.dify_client.get_current_model()
            current_prompt = self.dify_client.get_current_prompt()
            available_models = ["gpt-3.5-turbo", "gpt-4", "claude-2"]
            
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
                            "text": {"type": "mrkdwn", "text": "*현재 프롬프트*"}
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"```{current_prompt}```"}
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "프롬프트 수정"},
                                    "action_id": "prompt_edit"
                                },
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "🔄 프롬프트 새로고침"},
                                    "action_id": "prompt_refresh"
                                }
                            ]
                        }
                    ]
                }
            )
        except Exception as e:
            debug_print(f"Error in handle_settings_command: {e}")
            client.chat_postEphemeral(
                channel=body["channel_id"],
                user=body["user_id"],
                text="설정을 불러오는 중 오류가 발생했습니다."
            )

    def handle_model_select(self, ack, body, client):
        """모델 선택 처리"""
        ack()
        selected_model = body["actions"][0]["selected_option"]["value"]
        self.dify_client.set_model(selected_model)
        
        # 성공 메시지 표시
        client.views_update(
            view_id=body["view"]["id"],
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "설정 완료"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"모델이 *{selected_model}*로 변경되었습니다."}
                    }
                ]
            }
        )
    
    def handle_prompt_edit(self, ack, body, client):
        """프롬프트 편집 버튼 클릭 처리"""
        ack()
        
        try:
            current_prompt = self.dify_client.get_current_prompt()
            
            client.views_push(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "prompt_edit_modal",
                    "title": {"type": "plain_text", "text": "프롬프트 수정"},
                    "submit": {"type": "plain_text", "text": "저장"},
                    "close": {"type": "plain_text", "text": "취소"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "prompt_block",
                            "label": {"type": "plain_text", "text": "시스템 프롬프트"},
                            "element": {
                                "type": "plain_text_input",
                                "multiline": True,
                                "initial_value": current_prompt,
                                "action_id": "prompt_input"
                            }
                        }
                    ]
                }
            )
        except Exception as e:
            debug_print(f"Error in handle_prompt_edit: {e}")

    def handle_prompt_submit(self, ack, body, view, client):
        """프롬프트 수정 저장 처리"""
        ack()
        
        try:
            # 새 프롬프트 저장
            new_prompt = view["state"]["values"]["prompt_block"]["prompt_input"]["value"]
            result = self.dify_client.set_prompt(new_prompt)
            debug_print(f"Prompt update result: {result}")
            
        except Exception as e:
            debug_print(f"Error in handle_prompt_submit: {e}")

    def handle_prompt_refresh(self, ack, body, client):
        """프롬프트 새로고침 처리"""
        ack()
        
        try:
            # 현재 설정값 다시 조회
            current_model = self.dify_client.get_current_model()
            current_prompt = self.dify_client.get_current_prompt()
            available_models = ["gpt-3.5-turbo", "gpt-4", "claude-2"]
            
            # 모달 업데이트
            client.views_update(
                view_id=body["view"]["id"],
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
                            "text": {"type": "mrkdwn", "text": "*현재 프롬프트*"}
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"```{current_prompt}```"}
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "프롬프트 수정"},
                                    "action_id": "prompt_edit"
                                },
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "🔄 프롬프트 새로고침"},
                                    "action_id": "prompt_refresh"
                                }
                            ]
                        }
                    ]
                }
            )
        except Exception as e:
            debug_print(f"Error in handle_prompt_refresh: {e}")
    
    def run(self, port=web_port):
        self.app.run(port=port, debug=False)

if __name__ == '__main__':
    bot = SlackBot()
    bot.run()