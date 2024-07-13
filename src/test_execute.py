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

# ファイルをDockerボリュームにコピーするテスト
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

# Dockerコンテナのmysqlサーバーにあるtaskテーブルを操作するテスト
def test_InsertTaskTable():
    try:
        db = SessionLocal()

        # 試しにデータを追加
        task = submit_task(db, "/workdir/")

        test_logger.info(task)

        # データが追加されたことを確認
        inserted_task = fetch_task_by_id(db, task.id)

        assert inserted_task is not None

        assert inserted_task.path_to_dir == "/workdir/"

        assert inserted_task.status == "pending"

        assert inserted_task.ts == task.ts

        # データを削除
        delete_task_by_id(db, task.id)

        # データが削除されたことを確認
        deleted_task = fetch_task_by_id(db, task.id)

        assert deleted_task is None

        db.close()
    
    except Exception as e:
        test_logger.error(e)
        assert False

