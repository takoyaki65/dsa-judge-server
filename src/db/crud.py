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

# lecture_id, assignment_id, for_evaluationのデータから、それに対応するProblemデータ(実行ファイル名、制限リソース量)を取得する
def fetch_problem(db: Session, lecture_id: int, assignment_id: int, for_evaluation: bool) -> models.Problem | None:
    problem = db.query(models.Problem).filter(models.Problem.lecture_id == lecture_id,
                                              models.Problem.assignment_id == assignment_id,
                                              models.Problem.for_evaluation == for_evaluation
                                              ).first()
    
    return problem

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
def register_judge_result(db: Session, submission_id: int, testcase_id: int, timeMS: int, memoryKB: int, exit_code: int, stdout: str, stderr: str, result: str) -> None:
    judge_result = models.JudgeResult(
        submission_id=submission_id,
        testcase_id=testcase_id,
        timeMS=timeMS,
        memoryKB=memoryKB,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        result=result
    )
    db.add(judge_result)
    db.commit()
    
# 特定のsubmission_idに対応するジャッジリクエストの全体statusを変更する
# 注意: statusには'pending', 'queued', 'running', 'done'のみ入れる
def update_submission_status(db: Session, submission_id: int, status: str) -> None:
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if submission:
        submission.status = status
        db.commit()
    else:
        raise ValueError(f"Submission with id {submission_id} not found")

# 特定のsubmission_idに対応するジャッジリクエストのprebuilt_resultを変更する
# 注意: prebuilt_statusには'AC', 'WA', 'TLE', 'MLE', 'CE', 'RE', 'OLE', 'IE'のみ入る
def update_submission_prebuilt_result(db: Session, submission_id: int, prebuilt_result: str) -> None:
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if submission:
        submission.prebuilt_result = prebuilt_result
        db.commit()
    else:
        raise ValueError(f"Submission with id {submission_id} not found")

# 特定のsubmission_idに対応するジャッジリクエストのpostbuilt_resultを変更する
# 注意: postbuilt_statusには'AC', 'WA', 'TLE', 'MLE', 'CE', 'RE', 'OLE', 'IE'のみ入る
def update_submission_postbuilt_result(db: Session, submission_id: int, postbuilt_result: str) -> None:
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if submission:
        submission.postbuilt_result = postbuilt_result
        db.commit()
    else:
        raise ValueError(f"Submission with id {submission_id} not found")
    
# 特定のsubmission_idに対応するジャッジリクエストのjudge_resultを変更する
# 注意: judge_statusには'AC', 'WA', 'TLE', 'MLE', 'CE', 'RE', 'OLE', 'IE'のみ入る
def update_submission_judge_result(db: Session, submission_id: int, judge_result: str) -> None:
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if submission:
        submission.judge_result = judge_result
        db.commit()
    else:
        raise ValueError(f"Submission with id {submission_id} not found")

# 特定のsubmission_idに対応するジャッジリクエストのmessageを変更する。
def update_submission_message(db: Session, submission_id: int, message: str) -> None:
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if submission:
        submission.message = message
        db.commit()
    else:
        raise ValueError(f"Submission with id {submission_id} not found")