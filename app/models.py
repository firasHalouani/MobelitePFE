from sqlalchemy import Column, Integer, String
from app.database import Base

class Vulnerability(Base):
    __tablename__ = "vulnerabilities"

    id = Column(Integer, primary_key=True)
    pattern = Column(String)
    severity = Column(String)
    count = Column(Integer)
    recommendation = Column(String, nullable=True)
