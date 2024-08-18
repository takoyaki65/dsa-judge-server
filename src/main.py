from fastapi import FastAPI, HTTPException, UploadFile, File
from contextlib import asynccontextmanager
import logging

import asyncio
from db.crud import *
from db.models import *
from db.database import SessionLocal

logger = logging.getLogger("uvicorn")


async def process_judge_requests():
    while True:
        with SessionLocal() as db:
            queued_submissions = fetch_queued_judge(db, 10)  # 10件ずつ取得
            if queued_submissions:
                logger.info(
                    f"{len(queued_submissions)}件のジャッジリクエストを取得しました。"
                )
                # ここでジャッジ処理を実行する（実装は省略）
            else:
                logger.info("キューにジャッジリクエストはありません。")

        await asyncio.sleep(5)  # 500ミリ秒待機


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(process_judge_requests())
    yield
    task.cancel()
    # statusをrunningにしてしまっているタスクをqueuedに戻す
    # そして途中結果を削除する
    with SessionLocal() as db:
        undo_running_submissions(db)

app = FastAPI(lifespan=lifespan)
