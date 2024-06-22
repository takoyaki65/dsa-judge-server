"""
このプログラムでは、以下のような機能を実装する。
* Dockerボリュームの作成と削除を行うボリューム管理クラスVolume
* Dockerコンテナの作成と削除を行うコンテナ管理クラスContainerInfo
* タスクの実行を行うタスク管理クラスTaskInfo
* タスクの実行結果を格納するクラスTaskResult
"""

import uuid
import subprocess
from datetime import timedelta
from dataclasses import dataclass
import time # 実行時間の計測に使用


# エラーメッセージの型
class Error:
    message: str  # エラーメッセージ

    def __init__(self, message: str):
        self.message = message


# Dockerボリュームの管理クラス
class Volume:
    name: str  # ボリューム名

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def Create(cls) -> tuple["Volume", Error]:
        volumeName = "volume-" + str(uuid.uuid4())

        args = ["volume", "create"]
        args += ["--name", volumeName]

        # Dockerボリュームの作成
        cmd = ["docker"] + args
        err = ""

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            err = f"Failed to create volume: {e}"

        if err != "":
            return Volume(""), Error(err)
        return Volume(volumeName), Error("")

    def Remove(self) -> Error:
        args = ["volume", "rm", self.name]

        cmd = ["docker"] + args
        err = ""

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            err = f"Failed to remove volume: {e}"

        return Error(err)


# Dockerコンテナの管理クラス
class ContainerInfo:
    containerID: str  # コンテナID

    def __init__(self, containerID: str):
        self.containerID = containerID

@dataclass
class VolumeMountInfo:
    path: str       # コンテナ内のマウント先のパス
    volume: Volume  # マウントするボリュームの情報

# 時間計測用のモニター
class TaskMonitor:
    def __init__(self):
        self.start_time = 0
        self.end_time = 0

    def start(self):
        self.start_time = time.time_ns()
    
    def end(self):
        self.end_time = time.time_ns()
    
    def get_elapsed_time(self) -> float:
        return (self.end_time - self.start_time) / 1e9
    
    def get_elapsed_time_ms(self) -> float:
        return (self.end_time - self.start_time) / 1e6
    
    def get_elapsed_time_us(self) -> float:
        return (self.end_time - self.start_time) / 1e3
    
    def get_elapsed_time_ns(self) -> float:
        return self.end_time - self.start_time

# タスクの実行情報
@dataclass
class TaskInfo:
    name: str
    arguments: list[str]
    timeout: timedelta
    cpus: int  # CPUの割り当て数
    memoryLimitMB: int
    stackLimitKB: int  # リカージョンの深さを制限
    pidsLimit: int  # プロセス数の制限
    enableNetwork: bool
    enableLoggingDriver: bool
    workDir: str    # コンテナ内での作業ディレクトリ
    # cgroupをいじるにはroot権限が必要なので、現状は使わない
    # cgroupParent: str  # cgroupの親ディレクトリ
    volumeMountInfo: list[VolumeMountInfo]  # ボリュームのマウント情報
    taskMonitor: TaskMonitor




