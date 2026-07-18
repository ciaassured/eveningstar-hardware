#!/usr/bin/env node

const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { spawn } = require("node:child_process");

if (process.argv.length !== 3) {
  console.error("usage: review-server.js REPORT_DIR");
  process.exit(2);
}

const root = fs.realpathSync(process.argv[2]);
const mimeTypes = new Map([
  [".glb", "model/gltf-binary"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".pdf", "application/pdf"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
]);

function openBrowser(url) {
  if (process.env.EVENINGSTAR_REVIEW_NO_OPEN) return;
  const command = process.platform === "darwin" ? "open" : "xdg-open";
  try {
    const opener = spawn(command, [url], { detached: true, stdio: "ignore" });
    opener.on("error", () => {});
    opener.unref();
  } catch {
    // The printed URL remains the fallback when no desktop opener is available.
  }
}

function sendError(response, status, message) {
  response.writeHead(status, { "Content-Type": "text/plain; charset=utf-8" });
  response.end(`${message}\n`);
}

const server = http.createServer((request, response) => {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
  } catch {
    sendError(response, 400, "Bad request");
    return;
  }

  let file = path.resolve(root, `.${pathname}`);
  if (file !== root && !file.startsWith(`${root}${path.sep}`)) {
    sendError(response, 403, "Forbidden");
    return;
  }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, "index.html");
  if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {
    sendError(response, 404, "Not found");
    return;
  }

  response.writeHead(200, {
    "Content-Type": mimeTypes.get(path.extname(file).toLowerCase()) || "application/octet-stream",
    "Cache-Control": "no-store",
  });
  if (request.method === "HEAD") {
    response.end();
    return;
  }
  fs.createReadStream(file).on("error", () => response.destroy()).pipe(response);
});

server.on("error", (error) => {
  console.error(`error: could not start the review server: ${error.message}`);
  process.exit(1);
});

server.listen(0, "127.0.0.1", () => {
  const address = server.address();
  const url = `http://127.0.0.1:${address.port}/`;
  console.log(`Review server: ${url}`);
  console.log("Press Ctrl+C to stop.");
  openBrowser(url);
});

process.on("SIGINT", () => server.close(() => process.exit(0)));
process.on("SIGTERM", () => server.close(() => process.exit(0)));
