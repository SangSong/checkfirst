# Check First - 서버 연결 점검용 함수
# 표준 라이브러리만 사용하므로 requirements.txt가 필요하지 않습니다.

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error

MODEL = "gemini-2.5-flash"
ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODEL
    + ":generateContent"
)


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw.decode("utf-8")) if raw else {}
            prompt = (body.get("prompt") or "").strip()

            if not prompt:
                self._send(400, {"error": "prompt가 비어 있습니다."})
                return

            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                self._send(500, {
                    "error": "GEMINI_API_KEY가 설정되지 않았습니다. "
                             "Vercel 프로젝트 설정에서 환경변수를 등록한 뒤 "
                             "다시 배포해 주세요."
                })
                return

            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}]
            }).encode("utf-8")

            req = urllib.request.Request(
                ENDPOINT,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            text = result["candidates"][0]["content"]["parts"][0]["text"]
            self._send(200, {"text": text})

        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            self._send(e.code, {"error": "모델 호출 실패: " + detail})
        except urllib.error.URLError as e:
            self._send(502, {"error": "외부 연결 실패: " + str(e.reason)})
        except (KeyError, IndexError):
            self._send(502, {"error": "예상과 다른 응답 형식을 받았습니다."})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_GET(self):
        self._send(200, {
            "status": "ok",
            "message": "함수는 살아 있습니다. 실제 요청은 POST로 보내세요."
        })

    def _send(self, status, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        return
