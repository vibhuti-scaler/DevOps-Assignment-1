import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

/** Hello World web application for the Docker fundamentals homework. */
public class Main {

    private static final int PORT = 8080;
    private static final String STUDENT = "Vibhuti Bhatnagar";
    private static final String ROLL_NO = "24BCS10288";
    private static final String BATCH = "B";

    private static final String PAGE = """
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <title>Hello World - Java</title>
                <style>
                  body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
                         display: grid; place-items: center; height: 100vh; margin: 0; }
                  .card { background: #1e293b; padding: 2.5rem 3rem; border-radius: 12px;
                          border: 1px solid #334155; text-align: center; }
                  h1 { margin: 0 0 .5rem; color: #f97316; }
                  p { margin: .25rem 0; color: #94a3b8; }
                </style>
              </head>
              <body>
                <div class="card">
                  <h1>Hello World</h1>
                  <p>Java application running in Docker</p>
                  <p>%s &middot; %s &middot; Batch %s</p>
                </div>
              </body>
            </html>""".formatted(STUDENT, ROLL_NO, BATCH);

    public static void main(String[] args) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress("0.0.0.0", PORT), 0);
        server.createContext("/", exchange -> {
            byte[] body = PAGE.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "text/html; charset=utf-8");
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(body);
            }
        });
        server.start();
        System.out.println("Java app listening on port " + PORT);
    }
}
