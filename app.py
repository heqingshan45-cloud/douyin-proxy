"""
抖音移动端网页版反代 - 简单版
m.douyin.com 比 www 版简单很多，视频加载更容易穿透
"""
from flask import Flask, request, Response
import requests
import re
import os

app = Flask(__name__)

UPSTREAM = "https://m.douyin.com"

PATTERN = re.compile(
    r'https?://[\w.-]+\.(?:douyin\.com|douyinpic\.com|douyinvod\.com|douyinstatic\.com|snssdk\.com|bytedance\.com|byteimg\.com|douyincdn\.com|amemv\.com|iesdouyin\.com)'
)

def to_proxy(match):
    return "/go/" + match.group(0)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://m.douyin.com/",
}

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def proxy(path):
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

    if resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("Location", "")
        location = PATTERN.sub(to_proxy, location)
        return Response(status=resp.status_code, headers={"Location": location})

    excluded = ["content-encoding", "transfer-encoding", "content-length", "content-security-policy"]
    resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}

    if "text/html" in content_type:
        body = resp.text
        body = PATTERN.sub(to_proxy, body)
        inject = """<script>
(function(){
  var re=/https?:\\/\\/[\\w.-]+\\.(?:douyin\\.com|douyinpic\\.com|douyinvod\\.com|douyinstatic\\.com|snssdk\\.com|bytedance\\.com|byteimg\\.com|douyincdn\\.com|amemv\\.com|iesdouyin\\.com)/g;
  function rw(u){if(typeof u!=='string')return u;return u.replace(re,function(m){return '/go/'+m;});}
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
        resp_headers["Content-Type"] = "text/html; charset=utf-8"
        return Response(body, status=resp.status_code, headers=resp_headers)

    if "json" in content_type:
        body = resp.text
        body = PATTERN.sub(to_proxy, body)
        return Response(body, status=resp.status_code, headers=resp_headers)

    if "text/css" in content_type or "javascript" in content_type:
        body = resp.text
        body = PATTERN.sub(to_proxy, body)
        return Response(body, status=resp.status_code, headers=resp_headers)

    return Response(resp.content, status=resp.status_code, headers=resp_headers)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
