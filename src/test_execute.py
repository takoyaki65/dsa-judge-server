# テストプログラム実行方法
# $ cd src
# $ pytest --log-cli-level=INFO test_execute.py
import pytest
import sandbox_execution
from sandbox_execution.execute import TaskInfo
from sandbox_execution.execute import Volume
from sandbox_execution.execute import VolumeMountInfo
import logging
from datetime import timedelta
from tempfile import TemporaryDirectory
from pathlib import Path

# ロガーの設定
logging.basicConfig(level=logging.INFO)
test_logger = logging.getLogger(__name__)


def test_RunHelloWorld():
    task = TaskInfo(
        name="ubuntu", arguments=["echo", "Hello, World!"],
        timeout=timedelta(seconds=5),
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


def test_CopyFileFromHostToVolume():
    # ファイル転送先のボリュームの作成
    volume, err = Volume.create()

    assert err.message == ""

    # tempdir にファイルを作成
    with TemporaryDirectory() as tempdir:
        with open(Path(tempdir) / "test.txt", "w") as f:
            f.write("Hello, World!")
        
        # ファイルをボリュームにコピー
        volume.copyFile(str(Path(tempdir) / "test.txt"), "test.txt") 

    # ファイルがコピーされたことを確認
    task = TaskInfo(
        name="ubuntu", arguments=["cat", "test.txt"],
        workDir="/workdir/",
        volumeMountInfo=[
            VolumeMountInfo(
                path="/workdir/",
                volume=volume
            )
        ]
    )

    result, err = task.run()

    test_logger.info(result)

    assert err.message == ""

    assert result.exitCode == 0

    assert result.stdout == "Hello, World!"

    assert result.stderr == ""

    err = volume.remove()

    assert err.message == ""


