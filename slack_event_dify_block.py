import os
import re
import json
import time
import requests
import threading
from flask import Flask, request, jsonify, make_response

from config import *
from utils import debug_print
from dify_process import chat_messages
from slack_process import url_verification, post_messages, chat_update

conversation_mapper=dict() # Slack thread_ts와 dify conversation_id 매핑
processed_events = set() # 이미 처리된 이벤트를 저장하는 집합
dify_conversation_id=''

app = Flask(__name__)

# [Event_triggger](https://api.slack.com/automation/triggers/event)
@app.route('/slack/dify-chat', methods=['POST'])
def slack_bot():

    debug_print("#"*70+"START"+"#"*70)
    slack_data = request.get_json()
    
    if slack_data.get('type')  == 'url_verification' : return url_verification(slack_data)
    debug_print(f"Slack chat:{slack_data}")
    logger.log_slack_event(slack_data)
    
    #response_url = slack_web_hook
    event_data = slack_data.get('event', {})
    user_query = re.sub(r'^<@[^>]+>\s*', '', event_data.get('text', '')) # 멘션제거한 Slack 메시지
    user_id = event_data.get('user', '')  # Slack 사용자 ID
    channel_id = event_data.get('channel', '')  # Slack 채널 ID
    ts = event_data.get('ts', '')  # Slack 이벤트 타임스탬프
    thread_ts = event_data.get('thread_ts', ts) # Slack 이벤트 쓰레드 최상위 타임스탬프, 없으면 ts 사용
    event_id = slack_data.get('event_id', '')
    if event_id in processed_events:
        return "Already processed", 200
    
    processed_events.add(event_id)
    # 세트 크기 제한 (메모리 관리)
    if len(processed_events) > 1000:
        processed_events.clear()
    
    debug_print("-"*150)
    debug_print(f"사용자 쿼리: {user_query}, 사용자 ID: {user_id}, slack 쓰레드 ID: {thread_ts}")
    
    # 먼저 임시 메시지 전송
    tmp_response,tmp_response_json = post_messages(
        channel_id=channel_id,
        thread_ts=thread_ts,
        text="잠시만 기다려주세요... 🤔"
    )
    tmp_ts = tmp_response_json.get('ts')
    
    def core():
        
        class TypingState:
            def __init__(self):
                self.is_typing = True
                
        typing_state = TypingState()
        
        def typing_loop():
            typing_dots = ["", ".", "..", "..."]
            idx = 0
            while typing_state.is_typing:
                try:
                    current_text = f"생각하는 중{typing_dots[idx]}"
                    chat_update(channel_id, current_text, tmp_ts)
                    idx = (idx + 1) % len(typing_dots)
                    time.sleep(0.5)
                except Exception as e:
                    debug_print(f"Typing indicator error: {e}")
                    break
         # typing indicator 스레드 시작
        typing_thread = threading.Thread(target=typing_loop)
        typing_thread.daemon = True
        typing_thread.start()
        
        try:
            # dify의 conversation_id를 slack thread_ts로 매핑
            if conversation_mapper.get(str(thread_ts)): dify_conversation_id = conversation_mapper.get(str(thread_ts))
            else: dify_conversation_id = ''
            
            # dify로 쿼리를 날리고, 응답을 가져옴
            llm_response, llm_response_json = chat_messages(user_query, user_id, dify_conversation_id)
            
            dify_conversation_id = llm_response_json.get("conversation_id")
            conversation_mapper[str(thread_ts)] = dify_conversation_id
        
            #answer = f"```\n{llm_response_json.get('answer', '에러가 발생하였습니다. 다시 시도해주세요.')}\n```"
            answer = f"{llm_response_json.get('answer', '에러가 발생하였습니다. 다시 시도해주세요.')}"
            
            # typing indicator 중단
            typing_state.is_typing = False
            typing_thread.join(timeout=3)  # 3초 타임아웃 설정
        
            #post_messages(channel_id, answer, thread_ts)
            chat_update(channel_id, answer, tmp_ts)
            
        except Exception as e:
            typing_state.is_typing = False
            typing_thread.join(timeout=3)  # 3초 타임아웃 설정
            debug_print(f"Error in core processing: {e}")
            post_messages(channel_id, "처리 중 오류가 발생했습니다.", thread_ts)
        

    if ts != "" or thread_ts != "":
        threading.Thread(target=core).start()

    return "Processing your request...", 200

if __name__ == '__main__':
    app.run(port = web_port, debug=False)