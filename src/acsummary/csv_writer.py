import csv
from .models import Article

class CSVWriter:
    @staticmethod
    def write_articles(articles: list[Article], output_path: str) -> None:
        """記事情報をCSVファイルに出力"""
        headers = ['日付', 'ハンドルネーム', 'タイトル', 'ジャンル', '要約', 'URL']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for article in articles:
                writer.writerow({
                    '日付': f'"{article.date}"',
                    'ハンドルネーム': f'"{article.handle_name.replace("\"", "\\\"")}"',
                    'タイトル': f'"{article.title.replace("\"", "\\\"")}"',
                    'ジャンル': f'"{article.genre}"',
                    '要約': f'"{article.summary.replace("\"", "\\\"") if article.summary else ""}"',
                    'URL': f'"{article.url.replace("\"", "\\\"")}"'
                })