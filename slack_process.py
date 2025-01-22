from config import *
import requests
from flask import make_response
from utils import get_headers, debug_print


def url_verification(request_json):
    '''
    https://api.slack.com/events/url_verification
    https://stackoverflow.com/questions/70391828/slack-app-error-new-request-url-your-url-didnt-respond-with-the-value-of-the
    '''
    challenge = request_json.get('challenge')
    response = make_response(f"challenge={challenge}", 200)
    response.headers['Content-Type'] = 'application/x-www-form-urlencoded'

    return response

def post_messages(channel_id, message, thread_ts, icon_emoji=":white_check_mark:"):
    '''
    https://api.slack.com/messaging/sending#permissions
    Bot User OAuth Token과 channel_id가 있어야하며,
    channels:read, chat:write 권한이 있어야 함.(https://api.slack.com/apps/A089RJDC3LZ/oauth?success=1)
    '''
    api_url = f"{slack_base_url}/api/chat.postMessage",
    
    response = requests.post(api_url, 
                headers=get_headers(slack_OAuth_token),
                json={
                    "channel": channel_id,
                    "text": message,
                    "thread_ts": thread_ts,
                    "icon_emoji": icon_emoji, #ooth chat:write.customize permission required
                }
            )
    logger.log_slack_event(f'Slack chat.postMessage{response.status_code}: {response.text}')
    debug_print("응답 데이터를 Slack으로 전송합니다.")
    
    return response, response.json()

