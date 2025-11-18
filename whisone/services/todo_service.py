from typing import List, Optional
from whisone.models import Todo
from django.contrib.auth.models import User

class TodoService:
    def __init__(self, user: User):
        self.user = user

    def create_todo(self, task: str) -> Todo:
        todo = Todo.objects.create(user=self.user, task=task)
        return todo

    def update_todo(self, todo_id: int, task: str = None, done: bool = None) -> Optional[Todo]:
        try:
            todo = Todo.objects.get(id=todo_id, user=self.user)
            if task is not None:
                todo.task = task
            if done is not None:
                todo.done = done
            todo.save()
            return todo
        except Todo.DoesNotExist:
            return None

    def delete_todo(self, todo_id: int) -> bool:
        try:
            todo = Todo.objects.get(id=todo_id, user=self.user)
            todo.delete()
            return True
        except Todo.DoesNotExist:
            return False

    def fetch_todos(self, done: bool = None) -> List[Todo]:
        qs = Todo.objects.filter(user=self.user)
        if done is not None:
            qs = qs.filter(done=done)
        return qs.order_by('-created_at')

    def get_todos_for_today(self) -> List[Todo]:
        """
        Returns all todos due today and not yet completed.
        """
        now = datetime.now()
        start_of_day = datetime.combine(now.date(), datetime.min.time())
        end_of_day = datetime.combine(now.date(), datetime.max.time())

        return (
            Todo.objects.filter(
                user=self.user,
                done=False,
                created_at__gte=start_of_day,
                created_at__lte=end_of_day
            ).order_by('created_at')
        )
