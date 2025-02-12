from sqlalchemy import Column, Index, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship, declarative_base
from geoalchemy2 import Geometry

Base = declarative_base()

organization_activity_table = Table(
    "organization_activity",
    Base.metadata,
    Column(
        "organization_id", Integer, ForeignKey("organizations.id"), primary_key=True
    ),
    Column("activity_id", Integer, ForeignKey("activities.id"), primary_key=True),
)


class Building(Base):
    __tablename__ = "buildings"
    id = Column(Integer, primary_key=True)
    address = Column(String)
    coordinates = Column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True))
    organizations = relationship("Organization", back_populates="building")


class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True)
    activity_name = Column(String)
    parent_id = Column(Integer, ForeignKey("activities.id"), nullable=True)
    level = Column(Integer)

    parent = relationship("Activity", back_populates="children", remote_side=[id])
    children = relationship("Activity", back_populates="parent")

    organizations = relationship(
        "Organization",
        secondary=organization_activity_table,
        back_populates="activities",
    )

    __table_args__ = (Index("idx_activity_level_parent", "level", "parent_id"),)


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True)
    company_name = Column(String)
    building_id = Column(Integer, ForeignKey("buildings.id"), index=True)
    building = relationship("Building", back_populates="organizations")
    phones = relationship(
        "OrganizationPhone", back_populates="organization", cascade="all, delete-orphan"
    )
    activities = relationship(
        "Activity",
        secondary=organization_activity_table,
        back_populates="organizations",
    )


class OrganizationPhone(Base):
    __tablename__ = "organization_phone"
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    phone_number = Column(String, nullable=False)

    organization = relationship("Organization", back_populates="phones")
