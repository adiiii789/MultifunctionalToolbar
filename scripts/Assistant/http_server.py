from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = 8000

if __name__ == "__main__":
    Handler = SimpleHTTPRequestHandler
    with ThreadingHTTPServer(("", PORT), Handler) as httpd:
        print(f"Serving at http://localhost:{PORT}")
        httpd.serve_forever()
