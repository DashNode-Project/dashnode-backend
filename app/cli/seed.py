"""
Development database seeder.
@sad AD-09
@origin [Archetype Convention Addition]
"""

from datetime import UTC, datetime

from app.modules.auth.infrastructure.models import UserModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.modules.tasks.infrastructure.models import TaskModel
from app.shared.infrastructure.database import SessionLocal
from app.shared.infrastructure.hasher import Argon2PasswordHasher
from app.shared.infrastructure.id_generator import UuidGenerator


def seed() -> None:
    db = SessionLocal()
    hasher = Argon2PasswordHasher()
    id_gen = UuidGenerator()
    now = datetime.now(UTC)

    try:
        # Check if already seeded
        existing_user = db.query(UserModel).filter_by(email="admin@dashnode.io").first()
        if existing_user:
            print("Database already contains seed data.")
            return

        admin_id = id_gen.generate()
        admin_user = UserModel(
            id=admin_id,
            email="admin@dashnode.io",
            hashed_password=hasher.hash("AdminPassword123!"),
            name="Administrator",
            role="admin",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(admin_user)

        proj_id = id_gen.generate()
        sample_project = ProjectModel(
            id=proj_id,
            name="DashNode Initial Project",
            description="Initial seed project for DashNode platform",
            owner_id=admin_id,
            created_at=now,
            updated_at=now,
        )
        db.add(sample_project)

        lead_member = ProjectMemberModel(
            project_id=proj_id,
            user_id=admin_id,
            role="lead",
            joined_at=now,
        )
        db.add(lead_member)

        task_id = id_gen.generate()
        sample_task = TaskModel(
            id=task_id,
            project_id=proj_id,
            title="Setup development environment",
            description="Run docker-compose and verify backend",
            status="todo",
            priority="high",
            assignee_id=admin_id,
            creator_id=admin_id,
            has_open_fix=False,
            created_at=now,
            updated_at=now,
        )
        db.add(sample_task)

        db.commit()
        print("Seed data successfully created.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
