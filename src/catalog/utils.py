import random
from faker import Faker
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from .models import (
    Building,
    Organization,
    OrganizationPhone,
    Activity,
    organization_activity_table,
)


async def create_buildings(
    db: AsyncSession, num_buildings: int, fake: Faker
) -> list[Building]:
    buildings = [
        Building(
            address=fake.address(),
            coordinates=WKTElement(
                f"POINT({fake.longitude()} {fake.latitude()})", srid=4326
            ),
        )
        for _ in range(num_buildings)
    ]
    db.add_all(buildings)
    await db.flush()
    return buildings


async def create_organizations(
    db: AsyncSession, num_organizations: int, buildings: list[Building], fake: Faker
) -> list[Organization]:
    organizations = [
        Organization(
            company_name=fake.company(), building_id=random.choice(buildings).id
        )
        for _ in range(num_organizations)
    ]
    db.add_all(organizations)
    await db.flush()
    return organizations


async def create_phones(
    db: AsyncSession, num_phones: int, organizations: list[Organization], fake: Faker
) -> None:
    phones = [
        OrganizationPhone(
            organization_id=random.choice(organizations).id,
            phone_number=fake.phone_number(),
        )
        for _ in range(num_phones)
    ]
    db.add_all(phones)
    await db.flush()


async def create_root_activities(
    db: AsyncSession, categories: list[tuple[str, list[tuple[str, list[str]]]]]
) -> dict[str, Activity]:
    root_activities = {}
    for category_name, _ in categories:
        root_activity = Activity(activity_name=category_name, parent_id=None, level=0)
        db.add(root_activity)
        root_activities[category_name] = root_activity

    await db.flush()
    return root_activities


async def create_sub_activities(
    db: AsyncSession,
    categories: list[tuple[str, list[tuple[str, list[str]]]]],
    root_activities: dict[str, Activity],
) -> list[Activity]:
    all_activities = list(root_activities.values())

    for category_name, subcategories in categories:
        parent_activity = root_activities[category_name]
        for subcategory_name, sub_subcategories in subcategories:
            sub_activity = Activity(
                activity_name=subcategory_name, parent_id=parent_activity.id, level=1
            )
            db.add(sub_activity)
            all_activities.append(sub_activity)
            await db.flush()

            for sub_subcategory_name in sub_subcategories:
                sub_sub_activity = Activity(
                    activity_name=sub_subcategory_name,
                    parent_id=sub_activity.id,
                    level=2,
                )
                db.add(sub_sub_activity)
                all_activities.append(sub_sub_activity)

    await db.flush()
    return all_activities


async def assign_activities_to_organizations(
    db: AsyncSession, organizations: list[Organization], activities: list[Activity]
) -> None:
    for organization in organizations:
        selected_activities = random.sample(activities, k=random.randint(1, 3))
        for activity in selected_activities:
            await db.execute(
                organization_activity_table.insert().values(
                    organization_id=organization.id, activity_id=activity.id
                )
            )


async def generate_test_data(
    db: AsyncSession,
    num_buildings: int = 10,
    num_organizations: int = 30,
    num_phones: int = 50,
) -> None:
    fake = Faker()

    categories = [
        (
            "Еда",
            [
                ("Мясная продукция", ["говядина", "свинина"]),
                ("Молочная продукция", ["сыр", "молоко"]),
            ],
        ),
        (
            "Автомобили",
            [("Грузовые", []), ("Легковые", []), ("Запчасти", []), ("Аксессуары", [])],
        ),
    ]

    try:
        buildings = await create_buildings(db, num_buildings, fake)
        organizations = await create_organizations(
            db, num_organizations, buildings, fake
        )
        await create_phones(db, num_phones, organizations, fake)

        root_activities = await create_root_activities(db, categories)
        all_activities = await create_sub_activities(db, categories, root_activities)
        await assign_activities_to_organizations(db, organizations, all_activities)

        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e
