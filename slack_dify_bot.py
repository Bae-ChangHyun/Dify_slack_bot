import os
import re
import json
import time
import threading
from flask import Flask, request, g
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

from config import *
from utils import debug_print, logger
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
        self.available_models = ["exaone3.5", "llama3.2-vision", "deepseek-r1"]
        
        # 앱 멘션 이벤트 리스너 (일반 채널용)
        self.bolt_app.event("app_mention")(self.handle_mention)
        # DM 메시지 이벤트 리스너
        self.bolt_app.message()(self.handle_dm)
        # 슬래시 커맨드 등록
        self.bolt_app.command("/bot-settings")(self.handle_settings_command)
        
        # 모델 선택 액션 핸들러 추가
        self.bolt_app.action("model_select")(self.handle_model_select)
        
        # 프롬프트 수정 액션 핸들러 추가
        self.bolt_app.action("prompt_edit")(self.handle_prompt_edit)
        self.bolt_app.action("prompt_input")(self.handle_prompt_input)
        
        # 액션 핸들러 등록
        self.bolt_app.command("/bot-settings")(self.handle_settings_command)
        self.bolt_app.action("model_select")(self.handle_model_select)
        self.bolt_app.action("open_prompt_modal")(self.handle_open_prompt_modal)
        self.bolt_app.view("prompt_edit_modal")(self.handle_prompt_submit)
        self.bolt_app.view("main_settings_modal")(self.handle_settings_submit)
        
        self.is_complete = False  # is_complete 속성 초기화
        
    def handle_request(self,request):
        return self.handler.handle(request)
    
    def handle_mention(self, event, say):
        """일반 채널에서의 멘션 처리"""
        bot = SlackBot(self.user_db, self.conv_db)
        debug_print(f"SlackBot created for mention event")
        bot._process_message(event, say)
    
    def handle_dm(self, message, say):
        """DM 채널에서의 메시지 처리"""
        if message.get('bot_id') or message.get('channel_type') != 'im':
            return
            
        bot = SlackBot(self.user_db, self.conv_db)  
        debug_print(f"SlackBot created for DM event")
        bot._process_message(message, say)
    
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
            user_model = "exaone3.5"
            self.user_db.set_user_model(user_id, user_model)
        if not user_prompt:
            user_prompt = "test"
            self.user_db.set_user_prompt(user_id, user_prompt)
        
        user_query = f"Model:{user_model} Prompt:{user_prompt} Query:{user_query}" 
        
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
        
        # 3초 후에도 답변이 오지 않았다면 추가 메시지 전송
        if not self.is_complete:
            self.slack.chat_update(channel_id, "조금 더 시간이 걸릴 것 같습니다. 잠시만 기다려주세요...⏳", tmp_ts)
    
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
        formatted_line = self._format_line_for_logging(final_text)
        logger.log_llm_response(formatted_line)
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
        """메인 설정 모달"""
        ack()
        bot = SlackBot(self.user_db, self.conv_db)
        debug_print(f"SlackBot created")
        bot.handle_settings_command_impl(body, client)

    def handle_model_select(self, ack, body, client):
        """모델 선택 처리"""
        ack()
        try:
            user_id = body['user']['id']
            selected_model = body['actions'][0]['selected_option']['value']
            metadata = json.loads(body['view']['private_metadata'])
            metadata['current_model'] = selected_model
            
            # 현재 뷰의 블록 업데이트
            blocks = body['view']['blocks']
            client.views_update(
                view_id=body['view']['id'],
                view={
                    "type": "modal",
                    "callback_id": "main_settings_modal",
                    "title": {"type": "plain_text", "text": "Bot 설정"},
                    "blocks": blocks,
                    "submit": {"type": "plain_text", "text": "저장"},
                    "private_metadata": json.dumps(metadata)
                }
            )
        except Exception as e:
            debug_print(f"Error in handle_model_select: {e}")

    def handle_prompt_edit(self, ack, body, client):
        """프롬프트 수정 버튼 처리"""
        ack()
        try:
            user_id = body['user']['id']
            view_id = body['view']['id']
            
            # 현재 입력된 프롬프트 값 가져오기
            blocks = body['view']['blocks']
            prompt_block = next(
                (block for block in blocks if block.get('block_id') == 'prompt_input'),
                None
            )
            
            if prompt_block:
                new_prompt = prompt_block['element']['value']
                # DB에 새로운 프롬프트 저장
                self.user_db.set_user_prompt(user_id, new_prompt)
                
                # 모달 업데이트
                client.views_update(
                    view_id=view_id,
                    view={
                        "type": "modal",
                        "callback_id": "settings_modal",
                        "title": {"type": "plain_text", "text": "Bot 설정"},
                        "blocks": blocks,
                        "submit": {"type": "plain_text", "text": "저장"}
                    }
                )
        except Exception as e:
            debug_print(f"Error in handle_prompt_edit: {e}")

    def handle_prompt_input(self, ack, body, client):
        """프롬프트 입력 필드 변경 처리"""
        ack()
        try:
            user_id = body['user']['id']
            new_prompt = body['actions'][0]['value']
            self.user_db.set_user_prompt(user_id, new_prompt)
        except Exception as e:
            debug_print(f"Error in handle_prompt_input: {e}")

    def handle_open_prompt_modal(self, ack, body, client):
        """프롬프트 수정 모달 열기"""
        ack()
        try:
            metadata = json.loads(body['view']['private_metadata'])
            current_prompt = metadata['current_prompt']
            
            client.views_push(
                trigger_id=body['trigger_id'],
                view={
                    "type": "modal",
                    "callback_id": "prompt_edit_modal",
                    "title": {"type": "plain_text", "text": "프롬프트 수정"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "prompt_input_block",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "prompt_input",
                                "initial_value": current_prompt,
                                "multiline": True
                            },
                            "label": {"type": "plain_text", "text": "프롬프트"}
                        }
                    ],
                    "submit": {"type": "plain_text", "text": "완료"},
                    "private_metadata": body['view']['private_metadata']
                }
            )
        except Exception as e:
            debug_print(f"Error in handle_open_prompt_modal: {e}")

    def handle_prompt_submit(self, ack, body, client):
        """프롬프트 수정 완료 처리"""
        ack()
        try:
            metadata = json.loads(body['view']['private_metadata'])
            new_prompt = body['view']['state']['values']['prompt_input_block']['prompt_input']['value']
            metadata['current_prompt'] = new_prompt
            current_model = metadata['current_model']
            
            # 모델 선택 설정
            select_config = {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "모델 선택"},
                "options": [
                    {"text": {"type": "plain_text", "text": model}, "value": model}
                    for model in self.available_models
                ],
                "action_id": "model_select"
            }
            
            # 현재 모델이 available_models에 있는 경우에만 initial_option 설정
            if current_model in self.available_models:
                select_config["initial_option"] = {
                    "text": {"type": "plain_text", "text": current_model},
                    "value": current_model
                }
            
            # 메인 설정 모달로 돌아가기
            client.views_update(
                view_id=body['view']['previous_view_id'],
                view={
                    "type": "modal",
                    "callback_id": "main_settings_modal",
                    "title": {"type": "plain_text", "text": "Bot 설정"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "*AI 모델 설정*"},
                            "accessory": select_config
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*현재 프롬프트*\n{new_prompt}"},
                            "accessory": {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "프롬프트 수정"},
                                "action_id": "open_prompt_modal"
                            }
                        }
                    ],
                    "submit": {"type": "plain_text", "text": "저장"},
                    "private_metadata": json.dumps(metadata)
                }
            )
        except Exception as e:
            debug_print(f"Error in handle_prompt_submit: {e}")

    def handle_settings_submit(self, ack, body, client):
        """최종 설정 저장"""
        ack()
        try:
            user_id = body['user']['id']
            metadata = json.loads(body['view']['private_metadata'])
            
            # DB에 설정 저장
            self.user_db.set_user_model(user_id, metadata['current_model'])
            self.user_db.set_user_prompt(user_id, metadata['current_prompt'])
        except Exception as e:
            debug_print(f"Error in handle_settings_submit: {e}")

    def handle_settings_command_impl(self, body, client):
        """메인 설정 모달 구현부"""
        try:
            user_id = body['user_id']
            
            # 현재 설정 가져오기
            current_model = self.user_db.get_current_model(user_id) or "exaone3.5"
            current_prompt = self.user_db.get_current_prompt(user_id) or "기본 프롬프트"
            
            # 모델 선택 옵션 생성
            select_options = [
                {
                    "text": {"type": "plain_text", "text": model},
                    "value": model
                } for model in self.available_models
            ]
            
            # 모델 선택 설정
            select_config = {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "모델 선택"},
                "options": select_options,
                "action_id": "model_select"
            }
            
            if current_model in self.available_models:
                select_config["initial_option"] = {
                    "text": {"type": "plain_text", "text": current_model},
                    "value": current_model
                }
            
            # 메인 설정 모달 표시
            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "main_settings_modal",
                    "title": {"type": "plain_text", "text": "Bot 설정"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "*AI 모델 설정*"},
                            "accessory": select_config
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*현재 프롬프트*\n{current_prompt}"},
                            "accessory": {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "프롬프트 수정"},
                                "action_id": "open_prompt_modal"
                            }
                        }
                    ],
                    "submit": {"type": "plain_text", "text": "저장"},
                    "private_metadata": json.dumps({
                        "current_model": current_model,
                        "current_prompt": current_prompt
                    })
                }
            )
        except Exception as e:
            debug_print(f"Error in handle_settings_command_impl: {e}")

    def _format_line_for_logging(self, line_text):
        try:
            line_data = json.loads(line_text[6:])  # "data: " 제거
            return {
                "event": line_data.get("event", ""),
                "answer": line_data.get("answer", ""),
            }
        except json.JSONDecodeError:
            return {"event": "", "answer": line_text}

if __name__ == '__main__':
    server = SlackBotServer()
    server.run()