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
        text="잠시만 기다려주세요...🤔"
    )
    tmp_ts = tmp_response_json.get('ts')
    
    def core():
        typing_dots = ["", ".", "..", "..."]
        
        try:
            # 초기 "잠시만 기다려주세요" 메시지를 3초간 표시
            start_time = time.time()
            idx = 0
            while time.time() - start_time < 5.5:
                current_text = f"잠시만 기다려주세요{typing_dots[idx]}🤔"
                chat_update(channel_id, current_text, tmp_ts)
                idx = (idx + 1) % len(typing_dots)
                time.sleep(0.5)
            
            if conversation_mapper.get(str(thread_ts)): 
                dify_conversation_id = conversation_mapper.get(str(thread_ts))
            else: 
                dify_conversation_id = ''
            
            response = chat_messages_stream(user_query, user_id, dify_conversation_id)
            
            accumulated_response = ""
            conversation_id = None
            last_update_time = time.time()
            update_interval = 0.6
            is_complete = False  # 메시지 완료 여부 추적
            
            for line in response.iter_lines():
                if line:
                    try:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = json.loads(line[6:])
                            
                            if 'event' in data and data['event'] == 'message':
                                message_chunk = data.get('answer', '')
                                accumulated_response += message_chunk
                                
                                current_time = time.time()
                                if current_time - last_update_time >= update_interval:
                                    # 진행 중일 때는 모래시계 표시
                                    chat_update(channel_id, f"{accumulated_response} ⏳ ...", tmp_ts)
                                    last_update_time = current_time
                                
                            elif 'event' in data and data['event'] == 'end':
                                conversation_id = data.get('conversation_id')
                                is_complete = True
                                time.sleep(0.5)
                                # 완료되면 모래시계 제거
                                chat_update(channel_id, accumulated_response, tmp_ts)
                                break
                                
                    except json.JSONDecodeError as e:
                        debug_print(f"JSON decode error: {e}")
                        continue
            
            # 혹시 모를 마지막 업데이트
            time.sleep(0.5)
            final_text = accumulated_response if is_complete else f"{accumulated_response}"
            chat_update(channel_id, final_text, tmp_ts)
            
            if conversation_id:
                conversation_mapper[str(thread_ts)] = conversation_id
            
        except Exception as e:
            debug_print(f"Error in core processing: {e}")
            chat_update(channel_id, "처리 중 오류가 발생했습니다.", tmp_ts)

    if ts != "" or thread_ts != "":
        threading.Thread(target=core).start()

    return "Processing your request...", 200

if __name__ == '__main__':
    app.run(port = web_port, debug=False)