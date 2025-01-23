import os
import re
import json
import time
import requests
import threading
from flask import Flask, request, jsonify, make_response

from config import *
from utils import debug_print
from dify_process import chat_messages, chat_messages_stream
from slack_process import url_verification, post_messages, chat_update

class SlackBot:
    def __init__(self):
        self.app = Flask(__name__)
        self.conversation_mapper = dict()
        self.processed_events = set()
        self.typing_dots = ["", ".", "..", "..."]
        
        # 라우트 설정
        self.app.route('/slack/dify-chat', methods=['POST'])(self.handle_event)
    
    def handle_event(self):
        """슬랙 이벤트 처리 메인 핸들러"""
        debug_print("#"*70+"START"+"#"*70)
        slack_data = request.get_json()
        
        if slack_data.get('type') == 'url_verification':
            return url_verification(slack_data)
            
        debug_print(f"Slack chat:{slack_data}")
        logger.log_slack_event(slack_data)
        
        event_data = self._extract_event_data(slack_data)
        if not event_data:
            return "Invalid event data", 400
            
        if event_data['event_id'] in self.processed_events:
            return "Already processed", 200
            
        self._process_event(event_data)
        return "Processing your request...", 200
    
    def _extract_event_data(self, slack_data):
        """이벤트 데이터 추출 및 가공"""
        try:
            event = slack_data.get('event', {})
            return {
                'user_query': re.sub(r'^<@[^>]+>\s*', '', event.get('text', '')),
                'user_id': event.get('user', ''),
                'channel_id': event.get('channel', ''),
                'ts': event.get('ts', ''),
                'thread_ts': event.get('thread_ts', event.get('ts', '')),
                'event_id': slack_data.get('event_id', '')
            }
        except Exception as e:
            debug_print(f"Error extracting event data: {e}")
            return None
    
    def _process_event(self, event_data):
        """이벤트 처리 및 응답 생성"""
        self.processed_events.add(event_data['event_id'])
        if len(self.processed_events) > 1000:
            self.processed_events.clear()
        
        # 임시 메시지 전송
        tmp_response, tmp_response_json = post_messages(
            channel_id=event_data['channel_id'],
            thread_ts=event_data['thread_ts'],
            text="잠시만 기다려주세요...🤔"
        )
        tmp_ts = tmp_response_json.get('ts')
        
        # 스레드 시작
        threading.Thread(
            target=self._handle_conversation,
            args=(event_data, tmp_ts)
        ).start()
    
    def _handle_conversation(self, event_data, tmp_ts):
        """대화 처리 로직"""
        try:
            # 초기 대기 메시지 애니메이션
            self._show_waiting_animation(event_data['channel_id'], tmp_ts)
            
            # Dify 대화 처리
            dify_conversation_id = self.conversation_mapper.get(str(event_data['thread_ts']), '')
            
            self._process_dify_response(
                event_data,
                tmp_ts,
                dify_conversation_id
            )
            
        except Exception as e:
            debug_print(f"Error in conversation handling: {e}")
            chat_update(
                event_data['channel_id'],
                "처리 중 오류가 발생했습니다.",
                tmp_ts
            )
    
    def _show_waiting_animation(self, channel_id, tmp_ts):
        """대기 애니메이션 표시"""
        start_time = time.time()
        idx = 0
        while time.time() - start_time < 3:
            current_text = f"잠시만 기다려주세요{self.typing_dots[idx]}🤔..⏳"
            chat_update(channel_id, current_text, tmp_ts)
            idx = (idx + 1) % len(self.typing_dots)
            time.sleep(0.5)
    
    def _process_dify_response(self, event_data, tmp_ts, dify_conversation_id):
        """Dify 응답 처리 및 메시지 업데이트"""
        response = chat_messages_stream(
            event_data['user_query'],
            event_data['user_id'],
            dify_conversation_id
        )
        
        # 클래스 변수로 상태 관리
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
                    event_data,
                    tmp_ts
                )
            except json.JSONDecodeError as e:
                debug_print(f"JSON decode error: {e}")
        
        # 혹시 모를 마지막 업데이트
        time.sleep(0.5)
        final_text = self.accumulated_response if self.is_complete else f"{self.accumulated_response}"
        final_text += "\n더 필요하신 부분이 있으면 말씀해주세요."
        chat_update(event_data['channel_id'], final_text, tmp_ts)

    def _handle_stream_line(self, line, event_data, tmp_ts):
        """스트림 라인 처리"""
        if line.startswith('data: '):
            data = json.loads(line[6:])
            
            if 'event' in data and data['event'] == 'message':
                message_chunk = data.get('answer', '')
                self.accumulated_response += message_chunk
                
                current_time = time.time()
                if current_time - self.last_update_time >= self.update_interval:
                    # 진행 중일 때는 모래시계 표시
                    chat_update(
                        event_data['channel_id'], 
                        f"{self.accumulated_response} ⏳ ...", 
                        tmp_ts
                    )
                    self.last_update_time = current_time
                
            elif 'event' in data and data['event'] == 'end':
                conversation_id = data.get('conversation_id')
                self.is_complete = True
                time.sleep(0.5)
                # 완료되면 모래시계 제거
                chat_update(
                    event_data['channel_id'], 
                    self.accumulated_response, 
                    tmp_ts
                )
                
                if conversation_id:
                    self.conversation_mapper[str(event_data['thread_ts'])] = conversation_id
    
    def run(self, port=web_port):
        """서버 실행"""
        self.app.run(port=port, debug=False)

# 서버 실행
if __name__ == '__main__':
    bot = SlackBot()
    bot.run()