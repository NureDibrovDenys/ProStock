from app.core.enums import RoleName
from app.users.schemas import UserListItem

def serialize_user(user) -> UserListItem:
    """
    ORM User ==> list item for the frontend.
    """
    return UserListItem(
        user_id=user.id,
        user_email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.name if user.role else RoleName.GUEST,
        status=user.status,
        position=None,
        on_shift=False,
        created_at=user.created_at,
    )