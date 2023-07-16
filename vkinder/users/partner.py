class Partner:
    def __init__(self, user_id, first_name="", last_name=""):
        self.db_id = 0
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name

    def __str__(self):
        return f"id: {self.user_id}, Имя: {self.first_name}, Фамилия: {self.last_name}"
