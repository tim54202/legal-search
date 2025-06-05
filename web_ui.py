import streamlit as st
import re
from legal_search import Pipeline, WebContentExtractor
import logging
from dotenv import load_dotenv

load_dotenv()

# 設定日誌
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Streamlit 頁面配置
st.set_page_config(page_title="法律案例搜尋", page_icon="⚖️", layout="wide")

# 初始化 Pipeline
@st.cache_resource
def init_pipeline():
    return Pipeline()


# 頁面標題
st.title("⚖️ 法律案例搜尋系統")
st.markdown("輸入事件描述或新聞網址，系統將自動提取關鍵字，搜尋司法院相關案例並生成總結。")

# 輸入框
with st.form(key="query_form"):
    input_str = st.text_input(
        label="輸入事件描述或新聞網址",
        help="支援文字描述或新聞文章網址"
    )
    submit_button = st.form_submit_button(label="搜尋")

# 處理輸入
if submit_button and input_str:
    with st.spinner("處理中，請稍候..."):
        try:
            pipeline = init_pipeline()
            # 檢查是否為網址
            if re.match(r'^https?://', input_str, re.IGNORECASE):
                query = WebContentExtractor.extract_text_from_url(input_str)
                if not query:
                    st.error("無法從網址提取有效內容，請檢查網址或提供文字輸入")
                else:
                    st.info(f"從網址提取的內容：{query[:300]}...")
            else:
                query = input_str

            # 運行 Pipeline
            if query:
                result = pipeline.run(query)
                keywords: list[str] = result.get("keywords", [])
                summary: str = result.get("summary", "")

                if keywords or summary:
                    st.success("搜尋完成！")
                    st.markdown("### 搜尋結果")

                    # 顯示提取的關鍵字
                    if keywords:
                        st.markdown("**提取的關鍵字**： " + ", ".join(keywords))
                    else:
                        st.warning("未提取到關鍵字")

                    # 顯示總結
                    if summary:
                        st.markdown("**案例總結**：")
                        st.markdown(summary)
                        # 提供下載按鈕
                        st.download_button(
                            label="下載總結",
                            data=summary,
                            file_name="case_summary.md",
                            mime="text/markdown"
                        )
                    else:
                        st.error("未生成總結，請嘗試其他輸入")
                else:
                    st.error("未找到相關案例或關鍵字，請嘗試其他輸入")
            else:
                st.error("輸入無效，請提供有效文字或網址")
        except Exception as e:
            logger.error(f"處理失敗: {str(e)}")
            st.error(f"處理失敗：{str(e)}")