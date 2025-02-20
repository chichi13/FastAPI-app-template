from typing import Type, Union

from fastapi import status
from pydantic import BaseModel
from sqlalchemy import and_, case, exists, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import load_only
from sqlalchemy.sql import func

from app.utils.response import HTTPCustomErrorException


def get_all_paginate(model: Type):
    """
    Get all entries with pagination.
    Example:
    get_all_paginate(Role)
    """
    query = select(model)
    return query


async def get_entries(
    db: AsyncSession,
    model: Type,
    filter_lst: list | None = None,
    options: list | None = None,
    order_by: list | None = None,
    unique: bool = False,
):
    """
    Get all entries for a model with filters and options.

    Args:
        db: The AsyncSession object for database access.
        model: The model class representing the entries to retrieve.
        filter_lst: A list of SQLAlchemy filter expressions (optional).
        order_by: A list of SQLAlchemy order by expressions (optional).
        options: A list of SQLAlchemy query options (optional).
        unique: Whether to return unique results (default: False).

    Returns:
        A list of model instances or an empty list if no entries are found.
    """

    filters = filter_lst if filter_lst is not None else []

    query = select(model).where(*filters)

    if options:
        for option in options:
            query = query.options(option)

    if order_by:
        query = query.order_by(*order_by)

    result = await db.execute(query)
    if unique:
        return result.scalars().unique().all()
    else:
        return result.scalars().all()


async def get_specific_by_id(
    db: AsyncSession, model: Type, id: int, exception: bool = True
):
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
        raise HTTPCustomErrorException(
            status_code=status.HTTP_404_NOT_FOUND,
            msg=f"{model.__name__} not found",
            details={"id": id},
        )
    return None


async def get_entry(
    db: AsyncSession,
    model: Type,
    filter_lst: list | None = None,
    id: Union[int, str] | None = None,
    options: list | None = None,
    exception: bool = True,
    populate_existing: bool = False,
):
    """
    Get an entry by id or with specified filters and options
    example to get by id:
    get_entry(db, Role, id=role.id)
    example to get with filters:
    get_entry(db, Role, filter_lst=[Role.name == "test"])
    example to get with options:
    get_entry(db, User, filter_lst=[User.name == "test"], options=[selectinload(User.roles).joinedload(Role.permissions)])
    """
    filters = filter_lst if filter_lst is not None else []

    if id is not None:
        filters.append(model.id == id)

    query = select(model).where(*filters)

    if options:
        for option in options:
            query = query.options(option)

    if populate_existing:
        query = query.execution_options(populate_existing=True)

    result = await db.execute(query)
    entry = result.scalars().first()

    if entry is not None:
        return entry

    if exception:
        raise HTTPCustomErrorException(
            status_code=status.HTTP_404_NOT_FOUND,
            msg=f"{model.__name__} not found",
            details={"id": id},
        )
    return None


async def delete_by_id(db: AsyncSession, model: Type, id: int):
    """
    Delete an entry by id
    example:
    delete_by_id(db, Role, role.id)
    """
    query = await get_entry(db, model, id=id)

    if query is None:
        raise HTTPCustomErrorException(
            status_code=status.HTTP_404_NOT_FOUND,
            msg=f"{model.__name__} not found",
            details={"id": id},
        )

    await db.delete(query)
    await db.commit()
    await db.flush()

    return {
        "msg": f"{model.__name__} Deleted",
        "details": {
            "id": id,
        },
    }


async def check_if_exists(
    db: AsyncSession, model: Type, filter_lst: list, exception: bool = True
):
    """
    Check if an entry exists in the database
    example:
    filter_lst = [Role.name == "test"]
    check_if_exists(db, Role, filter_lst)
    """
    query = await db.execute(exists().where(*filter_lst).select())
    result = query.scalars().first()

    if result:
        if exception:
            raise HTTPCustomErrorException(
                status_code=status.HTTP_400_BAD_REQUEST,
                msg=f"{model.__name__} already exists",
            )
        return True
    return False


async def get_count(db: AsyncSession, model: Type, filter_lst: list | None = None):
    """
    Get the count of entries in the database.

    Args:
        db: The AsyncSession object for database access.
        model: The model class representing the entries to count.
        filter_lst: A list of SQLAlchemy filter expressions (optional).

    Returns:
        The count of entries that match the filters.
    """
    filters = filter_lst if filter_lst is not None else []

    # Constructing a query that only selects the 'id' column for counting
    query = select(func.count(model.id)).where(*filters)

    result = await db.execute(query)
    count = result.scalar()

    return count


async def create_entry(
    db: AsyncSession, model: Type, schema: Union[BaseModel, dict], refresh: bool = False
):
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
        data = model(**schema)
    elif hasattr(schema, "dict"):
        data = model(**schema.model_dump())
    else:
        data = schema

    db.add(data)

    await db.commit()
    if refresh:
        await db.refresh(data)
    return data


async def update_entry(
    db: AsyncSession,
    model: Type,
    entry_id: int,
    schema: Union[BaseModel, dict],
    id_field: str = "id",
):
    """
    Update an entry in the database
    example:
    update_entry(db, Role, role.id, RoleUpdate, id_field="user_id")
    """
    filters = [getattr(model, id_field) == entry_id]
    query = await get_entry(db, model, filter_lst=filters)

    if isinstance(schema, dict):
        updated_data = schema
    else:
        updated_data = schema.model_dump(exclude_unset=True)

    for key, value in updated_data.items():
        setattr(query, key, value)

    db.add(query)
    await db.commit()
    await db.refresh(query)

    return query


async def search_database(
    db: AsyncSession,
    model: Type,
    search_col: str,
    query: str,
    columns: list,
    limit: int = 5,
):
    """
    Search the database with prioritized results based on match type.

    Priority order:
    1. Exact matches (case-insensitive)
    2. Starts with the search term
    3. Contains all words in the search term
    4. Contains some words from the search term

    Args:
    - db (AsyncSession): The database session
    - model (Base): The SQLAlchemy model to search
    - search_col (str): The attribute of the model to search in
    - query (str): The search term
    - columns (list): List of attributes to load in the query
    - limit (int): Maximum number of results to return

    Returns:
    - List of results ordered by relevance
    """
    # Normalize the search query
    search_terms = query.lower().split()

    # Create the column reference
    col = getattr(model, search_col)

    # Define different match conditions with their priorities
    conditions = case(
        # Exact match (highest priority)
        (func.lower(col) == query.lower(), 1),
        # Starts with the search term
        (func.lower(col).like(f"{query.lower()}%"), 2),
        # Contains all words in order
        (func.lower(col).like(f"%{query.lower()}%"), 3),
        # Contains all words in any order
        (and_(*[func.lower(col).like(f"%{term}%") for term in search_terms]), 4),
        # Partial matches (lowest priority)
        else_=5,
    ).label("priority")

    # Build the search conditions
    search_conditions = or_(
        func.lower(col) == query.lower(),
        func.lower(col).like(f"{query.lower()}%"),
        func.lower(col).like(f"%{query.lower()}%"),
        and_(*[func.lower(col).like(f"%{term}%") for term in search_terms]),
    )

    # Execute the query with prioritized results
    search_res = await db.execute(
        select(model)
        .options(load_only(*[getattr(model, col) for col in columns]))
        .where(search_conditions)
        .order_by(conditions, col)
        .limit(limit)
    )

    return search_res.scalars().all()
