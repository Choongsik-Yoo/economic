import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import feedparser
import yfinance as yf
from openai import OpenAI
from notion_client import Client

# ---------------------------------------------------------
# 1. 환경 변수 및 설정
# ---------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
GMAIL_ID = os.environ.get("GMAIL_ID")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
TARGET_EMAIL = "csyoo22@gmail.com"

client = OpenAI(api_key=OPENAI_API_KEY)
notion = Client(auth=NOTION_TOKEN)

# ---------------------------------------------------------
# 2. 데이터 수집 함수
# ---------------------------------------------------------
def fetch_market_data():
    """주요 시장 지표(환율, 증시) 수집"""
    tickers = {
        "USD/KRW": "KRW=X",
        "KOSPI": "^KS11",
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Crude Oil": "CL=F"
    }
    market_info = {}
    for name, ticker in tickers.items():
        try:
            data = yf.Ticker(ticker).history(period="1d")
            close_price = data['Close'].iloc[0]
            market_info[name] = round(close_price, 2)
        except Exception:
            market_info[name] = "데이터 수집 실패"
    return market_info

def fetch_news_rss():
    """구글 뉴스 RSS를 통해 주요 경제, AI, 정책 뉴스 수집"""
    urls = [
        "https://news.google.com/rss/search?q=경제+OR+정책+OR+금리&hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/search?q=AI+PC+OR+온디바이스+OR+NPU+OR+위더스컴퓨터&hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/search?q=중소기업+OR+소상공인+OR+조달청+지원사업&hl=ko&gl=KR&ceid=KR:ko"
    ]
    
    news_items = []
    for url in urls:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]: # 각 카테고리별 상위 10개 추출
            news_items.append(f"제목: {entry.title}\n링크: {entry.link}\n")
    return "\n".join(news_items)

# ---------------------------------------------------------
# 3. AI 분석 및 요약 생성
# ---------------------------------------------------------
def generate_briefing(market_data, news_text):
    """OpenAI API를 활용하여 경영진 맞춤형 브리핑 및 노션 데이터 생성"""
    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    
    system_prompt = f"""
    당신은 위더스컴퓨터(주)의 경영진(전무이사)을 보좌하는 최고 전략 AI 비서입니다.
    오늘 날짜는 {today_str}입니다.
    제공된 시장 지표와 뉴스 헤드라인을 분석하여, 다음 두 가지를 JSON 형식으로 반환하세요.
    
    1. "email_html": 전무님께 보낼 이메일 본문 (HTML 형식). 
       - 오늘의 핵심 요약 5줄
       - 시장지표 요약 (위더스컴퓨터의 구매/재무 영향 포함)
       - 국내 경제/정책 뉴스
       - 글로벌 경제 뉴스
       - AI/PC 산업 및 위더스컴퓨터 신사업 관련 뉴스
       - 중소기업/조달청 정책 공고 요약
       - 오늘의 액션 아이템 (3~5개)
       디자인이 깔끔한 표와 글머리 기호를 활용하세요.

    2. "notion_items": 노션 데이터베이스에 저장할 주요 기사 목록 (List of Objects). 
       반드시 가장 중요하고 위더스컴퓨터에 시사점이 있는 기사 5~7개를 엄선하세요.
       각 객체는 다음 키를 가져야 합니다:
       - "title": 기사 제목
       - "date": YYYY-MM-DD 형식
       - "category": 경제, 금융, 산업, AI, 반도체, PC, 정책, 중소기업, 소상공인, 조달, 리스크 중 택 1
       - "summary": 3~5줄 요약
       - "source": 언론사/기관명
       - "url": 기사 링크
       - "importance": 높음, 중간, 낮음 중 택 1
       - "related_tasks": ["경영", "영업", "구매", "재무", "조달", "교육", "콘텐츠", "대리점"] 중 선택 (배열)
       - "withus_impact": 회사 관점 시사점
       - "action_item": 액션 아이템
       - "share_targets": ["임원", "팀장", "영업팀", "구매팀", "대리점", "블로그"] 중 선택 (배열)
       - "status": "확인 전" (고정)
    """

    user_prompt = f"### 시장 지표\n{market_data}\n\n### 오늘의 뉴스\n{news_text}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={ "type": "json_object" }
    )
    
    result = json.loads(response.choices[0].message.content)
    return result

# ---------------------------------------------------------
# 4. 이메일 발송 함수
# ---------------------------------------------------------
def send_email(html_content):
    """생성된 HTML 브리핑을 이메일로 발송"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[경영진 브리핑] {today_str} 위더스컴퓨터 아침 경제/산업 동향"
    msg['From'] = GMAIL_ID
    msg['To'] = TARGET_EMAIL

    part = MIMEText(html_content, "html")
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ID, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ID, TARGET_EMAIL, msg.as_string())
    print("이메일 발송 완료!")

# ---------------------------------------------------------
# 5. 노션 DB 저장 함수
# ---------------------------------------------------------
def save_to_notion(notion_items):
    """추출된 데이터를 노션 데이터베이스에 개별 페이지로 생성"""
    for item in notion_items:
        try:
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "제목": {"title": [{"text": {"content": item.get("title", "")}}]},
                    "날짜": {"date": {"start": item.get("date", datetime.now().strftime("%Y-%m-%d"))}},
                    "구분": {"select": {"name": item.get("category", "경제")}},
                    "핵심 요약": {"rich_text": [{"text": {"content": item.get("summary", "")}}]},
                    "출처": {"rich_text": [{"text": {"content": item.get("source", "미상")}}]},
                    "기사링크": {"url": item.get("url", "")},
                    "중요도": {"select": {"name": item.get("importance", "중간")}},
                    "관련 업무": {"multi_select": [{"name": task} for task in item.get("related_tasks", [])]},
                    "위더스컴퓨터 영향": {"rich_text": [{"text": {"content": item.get("withus_impact", "")}}]},
                    "액션 아이템": {"rich_text": [{"text": {"content": item.get("action_item", "")}}]},
                    "공유 대상": {"multi_select": [{"name": target} for target in item.get("share_targets", [])]},
                    "처리 상태": {"status": {"name": item.get("status", "확인 전")}}
                }
            )
        except Exception as e:
            print(f"노션 저장 중 오류 발생 ({item.get('title')}): {e}")
    print(f"노션 DB에 {len(notion_items)}개의 데이터 저장 완료!")

# ---------------------------------------------------------
# 6. 메인 실행 블록
# ---------------------------------------------------------
if __name__ == "__main__":
    print("아침 브리핑 생성을 시작합니다...")
    market_data = fetch_market_data()
    news_text = fetch_news_rss()
    
    ai_result = generate_briefing(market_data, news_text)
    
    email_html = ai_result.get("email_html", "<p>브리핑 생성 실패</p>")
    notion_items = ai_result.get("notion_items", [])
    
    send_email(email_html)
    save_to_notion(notion_items)
    print("모든 자동화 작업이 성공적으로 완료되었습니다.")