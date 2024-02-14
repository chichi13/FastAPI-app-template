from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


def get_all_paginate(model):
    """
    Get all entries with pagination : only works with FastAPI pagination
    example:
    get_all_paginate(Role)
    """
    return select(model)


async def get_all(db: AsyncSession, model):
    """
    Get all entries
    example:
    get_all(db, Role)
    """
    query = await db.execute(select(model))
    return query.scalars().all()


async def get_specific_by_id(db: AsyncSession, model, id: int, exception: bool = True):
    """
    Get an entry by id
    example:
    get_specific_by_id(db, Role, role.id)
    """
    query = await db.execute(select(model).where(model.id == id))
    result = query.scalars().first()

    if result is not None:
        return result

    if exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found"
        )
    return None


async def get_specific(
    db: AsyncSession, model, filter_lst: list, exception: bool = True
):
    """
    Get an entry by id
    example:
    get_specific(db, Role, [Role.name == "test"])
    """
    query = await db.execute(select(model).where(*filter_lst))
    result = query.scalars().first()

    if result is not None:
        return result

    if exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found"
        )
    return None


async def delete_by_id(db, model, id: int):
    """
    Delete an entry by id
    example:
    delete_by_id(db, Role, role.id)
    """
    query = await get_specific_by_id(db, model, id)

    if query is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found"
        )

    await db.delete(query)
    await db.commit()
    await db.flush()

    return {
        "status": True,
        "msg": f"{model.__name__} ({id}) Deleted",
    }


async def check_if_exists(
    db: AsyncSession, model, filter_lst: list, exception: bool = True
):
    """
    Check if an entry exists in the database
    example:
    filter_lst = [Role.name == "test"]
    check_if_exists(db, Role, filter_lst)
    """
    query = await db.execute(select(model).where(*filter_lst))
    result = query.scalars().first()

    if result:
        if exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{model.__name__} already exists",
            )
        return True
    return False


async def create_entry(db: AsyncSession, model, schema):
    """
    Create a new entry in the database
    example:
    data_in = {"name": "test", "description": "test"}
    create_entry(db, Role, data_in)
    or with schema:
    create_entry(db, Role, role)
    Where role is a RoleCreate object
    """
    if isinstance(schema, dict):
        updated_data = schema
    else:
        updated_data = schema.dict(exclude_unset=True)

    data = model(**updated_data)
    db.add(data)

    await db.commit()
    await db.flush()
    return data


async def update_entry(db: AsyncSession, model, entry_id: int, schema):
    """
    Update an entry in the database
    example:
    update_entry(db, Role, role.id, RoleUpdate)
    """
    query = await get_specific_by_id(db, model, entry_id)

    if isinstance(schema, dict):
        updated_data = schema
    else:
        updated_data = schema.dict(exclude_unset=True)

    for key, value in updated_data.items():
        setattr(query, key, value)

    db.add(query)
    await db.commit()
    await db.refresh(query)

    return query
