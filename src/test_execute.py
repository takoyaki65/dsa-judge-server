import pytest
import dsa_judge_server
import logging

# ロガーの設定
logging.basicConfig(level=logging.INFO)
test_logger = logging.getLogger(__name__)

def test_RunHelloWorld():
    task = dsa_judge_server.execute.TaskInfo("ubuntu", ["echo", "Hello, World!"])

    result, err = task.run()

    test_logger.info(result)
    test_logger.info(err)

    assert err.message == ""

    assert result.exitCode == 0

    assert result.stdout == "Hello, World!\n"

    assert result.stderr == ""
