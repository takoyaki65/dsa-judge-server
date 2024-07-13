from sqlalchemy import Column, Integer, String, TIMESTAMP, Enum, text
from sqlalchemy.orm import relationship

from .database import Base

class Task(Base):
    __tablename__ = 'task'
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    path_to_dir = Column(String(255), nullable=False)
    status = Column(Enum('pending', 'processing', 'done', 'error'), default='pending')
