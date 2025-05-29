import os, time, random, hashlib, pathlib, sqlite3, textwrap
import requests, bs4
from keybert import KeyBERT
from googlesearch import search         # google_search_python 套件
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import re

# ---------- 參數 ----------
RAW_DIR = pathlib.Path("raw") ; RAW_DIR.mkdir(exist_ok=True)
DB_PATH = pathlib.Path("cache.db")

# 1. extract keywords
class KeywordExtractor:
    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        self.kw_model = KeyBERT(model_name)

    def extract(self, text: str, top_k: int = 6) -> list[str]:
        # 取前6個相關詞，關鍵詞長度可以是 1 到 3 個詞的組合，忽略常見中文停用詞
        kws = self.kw_model.extract_keywords(text, top_n=top_k, keyphrase_ngram_range=(1, 3), stop_words="zh_cn")

        return [k for k, _ in kws]

# 2. google search
class GoogleSearch:
    PATTERN = re.compile(r"^https?://judgment\.judicial\.gov\.tw/.*FJUD.*", re.I)
    BAD = re.compile(r"/(default|readme)\.aspx", re.I)

    def search_judgments(self, keywords, num=20):
        query = "site:judgment.judicial.gov.tw/FJUD " + " ".join(keywords)
        raw = list(search(query, num_results=num))
        return [u for u in raw
                if self.PATTERN.match(u) and not self.BAD.search(u)]

# 3. HTML cache and download
class HtmlCache:
    def __init__(self, db = DB_PATH):
        self.conn = sqlite3.connect(db)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS html (url TEXT PRIMARY KEY, path TEXT)""")

    def url2path(self, url: str) -> pathlib.Path | None:
        row = self.conn.execute("SELECT path FROM html WHERE url = ?", (url,)).fetchone()
        return pathlib.Path(row[0]) if row else None

    def save(self, url: str, html: str) -> pathlib.Path | None:
        h = hashlib.md5(url.encode("utf-8")).hexdigest()
        p = RAW_DIR / f"{h}.html"
        p.write_text(html)
        self.conn.execute("INSERT OR REPLACE INTO html(url,path) VALUES(?,?)", (url, str(p)))
        self.conn.commit()
        return p

class HtmlDownloader:
    UA = {"User-Agent": "Mozilla/5.0", "Cookie": "legal-bot=1"}

    def __init__(self):
        self.cache = HtmlCache()

    def fetch(self, url: str, retry: int = 3):
        if (p := self.cache.url2path(url)) and p.exists():
            return p
        for _ in range(retry):
            try:
                r = requests.get(url, headers=self.UA, timeout=30)
                if r.status_code == 200 and "Jud_Fact" in r.text:
                    return self.cache.save(url, r.text)
            except Exception:
                time.sleep(1.0)
        raise RuntimeError(f"Failed fetch {url}")

# 4. parse
class JudgmentParser:
    def parse(self, html: str) -> dict:
        soup = bs4.BeautifulSoup(html, "lxml")
        fact = soup.find(id="Jud_Fact")
        reason = soup.find(id="Jud_Reason")
        return {"fact"  : fact.get_text(" ", strip=True)   if fact   else "",
            "reason": reason.get_text(" ", strip=True) if reason else ""
        }

# 5. context vector
class Embedder:
    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]):
        return self.model.encode(texts, normalize_embeddings=True)

#6. GPT-3.5 summary
class GPTSummarizer:
    SYS = ("你是法律助理，請比較下列判決與提問事件的異同，"
           "先用 2 行總結共同點，再條列 3-5 點差異，最後 1 行建議。")

    def __init__(self):
        self.client = OpenAI()      # 讀環境變數 OPENAI_API_KEY

    def summarize(self, query: str, cases: list[dict]) -> str:
        docs = "\n\n".join(
            f"[{i+1}] {c['fact'][:100]}…{c['reason'][:100]}…" for i, c in enumerate(cases)
        )
        prompt = textwrap.dedent(f"""
        事件描述：{query}

        以下是相似判決摘要：
        {docs}
        """)

        rsp = self.client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": self.SYS},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
        )
        return rsp.choices[0].message.content.strip()

# 7. Pipeline
class Pipeline:
    def __init__(self, top_k: int = 3):
        self.ke = KeywordExtractor()
        self.gf = GoogleSearch()
        self.dl = HtmlDownloader()
        self.jp = JudgmentParser()
        self.gpt = GPTSummarizer()
        self.top_k = top_k

    def run(self, query: str) -> str:
        #1. extract keywords
        keywords = self.ke.extract(query)

        # 2. Google address
        urls = self.gf.search_judgments(keywords, num=self.top_k *3)

        # 3. download and parse
        cases=[]
        for u in urls:
            try:
                html = self.dl.fetch(u).read_text(encoding="utf-8")
                parsed = self.jp.parse(html)
                if parsed["fact"]:
                    cases.append(parsed)
                if len(cases)>=self.top_k:
                    break
            except Exception as e:
                print("skip", u, e)

        # 4. GPT summarize
        return self.gpt.summarize(query, cases)
