from enum import Enum


class Sex(int, Enum):
    # 0
    UNKNOWN = 0
    FEMALE = 1
    MALE = 2


class User:
    def __init__(self, user_id):
        self.db_id = 0
        self.user_id = user_id
        self.city_id = None
        self.city_title = None
        self.age = None
        self.sex: Sex = Sex.UNKNOWN

    def set_city_title(self, value):
        self.city_title = value

    def set_city_id(self, value):
        self.city_id = value

    def set_age(self, value):
        self.age = value

    def set_sex(self, value):
        self.sex = value

    def __str__(self):
        return f"id: {self.user_id}, город: {self.city_title}, возраст: {self.age}"
