"""
このプログラムでは、以下のような機能を実装する。
* Dockerボリュームの作成と削除を行うボリューム管理クラスVolume
* Dockerコンテナの作成と削除を行うコンテナ管理クラスContainerInfo
* タスクの実行を行うタスク管理クラスTaskInfo
* タスクの実行結果を格納するクラスTaskResult
"""

# 外部定義モジュールのインポート
import uuid
import subprocess
import threading
from datetime import timedelta
from dataclasses import dataclass, field
from dataclasses import replace
import time  # 実行時間の計測に使用
import re
from pathlib import Path
from typing import Callable

# 内部定義モジュールのインポート
from .my_error import Error


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

    def copyFile(self, srcInHost: str, dstInVolume: str) -> Error:
        task = TaskInfo(
            name="ubuntu",
            volumeMountInfo=[VolumeMountInfo(path="/workdir", volume=self)],
        )
        ci, err = task.__create()
        if err.message != "":
            return err

        dstInContainer = Path("/workdir") / Path(dstInVolume)
        err = ci.copyFile(srcInHost, str(dstInContainer))

        ci.remove()
        return err


# Dockerコンテナの管理クラス
class ContainerInfo:
    containerID: str  # コンテナID

    def __init__(self, containerID: str):
        self.containerID = containerID

    def remove(self) -> Error:
        args = ["container", "rm", str(self.containerID)]

        cmd = ["docker"] + args

        err = ""

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            err = f"Failed to remove container: {e}"

        return Error(err)

    # ファイルのコピー
    def copyFile(self, srcInHost: str, dstInContainer: str) -> Error:
        args = ["cp", srcInHost, f"{self.containerID}:{dstInContainer}"]

        cmd = ["docker"] + args

        err = ""

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            err = f"Failed to copy file: {e}"

        return Error(err)


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
        # TODO: docker statsは遅いので、/sys/fs/cgroupからメモリ使用量を取得する方法を検討する
        self._monitor_thread = threading.Thread(
            target=self.__monitor_memory_usage_by_cgroup
        )
        self._monitor_thread.start()

    def end(self):
        self.endTime = time.time_ns()
        self._monitoring = False
        self._monitor_thread.join()

    def get_elapsed_time_ms(self) -> float:
        return (self.endTime - self.startTime) / 1e6

    def get_used_memory_byte(self) -> int:
        return self.maxUsedMemory

    def __monitor_memory_usage_by_docker_stats(self) -> None:
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
                used_memory = self.__parse_memory_usage_docker_stats(mem_usage)
                if used_memory > self.maxUsedMemory:
                    self.maxUsedMemory = used_memory
                time.sleep(0.001)  # 1ms待つ

    def __parse_memory_usage_docker_stats(self, mem_usage: str) -> int:
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

    def __monitor_memory_usage_by_cgroup(self) -> None:
        # /sys/fs/cgroup/system.slice/docker-xxxxxx.scope/memory.current
        # からメモリ使用量をバイト単位で取得する
        cgroup_path = (
            Path("/sys/fs/cgroup/system.slice/")
            / f"docker-{self.containerInfo.containerID}.scope"
            / "memory.current"
        )
        while self._monitoring:
            try:
                with cgroup_path.open("r") as f:
                    mem_usage = int(f.read())
                    if mem_usage > self.maxUsedMemory:
                        self.maxUsedMemory = mem_usage
            except FileNotFoundError:
                pass
            time.sleep(0.001)


@dataclass
class TaskResult:
    exitCode: int = -1
    stdout: str = ""
    stderr: str = ""
    timeMS: int = -1
    memoryByte: int = -1
    TLE: bool = True  # 制限時間を超えたかどうか


# タスクの実行情報
@dataclass
class TaskInfo:
    name: str  # コンテナイメージ名
    arguments: list[str] = field(default_factory=list)  # コンテナ内で実行するコマンド
    timeout: timedelta = timedelta(0)  # タイムアウト時間
    cpus: int = 0  # CPUの割り当て数
    memoryLimitMB: int = 0  # メモリ制限
    stackLimitKB: int = 0  # リカージョンの深さを制限
    pidsLimit: int = 0  # プロセス数の制限
    enableNetwork: bool = False
    enableLoggingDriver: bool = True
    workDir: str = "/workdir/"  # コンテナ内での作業ディレクトリ
    # cgroupをいじるにはroot権限が必要なので、現状は使わない
    # cgroupParent: str  # cgroupの親ディレクトリ
    volumeMountInfo: list[VolumeMountInfo] = field(
        default_factory=list
    )  # ボリュームのマウント情報
    taskMonitor: TaskMonitor = field(
        default_factory=lambda: TaskMonitor(ContainerInfo(""))
    )

    Stdin: str = ""  # 標準入力
    Stdout: str = ""  # 標準出力
    Stderr: str = ""  # 標準エラー出力

    # Dockerコンテナの作成
    def __create(self) -> tuple[ContainerInfo, Error]:
        # docker create ...
        args = ["create"]

        # enable interactive
        args += ["-i"]

        args += ["--init"]

        # CPUの割り当て数
        if self.cpus > 0:
            args += [f"--cpus={self.cpus}"]

        # メモリ制限
        if self.memoryLimitMB > 0:
            args += [f"--memory={self.memoryLimitMB}m"]
            args += [f"--memory-swap={self.memoryLimitMB}m"]

        # スタックサイズの制限
        if self.stackLimitKB > 0:
            args += ["--ulimit", f"stack={self.stackLimitKB}:{self.stackLimitKB}"]

        # プロセス数の制限
        if self.pidsLimit > 0:
            args += ["--pids-limit", str(self.pidsLimit)]

        # ネットワークの有効化
        if not self.enableNetwork:
            args += ["--network", "none"]

        # ロギングドライバの有効化
        if not self.enableLoggingDriver:
            args += ["--log-driver", "none"]

        # 作業ディレクトリ
        args += ["--workdir", self.workDir]

        for volumeMountInfo in self.volumeMountInfo:
            args += ["-v", f"{volumeMountInfo.volume.name}:{volumeMountInfo.path}"]

        # コンテナイメージ名
        args += [self.name]

        # コンテナ内で実行するコマンド
        args += self.arguments

        # Dockerコンテナの作成コマンド
        cmd = ["docker"] + args

        # Dockerコンテナの作成
        containerID = ""
        err = ""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            containerID = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            err = f"Failed to create container: {e}"

        if err != "":
            return ContainerInfo(""), Error(err)

        # モニターにコンテナ情報を設定
        self.taskMonitor.containerInfo = ContainerInfo(containerID)

        return ContainerInfo(containerID), Error("")

    # docker start ... を実行して、コンテナを起動する。
    # これにより、docker createで指定したコマンド(コンパイル、プログラムの実行等)が実行される。
    def __start(self, containerInfo: ContainerInfo) -> tuple[TaskResult, Error]:
        # docker start
        args = ["start"]

        # enable interactive
        args += ["-i"]

        # コンテナID
        args += [containerInfo.containerID]

        # Dockerコンテナの起動コマンド
        cmd = ["docker"] + args

        # self.timeout + 500msの制限時間を設定
        timeout = 100.0  # デフォルトは100秒
        if self.timeout != timedelta(0):
            timeout = self.timeout.total_seconds() + 0.5

        # モニターを開始
        self.taskMonitor.start()

        # Dockerコンテナの起動
        ProcessResult = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=self.Stdin,
            check=False,
        )

        # モニターを終了
        self.taskMonitor.end()

        self.Stdout = ProcessResult.stdout
        self.Stderr = ProcessResult.stderr

        # タイムアウトしたかどうか
        TLE = False
        if (
            self.timeout != timedelta(0)
            and self.timeout.total_seconds()
            < self.taskMonitor.get_elapsed_time_ms() / 1000
        ):
            TLE = True

        exit_code, err = inspectExitCode(containerId=containerInfo.containerID)
        if err.message != "":
            return TaskResult(), err

        return TaskResult(
            exitCode=exit_code,
            stdout=self.Stdout,
            stderr=self.Stderr,
            timeMS=int(self.taskMonitor.get_elapsed_time_ms()),
            memoryByte=self.taskMonitor.get_used_memory_byte(),
            TLE=TLE,
        ), Error("")

    def run(self) -> tuple[TaskResult, Error]:
        # コンテナ作成から起動までの処理を行う
        # 途中で失敗したら、作成したコンテナの削除を行い、エラーを返す
        containerInfo, err = self.__create()
        if err.message != "":
            # コンテナの作成に失敗した場合
            return TaskResult(), err

        result, err = self.__start(containerInfo)

        # コンテナの削除
        err2 = containerInfo.remove()
        if err2.message != "":
            err.message += "\n" + err2.message

        return result, err


def inspectExitCode(containerId: str) -> tuple[int, Error]:
    args = ["inspect", "--format={{.State.ExitCode}}", containerId]

    cmd = ["docker"] + args

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    err = ""
    if result.returncode != 0:
        err = f"Failed to inspect exit code: {result.stderr}"
        return -1, Error(err)

    return int(result.stdout), Error(err)
