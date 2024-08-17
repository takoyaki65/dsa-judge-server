from pathlib import Path
from dataclasses import dataclass, field
from sandbox.execute import Volume
from sandbox.my_error import Error
from sandbox.execute import TaskInfo
from sandbox.execute import VolumeMountInfo
from sandbox.execute import TaskResult
from dotenv import load_dotenv
from db.models import TestCases, Problem
from db.crud import (
    update_submission_status,
    register_judge_result,
    fetch_problem,
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
    lecture_id: int
    assignment_id: int
    for_evaluation: bool
    problem_record: Problem | None  # Problemテーブル内のテーブルレコード

    required_files: list[str]  # ユーザに提出を求められているソースコードの名前リスト
    arranged_filepaths: list[
        Path
    ]  # こちらが用意しているソースコードのファイルパスのリスト
    uploaded_filepaths: list[Path]  # ユーザが提出したソースコードのファイルパスのリスト

    entire_status: JudgeStatus  # テストケース全体のジャッジ結果

    prebuilt_testcases: list[TestCases]

    postbuilt_testcases: list[TestCases]

    judge_testcases: list[TestCases]

    def __init__(
        self,
        submission_id: int,
        lecture_id: int,
        assignment_id: int,
        for_evaluation: bool,
    ):
        self.submission_id = submission_id
        self.lecture_id = lecture_id
        self.assignment_id = assignment_id
        self.for_evaluation = for_evaluation

        self.problem_record = fetch_problem(
            db=db,
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
            RESOURCE_DIR / filepath
            for filepath in fetch_uploaded_filepaths(db=db, submission_id=submission_id)
        ]

        # Get testcases info
        testcases = fetch_testcases(
            db=db,
            lecture_id=lecture_id,
            assignment_id=assignment_id,
            for_evaluation=for_evaluation,
        )

        self.prebuilt_testcases = []
        self.postbuilt_testcases = []
        self.judge_testcases = []

        # prebuilt, postbuilt, judgeの種類ごとにtestcasesを分ける
        for testcase in testcases:
            if testcase.type == "preBuilt":
                self.prebuilt_testcases.append(testcase)
            elif testcase.type == "postBuilt":
                self.postbuilt_testcases.append(testcase)
            else:
                self.judge_testcases.append(testcase)

        self.entire_status = "AC"
        db.close()

    def _create_complete_volume(self) -> tuple[Volume, Error]:
        docker_volume, err = Volume.create()
        if not err.silence():
            return (Volume(""), Error(f"cannot create volume: {docker_volume.name}"))

        # copy uploaded files and arranged files to volume
        err = docker_volume.copyFiles(self.uploaded_filepaths + self.arranged_filepaths)
        if not err.silence():
            return (
                Volume(""),
                Error(f"failed to copy uploaded files to volume: {docker_volume.name}"),
            )

        return (docker_volume, Error.Nothing())

    def _prebuilt_check(self) -> JudgeStatus:
        assert self.problem_record is not None
        db = SessionLocal()
        for testcase in self.prebuilt_testcases:
            # ボリューム作成
            volume, err = self._create_complete_volume()
            if not err.silence():
                register_judge_result(
                    db=db,
                    submission_id=self.submission_id,
                    testcase_id=testcase.id,
                    timeMS=0,
                    memoryKB=0,
                    exit_code=-1,
                    stdout="",
                    stderr=err.message,
                    result="IE",
                )
                return JudgeStatus.IE

            args = []

            # スクリプトが要求されるならそれをボリュームにコピー
            if testcase.script_path is not None:
                volume.copyFile(
                    RESOURCE_DIR / testcase.script_path,
                    Path("./") / Path(testcase.script_path).name,
                )
                args = [str(Path("./") / Path(testcase.script_path).name)]
            else:
                # そうでないなら通常のexecutablesに変更
                args = [str(Path("./") / self.problem_record.executable)]

            # 引数をargに追加する

    def judge(self) -> Error:
        if self.problem_record is None:
            # SubmissionテーブルのstatusをIEに変更
            db = SessionLocal()
            update_submission_status(
                db=db, submission_id=self.submission_id, status="IE"
            )
            db.close()
            return Error(
                f"Error on Problem {self.lecture_id}-{self.assignment_id}:{self.for_evaluation}: Not found"
            )
        return Error.Nothing()
