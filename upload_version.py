import requests

# 配置参数
owner = "dingmama123141"
repo = "JsonConfiguration"
token = "577df5e6829a600271587e1af4793fb7"

# 创建 Release
def create_release():
    url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/releases"
    headers = {"Authorization": f"token {token}"}
    data = {
        "tag_name": "v1.0.1",
        "name": "Release v1.0.1",
        "body": "新增功能说明...",
        "target_commitish": "main"
    }
    response = requests.post(url, headers=headers, json=data)
    print(response.json())

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
create_release()
download_url = get_latest_download_url()
if download_url:
    download_file(download_url)