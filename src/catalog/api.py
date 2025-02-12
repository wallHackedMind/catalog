from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload, selectinload
from geoalchemy2 import functions as geofunc
from geoalchemy2.types import Geography

from catalog.utils import generate_test_data
from catalog import models
from catalog.scheme import OrganizationOut
from session import get_db
from auth import check_api_key


router = APIRouter(tags=["catalog API"], dependencies=[Depends(check_api_key)])


@router.get(
    "/activities/{activity_name}/organizations",
    response_model=list[OrganizationOut],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Invalid API Key"},
    },
)
async def get_organizations_by_activity(
    activity_name: str,
    level: int = Query(default=2, description="Уровень вложенности начиная с 0."),
    db: AsyncSession = Depends(get_db),
):
    """
    Список всех организаций, относящихся к указанному виду деятельности (включая вложенные).

    **Принцип работы параметра `level`:**

    - `0` – Фильтрует только по основной категории (например, "Еда").
    - `1` – Включает подкатегории первого уровня ("Мясная продукция", "Молочная продукция").
    - `2` – Добавляет более детализированные категории ("говядина", "сыр" и т. д.).
    """
    base = select(models.Activity.id, literal(0).label("level")).filter(
        models.Activity.activity_name == activity_name
    )

    act_cte = base.cte(recursive=True, name="activity_tree")

    child_alias = aliased(models.Activity, name="child")
    parent_alias = aliased(act_cte, name="parent")

    recursive_part = select(
        child_alias.id, (parent_alias.c.level + 1).label("level")
    ).filter(child_alias.parent_id == parent_alias.c.id, parent_alias.c.level < level)
    act_cte = act_cte.union_all(recursive_part)

    q = (
        select(models.Organization)
        .join(
            models.organization_activity_table,
            models.Organization.id
            == models.organization_activity_table.c.organization_id,
        )
        .join(act_cte, models.organization_activity_table.c.activity_id == act_cte.c.id)
        .options(
            selectinload(models.Organization.phones),
            selectinload(models.Organization.activities),
            joinedload(models.Organization.building),
        )
        .distinct()
    )

    result = await db.scalars(q)
    return result.all()


@router.get(
    "/organizations",
    response_model=list[OrganizationOut],
    description="Поиск организаций по названию или виду деятельности",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Invalid API Key"},
    },
)
async def search_organizations(
    name: Optional[str] = Query(None, description="Название организации"),
    activity_name: Optional[str] = Query(
        None, description="Название активности организации"
    ),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(models.Organization)
        .options(
            selectinload(models.Organization.phones),
            selectinload(models.Organization.activities),
            joinedload(models.Organization.building),
        )
        .distinct()
    )

    if name:
        q = q.filter(models.Organization.company_name.ilike(name))

    if activity_name:
        q = (
            q.join(
                models.organization_activity_table,
                models.Organization.id
                == models.organization_activity_table.c.organization_id,
            )
            .join(
                models.Activity,
                models.organization_activity_table.c.activity_id == models.Activity.id,
            )
            .filter(models.Activity.activity_name.ilike(activity_name))
        )

    organizations = await db.scalars(q)
    return organizations.all()


@router.get(
    "/buildings/{building_id}/organizations",
    response_model=list[OrganizationOut],
    description="получить список всех организаций находящихся в конкретном	здании",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Invalid API Key"},
    },
)
async def get_organizations_by_building(
    building_id: int, db: AsyncSession = Depends(get_db)
):

    q = (
        select(models.Organization)
        .filter_by(building_id=building_id)
        .options(
            selectinload(models.Organization.phones),
            selectinload(models.Organization.activities),
            joinedload(models.Organization.building),
        )
    )
    res = await db.scalars(q)
    return res.all()


@router.get(
    "/organizations/{organization_id}",
    response_model=OrganizationOut,
    description="получить организацию по её идентификатору",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Invalid API Key"},
        status.HTTP_404_NOT_FOUND: {"description": "Organization not found"},
    },
)
async def get_organizations_by_id(
    organization_id: int, db: AsyncSession = Depends(get_db)
):
    options = [
        selectinload(models.Organization.phones),
        selectinload(models.Organization.activities),
        joinedload(models.Organization.building),
    ]

    org = await db.get(models.Organization, ident=organization_id, options=options)

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return org


@router.get(
    "/organizations/location/nearby",
    response_model=list[OrganizationOut],
    description="Список организаций, находящихся в заданном радиусе от указанной точки на карте",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Invalid API Key"},
    },
)
async def get_organizations_nearby(
    lat: float = Query(..., description="Широта точки"),
    lon: float = Query(..., description="Долгота точки"),
    radius: float = Query(..., description="Радиус поиска в метрах"),
    db: AsyncSession = Depends(get_db),
):
    point = geofunc.ST_SetSRID(geofunc.ST_MakePoint(lon, lat), 4326)

    q = (
        select(models.Organization)
        .join(models.Building, models.Organization.building_id == models.Building.id)
        .filter(
            geofunc.ST_DWithin(
                models.Building.coordinates.cast(Geography),
                point.cast(Geography),
                radius,
            )
        )
        .options(
            selectinload(models.Organization.phones),
            selectinload(models.Organization.activities),
            joinedload(models.Organization.building),
        )
    )
    result = await db.scalars(q)

    return result.all()


@router.get(
    "/organizations/location/bounds",
    response_model=list[OrganizationOut],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Invalid API Key"},
    },
)
async def get_organizations_in_bounds(
    sw_lat: float = Query(..., description="Широта юго-западного угла"),
    sw_lon: float = Query(..., description="Долгота юго-западного угла"),
    ne_lat: float = Query(..., description="Широта северо-восточного угла"),
    ne_lon: float = Query(..., description="Долгота северо-восточного угла"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить список организаций в прямоугольной области.
    Область задается двумя точками: юго-западный и северо-восточный углы.
    """
    bounds = geofunc.ST_SetSRID(
        geofunc.ST_MakeEnvelope(sw_lon, sw_lat, ne_lon, ne_lat, 4326), 4326
    )

    q = (
        select(models.Organization)
        .join(models.Building, models.Organization.building_id == models.Building.id)
        .filter(geofunc.ST_Within(models.Building.coordinates, bounds))
        .options(
            selectinload(models.Organization.phones),
            selectinload(models.Organization.activities),
            joinedload(models.Organization.building),
        )
    )

    result = await db.scalars(q)
    return result.all()


@router.post("/test-data")
async def create_test_data(
    num_buildings: int = Query(...),
    num_organizations: int = Query(...),
    num_phones: int = Query(...),
    db: AsyncSession = Depends(get_db),
):

    await generate_test_data(
        db=db,
        num_buildings=num_buildings,
        num_organizations=num_organizations,
        num_phones=num_phones,
    )
