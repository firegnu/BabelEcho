#!/usr/bin/env python3
"""Static dev server for the BabelEcho read-only frontend, with HTTP Range support.

`python -m http.server` does NOT serve byte ranges, so audio seeking (clicking the
waveform, ±15s, keyboard) doesn't work with it. This adds Range/206 handling.

Usage (run from anywhere):
    python3 frontend/serve.py [port]        # default 8137
Then open http://127.0.0.1:<port>/frontend/

Serves the repo root so both /frontend/ and /workspace/published/ are reachable.
Read-only: it only serves files; it never writes or triggers anything.
"""
import functools
import http.server
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_range", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:  # source is already positioned at the range start
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def send_head(self):
        self._range = None
        path = self.translate_path(self.path)
        if os.path.isdir(path) or "Range" not in self.headers:
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        size = os.fstat(f.fileno()).st_size
        m = re.match(r"bytes=(\d*)-(\d*)\s*$", self.headers["Range"])
        if not m:
            f.close()
            return super().send_head()
        g1, g2 = m.group(1), m.group(2)
        if g1 == "":  # suffix range: bytes=-N
            length = int(g2 or 0)
            start = max(0, size - length)
            end = size - 1
        else:
            start = int(g1)
            end = int(g2) if g2 else size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_error(416, "Requested Range Not Satisfiable")
            f.close()
            return None
        length = end - start + 1
        f.seek(start)
        self._range = length
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Last-Modified", self.date_time_string(os.fstat(f.fileno()).st_mtime))
        self.end_headers()
        return f


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    handler = functools.partial(RangeHandler, directory=REPO_ROOT)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"BabelEcho frontend → http://127.0.0.1:{port}/frontend/   (serving {REPO_ROOT})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
