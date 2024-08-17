from pathlib import Path
from dataclasses import dataclass, field
from sandbox.execute import Volume
from sandbox.my_error import Error
from sandbox.execute import TaskInfo
from sandbox.execute import VolumeMountInfo
from sandbox.execute import TaskResult
from dotenv import load_dotenv
from db.models import TestCases
from db.crud import (
    fetch_required_files,
    fetch_arranged_filepaths,
    fetch_testcases,
    fetch_uploaded_filepaths,
)
from db.database import SessionLocal
import os
from enum import Enum

load_dotenv()

RESOURCE_DIR = Path(os.getenv("RESOURCE_PATH"))


class JudgeStatus(Enum):
    AC = "AC"  # 正解 (Accepted)
    WA = "WA"  # 不正解 (Wrong Answer)
    TLE = "TLE"  # 制限時間超過 (Time Limit Exceeded)
    MLE = "MLE"  # メモリー超過 (Memory Limit Exceeded)
    CE = "CE"  # コンパイルエラー (Compile Error)
    RE = "RE"  # 実行時エラー (Runtime Error)
    OLE = "OLE"  # 出力サイズ超過 (Output Limit Exceeded)
    IE = "IE"  # ジャッジサーバの内部エラー (Internal Error)

    def __str__(self):
        return self.value


@dataclass
class JudgeResult:
    testcase_id: int
    status: JudgeStatus
    timeMS: int
    memoryKB: int
    exitCode: int
    stdout: str
    stderr: str


@dataclass
class ProblemInfo:
    lecture_id: int
    assignment_id: int
    for_evaluation: bool


class JudgeInfo:
    submission_id: int
    problem_info: ProblemInfo
    required_files: list[str]  # ユーザに提出を求められているソースコードの名前リスト
    arranged_filepaths: list[
        Path
    ]  # こちらが用意しているソースコードのファイルパスのリスト
    uploaded_filepaths: list[Path]  # ユーザが提出したソースコードのファイルパスのリスト

    entire_status: JudgeStatus  # テストケース全体のジャッジ結果

    testcases: list[TestCases]  # 実行しなくてはならないテストケースの情報

    def __init__(
        self,
        submission_id: int,
        lecture_id: int,
        assignment_id: int,
        for_evaluation: bool,
    ):
        self.submission_id = submission_id
        self.problem_info = ProblemInfo(
            lecture_id=lecture_id,
            assignment_id=assignment_id,
            for_evaluation=for_evaluation,
        )

        db = SessionLocal()

        # Get required file names
        self.required_files = fetch_required_files(
            db=db,
            lecture_id=lecture_id,
            assignment_id=assignment_id,
            for_evaluation=for_evaluation,
        )

        # Get arranged filepaths
        self.arranged_filepaths = [
            RESOURCE_DIR / filepath
            for filepath in fetch_arranged_filepaths(
                db=db,
                lecture_id=lecture_id,
                assignment_id=assignment_id,
                for_evaluation=for_evaluation,
            )
        ]

        # Get uploaded filepaths
        self.uploaded_filepaths = [
            RESOURCE_DIR / fetch_arranged_filepaths
            for filepath in fetch_uploaded_filepaths(db=db, submission_id=submission_id)
        ]

        # Get testcases info
        self.testcases = fetch_testcases(
            db=db,
            lecture_id=lecture_id,
            assignment_id=assignment_id,
            for_evaluation=for_evaluation,
        )

        self.entire_status = "AC"
