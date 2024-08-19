from pathlib import Path
from dataclasses import dataclass, field
from sandbox.execute import Volume
from sandbox.my_error import Error
from sandbox.execute import TaskInfo
from sandbox.execute import VolumeMountInfo
from sqlalchemy.orm import Session
from sandbox.execute import TaskResult
from dotenv import load_dotenv
from db.models import TestCases, Problem
import logging
from db.crud import (
    update_submission_status,
    update_submission_message,
    update_submission_prebuilt_result,
    update_submission_postbuilt_result,
    update_submission_judge_result,
    register_judge_result,
    fetch_problem,
    fetch_required_files,
    fetch_arranged_filepaths,
    fetch_testcases,
    fetch_uploaded_filepaths,
)
from db.database import SessionLocal
from checker import StandardChecker
import os
from enum import Enum

# ロガーの設定
logging.basicConfig(level=logging.INFO)
test_logger = logging.getLogger(__name__)

load_dotenv()

RESOURCE_DIR = Path(os.getenv("RESOURCE_PATH"))


class JudgeStatusFlag(Enum):
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


StatusOrder = {
    "AC": 1,
    "WA": 2,
    "TLE": 3,
    "MLE": 4,
    "RE": 5,
    "CE": 6,
    "OLE": 7,
    "IE": 8,
}


class JudgeStatus:
    flag: JudgeStatusFlag

    def __init__(self, flag: JudgeStatusFlag):
        self.flag = flag

    def update(self, flag: JudgeStatusFlag) -> None:
        if StatusOrder[self.flag.__str__()] < StatusOrder[flag.__str__()]:
            self.flag = flag


@dataclass
class JudgeResult:
    testcase_id: int
    status: JudgeStatusFlag
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

        self.entire_status = JudgeStatus(JudgeStatusFlag.AC)
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

    def _result_check_and_register(
        self,
        db: Session,
        testcase: TestCases,
        result: TaskResult,
        expected_stdout: str,
        expected_stderr: str,
    ) -> JudgeStatus:
        status: JudgeStatus = JudgeStatus(JudgeStatusFlag.AC)
        # TLEチェック
        if result.TLE:
            register_judge_result(
                db=db,
                submission_id=self.submission_id,
                testcase_id=testcase.id,
                timeMS=result.timeMS,
                memoryKB=result.memoryByte / 1024,
                exit_code=result.exitCode,
                stdout=result.stdout,
                stderr=result.stderr,
                result="TLE",
            )
            status.update(JudgeStatusFlag.TLE)
            return status
        # MLEチェック
        elif result.memoryByte + 1024 * 1024 > 512 * 1024 * 1024:
            register_judge_result(
                db=db,
                submission_id=self.submission_id,
                testcase_id=testcase.id,
                timeMS=result.timeMS,
                memoryKB=result.memoryByte / 1024,
                exit_code=result.exitCode,
                stdout=result.stdout,
                stderr=result.stderr,
                result="MLE",
            )
            status.update(JudgeStatusFlag.MLE)
            return status
        # RE(Runtime Errorチェック)
        elif result.exitCode != testcase.exit_code:
            register_judge_result(
                db=db,
                submission_id=self.submission_id,
                testcase_id=testcase.id,
                timeMS=result.timeMS,
                memoryKB=result.memoryByte / 1024,
                exit_code=result.exitCode,
                stdout=result.stdout,
                stderr=result.stderr,
                result="RE",
            )
            status.update(JudgeStatusFlag.RE)
            return status
        # Wrong Answerチェック
        elif StandardChecker.check(
            expected_stdout, result.stdout
        ) and StandardChecker.check(expected_stderr, result.stderr):
            register_judge_result(
                db=db,
                submission_id=self.submission_id,
                testcase_id=testcase.id,
                timeMS=result.timeMS,
                memoryKB=result.memoryByte / 1024,
                exit_code=result.exitCode,
                stdout=result.stdout,
                stderr=result.stderr,
                result="AC",
            )
            status.update(JudgeStatusFlag.AC)
            return status
        else:
            register_judge_result(
                db=db,
                submission_id=self.submission_id,
                testcase_id=testcase.id,
                timeMS=result.timeMS,
                memoryKB=result.memoryByte / 1024,
                exit_code=result.exitCode,
                stdout=result.stdout,
                stderr=result.stderr,
                result="WA",
            )
            status.update(JudgeStatusFlag.WA)
            return status
    
    def _exec_checker(self, testcase_list: list[TestCases], initial_volume: Volume, container_name: str, timeoutSec: int, memoryLimitMB: int) -> JudgeStatus:
        assert self.problem_record is not None
        db = SessionLocal()
        summary_status: JudgeStatus = JudgeStatus(JudgeStatusFlag.AC)
        for testcase in testcase_list:
            # ボリューム作成
            volume, err = initial_volume.clone()
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
                    result="IE"
                )
                summary_status.update(JudgeStatusFlag.IE)
                continue
            
            args = []
            
            # スクリプトが要求されるならそれをボリュームにコピー
            if testcase.script_path is not None:
                volume.copyFile(
                    RESOURCE_DIR / testcase.script_path,
                    Path("./") / Path(testcase.script_path).name
                )
                args = [str(Path("./") / Path(testcase.script_path).name)]
            else:
                # そうでないなら通常のexecutableをargsに追加
                args = [str(Path("./") / self.problem_record.executable)]
            
            stdin: str = ""
            expected_stdout: str = ""
            expected_stderr: str = ""
            
            try:
                # 引数をargに追加する
                with open(RESOURCE_DIR / testcase.argument_path, "r", encoding='utf-8') as f:
                    arguments = f.read().strip().split()
                    args.extend(arguments)
                    
                # stdin, expected_stdout, expected_stderrを読み込む
                if testcase.stdin_path is not None:
                    with open(
                        RESOURCE_DIR / testcase.stdin_path, "r", encoding="utf-8"
                    ) as f:
                        stdin = f.read()
                else:
                    stdin = ""

                with open(
                    RESOURCE_DIR / testcase.stdout_path, "r", encoding="utf-8"
                ) as f:
                    expected_stdout = f.read()

                with open(
                    RESOURCE_DIR / testcase.stderr_path, "r", encoding="utf-8"
                ) as f:
                    expected_stderr = f.read()
        
            except FileNotFoundError:
                register_judge_result(
                    db=db,
                    submission_id=self.submission_id,
                    testcase_id=testcase.id,
                    timeMS=0,
                    memoryKB=0,
                    exit_code=-1,
                    stdout="",
                    stderr=f"ファイルが見つかりません: {FileNotFoundError.filename}",
                    result="IE",
                )
                summary_status.update(JudgeStatusFlag.IE)
                # ボリュームを削除
                err = volume.remove()
                if not err.silence():
                    test_logger.info(f"failed to remove volume: {volume.name}")
                continue
            
            # sandbox環境のセットアップ
            task = TaskInfo(
                name=container_name,
                arguments=args,
                workDir="/workdir/",
                volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=volume)],
                timeout=timeoutSec,
                memoryLimitMB=memoryLimitMB,
                Stdin=stdin,
            )

            # sandbox環境で実行
            result, err = task.run()

            status = self._result_check_and_register(
                db=db,
                testcase=testcase,
                result=result,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
            )
            
            # ボリュームを削除
            err = volume.remove()
            if not err.silence():
                test_logger.info(f"failed to remove volume: {volume.name}")
            
            summary_status.update(status)
        
        db.close()
        return summary_status

    def _compile(self, working_volume: Volume, container_name: str) -> Error:
        # コンパイルコマンドの取得
        args = []
        try:
            with open(RESOURCE_DIR / self.problem_record.build_script_path, mode='r', encoding='utf-8') as f:
                compile_command = f.read().strip().split()
                args.extend(compile_command)
        except FileNotFoundError:
            return Error(f"script for compile commands not found: {self.problem_record.build_script_path}")
    
        # sandbox環境のセットアップ
        task = TaskInfo(
            name=container_name,
            arguments=args,
            workDir="/workdir/",
            volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=working_volume)],
            timeout=2,
            memoryLimitMB=512
        )
        
        # sandbox環境で実行
        result, err = task.run()
        
        if not err.silence():
            return Error(f"compile failed: {result.stderr}")
        
        return Error.Nothing()

    def judge(self) -> Error:
        if self.problem_record is None:
            # Submissionテーブルのstatusをdoneに変更
            db = SessionLocal()
            update_submission_status(
                db=db, submission_id=self.submission_id, status="done"
            )
            # Submissionテーブルのmessageにエラー文を追加
            error_message = f"Error on Problem {self.lecture_id}-{self.assignment_id}:{self.for_evaluation}: Not found"
            update_submission_message(
                db=db, submission_id=self.submission_id, message=error_message
            )
            db.close()
            return Error(error_message)

        # 1. コンパイル前のチェックを行う
        # required_files, arranged_filesが入ったボリュームを作る
        working_volume, err = self._create_complete_volume()
        if not err.silence():
            return err
        # チェッカーを走らせる
        status = self._exec_checker(testcase_list=self.prebuilt_testcases, initial_volume=working_volume, container_name="binary-runner", timeoutSec=2, memoryLimitMB=512)
        if status.flag is not JudgeStatusFlag.AC:
            # 早期終了
            db = SessionLocal()
            update_submission_status(
                db=db, submission_id=self.submission_id, status="done"
            )
            update_submission_prebuilt_result(
                db=db, submission_id=self.submission_id, prebuilt_result=status.flag.value
            )
            db.close()
            return Error.Nothing()
        
        # 2. コンパイルを行う
        err = self._compile(working_volume=working_volume, container_name="checker-lang-gcc")
        
        if not err.silence():
            # 早期終了
            db = SessionLocal()
            update_submission_status(
                db=db, submission_id=self.submission_id, status="done"
            )
            update_submission_postbuilt_result(
                db=db, submission_id=self.submission_id, postbuilt_result="CE"
            )
            db.close()
            return Error.Nothing()
        
        # 3. コンパイル後のチェックを行う
        # チェッカーを走らせる
        status = self._exec_checker(testcase_list=self.postbuilt_testcases, initial_volume=working_volume, container_name="checker-lang-gcc", timeoutSec=2, memoryLimitMB=512)
        if status.flag is not JudgeStatusFlag.AC:
            # 早期終了
            db = SessionLocal()
            update_submission_status(
                db=db, submission_id=self.submission_id, status="done"
            )
            update_submission_postbuilt_result(
                db=db, submission_id=self.submission_id, postbuilt_result=status.flag.value
            )
            db.close()
            return Error.Nothing()
        
        # 4. ジャッジを行う
        # チェッカーを走らせる
        status = self._exec_checker(testcase_list=self.judge_testcases, initial_volume=working_volume, container_name="binary-runner", timeoutSec=self.problem_record.timeMS / 1000, memoryLimitMB=self.problem_record.memoryMB)
        
        # ボリュームを削除
        err = working_volume.remove()
        if not err.silence():
            test_logger.info(f"failed to remove volume: {working_volume.name}")
        
        # ジャッジ結果を登録
        db = SessionLocal()
        update_submission_judge_result(
            db=db, submission_id=self.submission_id, status="done"
        )
        update_submission_judge_result(
            db=db, submission_id=self.submission_id, judge_result=status.flag.value
        )
        db.close()
        return Error.Nothing()
