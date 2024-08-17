# テストプログラム実行方法
# $ cd src
# $ pytest --log-cli-level=INFO test_execute.py
import pytest
import sandbox
from sandbox.execute import TaskInfo
from sandbox.execute import Volume
from sandbox.execute import VolumeMountInfo
import logging
from datetime import timedelta
from tempfile import TemporaryDirectory
from pathlib import Path

from db.crud import *
from db.database import SessionLocal

# ロガーの設定
logging.basicConfig(level=logging.INFO)
test_logger = logging.getLogger(__name__)


# Dockerコンテナを起動して、Hello, World!を出力するテスト
def test_RunHelloWorld():
    task = TaskInfo(
        name="ubuntu",
        arguments=["echo", "Hello, World!"],
        timeout=5,
        memoryLimitMB=256,
        cpus=1,
    )

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert err.message == ""

    assert result.exitCode == 0

    assert result.stdout == "Hello, World!\n"

    assert result.stderr == ""


# sandboxの戻り値をきちんとチェックできているか確かめるテスト
def test_ExitCode():
    task = TaskInfo(
        name="ubuntu",
        arguments=["sh", "-c", "exit 123"],
        timeout=5,
        memoryLimitMB=256,
        cpus=1,
    )

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert err.message == ""
    assert result.exitCode == 123
    assert result.stdout == ""
    assert result.stderr == ""


# 標準入力をきちんと受け取れているか確かめるテスト
def test_Stdin():
    task = TaskInfo(
        name="ubuntu",
        arguments=["sh", "-c", "read input; test $input = dummy"],
        Stdin="dummy",
    )

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert err.message == ""
    assert result.exitCode == 0
    assert result.stdout == ""
    assert result.stderr == ""


# 標準出力をきちんとキャプチャできているか確かめるテスト
def test_Stdout():
    task = TaskInfo(name="ubuntu", arguments=["echo", "dummy"])

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert err.message == ""
    assert result.exitCode == 0
    assert result.stdout == "dummy\n"
    assert result.stderr == ""


# 標準エラー出力をちゃんとキャプチャできているか確かめるテスト
def test_Stderr():
    task = TaskInfo(name="ubuntu", arguments=["sh", "-c", "echo dummy >&2"])

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert err.message == ""
    assert result.exitCode == 0
    assert result.stdout == ""
    assert result.stderr == "dummy\n"


# sleepした分ちゃんと実行時間が計測されているか確かめるテスト
def test_SleepTime():
    task = TaskInfo(name="ubuntu", arguments=["sleep", "3"], timeout=5)

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert err.message == ""
    assert result.exitCode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.timeMS >= 2000 and result.timeMS <= 5000


# タイムアウトをきちんと検出できているか確かめるテスト
def test_Timeout():
    task = TaskInfo(name="ubuntu", arguments=["sleep", "100"], timeout=3)

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert err.message == ""
    assert result.TLE == True


# ファイルをDockerボリュームにコピーするテスト
def test_CopyFileFromClientToVolume():
    # ファイル転送先のボリュームの作成
    volume, err = Volume.create()

    assert err.message == ""

    # tempdir にファイルを作成
    with TemporaryDirectory() as tempdir:
        with open(Path(tempdir) / "test.txt", "w") as f:
            f.write("Hello, World!")

        # ファイルをボリュームにコピー
        volume.copyFile(Path(tempdir) / "test.txt", Path("test.txt"))

    # ファイルがコピーされたことを確認
    task = TaskInfo(
        name="ubuntu",
        arguments=["cat", "test.txt"],
        workDir="/workdir/",
        volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=volume)],
    )

    result, err = task.run()

    test_logger.info(result)

    assert err.message == ""

    assert result.exitCode == 0

    assert result.stdout == "Hello, World!"

    assert result.stderr == ""

    err = volume.remove()

    assert err.message == ""


# 複数のファイルをDockerボリュームにコピーするテスト
def test_CopyFilesFromClientToVolume():
    # ファイル転送先のボリュームの作成
    volume, err = Volume.create()

    assert err.message == ""

    # tempdir にファイルを作成
    with TemporaryDirectory() as tempdir:
        with open(Path(tempdir) / "test1.txt", "w") as f:
            f.write("Hello, World!")

        with open(Path(tempdir) / "test2.txt", "w") as f:
            f.write("Goodbye, World!")

        # ファイルをボリュームにコピー
        volume.copyFiles(
            filePathsFromClient=[
                Path(tempdir) / "test1.txt",
                Path(tempdir) / "test2.txt",
            ],
            DirPathInVolume=Path("./"),
        )

    # ファイルがコピーされたことを確認
    task = TaskInfo(
        name="ubuntu",
        arguments=["cat", "test1.txt", "test2.txt"],
        workDir="/workdir/",
        volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=volume)],
    )

    result, err = task.run()

    test_logger.info(result)

    assert err.message == ""

    assert result.exitCode == 0

    assert result.stdout == "Hello, World!Goodbye, World!"

    assert result.stderr == ""

    err = volume.remove()

    assert err.message == ""


# Dockerボリュームにある複数のファイルを削除するテスト
def test_RemoveFilesInVolume():
    # ファイル転送先のボリュームの作成
    volume, err = Volume.create()

    assert err.message == ""

    # tempdir にファイルを作成
    with TemporaryDirectory() as tempdir:
        with open(Path(tempdir) / "test1.txt", "w") as f:
            f.write("Hello, World!")

        with open(Path(tempdir) / "test2.txt", "w") as f:
            f.write("Goodbye, World!")

        # ファイルをボリュームにコピー
        volume.copyFiles(
            filePathsFromClient=[
                Path(tempdir) / "test1.txt",
                Path(tempdir) / "test2.txt",
            ],
            DirPathInVolume=Path("./"),
        )

    # ファイルがコピーされたことを確認
    task = TaskInfo(
        name="ubuntu",
        arguments=["ls"],
        workDir="/workdir/",
        volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=volume)],
    )

    result, err = task.run()

    test_logger.info(result)

    assert err.message == ""

    assert result.exitCode == 0

    assert result.stdout == "test1.txt\ntest2.txt\n"

    assert result.stderr == ""

    # ファイルを削除
    volume.removeFiles([Path("test1.txt"), Path("test2.txt")])

    # ファイルが削除されたことを確認
    task = TaskInfo(
        name="ubuntu",
        arguments=["ls"],
        workDir="/workdir/",
        volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=volume)],
    )

    result, err = task.run()

    test_logger.info(result)

    assert err.message == ""

    assert result.exitCode == 0

    assert result.stdout == ""

    assert result.stderr == ""

    err = volume.remove()

    test_logger.info(err)

    assert err.message == ""


# メモリ制限を検出できるかチェック
def test_MemoryLimit():
    task = TaskInfo(
        name="ubuntu",
        arguments=["dd", "if=/dev/zero", "of=/dev/null", "bs=800M"],
        timeout=3,
        memoryLimitMB=500,
    )

    result, err = task.run()

    assert err.message == ""

    test_logger.info(result)

    assert result.exitCode != 0
    # assert result.TLE == False
    assert abs(result.memoryByte - 500 * 1024 * 1024) < 1024 * 1024


# ネットワーク制限をできているかチェック
def test_NetworkDisable():
    task = TaskInfo(
        name="ibmcom/ping",
        arguments=["ping", "-c", "5", "google.com"],
        enableNetwork=None,
    )

    result, err = task.run()

    assert err.message == ""

    test_logger.info(result)

    assert result.exitCode != 0
    assert result.TLE == False
    assert result.stdout == ""


# フォークボムなどの攻撃に対処できるように、プロセス数制限ができているかチェック
def test_ForkBomb():
    volume, err = Volume.create()

    assert err.message == ""

    err = volume.copyFile(Path("sources/fork_bomb.sh"), Path("fork_bomb.sh"))

    assert err.message == ""

    task = TaskInfo(
        name="ubuntu",
        arguments=["./fork_bomb.sh"],
        workDir="/workdir/",
        volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=volume)],
        timeout=3,
        pidsLimit=10,
    )

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    err = volume.remove()

    assert err.message == ""


# スタックメモリの制限ができているかチェック
def test_UseManyStack():
    volume, err = Volume.create()

    assert err.message == ""

    err = volume.copyFile(Path("sources/use_many_stack.cpp"), Path("use_many_stack.cpp"))

    assert err.message == ""

    task = TaskInfo(
        name="gcc:13.3",
        arguments=["g++", "use_many_stack.cpp"],
        workDir="/workdir/",
        volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=volume)],
    )

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert err.message == ""
    assert result.exitCode == 0

    task = TaskInfo(
        name="gcc:13.3",
        arguments=["./a.out"],
        workDir="/workdir/",
        volumeMountInfo=[VolumeMountInfo(path="/workdir/", volume=volume)],
        stackLimitKB=10240,
        memoryLimitMB=256,
    )

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert result.exitCode != 0

    err = volume.remove()

    assert err.message == ""


# # Dockerコンテナのmysqlサーバーにあるtaskテーブルを操作するテスト
# def test_InsertTaskTable():
#     try:
#         db = SessionLocal()

#         # 試しにデータを追加
#         task = submit_task(db, "/workdir/")

#         test_logger.info(task)

#         # データが追加されたことを確認
#         inserted_task = fetch_task_by_id(db, task.id)

#         assert inserted_task is not None

#         assert inserted_task.path_to_dir == "/workdir/"

#         assert inserted_task.status == "pending"

#         assert inserted_task.ts == task.ts

#         # データを削除
#         delete_task_by_id(db, task.id)

#         # データが削除されたことを確認
#         deleted_task = fetch_task_by_id(db, task.id)

#         assert deleted_task is None

#         db.close()

#     except Exception as e:
#         test_logger.error(e)
#         assert False
