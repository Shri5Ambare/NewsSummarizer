import streamlit as st
from bs4 import BeautifulSoup as soup
from urllib.request import urlopen
from newspaper import Article
import pandas as pd
import nltk

# Download NLTK resources only once
nltk.download('punkt', quiet=True)

# ---------------------- Fetch News ----------------------
@st.cache_data(show_spinner=False)
def fetch_news_search_topic(query):
    site = f'https://news.google.com/rss/search?q={query}'
    with urlopen(site) as op:
        rd = op.read()
    sp_page = soup(rd, 'xml')
    return sp_page.find_all('item')

# ---------------------- Display News ----------------------
def display_news(news_list):
    st.title("Google News Scraper")
    data = []
    for news in news_list:
        st.subheader(news.title.text)
        st.write(f"**Published Date:** {news.pubDate.text}")

        article = Article(news.link.text)
        try:
            article.download()
            article.parse()
            article.nlp()
            summary = article.summary

            st.write(summary)
            if article.top_image:
                st.image(article.top_image, caption='Article Image', use_container_width=True)
            else:
                st.info("No image available")
            st.markdown(f"[Read more]({news.link.text})")
            st.write("---")

            # Store data for CSV export
            data.append({
                "Title": news.title.text,
                "Link": news.link.text,
                "Summary": summary,
                "Published Date": news.pubDate.text
            })
        except Exception as e:
            st.warning(f"Failed to extract article details: {e}")

    return pd.DataFrame(data)

# ---------------------- Main App ----------------------
def run():
    st.sidebar.title("Google News Scraper")
    query = st.sidebar.text_input("Enter a topic to search:")
    if st.sidebar.button("Search"):
        if query.strip():
            with st.spinner("Fetching news..."):
                news_list = fetch_news_search_topic(query.strip())
            if news_list:
                df = display_news(news_list)
                # Download CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download News CSV", csv, "news.csv", "text/csv")
            else:
                st.warning("No news found for the given topic.")
        else:
            st.warning("Please enter a search query.")

if __name__ == "__main__":
    run()
