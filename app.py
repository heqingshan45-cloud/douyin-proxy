"""
抖音网页版反代 v3 - 完整版
覆盖所有抖音CDN域名（图片/视频/静态资源）
"""
from flask import Flask, request, Response
import requests
import re
import os

app = Flask(__name__)

UPSTREAM = "https://www.douyin.com"

# 匹配所有抖音相关域名：xxx.douyin.com, xxx.douyinpic.com, xxx.douyinvod.com 等
PATTERN = re.compile(
    r'https?://[\w.-]+\.(?:douyin\.com|douyinpic\.com|douyinvod\.com|douyinstatic\.com|snssdk\.com|bytedance\.com|byteimg\.com)'
)

def to_proxy(match):
    """把匹配到的URL转成代理路径"""
    return "/go/" + match.group(0)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.douyin.com/",
}

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def proxy(path):
    # /go/https://xxx.com/yyy → 提取真实URL
    if path.startswith("go/"):
        target = path[3:]
        if request.query_string:
            target += "?" + request.query_string.decode()
    else:
        target = UPSTREAM + "/" + path
        if request.query_string:
            target += "?" + request.query_string.decode()

    try:
        resp = requests.request(
            method=request.method,
            url=target,
            headers=HEADERS,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=30,
        )
    except Exception as e:
        return f"代理错误: {e}", 502

    content_type = resp.headers.get("Content-Type", "")

    # 处理重定向
    if resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("Location", "")
        location = PATTERN.sub(to_proxy, location)
        return Response(status=resp.status_code, headers={"Location": location})

    # HTML页面
    if "text/html" in content_type:
        body = resp.text
        body = PATTERN.sub(to_proxy, body)
        inject = """<script>
(function(){
  var re=/https?:\\/\\/[\\w.-]+\\.(?:douyin\\.com|douyinpic\\.com|douyinvod\\.com|douyinstatic\\.com|snssdk\\.com|bytedance\\.com|byteimg\\.com)/g;
  function rw(u){
    if(typeof u!=='string')return u;
    return u.replace(re,function(m){return '/go/'+m;});
  }
  var of=window.fetch;
  window.fetch=function(){
    if(arguments[0]&&typeof arguments[0]==='string')arguments[0]=rw(arguments[0]);
    else if(arguments[0]&&arguments[0].url)arguments[0]=new Request(rw(arguments[0].url),arguments[0]);
    return of.apply(this,arguments);
  };
  var ox=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(m,u){return ox.call(this,m,rw(u));};
})();
</script>"""
        body = body.replace("</head>", inject + "</head>")
        excluded = ["content-encoding", "transfer-encoding", "content-length", "content-security-policy"]
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
        headers["Content-Type"] = "text/html; charset=utf-8"
        return Response(body, status=resp.status_code, headers=headers)

    # CSS/JS文件
    if "text/css" in content_type or "javascript" in content_type:
        body = resp.text
        body = PATTERN.sub(to_proxy, body)
        excluded = ["content-encoding", "transfer-encoding", "content-length"]
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
        return Response(body, status=resp.status_code, headers=headers)

    # 图片/视频/其他二进制直接透传
    excluded = ["content-encoding", "transfer-encoding", "content-length"]
    headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
    return Response(resp.content, status=resp.status_code, headers=headers)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
