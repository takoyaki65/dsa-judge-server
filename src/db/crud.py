# Create, Read, Update and Delete (CRUD)
from sqlalchemy.orm import Session

from . import models

# Submissionテーブルから、statusが"queued"のジャッジリクエストを数件取得し、statusを"running"
# に変え、変更したリクエスト(複数)を返す
def fetch_queued_judge(db: Session, n: int) -> list[models.Submission]:
    submissions = db.query(models.Submission).filter(models.Submission.status == 'queued').limit(n).all()
    for submission in submissions:
        submission.status = 'running'
    db.commit()
    return submissions

# ジャッジリクエストに紐づいている、アップロードされたファイルのパスのリストをUploadedFiles
# テーブルから取得して返す
def fetch_uploaded_filepaths(db: Session, submission_id: int) -> list[str]:
    uploaded_files = db.query(models.UploadedFiles).filter(models.UploadedFiles.submission_id == submission_id).all()
    return [file.path.__str__() for file in uploaded_files]

# 特定の問題でこちらで用意しているファイルのパス(複数)をArrangedFilesテーブルから取得する
def fetch_arranged_filepaths(db: Session, lecture_id: int, assignment_id: int, for_evaluation: bool) -> list[str]:
    arranged_files = db.query(models.ArrangedFiles).filter(
        models.ArrangedFiles.lecture_id == lecture_id,
        models.ArrangedFiles.assignment_id == assignment_id,
        models.ArrangedFiles.for_evaluation == for_evaluation
    ).all()
    return [file.path.__str__() for file in arranged_files]

# 特定の問題で必要とされているのファイル名のリストをRequiredFilesテーブルから取得する
def fetch_required_files(db: Session, lecture_id: int, assignment_id: int, for_evaluation: bool) -> list[str]:
    required_files = db.query(models.RequiredFiles).filter(
        models.RequiredFiles.lecture_id == lecture_id,
        models.RequiredFiles.assignment_id == assignment_id,
        models.RequiredFiles.for_evaluation == for_evaluation
    ).all()
    return [file.name.__str__() for file in required_files]

# 特定の問題に紐づいたテストケースのリストをTestCasesテーブルから取得する
def fetch_testcases(db: Session, lecture_id: int, assignment_id: int, for_evaluation: bool) -> list[models.TestCases]:
    return db.query(models.TestCases).filter(
        models.TestCases.lecture_id == lecture_id,
        models.TestCases.assignment_id == assignment_id,
        models.TestCases.for_evaluation == for_evaluation
    ).all()

# 特定のテストケースに対するジャッジ結果をJudgeResultテーブルに登録する
def register_judge_result(db: Session, submission_id: int, testcase_id: int, timeMS: int, memoryKB: int, result: str) -> None:
    judge_result = models.JudgeResult(
        submission_id=submission_id,
        testcase_id=testcase_id,
        timeMS=timeMS,
        memoryKB=memoryKB,
        result=result
    )
    db.add(judge_result)
    db.commit()
