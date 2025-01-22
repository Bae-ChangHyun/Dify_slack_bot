from flask import Flask, request, jsonify, make_response
import requests
import json
import os
from threading import Thread, Timer

app = Flask(__name__)

# .env 파일에서 API 키를 로드
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv('api_key')

if not api_key:
    raise ValueError("API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")

def send_processing_message(response_url, user_query):
    """주기적으로 'Processing your query' 메시지를 Slack에 전송"""
    def send_message():
        requests.post(response_url, json={"text": f"Processing your query: `{user_query}` ..."})
        Timer(3, send_message).start()  # 3초마다 반복

    send_message()

@app.route('/slack/dify-chat', methods=['POST'])
def handle_slash_command():
    slack_data = request.form
    user_query = slack_data.get('text', '')  # Slack 사용자가 입력한 텍스트
    response_url = slack_data.get('response_url')  # Slack response_url
    user_id = slack_data.get('user_id')  # Slack 사용자 ID
    
    if not response_url:
        return "Error: response_url is missing", 200
    
    print("사용자 쿼리:", user_query)  # 사용자 쿼리 로그 추가

    # 외부 API 호출 요청
    external_api_url = "http://118.38.20.101:81/v1/chat-messages"  # 실제 API 엔드포인트
    payload = {
        "inputs": {},
        "query": user_query,
        "response_mode": "blocking",  # blocking 모드
        "user": user_id,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 초기 응답 전송
    initial_response = {
        "response_type": "ephemeral",
        "text": f"Processing your query: `{user_query}` ..."
    }
    requests.post(response_url, json=initial_response)

    # 주기적으로 'Processing your query' 메시지 전송
    #send_processing_message(response_url, user_query)

    def fetch_response():
        try:
            # 외부 API로 요청을 보내고 전체 응답을 기다림
            response = requests.post(external_api_url, json=payload, headers=headers)
            print(f"외부 API 응답 상태 코드: {response.status_code}")  # 응답 상태 코드 로그 추가

            if response.status_code == 401:
                print("인증 실패: API 키를 확인하세요.")  # 인증 실패 로그 추가
                requests.post(response_url, json={"text": "Authentication failed. Please check the API key."})
                return

            if response.status_code != 200:
                print(f"오류 발생: {response.text}")  # 오류 로그 추가
                requests.post(response_url, json={"text": f"Error: {response.text}"})
                return

            # 응답 데이터를 JSON으로 디코딩
            json_data = response.json()
            print(f"받은 데이터: {json_data}")  # 받은 데이터 로그 추가

            # 중요한 데이터를 Slack에 보내기
            if json_data.get("mode") == "advanced-chat":
                print("응답 데이터를 Slack으로 전송합니다.")
                answer = json_data.get("answer", "")
                markdown_answer = f"```\n{answer}\n```"
                slack_response = requests.post(response_url, json={"text": markdown_answer})
                print(f"Slack response url:{response_url}")
                print(f"Slack 응답 상태 코드: {slack_response.status_code}")  # Slack 응답 상태 코드 로그 추가
                if slack_response.status_code != 200:
                    print(f"Slack 응답 오류: {slack_response.text}")  # Slack 응답 오류 로그 추가

        except requests.RequestException as e:
            print(f"요청 예외 발생: {str(e)}")  # 예외 로그 추가
            requests.post(response_url, json={"text": f"Request failed: {str(e)}"})

    # 비동기적으로 fetch_response 함수 실행
    thread = Thread(target=fetch_response)
    thread.start()

    return "Processing your request...", 200

if __name__ == '__main__':
    app.run(port = 3000, debug=True)