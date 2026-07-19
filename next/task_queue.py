class TaskQueue:
    def __init__(self):
        self.tasks = []
        self.done = []

    def add(self, task: str):
        if task and task not in self.tasks and task not in self.done:
            self.tasks.append(task)

    def add_many(self, tasks):
        for task in tasks:
            self.add(task)

    def next(self):
        if not self.tasks:
            return None

        task = self.tasks.pop(0)
        self.done.append(task)
        return task

    def has_tasks(self):
        return len(self.tasks) > 0

    def history(self):
        return {
            "pending": self.tasks,
            "done": self.done
        }