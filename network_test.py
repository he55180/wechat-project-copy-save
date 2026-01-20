
import requests
import platform

print(f"--- 启动网络连通性测试 ---")
print(f"Python 版本: {platform.python_version()}")
print(f"requests 库版本: {requests.__version__}")
print("-" * 30)

services = [
    {"name": "Google News RSS", "url": "https://news.google.com/rss/search?q=test&hl=zh-CN&gl=CN"},
    {"name": "Bing News Search", "url": "https://www.bing.com/news/search?q=test&format=rss"},
    {"name": "Google Gemini API", "url": "https://generativelanguage.googleapis.com"}
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

all_success = True
results = []

for service in services:
    name = service["name"]
    url = service["url"]
    result = {"name": name, "status": "", "details": ""}
    print(f"[*] 正在测试: {name} ({url})...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if 200 <= response.status_code < 300:
            result["status"] = "成功"
            result["details"] = f"服务器响应状态码 {response.status_code}"
            print(f"  [✓] 成功: {result['details']}\n")
        else:
            all_success = False
            result["status"] = "失败"
            result["details"] = f"服务器返回错误状态码 {response.status_code}"
            print(f"  [!] 失败: {result['details']}\n")
    except requests.exceptions.RequestException as e:
        all_success = False
        result["status"] = "失败"
        result["details"] = f"发生网络请求错误。类型: {type(e).__name__}"
        print(f"  [X] 失败: {result['details']}\n      错误信息: {e}\n")
    results.append(result)

print("-" * 30)
print("--- 测试结论 ---")
if all_success:
    print("[✓] 所有核心服务均可正常连接。网络通畅。" )
else:
    print("[X] 检测到网络连接问题。请检查以下失败的服务项：")
    for res in results:
        if res['status'] == '失败':
            print(f"  - 服务: {res['name']}")
            print(f"    状态: {res['details']}")
print("-" * 30)
