from datetime import datetime, timezone
from db.connect import Base
from sqlalchemy import Column, DateTime, Table, ForeignKey, Integer, String, UniqueConstraint, BigInteger,Date
from sqlalchemy.orm import relationship

# промежуточная таблица для связей
registration_table = Table('registrations',
                           Base.metadata,
                           Column('user_id', Integer, ForeignKey('users.id')),
                           Column('lesson_id', Integer, ForeignKey('lessons.id')))

class User(Base):
  __tablename__ = 'users'

  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String, nullable=False)
  user_id = Column(BigInteger, nullable=False)#unique=True если захотим сделать уникальным


  # Используем lambda, чтобы дата вычислялась при создании каждого объекта:
  created_at = Column(
      DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
  )
  lessons = relationship('Lesson', secondary=registration_table, back_populates='users')
class Lesson(Base):
  __tablename__ = 'lessons'

  id = Column(Integer, primary_key=True)
  date = Column(Date, nullable=False)
  title = Column(String, nullable=False)
  link = Column(String, nullable=True) # ссылка на урок
  spots = Column(Integer, nullable=False)
  created_at = Column(
    DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
  )
  users = relationship('User',secondary=registration_table, back_populates='lessons')



