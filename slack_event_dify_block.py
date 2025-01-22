import os
import re
import json
import uuid
import requests
import threading
from flask import Flask, request, jsonify, make_response

from logger import CustomLogger  # CustomLogger 임포트
from dotenv import load_dotenv
load_dotenv()

web_port = os.getenv('web_port')
dify_api_key = os.getenv('dify_api_key')
slack_web_hook = os.getenv('slack_web_hook')
slack_OAuth_token = os.getenv('slack_OAuth_token')

dify_headers = {
        "Authorization": f"Bearer {dify_api_key}",
        "Content-Type": "application/json",
    }

conversation_mapper=dict() # Slack thread_ts와 dify conversation_id 매핑

app = Flask(__name__)
logger = CustomLogger("chat_log")

# [Event_triggger](https://api.slack.com/automation/triggers/event)
@app.route('/slack/dify-chat', methods=['POST'])
def slack_bot():

    print("#"*70+"START"+"#"*70)
    slack_data = request.get_json()
    print(f"Slack chat:{slack_data}")
    logger.log_slack_event(slack_data)
    
    if slack_data.get('type') == 'url_verification':
        # https://api.slack.com/events/url_verification
        # https://stackoverflow.com/questions/70391828/slack-app-error-new-request-url-your-url-didnt-respond-with-the-value-of-the
        challenge = slack_data.get('challenge')
        response = make_response(f"challenge={challenge}", 200)
        response.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return response
    
    #response_url = slack_web_hook
    event_data = slack_data.get('event', {})
    user_query = event_data.get('text', '')  # Slack 사용자가 입력한 텍스트
    user_query = re.sub(r'^<@[^>]+>\s*', '', user_query)
    user_id = event_data.get('user', '')  # Slack 사용자 ID
    channel_id = event_data.get('channel', '')  # Slack 채널 ID
    ts = event_data.get('ts', '')  # Slack 이벤트 타임스탬프
    thread_ts = event_data.get('thread_ts', ts) # Slack 이벤트 쓰레드 최상위 타임스탬프, 없으면 ts 사용
    
    # dify의 conversation_id를 thread_ts로 매핑
    if conversation_mapper.get(str(thread_ts)):
        dify_conversation_id = conversation_mapper.get(str(thread_ts))
    else:
        dify_conversation_id = ''
    
    # # conversation_id를 확인하기 위한 GET 요청
    # dify_conversation_api = f"http://118.38.20.101/v1/messages?user={user_id}&conversation_id="
    # response = requests.get(dify_conversation_api, headers=dify_headers)
    # if response.status_code == 200 and response.json(): conversation_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, conversation_id))
    # else: conversation_id = ""
    
    print("-"*150)
    print(f"사용자 쿼리: {user_query}, 사용자 ID: {user_id}, slack 쓰레드 ID: {thread_ts}")
    
    # https://docs.dify.ai/guides/extension/api-based-extension
    external_api_url = "http://118.38.20.101:81/v1/chat-messages"  # http://118.38.20.101:81/app/e7882139-3377-41e3-968b-866d89702c1d/develop
    payload = {
        "inputs": {},
        "query": user_query,
        "response_mode": "blocking",  # blocking 모드
        "user": user_id,
        "conversation_id":dify_conversation_id
    }            
    def send_request():
        try:
            response = requests.post(external_api_url, json=payload, headers=dify_headers)
            json_data = response.json()
            print(f"LLM BOT: {json_data}")  # dify로 부터 받은 데이터 로그 추가
            logger.log_llm_response(json_data)
            
            dify_conversation_id = json_data.get("conversation_id", '')
            conversation_mapper[str(thread_ts)] = dify_conversation_id

            if json_data.get("mode") == "advanced-chat":
                print("응답 데이터를 Slack으로 전송합니다.")
                answer = json_data.get("answer", "")
                markdown_answer = f"```\n{answer}\n```"
                
                # https://api.slack.com/messaging/sending#permissions
                # Bot User OAuth Token과 channel_id가 있어야하며,
                # channels:read, chat:write 권한이 있어야 함.(https://api.slack.com/apps/A089RJDC3LZ/oauth?success=1)
                slack_response = requests.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={
                        "Authorization": f"Bearer {slack_OAuth_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "channel": channel_id,
                        "text": markdown_answer,
                        "thread_ts": thread_ts,
                        "icon_emoji": ":white_check_mark:", #ooth chat:write.customize permission required
                    }
                )
                    
                # else:
                # #그냥 글로 답변할 때.
                #     slack_response = requests.post(
                #         response_url,
                #         json={"text": markdown_answer,
                #               "icon_emoji": ":white_check_mark:", #ooth chat:write.customize permission required})
                #         }
                #     )     
                # if slack_response.status_code != 200: print(f"Slack {slack_response.status_code}: {slack_response.text}")  # Slack 응답 오류 로그 추가
                # else:print(f"Slack {slack_response.status_code}")  # Slack 응답 성공 로그 추가

        except requests.RequestException as e:
            print(f"요청 예외 발생: {str(e)}")
            # API 오류 로그 기록
            logger.log_api_error({
                "error": str(e),
                "status_code": response.status_code if response else "N/A",
                "url": external_api_url,
                "method": "POST",
                "response": response.text if response else "N/A"
            })

    if ts != "":  threading.Thread(target=send_request).start()
    elif thread_ts != "":  threading.Thread(target=send_request).start()

    return "Processing your request...", 200

if __name__ == '__main__':
    app.run(port = web_port, debug=True)