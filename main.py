import sys

from legal_search import Pipeline, WebContentExtractor
import re
from dotenv import load_dotenv

load_dotenv()


def main():
    # 檢查命令列參數
    if len(sys.argv) >= 2:
        input_str = sys.argv[1]
    else:
        # 無參數時，提示使用者輸入
        print("請輸入事件描述或新聞網址：")
        input_str = input().strip()

    # 檢查輸入是否為空
    if not input_str:
        print("輸入為空，請提供有效文字或網址")
        sys.exit(1)
    pipeline = Pipeline()

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

