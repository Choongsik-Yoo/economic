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
    urls = [
        "https://news.google.com/rss/search?q=경제+OR+정책+OR+금리&hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/search?q=AI+PC+OR+온디바이스+OR+NPU+OR+위더스컴퓨터&hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/search?q=중소기업+OR+소상공인+OR+조달청+지원사업&hl=ko&gl=KR&ceid=KR:ko"
    ]
    news_items = []
    for url in urls:
        feed = feedparser.parse(url)
        for entry in feed.entries[:15]: 
            news_items.append(f"제목: {entry.title}\n링크: {entry.link}\n")
    return "\n".join(news_items)

# ---------------------------------------------------------
# 3. AI 분석 및 요약 생성
# ---------------------------------------------------------
def generate_briefing(market_data, news_text):
    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    
    system_prompt = f"""
    당신은 WITHCOM AI의 경영진을 보좌하는 최고 전략 AI 비서입니다.
    오늘 날짜는 {today_str}입니다.
    제공된 시장 지표와 뉴스 헤드라인을 분석하여, 다음 두 가지를 JSON 형식으로 반환하세요.
    
    1. "email_html": 전무님께 보낼 이메일 본문 (HTML 형식). 
       - 오늘의 핵심 요약 5줄
       - 시장지표 요약
       - 국내 경제/정책 뉴스 (5개 선정, <a href="기사링크">기사 제목</a> 형식)
       - 글로벌 경제 뉴스 (5개 선정, <a href="기사링크">기사 제목</a> 형식)
       - AI/PC 산업 주요 뉴스 (5개 선정, <a href="기사링크">기사 제목</a> 형식)
       - 오늘의 액션 아이템 (3~5개)

    2. "notion_items": 노션 데이터베이스에 저장할 주요 기사 목록 (List of Objects). 
       가장 중요하고 회사에 시사점이 있는 기사 5~7개를 엄선하세요.
       각 객체는 다음 키를 가져야 합니다:
       - "title": 기사 제목
       - "date": YYYY-MM-DD
       - "category": 경제, 금융, 산업, AI, 반도체, PC, 정책, 중소기업, 소상공인, 조달, 리스크 중 택 1
       - "summary": 3~5줄 요약
       - "source": 언론사명
       - "url": 기사 링크
       - "importance": 높음, 중간, 낮음 중 택 1
       - "related_tasks": ["경영", "영업", "구매", "재무", "조달", "교육", "콘텐츠", "대리점"] 중 선택 (배열)
       - "withus_impact": 위더스컴퓨터 매출/구매/영업 관점의 시사점 (텍스트)
       - "action": 뉴스를 바탕으로 오늘 확인하거나 실행할 일 (상세 텍스트)
       - "share_target": 임원, 팀장, 영업팀, 구매팀, 대리점, 블로그 중 택 1
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
    return json.loads(response.choices[0].message.content)

# ---------------------------------------------------------
# 4. 이메일 발송 & 5. 노션 DB 저장 
# ---------------------------------------------------------
def send_email(html_content):
    today_str = datetime.now().strftime("%Y-%m-%d")
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[경영진 브리핑] {today_str} WITHCOM AI 아침 경제/산업 동향"
    msg['From'] = GMAIL_ID
    msg['To'] = TARGET_EMAIL

    part = MIMEText(html_content, "html")
    msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ID, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ID, TARGET_EMAIL, msg.as_string())
    print("이메일 발송 완료!")

def save_to_notion(notion_items):
    for item in notion_items:
        try:
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "기사제목": {"title": [{"text": {"content": item.get("title", "")}}]},
                    "발행일": {"date": {"start": item.get("date", datetime.now().strftime("%Y-%m-%d"))}},
                    "구분": {"select": {"name": item.get("category", "경제")}},
                    "본문요약": {"rich_text": [{"text": {"content": item.get("summary", "")}}]},
                    "언론사": {"select": {"name": item.get("source", "미상")[:50]}},
                    "기사링크": {"url": item.get("url", "") if str(item.get("url")).startswith("http") else None},
                    "중요도": {"select": {"name": item.get("importance", "중간")}},
                    "관련업무": {"multi_select": [{"name": task} for task in item.get("related_tasks", [])]},
                    "위더스컴퓨터영향": {"rich_text": [{"text": {"content": item.get("withus_impact", "")}}]},
                    
                    # 액션 항목을 '텍스트(Rich Text)' 형식에 맞게 수정했습니다.
                    "액션": {"rich_text": [{"text": {"content": item.get("action", "")}}]},
                    
                    "공유대상": {"select": {"name": item.get("share_target", "임원")[:50]}},
                    "처리상태": {"select": {"name": item.get("status", "확인 전")[:50]}}
                }
            )
        except Exception as e:
            print(f"노션 저장 중 오류 발생 ({item.get('title')}): {e}")
    print(f"노션 DB에 {len(notion_items)}개의 데이터 저장 시도 완료!")

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
