"""Hello World web application for the Docker fundamentals homework."""

import os
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "5000"))
STUDENT = "Vibhuti Bhatnagar"
ROLL_NO = "24BCS10288"
BATCH = "B"

PAGE = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Hello World - Python</title>
    <style>
      body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
             display: grid; place-items: center; height: 100vh; margin: 0; }}
      .card {{ background: #1e293b; padding: 2.5rem 3rem; border-radius: 12px;
              border: 1px solid #334155; text-align: center; }}
      h1 {{ margin: 0 0 .5rem; color: #60a5fa; }}
      p {{ margin: .25rem 0; color: #94a3b8; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Hello World</h1>
      <p>Python application running in Docker</p>
      <p>{STUDENT} &middot; {ROLL_NO} &middot; Batch {BATCH}</p>
    </div>
  </body>
</html>"""


class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("python-app: " + fmt % args, flush=True)


if __name__ == "__main__":
    print(f"Python app listening on port {PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), HelloHandler).serve_forever()
