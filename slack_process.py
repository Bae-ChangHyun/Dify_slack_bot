from config import *
import requests
from flask import make_response
from utils import get_headers, debug_print
import time

from slack_bolt import App

app = App(token=slack_OAuth_token)

# https://api.slack.com/methods

def url_verification(request_json):
    '''
    https://api.slack.com/apps/A089RJDC3LZ/event-subscriptions?
    https://api.slack.com/events/url_verification
    https://stackoverflow.com/questions/70391828/slack-app-error-new-request-url-your-url-didnt-respond-with-the-value-of-the
    '''
    challenge = request_json.get('challenge')
    response = make_response(f"challenge={challenge}", 200)
    response.headers['Content-Type'] = 'application/x-www-form-urlencoded'
    
    #TODO -request에서 error나는 경우 정의하기
    #error = request_json.get('error','')
    #logger.log_api_status('GET',f"/slack/dify-chat", response, error)
    logger.log_api_status('GET',f"/slack/dify-chat", response)

    return response

def post_messages(channel_id, text, thread_ts, icon_emoji=":white_check_mark:"):
    '''
    https://api.slack.com/messaging/sending#permissions
    Bot User OAuth Token과 channel_id가 있어야하며,
    channels:read, chat:write 권한이 있어야 함.(https://api.slack.com/apps/A089RJDC3LZ/oauth?success=1)
    '''
    end_point = "api/chat.postMessage"
    api_url = f"{slack_base_url}/{end_point}"
    
    response = requests.post(api_url, 
                headers=get_headers(slack_OAuth_token),
                json={
                    "channel": channel_id,
                    "text": text,
                    "thread_ts": thread_ts,
                    "icon_emoji": icon_emoji, #ooth chat:write.customize permission required
                    "mrkdwn": True
                }
            )
    
    # 실패해도 200으로 응답됨 -> error 필드로 확인
    error = response.json().get('error','')
    logger.log_api_status("POST", f"/{end_point}", response, error)

    return response, response.json()

def chat_update(channel_id, text, ts, retry_count=3):
    '''
    https://api.slack.com/methods/chat.update
    '''
    end_point = "api/chat.update"
    api_url = f"{slack_base_url}/{end_point}"
    
    for attempt in range(retry_count):
        response = requests.post(api_url,
                    headers=get_headers(slack_OAuth_token),
                    json={
                        "channel": channel_id,
                        "text": text,
                        "ts": ts,
                        "as_user": True
                    }
                )
        error = response.json().get('error','')
        
        if not error:
            break
            
        if error == 'message_not_found' and attempt < retry_count - 1:
            time.sleep(0.5)  # 재시도 전 대기
            continue
            
        logger.log_api_status("POST", f"/{end_point}", response, error)
        
        if attempt == retry_count - 1:
            raise Exception(f"Failed to update message after {retry_count} attempts: {error}")
    
    return response


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
