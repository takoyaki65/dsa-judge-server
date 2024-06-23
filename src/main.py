from fastapi import FastAPI, HTTPException, UploadFile, File
import subprocess
import os
import zipfile
from pydantic import BaseModel
import docker
import uuid
import yaml

app = FastAPI()

# Dockerクライアントの設定
client = docker.DockerClient(base_url="unix:///var/run/docker.sock")

class Volume(BaseModel):
    Name: str # ボリューム名

class VolumeMountInfo(BaseModel):
    Path: str # ホストのパス
    Volume: Volume # ボリューム情報

class TaskInfo(BaseModel):
    Name: str # コンテナ名 e.g. ubuntu
    Argments: list[str] # docker createに渡す追加の引数
    Timeout: int # タイムアウト時間[ms]
    Cpuset: int # CPUの割り当て
    MemoryLimitMB: int # メモリの割り当て[MB]
    StackLimitKB: int # スタックの割り当て[KB], -1で無制限
    PidsLimit: int # プロセス数の制限
    EnableNetwork: bool # ネットワークの有効化
    EnableLoggingDriver: bool # ロギングドライバの有効化
    WorkDir: str # 作業ディレクトリ
    cgroupParent: str # cgroupの親ディレクトリ

class Task(BaseModel):
    container_name: str
    task_info: dict
    result: dict


# associative array of Task objects
tasks: dict[str, Task] = {}


@app.post("/task")
async def create_task(task: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    task_path = f"/tmp/{task_id}"
    os.makedirs(task_path, exist_ok=True)

    # ファイルの保存
    with open(f"{task_path}/{task.filename}", "wb") as buffer:
        buffer.write(await task.read())

    # zipファイルの解凍
    with zipfile.ZipFile(f"{task_path}/{task.filename}", "r") as zip_ref:
        zip_ref.extractall(task_path)

    # Dockerコンテナの作成と起動
    container_name = f"dsa_sandbox_{task_id}"
    command = f"docker run --name {container_name} -v {task_path}:/app -d dsa_sandbox"
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="Failed to create container")

    # task.yamlの読み込み
    with open(f"{task_path}/task.yaml", "r", encoding="utf8") as file:
        task_info = yaml.safe_load(file)

    tasks[task_id] = Task(container_name=container_name, task_info=task_info, result={})

    return {"task_id": task_id}


@app.get("task/{task_id}")
def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    container_id = tasks[task_id]
    container = client.containers.get(container_id)
    return {"status": container.status, "logs": container.logs().decode("utf-8")}
