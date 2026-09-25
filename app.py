import streamlit as st
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pandas as pd

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="MY STOCK MATE (MSM)",
    page_icon="📈",
    layout="centered"
)

# 2. 실시간 데이터 처리 함수들
def fetch_news_score(stock_name):
    """네이버 뉴스에서 기사 헤드라인을 가져와 분석"""
    url = f"https://search.naver.com/search.naver?where=news&query={stock_name}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        titles = [a['title'] for a in soup.select('a.news_tit')]
        
        pos_keywords = ['상승', '호재', '실적', '흑자', '수주', '돌파', '신고가', '매수']
        neg_keywords = ['하락', '악재', '적자', '급락', '위기', '손실', '우려', '매도']
        reverse_words = ['멈춰', '극복', '탈출', '반등', '해소']
        
        score = 0
        for title in titles:
            has_reverse = any(rw in title for rw in reverse_words)
            for pk in pos_keywords:
                if pk in title: score += 1.5
            for nk in neg_keywords:
                if nk in title and not has_reverse: score -= 1.5
                
        return titles[:5], score
    except Exception:
        return ["뉴스 데이터를 가져오는 중 오류가 발생했습니다."], 0

def fetch_chart_data(ticker_symbol):
    """yfinance를 통해 실시간 차트 지표 계산 (안정성 강화 버전)"""
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        df = ticker_obj.history(period="6mo")
        
        if df.empty:
            return None
        
        # 20일 이동평균선
        df['MA20'] = df['Close'].rolling(window=20).mean()
        
        # RSI (14일)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        latest = df.iloc[-1]
        return {
            "price": float(latest['Close']),
            "ma20": float(latest['MA20']),
            "rsi": float(latest['RSI']),
            "df": df
        }
    except Exception as e:
        return None

# 3. 화면 상단 타이틀
st.title("📈 MY STOCK MATE (MSM)")
st.caption("내 손안의 스마트 AI 주식 분석 비서")
st.divider()

# 4. 입력 섹션
col1, col2 = st.columns(2)
with col1:
    stock_name = st.text_input("🏢 기업 이름", value="삼성전자")
with col2:
    ticker = st.text_input("🔢 종목 티커", value="005930.KS")

st.markdown("---")

# 5. 분석 시작 버튼 동작
if st.button("📊 MSM 정밀 분석 시작하기", use_container_width=True):
    with st.spinner("최신 뉴스 및 차트 데이터를 수집 중입니다..."):
        chart_data = fetch_chart_data(ticker.strip().upper())
        news_titles, news_score = fetch_news_score(stock_name)
    
    if chart_data is None:
        st.error("❌ 주가 데이터를 불러올 수 없습니다. 종목 티커를 확인해 주세요. (예: 삼성전자 -> 005930.KS, 애플 -> AAPL)")
    else:
        st.subheader(f"📊 [{stock_name}] MSM 정밀 분석 결과")
        
        price = chart_data['price']
        ma20 = chart_data['ma20']
        rsi = chart_data['rsi']
        
        # 뉴스 점수 텍스트 변환
        if news_score > 0:
            news_text = f"긍정 우세 (+{news_score:.1f})"
            news_delta = "호재 기사 우세"
        elif news_score < 0:
            news_text = f"부정 우세 ({news_score:.1f})"
            news_delta = "악재 기사 주의"
        else:
            news_text = "중립 (0.0)"
            news_delta = "특이 기사 없음"
            
        # 메트릭 카드 배치
        m1, m2, m3 = st.columns(3)
        
        # 한국 주가와 해외 주가 단주 단위 표기 구분
        is_kor = ticker.endswith(".KS") or ticker.endswith(".KQ")
        price_str = f"{price:,.0f}원" if is_kor else f"${price:,.2f}"
        
        m1.metric("현재가", price_str, f"20일선: {ma20:,.0f}" if is_kor else f"20일선: ${ma20:,.2f}")
        m2.metric("뉴스 분위기", news_text, news_delta)
        m3.metric("RSI (과열도)", f"{rsi:.1f}", "70이상 과열 / 30이하 과매도")
        
        st.markdown("---")
        
        # 시그널 판정
        if news_score > 0 and price > ma20 and rsi < 70:
            st.success("🔥 **[종합 시그널: 강력 관심]** 뉴스 호재와 함께 주가가 20일선 위에 안착했으며, 과열되지 않은 적정 매수 구간입니다.")
        elif rsi >= 70:
            st.warning("⚠️ **[종합 시그널: 과열 주의]** 단기 급등 상태입니다. RSI 지표가 과열 상태이므로 추격 매수에 주의하세요.")
        elif price < ma20:
            st.info("📉 **[종합 시그널: 관망 구간]** 주가가 20일 이동평균선 밑에 위치해 있어 하방 지지선을 확인할 필요가 있습니다.")
        else:
            st.warning("➡️ **[종합 시그널: 중립]** 명확한 방향성이 나타날 때까지 관찰이 필요한 구간입니다.")
            
        # 차트 그래프 간단 표시
        with st.expander("📈 주가 및 20일선 추이 차트 보기"):
            st.line_chart(chart_data['df'][['Close', 'MA20']])
            
        # 뉴스 및 손절 라인 안내
        with st.expander("📰 분석에 반영된 최근 뉴스 보기", expanded=True):
            for i, t in enumerate(news_titles, 1):
                st.write(f"{i}. {t}")
                
        stop_loss = ma20 * 0.97
        stop_loss_str = f"{stop_loss:,.0f}원" if is_kor else f"${stop_loss:,.2f}"
        st.caption(f"🛡️ **[위험 관리 기준]:** 20일선 -3% 이탈 지점인 **{stop_loss_str}** 부근을 참고 손절선으로 제시합니다.")
