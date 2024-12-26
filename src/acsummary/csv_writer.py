import csv
from typing import List
from .models import Article

class CSVWriter:
    @staticmethod
    def write_articles(articles: List[Article], output_path: str) -> None:
        """記事情報をCSVファイルに出力"""
        headers = ['日付', 'ハンドルネーム', 'タイトル', 'ジャンル', '要約', 'URL']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for article in articles:
                writer.writerow({
                    '日付': article.date,
                    'ハンドルネーム': article.handle_name,
                    'タイトル': article.title,
                    'ジャンル': article.genre,
                    '要約': article.summary,
                    'URL': article.url
                })