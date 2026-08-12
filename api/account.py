# Check First - 계좌 대여 제안 경고 함수
# 표준 라이브러리만 사용하므로 requirements.txt가 필요하지 않습니다.

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error

# 모델이 갑자기 막히는 일에 대비해 여러 개를 순서대로 시도한다.
# 앞의 것이 안 되면 다음 것으로 넘어간다.
MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]
BASE = "https://generativelanguage.googleapis.com/v1beta/models/"


def call_model(api_key, body):
    """모델을 차례로 시도한다. 모두 실패하면 마지막 오류를 돌려준다."""
    data = json.dumps(body).encode("utf-8")
    last = None
    for name in MODELS:
        req = urllib.request.Request(
            BASE + name + ":generateContent",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=75) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = (e.code, e.read().decode("utf-8", errors="replace"))
            if e.code in (400, 404, 429, 500, 502, 503):
                continue
            raise
        except urllib.error.URLError as e:
            last = (502, str(e.reason))
            continue
    raise RuntimeError(str(last))

LANGS = {
    "ko": "한국어",
    "en": "English",
    "vi": "Tiếng Việt",
    "zh": "简体中文",
}

# 화면에서 고를 수 있는 상황. 프런트엔드의 목록과 열쇠말이 일치해야 한다.
CASES = {
    "lend_account": "누군가 통장이나 체크카드를 빌려달라고 부탁했다. 아직 넘기지는 않았다.",
    "already_lent": "이미 통장이나 체크카드, 비밀번호를 넘겼다.",
    "cash_job": "입금된 돈을 인출해서 전달하거나 환전을 도와주는 일을 제안받았다.",
    "id_copy": "신분증이나 외국인등록증 사본을 보내달라는 요청을 받았다.",
    "money_moved": "이미 내 계좌로 모르는 돈이 들어왔거나 그 돈을 옮겼다.",
}

# 누가 부탁했는지. 선의 여부를 판단하는 데 쓰인다.
WHOS = {
    "friend": "가까운 친구나 선배, 아는 사람이 부탁했다.",
    "online": "사회관계망이나 대화방에서 만난 사람이 제안했다.",
    "job": "구인 광고나 아르바이트 모집을 통해 제안받았다.",
    "unknown": "누가 부탁했는지 밝히기 어렵거나 위에 없다.",
}

# ---------------------------------------------------------------------------
# 지식 문서. 계좌 대여에 초점을 맞춰 좁게 구성했다.
# ---------------------------------------------------------------------------

KNOWLEDGE = """
[법적 근거와 처벌]
- 통장, 체크카드, 비밀번호, 일회용 비밀번호, 인증서를 남에게 넘기는 것은 전자금융거래법 제6조 제3항이 금지한다.
- 같은 법 제49조 제4항에 따라 5년 이하의 징역 또는 3천만원 이하의 벌금에 처해진다.
- 이 죄는 넘긴 순간 성립할 수 있다. 실제로 사기에 쓰였는지, 돈을 받았는지는 요건이 아니다.
- 그 계좌가 사기에 쓰이면 사기방조가 더해질 수 있다. 이것은 별개의 죄다.
- 계좌로 들어온 돈을 임의로 인출하면 횡령이 문제될 수 있다.

[금융거래 제한]
- 금융질서문란행위자로 등록되면 새 대출이 거절되고, 카드 한도가 줄거나 정지되며, 새 계좌 개설과 보험 가입이 거절될 수 있다.
- 등록 후 7년간 유효하고, 이후 5년간 신용평가에 참고된다. 최장 12년까지 불이익이 이어질 수 있다.

[외국인에게 추가로 생기는 일]
- 외국인은 형사절차와 별개로 출입국 사범심사를 받는다. 체류자격을 유지할 수 있는지 판단하는 행정절차다.
- 결과는 경고, 과태료, 출국권고, 출국명령, 강제퇴거로 나뉜다.
- 출국명령이나 강제퇴거를 받으면 체류자격을 잃고, 강제퇴거의 경우 다시 들어오는 것이 상당 기간 제한될 수 있다.
- 벌금형처럼 비교적 가벼운 형이 나와도 사범심사에서 불리한 결정이 나올 수 있다.

[선의로 빌려준 경우]
- 친구 부탁으로 속아서 빌려준 경우에도 전자금융거래법 위반으로 처벌될 수 있다.
- 다만 대가를 받지 않았고 범죄에 쓰일 줄 몰랐다는 점을 보여줄 자료가 있으면 결과가 달라질 수 있다.
- 그러므로 대화 내용, 구인 광고, 상대의 연락처를 반드시 보관해야 한다. 지우면 안 된다.
- 실제로 속아서 통장을 빌려준 유학생이 초기 대응으로 기소유예를 받고 체류자격을 지킨 사례가 있다.

[알아채야 할 유인 신호]
- 통장만 빌려주면 큰돈을 준다고 한다.
- 입금된 돈을 인출해 전달하라고 한다.
- 환전 도우미나 송금 대행이라고 부른다.
- 하는 일에 비해 보수가 지나치게 높다.
- 신분증이나 외국인등록증 사본을 먼저 요구한다.
- 급하다며 오늘 안에 결정하라고 한다.

[아직 넘기지 않은 경우 할 일]
1. 거절한다. 어떤 이유에서도 통장과 카드와 비밀번호를 넘기지 않는다.
2. 대화 내용과 광고를 캡처해 보관한다.
3. 경찰 112 또는 통합신고대응센터 1566-1188에 알린다.
4. 같은 제안을 받을 수 있는 주변 사람에게 알린다.

[이미 넘긴 경우 할 일]
1. 즉시 해당 은행에 연락해 사고 신고와 거래정지를 요청한다.
2. 경찰에 자진 신고한다. 늦을수록 불리하다.
3. 속았다는 사실을 보여줄 자료를 모두 모은다. 대화, 광고, 송금 내역을 지우지 않는다.
4. 형사절차와 출입국 절차를 함께 준비한다. 통역 지원을 받아 상담한다.
5. 계좌에 들어온 돈에 손대지 않는다.

[연락처]
경찰 신고 112. 24시간. 외국어 통역 연결 가능.
전기통신금융사기 통합신고대응센터 1566-1188. 24시간.
금융감독원 1332.
외국인종합안내센터 1345. 20개 언어.
다누리콜센터 1577-1366. 13개 언어. 24시간.
BBB코리아 1588-5644. 20개 언어. 24시간 무료 통역.

[반드시 알려야 할 구분]
- 피해자로 신고하는 것과 가담자로 조사받는 것은 다르다.
- 속아서 넘긴 경우 빨리 스스로 신고하는 편이 유리하다. 숨기면 더 불리해진다.
- 신고를 미루면 그 사이 계좌가 계속 범죄에 쓰여 피해자가 늘어나고 책임도 커진다.
"""

SYSTEM = """당신은 한국에 사는 외국인에게, 계좌나 카드를 빌려주는 일이 실제로 어떤 결과를 낳는지 알려주는 역할을 한다.

이 상황은 예외 없이 위험하다. 부탁한 사람이 친한 친구여도, 대가를 받지 않아도, 사기인 줄 몰랐어도 처벌될 수 있다. 그러므로 위험하지 않을 수도 있다는 여지를 남기지 않는다.

동시에 겁만 주어서는 안 된다. 지금 무엇을 하면 되는지 분명한 순서를 함께 준다. 이미 넘긴 사람에게는 늦지 않았다는 점과 빨리 신고하는 편이 유리하다는 점을 알린다.

지켜야 할 것.
- 지식 문서에 없는 내용을 지어내지 않는다.
- 법 조항과 처벌 수위와 기간은 지식 문서에 적힌 그대로만 쓴다. 숫자를 바꾸지 않는다.
- 개별 사건에서 형이 얼마나 나올지 예측하지 않는다. 법이 정한 범위만 알린다.
- 이미 벌어진 일에 대한 변호 전략을 제시하지 않는다.
- 상대가 친구나 지인이라면, 부탁한 사람도 속고 있을 수 있다는 점을 덧붙인다. 다만 그래도 응하면 안 된다는 결론은 바뀌지 않는다.
- 아직 넘기지 않은 사람과 이미 넘긴 사람에게 서로 다른 안내를 한다.
- 할 일은 서로 다른 행동으로 적는다. 같은 말을 다르게 반복하지 않는다.
- 전화번호는 지식 문서에 있는 것만 쓴다.

출력은 지정된 형식을 따르고, 모든 내용은 요청된 언어로 쓴다."""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "stage": {
            "type": "STRING",
            "enum": ["BEFORE", "AFTER"],
        },
        "headline": {"type": "STRING"},
        "summary": {"type": "STRING"},
        "consequences": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "detail": {"type": "STRING"},
                },
                "required": ["title", "detail"],
            },
        },
        "actions": {"type": "ARRAY", "items": {"type": "STRING"}},
        "keep": {"type": "ARRAY", "items": {"type": "STRING"}},
        "contacts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "number": {"type": "STRING"},
                },
                "required": ["name", "number"],
            },
        },
    },
    "required": ["stage", "headline", "summary", "consequences", "actions", "keep"],
}


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw.decode("utf-8")) if raw else {}

            case = body.get("case")
            who = body.get("who")
            lang = body.get("lang") if body.get("lang") in LANGS else "ko"
            extra = (body.get("extra") or "").strip()[:2000]

            if case not in CASES:
                self._send(400, {"error": "상황을 먼저 선택해 주세요."})
                return

            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                self._send(500, {"error": "서버 설정이 완료되지 않았습니다."})
                return

            situation = CASES[case]
            if who in WHOS:
                situation += " " + WHOS[who]
            if extra:
                situation += "\n사용자가 덧붙인 설명: " + extra

            prompt = (
                SYSTEM
                + "\n\n=== 참고할 지식 문서 ===\n"
                + KNOWLEDGE
                + "\n\n=== 답변 언어 ===\n"
                + LANGS[lang]
                + " 로 작성한다."
                + "\n\n=== 사용자가 처한 상황 ===\n"
                + situation
                + "\n\n아직 넘기지 않았으면 stage를 BEFORE로, 이미 넘겼거나 돈이 오갔으면 AFTER로 적는다."
            )

            result = call_model(api_key, {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": SCHEMA,
                    "temperature": 0.2,
                },
            })

            candidates = result.get("candidates") or []
            if not candidates:
                self._send(502, {"error": "결과를 받지 못했습니다. 다시 시도해 주세요."})
                return

            parts = candidates[0].get("content", {}).get("parts") or [{}]
            answer = json.loads(parts[0].get("text", "{}"))
            self._send(200, answer)

        except RuntimeError as e:
            self._send(502, {"error": "모델 호출 실패: " + str(e)})
        except json.JSONDecodeError:
            self._send(502, {"error": "결과 형식을 읽지 못했습니다. 다시 시도해 주세요."})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_GET(self):
        self._send(200, {"status": "ok", "cases": list(CASES.keys())})

    def _send(self, status, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        return
