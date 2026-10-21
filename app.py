"""
抖音网页版反代 v4 - 修复视频播放
重写JSON API响应中的视频/图片URL
"""
from flask import Flask, request, Response
import requests
import re
import json
import os

app = Flask(__name__)

UPSTREAM = "https://www.douyin.com"

# 匹配所有抖音相关域名
PATTERN = re.compile(
    r'https?://[\w.-]+\.(?:douyin\.com|douyinpic\.com|douyinvod\.com|douyinstatic\.com|snssdk\.com|bytedance\.com|byteimg\.com|douyincdn\.com)'
)

def to_proxy(match):
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

    excluded = ["content-encoding", "transfer-encoding", "content-length", "content-security-policy"]
    resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}

    # HTML页面
    if "text/html" in content_type:
        body = resp.text
        body = PATTERN.sub(to_proxy, body)
        inject = """<script>
(function(){
  var re=/https?:\\/\\/[\\w.-]+\\.(?:douyin\\.com|douyinpic\\.com|douyinvod\\.com|douyinstatic\\.com|snssdk\\.com|bytedance\\.com|byteimg\\.com|douyincdn\\.com)/g;
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
  // 拦截动态创建的video/img/script标签
  function fixEl(el){
    if(el.src&&re.test(el.src))el.src=rw(el.src);
    if(el.href&&re.test(el.href))el.href=rw(el.href);
  }
  var obs=new MutationObserver(function(muts){
    muts.forEach(function(m){
      m.addedNodes.forEach(function(n){
        if(n.nodeType===1){
          fixEl(n);
          n.querySelectorAll&&n.querySelectorAll('img,video,script,source,link').forEach(fixEl);
        }
      });
    });
  });
  obs.observe(document.documentElement,{childList:true,subtree:true});
})();
</script>"""
        body = body.replace("</head>", inject + "</head>")
        resp_headers["Content-Type"] = "text/html; charset=utf-8"
        return Response(body, status=resp.status_code, headers=resp_headers)

    # JSON API响应 - 重写里面的视频/图片URL
    if "json" in content_type:
        body = resp.text
        body = PATTERN.sub(to_proxy, body)
        return Response(body, status=resp.status_code, headers=resp_headers)

    # CSS/JS文件
    if "text/css" in content_type or "javascript" in content_type:
        body = resp.text
        body = PATTERN.sub(to_proxy, body)
        return Response(body, status=resp.status_code, headers=resp_headers)

    # 图片/视频/其他二进制直接透传
    return Response(resp.content, status=resp.status_code, headers=resp_headers)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
