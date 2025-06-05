# Legal-Search / 台灣裁判書語意搜尋與摘要工具

## Overview

This application is designed to assist users in legal research by enabling them to input content (e.g., text or URLs) and retrieve relevant legal cases from the Taiwan Judicial Yuan's judgment database. It analyzes the input, searches for matching cases, and provides a comprehensive summary including similarities, differences, and conclusions. 



## Feature
- Extract keywords from user input or web content using KeyBERT.

- Fetch legal case links from the Taiwan Judicial Yuan website using Selenium.

- Analyze the similarity between keywords and case facts using TF-IDF and cosine similarity.

- Generate summaries comparing cases with user queries using OpenAI.

- Support for extracting content from news websites (e.g., Yahoo News, Chinatimes) with fallback to Selenium for anti-scraping protection.

- Save error page sources for debugging.


## Prerequisites

1. **Environment Variables:**
   You must set the `OPENAI_API_KEY` environment variable with a valid OpenAI API key.

   ```bash
   OPENAI_API_KEY=your_api_key_here
   ```
   
3. **Selenium Google Chrome Driver:**
  Install Google Chrome and the corresponding ChromeDriver. Ensure the ChromeDriver executable is in your system PATH or specify the path in the code (e.g., `/usr/local/bin/chromedriver`).

  ```bash
  chmod +x /usr/local/bin/chromedriver
  ```

3. **Python Environment:**
  Python 3.8 or higher is required.

## Installation and Setup

1. Clone the Repository
  ```bash
  git clone https://github.com/tim54202/legal-search.git
  ```

2. Install Dependencies
  ```bash
  pip install -r requirements.txt
  ```

3. Run the Application
   There are two ways to run the application. One is to use `main.py` in the terminal or IDE.
   The other one is to run the command below, then it will operate in the web.
   
  ```bash
  streamlit run web_ui.py
  ```

## Usage
Input a URL (e.g., Yahoo News) or a text query (e.g., "a 72-year-old man crashed into a crowd in Sanxia District").

The app will extract keywords, fetch relevant legal cases, compute similarities, and provide a summary.


## Demo
 ![Here is a demo video.](Demo_Legal_Search.mov)

## License

This project is licensed under the MIT License - see the LICENSE file for details.












  
