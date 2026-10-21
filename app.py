"""
抖音网页版反代 - 部署在 Render.com 上（免费）
使用方法：
  1. 打开 https://render.com 注册（GitHub登录）
  2. New → Web Service → 部署这个文件
  3. Build Command: pip install flask requests
  4. Start Command: python app.py
  5. 部署完后打开给你的 onrender.com 地址即可刷抖音
"""
from flask import Flask, request, Response
import requests
import re

app = Flask(__name__)

UPSTREAM = "https://www.douyin.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.douyin.com/",
}

DOUYIN_SUBDOMAINS = r"(www|api|v|webcast|sso|passport|m|creator|buyin|ecom)"

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def proxy(path):
    # /go/https://api.douyin.com/xxx → 代理到子域名
    if path.startswith("go/"):
        target = request.fullpath[4:]  # 去掉 "/go/"
    else:
        target = UPSTREAM + "/" + path + ("?" + request.query_string.decode() if request.query_string else "")

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
        # 如果重定向到抖音子域名，改写为通过代理访问
        location = re.sub(
            r"https?://" + DOUYIN_SUBDOMAINS + r"\.douyin\.com",
            "/go/https://" + r"\1.douyin.com",
            location
        )
        # 相对路径转绝对
        if location.startswith("/go/"):
            pass  # 已经是代理路径
        elif location.startswith("/"):
            location = location
        return Response(
            status=resp.status_code,
            headers={"Location": location}
        )

    # 处理HTML：重写链接 + 注入拦截脚本
    if "text/html" in content_type:
        body = resp.text
        worker_host = request.host

        # 重写HTML中所有抖音子域名链接
        body = re.sub(
            r"https?://" + DOUYIN_SUBDOMAINS + r"\.douyin\.com",
            f"/go/https://" + r"\1.douyin.com",
            body
        )

        # 注入脚本：拦截JS动态请求
        inject = f"""<script>
(function(){{
  function rewrite(u){{
    if(typeof u!=='string')return u;
    return u.replace(new RegExp('https?://((?:{DOUYIN_SUBDOMAINS})\\\\.douyin\\\\.com)','g'),'/go/https://$1');
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

        # 转发响应头（过滤掉不能跨域的）
        excluded = ["content-encoding", "transfer-encoding", "content-length", "content-security-policy"]
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
        headers["Content-Type"] = "text/html; charset=utf-8"

        return Response(body, status=resp.status_code, headers=headers)

    # 其他内容直接透传
    excluded = ["content-encoding", "transfer-encoding", "content-length"]
    headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
    return Response(resp.content, status=resp.status_code, headers=headers)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
