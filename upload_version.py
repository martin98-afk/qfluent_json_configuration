import requests

# 配置参数
owner = "mading12315"
repo = "JsonConfiguration"
token = "J9r98fXvxywspbdivTje2yQM"

# 创建 Release
def create_release(tag_name, name, body):
    url = f"https://api.gitcode.com/api/v5/repos/{owner}/{repo}/releases"
    headers = {"Authorization": token}
    data = {
        "tag_name": tag_name,
        "name": name,
        "body": body,
        "target_commitish": "master"
    }
    response = requests.post(url, headers=headers, json=data)
    print(response.json())

def get_upload_url(tag_name):
    url = f"https://api.gitcode.com/api/v5/repos/mading12315/JsonConfiguration/releases/0.1.1/upload_url"
    headers = {
        "Authorization": token,
        'Accept': 'application/json'
    }
    payload = {
        "file_name": "main.exe"
    }
    response = requests.get(url, headers=headers, data=payload)
    return response.json()

# 获取最新 Release 下载链接
def get_latest_download_url():
    url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/releases/latest"
    response = requests.get(url)
    assets = response.json().get("assets", [])
    if assets:
        return assets[0]["browser_download_url"]
    return None

# 下载文件
def download_file(download_url):
    response = requests.get(download_url, stream=True)
    with open("software.zip", "wb") as f:
        for chunk in response.iter_content(chunk_size=1024):
            f.write(chunk)

# 示例流程
import json
with open("versions.json", "r", encoding="utf-8") as f:
    data = json.load(f)
latest_release = sorted(data, key=lambda x: x["version"], reverse=True)[0]
create_release(latest_release["version"], "参数配置工具", "\n".join(latest_release["publishNotes"]))
url = get_upload_url(latest_release["version"])
print(url)
download_url = get_latest_download_url()
if download_url:
    download_file(download_url)