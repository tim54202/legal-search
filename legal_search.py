import argparse, hashlib, os, pathlib, re, sqlite3, textwrap, time, requests, bs4
from keybert import KeyBERT
from openai import OpenAI
import jieba
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# parameter
RAW = pathlib.Path("raw"); RAW.mkdir(exist_ok=True)
DB  = pathlib.Path("cache.db")

# 1. Extract Keyword
class KeywordExtractor:
    def __init__(self):
        self.model = KeyBERT("paraphrase-multilingual-MiniLM-L12-v2")

    def extract(self, txt, top=10):
        # 使用 jieba 分詞
        words = jieba.cut(txt, cut_all=False)
        segmented_txt = " ".join(words)
        logger.debug(f"分詞後文字: {segmented_txt}")

        # 提取關鍵字
        keywords = self.model.extract_keywords(
            segmented_txt,
            top_n=top,
            keyphrase_ngram_range=(1, 1),
            stop_words=None  # 移除停用詞
        )
        result = [k for k, _ in keywords]

        # 如果未提取到關鍵字，備用方案：使用分詞結果
        if not result:
            logger.warning("KeyBERT 未提取到關鍵字，使用分詞結果")
            result = [word for word in words if len(word) >= 2][:top]

        return result

# Auto crawler
class FetchLinks:
    def fetch_judgment_links_by_keywords(self, keywords, max_results=5, driver_path="/usr/local/bin/chromedriver"):
        try:
            # 檢查 chromedriver 路徑
            logger.info(f"Use chromedriver: {driver_path}")
            service = Service(driver_path)
            options = webdriver.ChromeOptions()
            # options.add_argument('--headless')  # 取消註解以啟用無頭模式
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("Chrome 瀏覽器已啟動")

            # 步驟 1: 訪問網站
            logger.info("訪問司法院網站")
            driver.get("https://judgment.judicial.gov.tw/FJUD/default.aspx")
            time.sleep(3)  # 增加等待時間

            # 處理可能的彈窗或多窗口
            if len(driver.window_handles) > 1:
                logger.info("檢測到多個窗口，切換到最新窗口")
                driver.switch_to.window(driver.window_handles[-1])

            # 步驟 2: 輸入關鍵字並提交查詢
            logger.info(f"輸入關鍵字: {' '.join(keywords)}")
            wait = WebDriverWait(driver, 20)  # 超時時間 20 秒
            search_box = wait.until(EC.presence_of_element_located((By.ID, "txtKW")))
            search_box.clear()
            search_box.send_keys(" ".join(keywords))
            search_box.send_keys(Keys.ENTER)
            logger.info("已提交查詢")

            # 步驟 3: 等待 iframe 載入並切換
            logger.info("等待 iframe 載入")
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "iframe-data")))
            time.sleep(5)  # 確保動態內容載入
            logger.info("已切換到 iframe")

            # 輸出 iframe 內的 HTML 用於調試
            # logger.debug(f"iframe HTML: {driver.page_source[:2000]}")
            # with open("iframe_source.html", "w", encoding="utf-8") as f:
            #     f.write(driver.page_source)
            # logger.info("已將 iframe HTML 寫入 iframe_source.html")

            # 步驟 4: 抓取案例連結
            logger.info("開始抓取案例連結")
            results = []
            # 使用精確的選擇器，抓取案例標題的 <a> 標籤
            links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table a.hlTitle_scroll")))
            summaries = driver.find_elements(By.CSS_SELECTOR, "span.tdCut")

            for i, a in enumerate(links[:max_results]):
                title = a.text.strip()
                link = a.get_attribute("href")
                summary = summaries[i].text.strip() if i < len(summaries) else ""
                if link and link.startswith("/"):
                    link = "https://judgment.judicial.gov.tw" + link
                if title and link and "data.aspx?ty=JD" in link:
                    case_id = link.split("id=")[1].split("&")[0] if "id=" in link else ""
                    results.append({
                        "id": case_id,
                        "title": title,
                        "link": link,
                        "fact": summary
                    })
                    logger.info(f"找到案例: {title} - {link}")

            if not results:
                logger.warning("未找到任何符合條件的案例連結")

            logger.info(f"共抓取 {len(results)} 個案例連結")
            return results

        except Exception as e:
            logger.error(f"發生錯誤: {str(e)}")
            try:
                with open("error_page_source.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logger.debug("已將錯誤時的頁面 HTML 寫入 error_page_source.html")
            except:
                logger.debug("無法獲取頁面 HTML")
            return []

        finally:
            try:
                driver.quit()
                logger.info("Chrome 瀏覽器已關閉")
            except:
                logger.error("關閉瀏覽器時發生錯誤")

# 3. Similarity check
class Similarity:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()

    def compute(self, keywords, cases):
        """計算案例摘要與關鍵字的相似度"""
        if not cases:
            return []

        keyword_text = " ".join(keywords)
        case_texts = [case["fact"] for case in cases]

        texts = [keyword_text] + case_texts
        tfidf_matrix = self.vectorizer.fit_transform(texts)
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

        for case, sim in zip(cases, similarities):
            case["similarity"] = sim

        ranked_cases = sorted(cases, key=lambda x: x["similarity"], reverse=True)
        return ranked_cases


# ---------- GPT ----------
class Summarizer:
    SYS = "你是法律助理，請先列出各個判決的特點，然後比較下列判決與提問事件的異同，先 2 行針對案件的共同點，再條列 3-5 點差異，最後 3 行總結預計的判罰會怎樣。"
    def __init__(self): self.cli = OpenAI()
    def summarize(self, query, cases):
        docs = "\n\n".join(
            f"[{i+1}] {( '案號：'+c['id']) if c.get('id') else '新聞／其他'}\n"
            f"{c['fact'][:200]}…" for i,c in enumerate(cases))
        rsp = self.cli.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[{"role":"system","content":self.SYS},
                      {"role":"user","content":f"事件：{query}\n\n資料：\n{docs}"}])
        return rsp.choices[0].message.content.strip()

# ---------- Pipeline ----------
class Pipeline:
    def __init__(self, k=5):
        self.keyword_extractor = KeywordExtractor()
        self.fetch_links = FetchLinks()
        self.similarity = Similarity()
        self.summarize = Summarizer()
        self.k = k  # 關鍵字數量

    def run(self, query):
        logger.info(f"提取關鍵字: {query}")
        keywords = self.keyword_extractor.extract(query, top=self.k)
        logger.info(f"提取的關鍵字: {keywords}")

        # 只用第一個關鍵字搜尋
        if not keywords:
            logger.warning("未提取到關鍵字")
            return "未提取到關鍵字，請嘗試其他輸入。"

        cases = self.fetch_links.fetch_judgment_links_by_keywords([keywords[0]], max_results=20)

        if not cases:
            logger.warning("未找到任何案例")
            return "未找到相關案例，請嘗試其他關鍵字。"

        ranked_cases = self.similarity.compute(keywords, cases)
        top_cases = ranked_cases[:5]

        summary = self.summarize.summarize(query, top_cases)
        return summary

class WebContentExtractor:
    @staticmethod
    def extract_text_from_url(url, timeout=10):
        try:
            logger.info(f"開始爬取網址: {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding

            soup = bs4.BeautifulSoup(response.text, 'html.parser')
            title = soup.find('title') or soup.find('h1')
            title_text = title.get_text(strip=True) if title else ''

            content = ''
            for tag in soup.find_all(['article', 'div', 'p']):
                if tag.get('class') and 'content' in ''.join(tag.get('class')).lower():
                    content = tag.get_text(strip=True)
                    break
            if not content:
                paragraphs = soup.find_all('p')
                content = ' '.join(p.get_text(strip=True) for p in paragraphs)

            text = f"{title_text} {content}".strip()
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'[^\w\s]', '', text)

            logger.debug(f"提取的網頁文本（前200字）：{text[:200]}...")
            if not text or len(text) < 50:
                logger.warning("網頁內容過少，可能為動態加載或無有效文本")
                return ''

            return text

        except requests.exceptions.RequestException as e:
            logger.error(f"爬取網址失敗: {url}, 錯誤: {str(e)}")
            return ''
        except Exception as e:
            logger.error(f"解析網頁內容失敗: {url}, 錯誤: {str(e)}")
            return ''

