import sys

from legal_search import Pipeline, WebContentExtractor
import re



def main():
    if len(sys.argv) < 2:
        print(
            "請提供輸入文字或網址，例如：python main.py '台中市一名男子酒駕致三人死亡' 或 python main.py 'https://news.example.com/drunk-driving-taichung'")
        sys.exit(1)

    input_str = sys.argv[1]
    pipeline = Pipeline(k=3)

    # 檢查是否為網址
    if re.match(r'^https?://', input_str, re.IGNORECASE):
        # 爬取網頁內容
        query = WebContentExtractor.extract_text_from_url(input_str)
        if not query:
            print("無法從網址提取有效內容，請檢查網址或提供文字輸入")
            sys.exit(1)
    else:
        # 直接使用文字輸入
        query = input_str

    # 運行 Pipeline
    summary = pipeline.run(query)

    # 輸出結果
    print(summary)
    with open("case_summary.md", "w", encoding="utf-8") as f:
        f.write(summary)



if __name__ == "__main__":
    main()

