from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    status = Column(String) # 'ready', 'drafting', 'review', 'finalized', 'archived'
    progress = Column(Integer, default=0) # 0-100
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OBSGrade(Base):
    __tablename__ = "obs_grades"

    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String, index=True)
    course_name = Column(String)
    vize = Column(String)
    final = Column(String)
    average = Column(String)
    letter_grade = Column(String)
    student_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OBSAttendance(Base):
    __tablename__ = "obs_attendance"

    id = Column(Integer, primary_key=True, index=True)
    course_name = Column(String)
    teorik_devamsizlik = Column(String)
    uygulama_devamsizlik = Column(String)
    status = Column(String)
    student_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
