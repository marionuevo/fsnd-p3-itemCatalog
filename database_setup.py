"""This file creates and setups the required database."""
# imprt section
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()


# Define the users table.
class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    email = Column(String(80), nullable=False)
    picture = Column(String(250))


# Define the styles table.
class Style(Base):
    __tablename__ = 'style'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        """Return object data in easily serializeable format."""
        return {
            'name': self.name,
            'id': self.id
        }


# Define the models table.
class Model(Base):
    __tablename__ = 'model'

    name = Column(String(80), nullable=False)
    id = Column(Integer, primary_key=True)
    description = Column(String(1024))
    price = Column(String(8))
    power = Column(String(250))
    image = Column(String(512))
    style_id = Column(Integer, ForeignKey('style.id'))
    style = relationship(Style)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        """Return object data in easily serializeable format."""
        return {
            'name': self.name,
            'description': self.description,
            'id': self.id,
            'price': self.price,
            'power': self.power
        }


engine = create_engine('postgresql://catalog:logcata@localhost/')

Base.metadata.create_all(engine)
