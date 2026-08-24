import enum


class ProjectRole(str, enum.Enum):
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    REVIEWER = "REVIEWER"
    VIEWER = "VIEWER"


ROLE_HIERARCHY = {
    ProjectRole.ADMIN: 0,
    ProjectRole.EDITOR: 1,
    ProjectRole.REVIEWER: 2,
    ProjectRole.VIEWER: 3,
}


def role_has_permission(role: ProjectRole, minimum: ProjectRole) -> bool:
    return ROLE_HIERARCHY[role] <= ROLE_HIERARCHY[minimum]
