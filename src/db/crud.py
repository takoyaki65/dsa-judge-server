# Create, Read, Update and Delete (CRUD)
from sqlalchemy.orm import Session

from . import models

def fetch_task_by_id(db: Session, task_id: int) -> models.Task | None:
    return db.query(models.Task).filter(models.Task.id == task_id).first()

def fetch_pending_task_and_update_to_processing(db: Session, limit: int = 1) -> list[models.Task]:
    # 他のワーカが同じタスクを取得しないように、with_for_update()を使ってロックをかける
    task = db.query(models.Task).filter(models.Task.status == 'pending').limit(limit).with_for_update().all()
    for t in task:
        t.status = 'processing'
    db.commit()
    return task

def mark_task_as_done(db: Session, task_id: int) -> None:
    task = db.query(models.Task).filter(models.Task.id == task_id).one()
    if task is None:
        return
    task.status = 'done'
    db.commit()

def submit_task(db: Session, path_to_dir: str) -> models.Task:
    task = models.Task(path_to_dir=path_to_dir)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def delete_task_by_id(db: Session, task_id: int) -> None:
    task_to_delete = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task_to_delete is None:
        return
    db.delete(task_to_delete)
    db.commit()
