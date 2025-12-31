import os
import requests
import json

# 尝试加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.getenv("BAIDU_API_KEY", "")
SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")

def main():
        
    url = os.getenv("BAIDU_ASR_URL", "https://vop.baidu.com/server_api")
    
    payload = json.dumps({
        "format": "pcm",
        "rate": 16000,
        "channel": 1,
        "cuid": "esFgXNWKYPicbF9pIWU04x0R83N6SBCK",
        "token": get_access_token()
    }, ensure_ascii=False)
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload.encode("utf-8"))
    
    response.encoding = "utf-8"
    print(response.text)
    

def get_access_token():
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    url = os.getenv("BAIDU_TOKEN_URL", "https://aip.baidubce.com/oauth/2.0/token")
    params = {"grant_type": "client_credentials", "client_id": API_KEY, "client_secret": SECRET_KEY}
    return str(requests.post(url, params=params).json().get("access_token"))

if __name__ == '__main__':
    main()
