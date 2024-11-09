from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./database.db"

# SQLAlchemy base class
Base = declarative_base()

# Define the User model
class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(String(50), primary_key=True, index=True)
    username = Column(String(100))
    mail = Column(String(100))
    coins = Column(Integer)
    phone_number = Column(String(15))
    api_token = Column(Text)
    discount = Column(Integer)
    link_app = Column(String(100))
    phone_id = Column(String(50))
    waba_id = Column(String(50))

# Create a sessionmaker for the database
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the database tables
Base.metadata.create_all(bind=engine)
