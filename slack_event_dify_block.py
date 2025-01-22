import os
import re
import json
import uuid
import requests
import threading
from flask import Flask, request, jsonify, make_response

from config import *
from utils import debug_print
from dify_process import chat_messages
from slack_process import url_verification, post_messages

conversation_mapper=dict() # Slack thread_ts와 dify conversation_id 매핑
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
    
    debug_print("-"*150)
    debug_print(f"사용자 쿼리: {user_query}, 사용자 ID: {user_id}, slack 쓰레드 ID: {thread_ts}")
    
    def core():
        
        # dify의 conversation_id를 slack thread_ts로 매핑
        if conversation_mapper.get(str(thread_ts)): dify_conversation_id = conversation_mapper.get(str(thread_ts))
        else: dify_conversation_id = ''
                # dify로 쿼리를 날리고, 응답을 가져옴
        llm_response, llm_response_json = chat_messages(user_query, user_id, dify_conversation_id
                                                        )
        dify_conversation_id = llm_response_json.get("conversation_id")
        conversation_mapper[str(thread_ts)] = dify_conversation_id
    
        answer = f"```\n{llm_response_json.get('answer', '에러가 발생하였습니다. 다시 시도해주세요.')}\n```"
        
        post_messages(channel_id, answer, thread_ts)
           
        

    if ts != "":  threading.Thread(target=core).start()
    elif thread_ts != "":  threading.Thread(target=core).start()

    return "Processing your request...", 200

if __name__ == '__main__':
    app.run(port = web_port, debug=True)