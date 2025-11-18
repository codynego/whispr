from __future__ import annotations

from typing import List, Optional

from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import QuerySet

from whisone.models import Todo


class TodoService:
    """Service layer for Todo operations scoped to a specific user."""

    def __init__(self, user: User):
        self.user = user

    def create_todo(self, task: str) -> Todo:
        """Create a new todo for the user."""
        return Todo.objects.create(user=self.user, task=task.strip())

    def update_todo(self, todo_id: int, *, task: Optional[str] = None, done: Optional[bool] = None) -> Optional[Todo]:
        """
        Update an existing todo.
        Returns the updated todo or None if not found/doesn't belong to user.
        """
        try:
            todo = Todo.objects.get(id=todo_id, user=self.user)
            if task is not None:
                todo.task = task.strip()
            if done is not None:
                todo.done = done
            todo.save()
            return todo
        except Todo.DoesNotExist:
            return None

    def delete_todo(self, todo_id: int) -> bool:
        """Delete a todo if it belongs to the user. Returns success status."""
        return bool(Todo.objects.filter(id=todo_id, user=self.user).delete()[0])

    def fetch_todos(self, *, done: Optional[bool] = None) -> QuerySet[Todo]:
        """
        Fetch todos for the user, optionally filtered by completion status.
        Ordered by most recent first.
        """
        queryset = Todo.objects.filter(user=self.user)
        if done is not None:
            queryset = queryset.filter(done=done)
        return queryset.order_by("-created_at")

    def get_todos_for_today(self) -> QuerySet[Todo]:
        """
        Return all incomplete todos created today (based on user's timezone if USE_TZ=True).
        Uses timezone-aware datetimes when USE_TZ is enabled (recommended).
        """
        today = timezone.localdate()  # Uses timezone.today() if USE_TZ=True, else date.today()
        start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end_of_day = timezone.make_aware(datetime.combine(today, datetime.max.time()))

        return (
            Todo.objects.filter(
                user=self.user,
                done=False,
                created_at__gte=start_of_day,
                created_at__lte=end_of_day,
            )
            .order_by("created_at")
        )

    def get_overdue_todos(self) -> QuerySet[Todo]:
        """Bonus: commonly useful — incomplete todos from before today."""
        today = timezone.localdate()
        start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))

        return (
            Todo.objects.filter(
                user=self.user,
                done=False,
                created_at__lt=start_of_day,
            )
            .order_by("created_at")
        )