"""Serve the browser wallpaper exporter using only Python's standard library.

Run from any directory:
    python scripts/build_wallpapers.py
Then open http://127.0.0.1:8765/export-wallpapers.html and click the button.
The browser uses the project's wallpaper.js renderer. Accepted PNG uploads are
saved as wallpapers/verse-01.png through wallpapers/verse-75.png.
RGBA8 PNG image data is recompressed losslessly with zlib level 6; image pixels,
dimensions, filters, and all non-IDAT chunks are preserved.
Press Ctrl+C to stop. This module does not start a server when imported.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import time
import zlib


ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8765
ORIGIN = f"http://{HOST}:{PORT}"
MAX_PNG_BYTES = 15_000_000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RGBA_SCANLINE_BYTES = 3120 * (1 + 1440 * 4)
FILE_NAME = re.compile(r"verse-(?:0[1-9]|[1-6][0-9]|7[0-5])\.png", re.ASCII)
UPLOAD_ROUTE = re.compile(r"/__wallpaper-export/(verse-(?:0[1-9]|[1-6][0-9]|7[0-5])\.png)", re.ASCII)
FILES = {
    "/": ("scripts/export_wallpapers.html", "text/html; charset=utf-8"),
    "/export-wallpapers.html": ("scripts/export_wallpapers.html", "text/html; charset=utf-8"),
    "/wallpaper.js": ("wallpaper.js", "text/javascript; charset=utf-8"),
    "/content.json": ("content.json", "application/json; charset=utf-8"),
    "/wallpaper-background.png": ("wallpaper-background.png", "image/png"),
}


def workspace_path(relative: str) -> Path:
    """Reject paths or pre-existing symlinks which resolve outside the workspace."""
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Workspace 밖의 경로는 사용할 수 없습니다.")
    return path


def validate_png(filename: str, content: bytes) -> tuple[int, int]:
    if not FILE_NAME.fullmatch(filename):
        raise ValueError("파일 이름은 verse-01.png부터 verse-75.png까지 허용합니다.")
    if not 33 <= len(content) <= MAX_PNG_BYTES:
        raise ValueError("PNG 파일 크기는 33바이트 이상, 15 MB 이하여야 합니다.")
    if content[:8] != PNG_SIGNATURE:
        raise ValueError("올바른 PNG 서명이 아닙니다.")
    if content[8:12] != b"\x00\x00\x00\x0d" or content[12:16] != b"IHDR":
        raise ValueError("PNG의 첫 청크는 13바이트 IHDR이어야 합니다.")
    dimensions = struct.unpack(">II", content[16:24])
    if dimensions != (1440, 3120):
        raise ValueError("PNG 해상도는 1440 × 3120이어야 합니다.")
    return dimensions


def recompress_png(content: bytes) -> bytes:
    """Recompress supported RGBA8 IDAT data, retaining every other chunk verbatim.

    Unsupported or malformed inputs are returned unchanged. Decompression is
    bounded to exactly this image size's filtered RGBA8 scanline byte count;
    nothing is unfiltered, recolored, resized, or rendered again.
    """
    if len(content) < 33 or content[:8] != PNG_SIGNATURE:
        return content
    expected_ihdr = struct.pack(">II", 1440, 3120) + b"\x08\x06\x00\x00\x00"
    if content[8:16] != b"\x00\x00\x00\x0dIHDR" or content[16:29] != expected_ihdr:
        return content
    chunks = []
    idat_parts = []
    offset = 8
    idat_finished = False
    while offset < len(content):
        if offset + 12 > len(content):
            return content
        length = struct.unpack(">I", content[offset:offset + 4])[0]
        end = offset + length + 12
        if end > len(content):
            return content
        tag = content[offset + 4:offset + 8]
        payload = content[offset + 8:end - 4]
        crc = struct.unpack(">I", content[end - 4:end])[0]
        if zlib.crc32(tag + payload) & 0xFFFFFFFF != crc:
            return content
        if tag in (b"acTL", b"fcTL", b"fdAT"):
            return content
        if tag == b"IHDR" and offset != 8:
            return content
        if tag == b"IDAT":
            if idat_finished:
                return content
            idat_parts.append(payload)
        elif idat_parts:
            idat_finished = True
        if tag == b"IEND" and (length != 0 or end != len(content)):
            return content
        chunks.append((tag, content[offset:end]))
        offset = end
    if not chunks or chunks[-1][0] != b"IEND" or not idat_parts:
        return content

    def bounded_decompress(compressed: bytes) -> bytes | None:
        try:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(compressed, RGBA_SCANLINE_BYTES)
        except zlib.error:
            return None
        if (len(raw) != RGBA_SCANLINE_BYTES or not decoder.eof
                or decoder.unconsumed_tail or decoder.unused_data):
            return None
        return raw

    raw = bounded_decompress(b"".join(idat_parts))
    if raw is None:
        return content
    compressed = zlib.compress(raw, level=6)
    if bounded_decompress(compressed) != raw:
        raise ValueError("PNG 재압축 전후의 이미지 데이터가 다릅니다.")
    chunk_body = b"IDAT" + compressed
    replacement = struct.pack(">I", len(compressed)) + chunk_body + struct.pack(">I", zlib.crc32(chunk_body) & 0xFFFFFFFF)
    result = [PNG_SIGNATURE]
    wrote_idat = False
    for tag, original_chunk in chunks:
        if tag == b"IDAT":
            if not wrote_idat:
                result.append(replacement)
                wrote_idat = True
        else:
            result.append(original_chunk)
    optimized = b"".join(result)
    return optimized if len(optimized) < len(content) else content


def save_png(filename: str, content: bytes) -> int:
    validate_png(filename, content)
    content = recompress_png(content)
    folder = workspace_path("wallpapers")
    folder.mkdir(exist_ok=True)
    target = workspace_path(f"wallpapers/{filename}")
    if target.parent != folder:
        raise ValueError("허용되지 않는 저장 경로입니다.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".wallpaper-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        for attempt in range(5):
            try:
                os.replace(temporary, target)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                # Windows scanners can briefly hold the destination file open.
                time.sleep(0.1 * (attempt + 1))
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return len(content)


class ExportHandler(BaseHTTPRequestHandler):
    server_version = "ScriptureWallpaperExporter/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def send_bytes(self, status: int, content: bytes, mime: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(content)
        self.close_connection = True

    def send_json(self, status: int, value: dict) -> None:
        self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def local_host(self) -> bool:
        if self.headers.get("Host") != f"{HOST}:{PORT}":
            self.send_json(403, {"error": f"{ORIGIN} 주소로 접속해 주세요."})
            return False
        return True

    def do_GET(self):
        if not self.local_host():
            return
        asset = FILES.get(self.path)
        if asset is None:
            self.send_json(404, {"error": "허용된 내보내기 파일만 제공됩니다."})
            return
        relative, mime = asset
        try:
            content = workspace_path(relative).read_bytes()
        except (OSError, ValueError):
            self.send_json(404, {"error": f"필요한 파일을 찾지 못했습니다: {relative}"})
            return
        self.send_bytes(200, content, mime)

    def do_POST(self):
        if not self.local_host():
            return
        if self.headers.get("Origin") != ORIGIN:
            self.send_json(403, {"error": "이 로컬 내보내기 페이지에서 보낸 요청만 허용합니다."})
            return
        route = UPLOAD_ROUTE.fullmatch(self.path)
        if route is None:
            self.send_json(404, {"error": "허용되지 않는 파일 이름 또는 업로드 경로입니다."})
            return
        if self.headers.get("Transfer-Encoding"):
            self.send_json(400, {"error": "Content-Length가 있는 PNG 요청이 필요합니다."})
            return
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit():
            self.send_json(411, {"error": "올바른 Content-Length가 필요합니다."})
            return
        length = int(lengths[0])
        if not 33 <= length <= MAX_PNG_BYTES:
            self.send_json(413, {"error": "PNG 파일 크기는 33바이트 이상, 15 MB 이하여야 합니다."})
            return
        if self.headers.get_content_type() != "image/png":
            self.send_json(415, {"error": "image/png 형식만 저장할 수 있습니다."})
            return
        try:
            content = self.rfile.read(length)
            if len(content) != length:
                raise ValueError("PNG 업로드가 끝나기 전에 연결이 종료되었습니다.")
            filename = route.group(1)
            saved_bytes = save_png(filename, content)
        except TimeoutError:
            self.send_json(408, {"error": "PNG 업로드 대기 시간을 초과했습니다."})
            return
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
            return
        except OSError:
            self.send_json(500, {"error": "wallpapers 폴더에 PNG를 저장하지 못했습니다."})
            return
        self.send_json(201, {"ok": True, "filename": filename, "receivedBytes": len(content), "bytes": saved_bytes, "width": 1440, "height": 3120})


def main() -> None:
    for relative, _ in FILES.values():
        if not workspace_path(relative).is_file():
            raise SystemExit(f"Required file missing: {relative}")
    with ThreadingHTTPServer((HOST, PORT), ExportHandler) as server:
        print(f"Open {ORIGIN}/export-wallpapers.html", flush=True)
        print("Click the export button. PNG files will be saved to wallpapers/.", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nWallpaper exporter stopped.", flush=True)


if __name__ == "__main__":
    main()
