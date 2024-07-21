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
from dataclasses import dataclass, field
from dataclasses import replace
import time  # 実行時間の計測に使用
import re
from pathlib import Path
from typing import Callable
import logging

# 内部定義モジュールのインポート
from .my_error import Error

# ロガーの設定
logging.basicConfig(level=logging.INFO)
test_logger = logging.getLogger(__name__)


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

        test_logger.info(f"volumeName: {volumeName}")
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

    def copyFile(self, filePathFromClient: str, filePathInVolume: str) -> Error:
        ci = ContainerInfo("")

        err = ci.create(
            containerName="ubuntu",
            arguments=["echo", "Hello, World!"],
            workDir="/workdir/",
            volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=self)],
        )
        if err.message != "":
            return err

        dstInContainer = Path("/workdir") / Path(filePathInVolume)
        err = ci.copyFile(filePathFromClient, str(dstInContainer))

        ci.remove()
        return err

    def copyFiles(self, filePathsFromClient: list[str], DirPathInVolume: str) -> Error:
        ci = ContainerInfo("")

        err = ci.create(
            containerName="ubuntu",
            arguments=["echo", "Hello, World!"],
            workDir="/workdir/",
            volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=self)],
        )

        if err.message != "":
            return err

        for PathInClient in filePathsFromClient:
            dstInContainer = (
                Path("/workdir") / Path(DirPathInVolume) / Path(PathInClient).name
            ).resolve()
            err = ci.copyFile(PathInClient, str(dstInContainer))
            if err.message != "":
                return err

        ci.remove()
        return Error("")

    def removeFiles(self, filePathsInVolume: list[str]) -> Error:
        arguments = ["rm"]

        for filePath in filePathsInVolume:
            filePathInContainer = Path("/workdir") / Path(filePath)
            arguments += [str(filePathInContainer.resolve())]

        ci = ContainerInfo("")

        err = ci.create(
            containerName="ubuntu",
            arguments=arguments,
            workDir="/workdir/",
            volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=self)],
        )

        if err.message != "":
            return err

        result, err = ci.run()

        if err.message != "":
            return err

        if result.exitCode != 0:
            return Error(f"Failed to remove files: {result.stderr}")

        return Error("")


@dataclass
class VolumeMountInfo:
    path: str  # コンテナ内のマウント先のパス
    volume: Volume  # マウントするボリュームの情報


# Dockerコンテナの管理クラス
class ContainerInfo:
    containerID: str  # コンテナID

    def __init__(self, containerID: str):
        self.containerID = containerID

    # Dockerコンテナの作成
    def create(
        self,
        containerName: str,
        arguments: list[str],
        cpus: int = -1,
        memoryLimitMB: int = -1,
        stackLimitKB: int = -1,
        pidsLimit: int = -1,
        enableNetwork: bool = False,
        enableLoggingDriver: bool = True,
        workDir: str = "/workdir/",
        volumeMountInfo: list[VolumeMountInfo] = None,
    ) -> Error:
        # docker create ...
        args = ["create"]

        # enable interactive
        args += ["-i"]

        args += ["--init"]

        # CPUの割り当て数
        if cpus > 0:
            args += [f"--cpus={cpus}"]

        # メモリ制限
        if memoryLimitMB > 0:
            args += [f"--memory={memoryLimitMB}m"]
            args += [f"--memory-swap={memoryLimitMB}m"]

        # スタックサイズの制限
        if stackLimitKB > 0:
            args += ["--ulimit", f"stack={stackLimitKB}:{stackLimitKB}"]

        # プロセス数の制限
        if pidsLimit > 0:
            args += ["--pids-limit", str(pidsLimit)]

        # ネットワークの有効化
        if not enableNetwork:
            args += ["--network", "none"]

        # ロギングドライバの有効化
        if not enableLoggingDriver:
            args += ["--log-driver", "none"]

        # 作業ディレクトリ
        args += ["--workdir", workDir]

        for volumeMountInfo in volumeMountInfo:
            args += ["-v", f"{volumeMountInfo.volume.name}:{volumeMountInfo.path}"]

        # コンテナイメージ名
        args += [containerName]

        # コンテナ内で実行するコマンド
        args += arguments

        # Dockerコンテナの作成コマンド
        cmd = ["docker"] + args

        test_logger.info(f"docker create command: {cmd}")

        # Dockerコンテナの作成
        containerID = ""
        err = ""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            containerID = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            err = f"Failed to create container: {e}"

        test_logger.info(f'containerID: {containerID}, err: "{err}"')

        if err != "":
            return Error(err)

        self.containerID = containerID

        return Error("")

    def remove(self) -> Error:
        args = ["container", "rm", str(self.containerID)]

        cmd = ["docker"] + args

        err = ""

        test_logger.info(f"remove container command: {cmd}")

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

            test_logger.info(f"docker stats: {result.stdout}")

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
            Path("/sys-host/fs/cgroup/system.slice/")
            / f"docker-{self.containerInfo.containerID}.scope"
            / "memory.current"
        )
        while self._monitoring:
            try:
                if cgroup_path.exists():
                    with cgroup_path.open("r") as f:
                        mem_usage = int(f.read())
                        if mem_usage > self.maxUsedMemory:
                            self.maxUsedMemory = mem_usage
            except FileNotFoundError:
                # test_logger.info(f"Cgroup Path not exists: {cgroup_path}")
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
    timeout: int = 0  # タイムアウト時間
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
        containerInfo = ContainerInfo("")

        err = containerInfo.create(
            containerName=self.name,
            arguments=self.arguments,
            cpus=self.cpus,
            memoryLimitMB=self.memoryLimitMB,
            stackLimitKB=self.stackLimitKB,
            pidsLimit=self.pidsLimit,
            enableNetwork=self.enableNetwork,
            enableLoggingDriver=self.enableLoggingDriver,
            workDir=self.workDir,
            volumeMountInfo=self.volumeMountInfo,
        )

        # Dockerコンテナの作成
        test_logger.info(
            f'containerID: {containerInfo.containerID}, err: "{err.message}"'
        )

        if err.message != "":
            return ContainerInfo(""), err

        # モニターにコンテナ情報を設定
        self.taskMonitor.containerInfo = containerInfo

        return containerInfo, Error("")

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

        test_logger.info(f"docker start command: {cmd}")

        # self.timeout + 500msの制限時間を設定
        timeout = 30.0  # デフォルトは30秒
        if self.timeout != 0:
            timeout = self.timeout + 0.5

        # モニターを開始
        self.taskMonitor.start()

        # Dockerコンテナの起動
        TLE = False
        try:
            ProcessResult = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=self.Stdin,
                check=False,
            )
        except subprocess.TimeoutExpired:
            # タイムアウトした場合
            # モニターを終了(これをしないとtaskMonitorのスレッドが終了しない)
            self.taskMonitor.end()

            # まだ実行中の場合があるので、docker stop...で停止させる。
            stop_cmd = ["docker", "stop", containerInfo.containerID]
            test_logger.info(stop_cmd)
            resultForStop = subprocess.run(stop_cmd, check=False)
            if resultForStop.returncode != 0:
                message = f"failed to stop docker: {containerInfo.containerID}"
                test_logger.info(message)
                return TaskResult(
                    TLE=True,
                    timeMS=int(self.taskMonitor.get_elapsed_time_ms()),
                    memoryByte=self.taskMonitor.get_used_memory_byte(),
                ), Error(message)
            # 戻り値を検出
            exit_code, err = inspectExitCode(containerId=containerInfo.containerID)
            if err.message != "":
                return (
                    TaskResult(
                        TLE=True,
                        timeMS=int(self.taskMonitor.get_elapsed_time_ms()),
                        memoryByte=self.taskMonitor.get_used_memory_byte(),
                    ),
                    err,
                )
            return TaskResult(
                exitCode=exit_code,
                TLE=True,
                timeMS=int(self.taskMonitor.get_elapsed_time_ms()),
                memoryByte=self.taskMonitor.get_used_memory_byte(),
            ), Error("")

        test_logger.info(ProcessResult)

        # モニターを終了
        self.taskMonitor.end()

        self.Stdout = ProcessResult.stdout
        self.Stderr = ProcessResult.stderr

        # タイムアウトしたかどうか
        if (
            self.timeout != 0
            and self.timeout < self.taskMonitor.get_elapsed_time_ms() / 1000
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
        test_logger.info(
            f'containerID: {containerInfo.containerID}, err: "{err.message}"'
        )
        if err.message != "":
            # コンテナの作成に失敗した場合
            return TaskResult(), err
        test_logger.info(f"containerID: {containerInfo.containerID}")

        test_logger.info("start container")
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

    test_logger.info(f"inspect exit code: {result}")

    err = ""
    if result.returncode != 0:
        err = f"Failed to inspect exit code: {result.stderr}"
        return -1, Error(err)

    return int(result.stdout), Error(err)
