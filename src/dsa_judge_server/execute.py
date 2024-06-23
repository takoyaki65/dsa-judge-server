"""
このプログラムでは、以下のような機能を実装する。
* Dockerボリュームの作成と削除を行うボリューム管理クラスVolume
* Dockerコンテナの作成と削除を行うコンテナ管理クラスContainerInfo
* タスクの実行を行うタスク管理クラスTaskInfo
* タスクの実行結果を格納するクラスTaskResult
"""

import uuid
import subprocess
import threading
from datetime import timedelta
from dataclasses import dataclass
import time  # 実行時間の計測に使用
import re


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
    def create(cls) -> tuple["Volume", Error]:
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

    def remove(self) -> Error:
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
    path: str  # コンテナ内のマウント先のパス
    volume: Volume  # マウントするボリュームの情報


__MEM_USAGE_PATTERN = re.compile(r"^(\d+(\.\d+)?)([KMG]i?)B")


# 時間・メモリ計測用のモニター
class TaskMonitor:
    startTime: int
    endTime: int
    maxUsedMemory: int  # 最大使用メモリ量[Byte]
    containerInfo: ContainerInfo  # モニタリング対象のコンテナ情報
    _monitoring: bool  # モニタリング中かどうか
    _monitor_thread: threading.Thread  # モニタリングスレッド

    def __init__(self, containerInfo: ContainerInfo):
        self.startTime = 0
        self.endTime = 0
        self.maxUsedMemory = 0
        self.containerInfo = containerInfo
        self._monitoring = False

    def start(self):
        self.startTime = time.time_ns()
        # containerInfo.containerIDを使ってコンテナのメモリ使用量を取得する
        # 取得はdocker statsコマンドを使い、1msごとに取得する
        # 取得したメモリ使用量からmaxUsedMemoryを更新する
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self.__monitor_memory_usage)
        self._monitor_thread.start()

    def end(self):
        self.endTime = time.time_ns()
        self._monitoring = False
        self._monitor_thread.join()

    def get_elapsed_time_ms(self) -> float:
        return (self.endTime - self.startTime) / 1e6

    def get_used_memory_byte(self) -> int:
        return self.maxUsedMemory

    def __monitor_memory_usage(self):
        while self._monitoring:
            # docker statsコマンドを使ってコンテナのメモリ使用量を取得する
            result = subprocess.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{.MemUsage}}",
                    self.containerInfo.containerID,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            # result.stdout = "1.23GiB / 2.00GiB"といった形式でメモリ使用量が取得できる
            # この値をパースしてmaxUsedMemoryを更新する
            if result.returncode == 0:
                mem_usage = result.stdout.strip()
                used_memory = self.__parse_memory_usage(mem_usage)
                if used_memory > self.maxUsedMemory:
                    self.maxUsedMemory = used_memory
                time.sleep(0.001) # 1ms待つ

    def __parse_memory_usage(self, mem_usage: str) -> int:
        # "1.23 GiB / 2.00 GiB" -> 1.23 -> 1.23 * 1024 * 1024 * 1024
        match = __MEM_USAGE_PATTERN.match(mem_usage)
        if match:
            # __MEM_USAGE_PATTERN.match("1.23 GiB / 2.00 GiB")
            # match.group(1) = "1.23"
            # match.group(2) = ".23"
            # match.group(3) = "Gi"
            value = float(match.group(1))
            unit = match.group(3)
            if unit == "Ki":
                return int(value * 1024)
            elif unit == "Mi":
                return int(value * 1024 * 1024)
            else:
                assert unit == "Gi"
                return int(value * 1024 * 1024 * 1024)
        return 0


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
    workDir: str  # コンテナ内での作業ディレクトリ
    # cgroupをいじるにはroot権限が必要なので、現状は使わない
    # cgroupParent: str  # cgroupの親ディレクトリ
    volumeMountInfo: list[VolumeMountInfo]  # ボリュームのマウント情報
    taskMonitor: TaskMonitor
