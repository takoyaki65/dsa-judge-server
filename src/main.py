from fastapi import FastAPI, HTTPException, UploadFile, File
from contextlib import asynccontextmanager
import logging
from concurrent.futures import ThreadPoolExecutor
import asyncio
from db.crud import *
from db.models import *
from db.database import SessionLocal
from sandbox.my_error import Error
from judge import JudgeInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

thread_pool = ThreadPoolExecutor(max_workers=50)

def process_one_judge_request(submission: SubmissionRecord) ->None:
    logger.info(f"JudgeInfo(submission_id={submission.id}, lecture_id={submission.lecture_id}, assignment_id={submission.assignment_id}, for_evaluation={submission.for_evaluation}) will be created...")
    judge_info = JudgeInfo(submission)
    logger.info("START JUDGE...")
    err = judge_info.judge()
    logger.info(f"JUDGE ERROR: \"{err}\"")
    logger.info("END JUDGE")
    
    if not err.silence():
        logger.error(f"ジャッジ中にエラーが生じました: {err}")

async def process_judge_requests():
    while True:
        try:
            with SessionLocal() as db:
                queued_submissions = fetch_queued_judge_and_change_status_to_running(db, 10)  # 10件ずつ取得
                if queued_submissions:
                    logger.info(
                        f"{len(queued_submissions)}件のジャッジリクエストを取得しました。"
                    )
                    # スレッドプールを使用して各ジャッジリクエストを処理
                    for submission in queued_submissions:
                        logger.info(f"submission: {submission}")
                        logger.info("throw judge request to thread pool...")
                        thread_pool.submit(process_one_judge_request, submission)
                else:
                    logger.info("キューにジャッジリクエストはありません。")
        except Exception as e:
            logger.info(f"{type(e)} exception detected: \"{e}\"cannot connect to db, maybe it is not ready.")

        await asyncio.sleep(5)  # 5秒待機


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LIFESPAN LOGIC INITIALIZED...")
    task = asyncio.create_task(process_judge_requests())
    yield
    task.cancel()
    logger.info("LIFESPAN LOGIC DEACTIVATED...")
    # 現在実行しているジャッジリクエストを最後まで実行し、保留状態のものは破棄する
    thread_pool.shutdown(wait=True, cancel_futures=True)
    # statusをrunningにしてしまっているタスクをqueuedに戻す
    # そして途中結果を削除する
    with SessionLocal() as db:
        undo_running_submissions(db)

app = FastAPI(lifespan=lifespan)
