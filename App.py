# samachar_plus.py
import streamlit as st
import pandas as pd
from PIL import Image
from bs4 import BeautifulSoup as soup
from urllib.request import urlopen, Request
from urllib.parse import quote_plus
from urllib.error import URLError, HTTPError
from newspaper import Article
from textblob import TextBlob
import io, time, re
from functools import wraps
import json

# ---------- CONFIG ----------
st.set_page_config(
    page_title="SAMACHAR+ 📰",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- CACHING ----------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_rss(url: str):
    """Fetch RSS with retry & 10 s timeout."""
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=10) as resp:
                return soup(resp.read(), features='xml')
        except (URLError, HTTPError):
            time.sleep(1.5)
    return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_top_news():
    xml = fetch_rss("https://news.google.com/news/rss")
    return xml.find_all('item') if xml else []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_category_news(cat: str):
    xml = fetch_rss(f"https://news.google.com/news/rss/headlines/section/topic/{cat.upper()}")
    return xml.find_all('item') if xml else []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_news_search_topic(topic: str):
    xml = fetch_rss(f"https://news.google.com/rss/search?q={quote_plus(topic)}")
    return xml.find_all('item') if xml else []

# ---------- UTILITIES ----------
def fetch_news_poster(poster_link, width=300):
    if poster_link and poster_link.startswith('http'):
        try:
            img = Image.open(io.BytesIO(urlopen(poster_link, timeout=5).read()))
            st.image(img, width=width)
            return
        except Exception:
            pass
    # Fallback
    st.image("https://via.placeholder.com/300x200?text=No+Image", width=width)

def highlight(text, kw):
    if not kw:
        return text
    kw = re.escape(kw.strip())
    return re.sub(f'({kw})', r'**\1**', text, flags=re.IGNORECASE)

def get_sentiment(text):
    pol = TextBlob(text).sentiment.polarity
    if pol > 0.15:
        return ("🙂 Positive", "green")
    elif pol < -0.15:
        return ("☹️ Negative", "red")
    else:
        return ("😐 Neutral", "gray")

def display_news(items, qty, kw=''):
    rows = []
    for idx, item in enumerate(items[:qty], 1):
        title = item.title.text
        link = item.link.text
        pub = item.pubDate.text if item.pubDate else "N/A"
        st.markdown(f"### {idx}. {highlight(title, kw)}")
        art = Article(link, language='en')
        try:
            art.download(); art.parse(); art.nlp()
            summary = art.summary or art.text[:300] + "..."
        except:
            summary = "Summary not available."
        sentiment, color = get_sentiment(summary)
        fetch_news_poster(art.top_image)
        with st.expander("📋 Summary & sentiment"):
            st.write(highlight(summary, kw))
            st.markdown(f":{color}[**Sentiment:** {sentiment}]")
            st.markdown(f"[📖 Read full article]({link})")
        st.caption(f"Published: {pub}")
        st.markdown("---")
        rows.append({"Title": title, "Summary": summary,
                     "Link": link, "Sentiment": sentiment, "Published": pub})
    return pd.DataFrame(rows)

# ---------- STREAMLIT UI ----------
def main():
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Controls")
        dark = st.checkbox("Dark mode")
        if dark:
            st.markdown("""
            <style>
            .main {background-color: #111 !important; color: #eee !important;}
            </style>
            """, unsafe_allow_html=True)
        if st.button("🔄 Refresh News"):
            st.cache_data.clear(); st.rerun()

    # Header / logo
    c1, c2, c3 = st.columns([1, 3, 1])
    with c2:
        st.image("https://via.placeholder.com/220x220?text=SAMACHAR+", width=220)
    st.title("📰 SAMACHAR+ – Advanced News Portal")

    tabs = st.tabs(["🔥 Trending", "💙 Topics", "🔍 Search", "📊 Export"])

    # ---------- Trending ----------
    with tabs[0]:
        n = st.slider("Articles", 5, 25, 10, key="trend")
        items = fetch_top_news()
        if items:
            df = display_news(items, n)
            if not df.empty:
                st.download_button("⬇️ CSV", df.to_csv(index=False), "trending.csv")
                buf = io.BytesIO()
                df.to_excel(buf, index=False, engine='openpyxl')
                buf.seek(0)
                st.download_button("⬇️ Excel", buf, "trending.xlsx")

    # ---------- Topics ----------
    with tabs[1]:
        cats = ['WORLD', 'NATION', 'BUSINESS', 'TECHNOLOGY', 'ENTERTAINMENT',
                'SPORTS', 'SCIENCE', 'HEALTH']
        cat = st.selectbox("Pick category", cats)
        n = st.slider("Articles", 5, 25, 10, key="cat")
        items = fetch_category_news(cat)
        if items:
            df = display_news(items, n)
            if not df.empty:
                st.download_button(f"⬇️ {cat}.csv", df.to_csv(index=False), f"{cat}.csv")
                buf = io.BytesIO()
                df.to_excel(buf, index=False, engine='openpyxl')
                buf.seek(0)
                st.download_button(f"⬇️ {cat}.xlsx", buf, f"{cat}.xlsx")

    # ---------- Search ----------
    with tabs[2]:
        kw = st.text_input("Enter keyword(s) (comma separated)")
        n = st.slider("Per keyword", 3, 15, 5, key="search")
        if st.button("🔍 Search"):
            for k in map(str.strip, kw.split(",")):
                if not k:
                    continue
                st.subheader(f"Results for **{k}**")
                items = fetch_news_search_topic(k)
                if items:
                    df = display_news(items, n, kw=k)
                    buf = io.BytesIO()
                    df.to_excel(buf, index=False, engine='openpyxl')
                    buf.seek(0)
                    st.download_button(f"⬇️ {k}.xlsx", buf, f"{k}.xlsx")
                    st.download_button(f"⬇️ {k}.json", json.dumps(df.to_dict("records"), indent=2),
                                       f"{k}.json", "application/json")
                else:
                    st.warning("No results for " + k)

    # ---------- Export ----------
    with tabs[3]:
        st.info("Use the ⬇️ download buttons in each tab.")

if __name__ == "__main__":
    main()