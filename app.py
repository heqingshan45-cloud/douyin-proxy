"""
抖音网页版反代 - 修复版
"""
from flask import Flask, request, Response
import requests
import re
import os

app = Flask(__name__)

UPSTREAM = "https://www.douyin.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.douyin.com/",
}

SUBS = r"(www|api|v|webcast|sso|passport|m|creator|buyin|ecom|fulink|live)"

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def proxy(path):
    # /go/https://api.douyin.com/xxx → 提取真实URL
    if path.startswith("go/"):
        target = path[3:]  # 直接得到 https://api.douyin.com/xxx
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
        location = re.sub(
            r"https?://" + SUBS + r"\.douyin\.com",
            "/go/https://" + r"\1.douyin.com",
            location
        )
        return Response(status=resp.status_code, headers={"Location": location})

    # 处理HTML
    if "text/html" in content_type:
        body = resp.text
        body = re.sub(
            r"https?://" + SUBS + r"\.douyin\.com",
            "/go/https://" + r"\1.douyin.com",
            body
        )
        inject = f"""<script>
(function(){{
  function rewrite(u){{
    if(typeof u!=='string')return u;
    return u.replace(new RegExp('https?://((?:{SUBS})\\.douyin\\.com)','g'),'/go/https://$1');
  }}
  var of=window.fetch;
  window.fetch=function(){{
    if(arguments[0]&&typeof arguments[0]==='string')arguments[0]=rewrite(arguments[0]);
    else if(arguments[0]&&arguments[0].url)arguments[0]=new Request(rewrite(arguments[0].url),arguments[0]);
    return of.apply(this,arguments);
  }};
  var ox=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(m,u){{return ox.call(this,m,rewrite(u));}};
}})();
</script>"""
        body = body.replace("</head>", inject + "</head>")
        excluded = ["content-encoding", "transfer-encoding", "content-length", "content-security-policy"]
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
        headers["Content-Type"] = "text/html; charset=utf-8"
        return Response(body, status=resp.status_code, headers=headers)

    # JSON/其他内容直接透传
    excluded = ["content-encoding", "transfer-encoding", "content-length"]
    headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
    return Response(resp.content, status=resp.status_code, headers=headers)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
