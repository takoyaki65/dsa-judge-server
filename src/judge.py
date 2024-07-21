import yaml
from jsonschema import validate
from pathlib import Path
import json
from dataclasses import dataclass, field
from sandbox.execute import Volume
from sandbox.my_error import Error
from sandbox.execute import TaskInfo
from sandbox.execute import VolumeMountInfo
from sandbox.execute import TaskResult
from dotenv import load_dotenv
import os
from enum import Enum

load_dotenv()

PATH_TO_TASK_DIR = Path(os.getenv("PATH_TO_TASK_DIR")).resolve()

PATH_TO_SCHEMA = "/task_schema.json"

COMPILE_TIMEOUT = 30  # コンパイルのタイムアウト時間 30秒
CHECKER_TIMEOUT = 30  # チェッカーのタイムアウト時間 30秒

DEFAULT_PIDS_LIMIT = 100  # プロセス数のデフォルトの制限
DEFAULT_STACK_LIMIT = -1  # スタックサイズのデフォルトの制限(-1は無制限)
DEFAULT_MEMORY_LIMIT = 1024  # メモリのデフォルトの制限 1024MB

class JudgeStatus(Enum):
    AC = "AC"  # 正解
    WA = "WA"  # 不正解
    TLE = "TLE"  # 制限時間超過
    MLE = "MLE"  # メモリー超過
    CE = "CE"  # 実行時エラー

    def __str__(self):
        return self.value

@dataclass
class JudgeResult:
    status: JudgeStatus
    timeMS: int
    memoryMB: int
    exitCode: int
    stdout: str
    stderr: str

class JudgeSummary:
    status: JudgeStatus
    

class JudgeInfo:
    schema: dict
    judge_data: dict
    volume: Volume
    directory_path: Path  # 課題のディレクトリの絶対パス
    requiredFiles: list[str]
    buildCommands: list[str]
    executable: str
    timeLimitS: int
    memoryLimitMB: int
    testCases: list[
        dict
    ]  # [{"input": "input.txt", "output": "output.txt", "checker": "exact", "exitCode": 0}, ...]

    def __init__(self, directory_path: str) -> None:
        """
        directory_path: PATH_TO_TASK_DIR("./task_dir")から見た、課題のディレクトリの相対パス
        """
        # jsonschema.execptions.ValidationErrorが発生する場合があるのでJudgeInfoインスタンスを生成するときはtry-exceptで囲むこと
        with open(PATH_TO_SCHEMA, "r") as f:
            self.schema = json.load(f)

        # directory_pathを絶対パスに変換
        self.directory_path = (PATH_TO_TASK_DIR / directory_path).resolve()

        task_yaml_path = self.directory_path / "task.yaml"

        with open(task_yaml_path, "r") as f:
            self.judge_data = yaml.load(f, Loader=yaml.CLoader)

        validate(self.judge_data, self.schema)

        self.requiredFiles = self.judge_data["requiredFiles"]
        # 相対パスを絶対パスに変換
        for i in range(len(self.requiredFiles)):
            self.requiredFiles[i] = (
                self.directory_path / self.requiredFiles[i]
            ).resolve()

        self.buildCommands = self.judge_data["build"]
        # buildCommandsを&&でつなげる
        # 例) ["g++ -o a.out main.cpp", "g++ -o b.out main.cpp"] -> "g++ -o a.out main.cpp && g++ -o b.out main.cpp"
        self.buildCommands = " && ".join(self.buildCommands)
        # splitする
        # 例) "g++ -o a.out main.cpp && g++ -o b.out main.cpp" -> ["g++", "-o", "a.out", "main.cpp", "&&", "g++", "-o", "b.out", "main.cpp"]
        self.buildCommands = self.buildCommands.split(" ")

        self.executable = self.judge_data["executable"]

        self.timeLimitS = self.judge_data["timeS"]
        self.memoryLimitMB = self.judge_data["memoryMB"]

        self.testCases = self.judge_data["testCases"]
        # testCases内のファイルパスを絶対パスに変換
        for i in range(len(self.testCases)):
            self.testCases[i]["input"] = (
                self.directory_path / self.testCases[i]["input"]
            ).resolve()
            self.testCases[i]["output"] = (
                self.directory_path / self.testCases[i]["output"]
            ).resolve()

    def __str__(self) -> str:
        return str(self.judge_data)

    def compile(self) -> tuple[TaskResult, Error]:
        self.volume, err = Volume.create()
        if err.message != "":
            return (TaskResult(), err)

        # 必要なファイルをボリュームにコピー
        err = self.volume.copyFiles(
            filePathsFromClient=self.requiredFiles, DirPathInVolume="./"
        )

        if err.message != "":
            return (TaskResult(), err)

        # TODO: 複数言語に対応する
        task = TaskInfo(
            name="checker-lang-gcc",
            arguments=self.buildCommands,
            timeout=COMPILE_TIMEOUT,
            workDir="/workdir/",
            volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=self.volume)],
            memoryLimitMB=DEFAULT_MEMORY_LIMIT,
            pidsLimit=DEFAULT_PIDS_LIMIT,
        )

        result, err = task.run()

        if err.message != "":
            return (TaskResult(), err)

        # ボリューム内のソースコードを削除
        filePathsInVolume: list[str] = [
            str(Path("./") / Path(requiredFile).name)
            for requiredFile in self.requiredFiles
        ]
        err = self.volume.removeFiles(filePathsInVolume)

        if err.message != "":
            return (result, err)

        return (result, Error(""))

    def __run(self, input_path: str) -> tuple[TaskResult, Error]:
        # 一つの入出力例に対してサンドボックス実行する
        # input_path: 入力ファイルの絶対パス
        # output_path: 出力ファイルの絶対パス
        # 前提: 入力ファイルは既にボリュームにコピーされている
        # sandbox内で実行する

        # 実行コマンドを作成
        # ex. ["./a.out", "<", "input.txt"]
        # 出力は実行結果から取得する
        command = [("./" + self.executable), "<", Path(input_path).name]

        task = TaskInfo(
            name="binary-runner",
            arguments=command,
            timeout=self.timeLimitS,
            cpus=1,
            memoryLimitMB=self.memoryLimitMB,
            pidsLimit=DEFAULT_PIDS_LIMIT,
            workDir="/workdir/",
            volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=self.volume)],
        )

        result, err = task.run()

        if err.message != "":
            return (TaskResult(), err)

        return (result, Error(""))

    def judge(self) ->