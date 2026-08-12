# Check First - 이미 당한 뒤 응급 대응 함수
# 표준 라이브러리만 사용하므로 requirements.txt가 필요하지 않습니다.

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error

MODEL = "gemini-3.6-flash"
ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODEL
    + ":generateContent"
)

LANGS = {
    "ko": "한국어",
    "en": "English",
    "vi": "Tiếng Việt",
    "zh": "简体中文",
}

# 피해 유형. 화면의 목록과 열쇠말이 일치해야 한다.
KINDS = {
    "transfer": "계좌이체로 돈을 보냈다.",
    "cash": "사기범을 직접 만나 현금을 건넸다.",
    "giftcard": "상품권이나 기프트카드 번호를 알려줬다.",
    "crypto": "가상자산으로 보냈다.",
    "overseas": "해외로 송금했다.",
    "card": "카드 결제나 소액결제가 됐다.",
    "info_only": "계좌번호나 개인정보만 알려줬고 아직 돈은 나가지 않았다.",
    "app": "링크를 눌렀거나 앱을 설치했다.",
}

# 지난 시간. 급한 정도를 판단하는 데 쓰인다.
WHENS = {
    "just_now": "방금 벌어졌다. 30분이 지나지 않았다.",
    "today": "오늘 안에 벌어졌다.",
    "days": "하루 이상 지났다.",
}

# ---------------------------------------------------------------------------
# 지식 문서. 이미 당한 뒤의 대응에 초점을 맞췄다.
# ---------------------------------------------------------------------------

KNOWLEDGE = """
[가장 급한 것]
- 계좌이체로 보낸 경우 돈이 사기범 계좌에 남아 있을 때만 되찾을 수 있다. 사기범이 인출하면 회수가 매우 어려워진다.
- 그래서 신고 속도가 전부다. 30분이 넘어가면 회수 가능성이 크게 떨어진다.
- 1회 100만원 이상이 입금되면 입금된 때부터 30분간 자동화기기 인출이 지연된다. 이 30분 안에 지급정지를 걸면 막을 수 있다.
- 금융감독원 조사에서 피해자의 26퍼센트만 30분 안에 피해를 알아챘다.

[지급정지를 실제로 걸어주는 곳]
- 경찰 112. 24시간. 경찰과 금융회사 사이 연결로 지급정지가 실제로 걸린다. 사건번호를 받아둔다.
- 내가 돈을 보낸 은행 또는 받은 은행의 고객센터. 직접 전화하면 가장 빠르다.
- 금융감독원 1332. 24시간. 상담과 안내가 주된 역할이며 지급정지 연결도 가능하다.
- 전기통신금융사기 통합대응단 1394. 24시간. 기존 번호 1566-1188도 함께 쓰인다.
- 주말이나 밤에도 112와 1332와 1394는 열려 있다. 은행 영업점이 닫혀 있어도 고객센터로 지급정지가 가능하다.

[전화로 막은 뒤 반드시 해야 하는 것]
- 전화로 급하게 지급정지를 걸었다면, 그날부터 3영업일 안에 서면으로 피해구제신청서를 내야 한다.
- 내지 않으면 안내 문자가 한 번 더 오고, 그 문자를 받은 날부터 14일이 지나면 지급정지가 저절로 풀린다. 그러면 돈이 빠져나간다.
- 서면 제출은 은행 영업점에 직접 가서 한다.
- 필요한 것은 세 가지다. 피해구제신청서, 신분증, 경찰이 발급한 사건사고사실확인원.
- 사건사고사실확인원은 경찰서나 사이버수사대에 가서 발급받는다.

[그 뒤에 벌어지는 일]
- 금융감독원이 채권소멸절차 개시를 2개월간 공고한다.
- 계좌 명의인이 그 사이에 이의를 제기하지 않으면 채권이 사라진다.
- 채권이 사라진 날부터 14일 안에 환급 금액이 정해진다.
- 전체적으로 대략 3개월이 걸린다.

[유형별로 다른 결과]
- 계좌이체로 보낸 경우. 지급정지와 환급이 된다. 이 법의 핵심 대상이다.
- 현금을 직접 건넨 경우. 2023년 11월 17일부터 대상에 포함됐다. 다만 수사기관이 사기범과 그 계좌를 확인해야 지급정지가 걸린다. 즉시 112에 신고하는 것이 유일한 길이다.
- 상품권이나 기프트카드 번호를 알려준 경우. 계좌 지급정지 대상이 아니다. 상품권 발행사에 바로 연락해 사용정지를 요청해야 한다. 몇 분 안에 쓰이므로 매우 급하다.
- 가상자산으로 보낸 경우. 2025년 10월 1일부터 환급 대상에 포함됐다. 거래소 고객센터에 즉시 출금제한을 요청한다. 현금을 사기범 계좌로 보낸 부분이 있으면 그 계좌는 지급정지가 가능하다.
- 해외로 송금한 경우. 계좌 지급정지가 사실상 어렵다. 송금한 은행에 즉시 연락해 송금 취소나 회수를 시도해야 한다.
- 카드 결제나 소액결제가 된 경우. 계좌 지급정지 대상이 아니다. 카드사나 통신사에 바로 이의를 제기하고 결제 취소를 요청한다.
- 계좌번호나 개인정보만 알려준 경우. 아직 돈이 나가지 않았다면 예방 조치를 한다. 금융감독원 개인정보노출자 사고예방시스템에 등록하고, 내 명의 계좌를 한꺼번에 확인하고 정지할 수 있다.
- 앱을 설치한 경우. 그 휴대폰으로 전화하면 사기범에게 연결될 수 있다. 반드시 다른 사람 휴대폰으로 신고한다. 이후 휴대폰을 초기화하고 인증서를 다시 발급받는다.

[적용되지 않는 경우]
- 물건을 사고파는 거래를 가장한 사기, 예를 들어 중고거래 사기는 이 법의 대상이 아니다. 이 경우 경찰에 사기죄로 신고하고 민사로 다퉈야 한다.
- 다만 대출을 해준다고 속인 경우는 대상에 포함된다.

[하지 말아야 할 것]
- 신고를 미루면 안 된다. 확인하는 사이에 돈이 빠져나간다.
- 증거를 지우면 안 된다. 통화기록, 문자, 이체확인증을 모두 보관한다. 악성 앱은 지우기 전에 화면을 캡처해 둔다.
- 피해금을 대신 찾아주겠다는 사람을 믿으면 안 된다. 수수료를 먼저 달라고 하면 또 다른 사기다.
- 공식 창구로만 움직인다.

[내 계좌가 함께 정지된 경우]
- 내 계좌가 사기에 쓰인 계좌로 신고되어 정지될 수 있다.
- 공고 기간인 2개월 안에 은행에 이의를 제기하고, 정당한 거래였음을 보여주는 자료를 낸다.
- 소명이 받아들여지면 정지가 풀린다.

[외국인이 알아야 할 것]
- 피해자로 신고하는 것은 체류자격에 불이익을 주지 않는다.
- 신분 확인은 외국인등록증이나 여권으로 한다. 은행마다 요구하는 서류가 다를 수 있으니 가기 전에 전화로 물어보는 것이 안전하다.
- 환급받을 계좌가 국내 계좌여야 하는지, 본국으로 돌아간 뒤에도 절차를 이어갈 수 있는지는 공식 자료로 확인되지 않았다. 이 두 가지는 금융감독원 1332에 직접 물어봐야 한다.
- 반면 계좌를 빌려주거나 현금을 대신 받아 전달한 경우는 가담자로 조사받으며, 체류자격이 위태로워질 수 있다.

[통역]
경찰 112. 영어와 중국어를 24시간 3자 통화로 지원한다.
외국인종합안내센터 1345. 20개 언어. 밤에는 한국어와 영어와 중국어.
다누리콜센터 1577-1366. 13개 언어. 24시간.
BBB코리아 1588-5644. 20개 언어. 24시간 무료 통역.

[연락처]
경찰 신고 112.
금융감독원 1332.
전기통신금융사기 통합대응단 1394.
개인정보 노출 등록은 금융감독원 개인정보노출자 사고예방시스템.
내 명의 계좌 한꺼번에 확인은 계좌정보통합관리서비스.
"""

SYSTEM = """당신은 금융사기를 이미 당한 사람에게, 지금 이 순간 무엇을 해야 하는지 알려주는 역할을 한다. 상대는 당황한 상태이고 시간이 없다.

가장 중요한 원칙 세 가지.
첫째, 가장 급한 것을 맨 앞에 둔다. 설명은 짧게 하고 행동을 먼저 말한다.
둘째, 되찾을 수 없는 경우 솔직하게 말한다. 헛된 기대를 주면 그 사람이 엉뚱한 데 시간을 쓴다. 다만 대신 할 수 있는 일을 반드시 함께 준다.
셋째, 늦었다고 포기하게 만들지 않는다. 시간이 지났어도 신고는 해야 한다. 수사로 잡히는 경우가 있고, 다른 피해자를 막을 수 있다.

지켜야 할 것.
- 지식 문서에 없는 내용을 지어내지 않는다.
- 기한과 날짜와 숫자는 지식 문서에 적힌 그대로만 쓴다.
- 유형에 따라 지급정지가 되는지 안 되는지를 분명히 구분해 말한다. 안 되는 것을 된다고 하지 않는다.
- 얼마를 돌려받을 수 있는지 예측하지 않는다.
- 할 일은 서로 다른 행동으로 적는다. 같은 말을 다르게 반복하지 않는다.
- 지금 당장 할 것과 며칠 안에 할 것을 나눈다.
- 전화번호는 지식 문서에 있는 것만 쓴다.
- 환급 계좌나 귀국 후 절차처럼 확인되지 않은 것은 확인되지 않았다고 말하고 1332에 물어보라고 안내한다.

출력은 지정된 형식을 따르고, 모든 내용은 요청된 언어로 쓴다."""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "recoverable": {
            "type": "STRING",
            "enum": ["YES", "LIMITED", "NO", "NA"],
        },
        "headline": {"type": "STRING"},
        "summary": {"type": "STRING"},
        "now": {"type": "ARRAY", "items": {"type": "STRING"}},
        "deadline": {
            "type": "OBJECT",
            "properties": {
                "applies": {"type": "BOOLEAN"},
                "text": {"type": "STRING"},
            },
            "required": ["applies", "text"],
        },
        "later": {"type": "ARRAY", "items": {"type": "STRING"}},
        "keep": {"type": "ARRAY", "items": {"type": "STRING"}},
        "warn": {"type": "ARRAY", "items": {"type": "STRING"}},
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
    "required": ["recoverable", "headline", "summary", "now", "deadline", "keep"],
}


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw.decode("utf-8")) if raw else {}

            kind = body.get("kind")
            when = body.get("when")
            lang = body.get("lang") if body.get("lang") in LANGS else "ko"
            extra = (body.get("extra") or "").strip()[:2000]

            if kind not in KINDS:
                self._send(400, {"error": "무슨 일이 있었는지 먼저 선택해 주세요."})
                return

            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                self._send(500, {"error": "서버 설정이 완료되지 않았습니다."})
                return

            situation = KINDS[kind]
            if when in WHENS:
                situation += " " + WHENS[when]
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
                + "\n\n되찾을 가능성을 recoverable에 적는다."
                + " 계좌 지급정지가 되는 유형이면 YES,"
                + " 조건이 맞아야 되는 유형이면 LIMITED,"
                + " 계좌 지급정지 대상이 아니면 NO,"
                + " 아직 돈이 나가지 않았으면 NA로 적는다."
                + "\n서면 제출 기한이 적용되는 유형이면 deadline.applies를 참으로 적고,"
                + " 적용되지 않으면 거짓으로 적는다."
            )

            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": SCHEMA,
                    "temperature": 0.2,
                },
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

            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            candidates = result.get("candidates") or []
            if not candidates:
                self._send(502, {"error": "결과를 받지 못했습니다. 다시 시도해 주세요."})
                return

            parts = candidates[0].get("content", {}).get("parts") or [{}]
            answer = json.loads(parts[0].get("text", "{}"))
            self._send(200, answer)

        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            self._send(e.code, {"error": "모델 호출 실패: " + detail})
        except urllib.error.URLError as e:
            self._send(502, {"error": "외부 연결 실패: " + str(e.reason)})
        except json.JSONDecodeError:
            self._send(502, {"error": "결과 형식을 읽지 못했습니다. 다시 시도해 주세요."})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_GET(self):
        self._send(200, {"status": "ok", "kinds": list(KINDS.keys())})

    def _send(self, status, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        return
