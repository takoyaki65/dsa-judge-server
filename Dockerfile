# ベースイメージとしてPython 3.9を使用
FROM python:3.12.4-slim

# 作業ディレクトリの設定
WORKDIR /app

# 必要なPythonライブラリのインストール
# (pyproject.tomlからryeによって自動生成されたrequirements.lockを使用)
COPY requirements.lock .
RUN PYTHONDONTWRITEBYTECODE=1 pip install --no-cache-dir -r requirements.lock

# アプリケーションのソースコードをコピー
COPY src/ .

# FastAPIアプリケーションの起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
