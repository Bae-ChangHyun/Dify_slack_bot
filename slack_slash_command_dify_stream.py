from flask import Flask, Response, request
import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('api_key')

app = Flask(__name__)

# Slack 명령어 엔드포인트
@app.route('/slack/dify-chat', methods=['POST'])
def handle_slash_command():
    # Slack 명령 처리
    slack_data = request.form
    print(slack_data)
    user_query = slack_data.get('text', '')  # Slack 사용자가 입력한 텍스트
    response_url = slack_data.get('response_url')  # Slack response_url
    user_id = slack_data.get('user_id')  # Slack 사용자 ID
    
    # 외부 API 호출 요청
    external_api_url = "http://118.38.20.101:81/v1/chat-messages"  # 실제 API 엔드포인트
    payload = {
        "inputs": {},
        "query": user_query,
        "response_mode": "streaming",  # streaming 모드
        "user": user_id,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 비동기 데이터 전송을 위한 Slack 초기 응답
    initial_response = {
        "response_type": "ephemeral",
        "text": f"Processing your query: `{user_query}` ..."
    }
    requests.post(response_url, json=initial_response)

   # SSE 데이터 처리 함수
    def stream_data():
        try:
            # SSE 요청을 외부 API로 전송 (stream=True)
            with requests.post(external_api_url, json=payload, headers=headers, stream=True) as response:
                print("Connected to the streaming API")
                buffer = ""
                # 외부 API에서 데이터를 청크 단위로 받아 처리
                print(response)
                for chunk in response.iter_content(chunk_size=512):  # 청크 크기: 512바이트
                    if chunk:
                        decoded_chunk = chunk.decode('utf-8')  # 데이터를 문자열로 디코딩
                        buffer += decoded_chunk

                        # 청크에서 개별 'data:' 메시지를 추출
                        while "data:" in buffer:
                            newline_index = buffer.find("\n\n")  # 개별 데이터 종료 위치
                            if newline_index == -1:
                                break
                            # 개별 메시지를 data로 추출
                            sse_data = buffer[:newline_index].strip().replace("data: ", "")
                            buffer = buffer[newline_index + 2:]

                            # JSON으로 디코딩
                            try:
                                json_data = json.loads(sse_data)
                                with open("log.txt", "a") as f:
                                    f.write(json.dumps(json_data) + "\n")
                            except json.JSONDecodeError:
                                print("JSON decoding error")
                                continue  # JSON 해석 오류는 건너뛴다

                            # 중요한 데이터를 Slack에 보내기 (message 관련 이벤트 처리 예제)
                            if json_data.get("event") == "message":
                                answer_chunk = json_data.get("answer", "")
                                # Slack 추가 응답
                                requests.post(response_url, json={"text": answer_chunk})
                            elif json_data.get("event") == "message_end":
                                # 스트리밍 종료 이벤트 처리
                                requests.post(response_url, json={"text": "Streaming has ended."})
                                return
                            elif json_data.get("event") == "error":
                                # 오류 이벤트 처리
                                error_message = json_data.get("message", "An error occurred.")
                                requests.post(response_url, json={"text": f"Error: {error_message}"})
                                return

        except requests.RequestException as e:
            # 요청 예외 처리
            requests.post(response_url, json={"text": f"Request failed: {str(e)}"})

    # 비동기적으로 stream_data 함수 실행
    from threading import Thread
    thread = Thread(target=stream_data)
    thread.start()

    return "Processing your request...", 200


if __name__ == '__main__':
    app.run(port=3000, debug=True)