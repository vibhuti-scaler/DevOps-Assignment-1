const http = require("http");

const PORT = process.env.PORT || 3000;
const STUDENT = "Vibhuti Bhatnagar";
const ROLL_NO = "24BCS10288";
const BATCH = "B";

const page = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Hello World - Node.js</title>
    <style>
      body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
             display: grid; place-items: center; height: 100vh; margin: 0; }
      .card { background: #1e293b; padding: 2.5rem 3rem; border-radius: 12px;
              border: 1px solid #334155; text-align: center; }
      h1 { margin: 0 0 .5rem; color: #4ade80; }
      p { margin: .25rem 0; color: #94a3b8; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Hello World</h1>
      <p>Node.js application running in Docker</p>
      <p>${STUDENT} &middot; ${ROLL_NO} &middot; Batch ${BATCH}</p>
    </div>
  </body>
</html>`;

http
  .createServer((req, res) => {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(page);
  })
  .listen(PORT, () => console.log(`Node.js app listening on port ${PORT}`));
