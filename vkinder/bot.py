from datetime import datetime
from enum import StrEnum
from typing import Generator, TypeAlias

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

from vkinder.config import db, Database, START_KB
from vkinder.users import User, Partner

AttachmentType: TypeAlias = str


class State(StrEnum):
    BEGIN = "begin"
    START = "start"
    CITY = "city"
    AGE = "age"
    SEX = "sex"
    SEARCH = "search"


class StateMachine:
    def __init__(self):
        self.state = State.BEGIN
        self.user_state = {}

    def get_state(self, user_id: int) -> State:
        return self.user_state.get(user_id, State.BEGIN)

    def set_state(self, user_id: int, state: State):
        self.user_state[user_id] = state

    def clear_state(self, user_id: int):
        self.user_state.pop(user_id, State.BEGIN)


class Message:
    def __init__(self, text: str, user_id: int):
        self.text = text
        self.user_id = user_id


class Bot:

    def __init__(self, user_token: str, group_token: str):
        self.user_api = vk_api.VkApi(token=user_token)
        self.group_api = vk_api.VkApi(token=group_token)
        self.state_machine = StateMachine()
        self.db: Database = db
        self.users_searching_generators: dict[int, Generator] = {}

    @classmethod
    def parse_age(cls, age_str: str) -> int | None:
        try:
            age = age_str.split(".")
            if len(age) == 3:
                return datetime.now().year - int(age[2])
        except Exception as e:
            return None

    def get_or_create_user(self, user_id: int) -> User:
        user = self.db.get_user(user_id)
        if not user:
            user_data = self.user_api.method("users.get", {"user_ids": user_id, "fields": "city,sex,bdate"})
            user_data = user_data[0]
            user = User(user_id)
            user.set_city_id(user_data.get("city", {}).get("id"))
            user.set_city_title(user_data.get("city", {}).get("title"))
            user.set_age(self.parse_age(user_data.get("bdate")))
            user.set_sex(user_data.get("sex"))
            self.db.create_user_from_model(user)
        return user

    def get_city_title(self, city_id: int) -> str | None:
        city_data = self.user_api.method("database.getCitiesById", {"city_ids": city_id})
        try:
            return city_data[0].get("title")
        except Exception as e:
            return None

    def get_city_id(self, city_title: str) -> int | None:
        city_data = self.user_api.method("database.getCities", {"q": city_title, "count": 1})
        try:
            return city_data.get("items", [{}])[0].get("id")
        except Exception as e:
            return None

    def get_user_city(self, user_id: int) -> int | None:
        user_data = self.user_api.method("users.get", {"user_ids": user_id, "fields": "city"})
        return user_data[0].get("city", {}).get("id")

    def send_message(self, user_id: int, text: str, reply_markup: str = None, attachment: str = None):
        self.group_api.method(
            'messages.send', {
                'user_id': user_id,
                'message': text,
                'keyboard': reply_markup,
                'attachment': attachment,
                'random_id': 0, }
        )

    def start_worker(self):
        longpoll = VkLongPoll(self.group_api)
        for event in longpoll.listen():
            if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
                continue
            state = self.state_machine.get_state(event.user_id)
            user = self.get_or_create_user(event.user_id)
            message = Message(event.text, event.user_id)

            if message.text.startswith("Очистить"):
                self.state_machine.clear_state(event.user_id)
                self.db.delete_user(event.user_id)
                self.db.delete_all_partners()
                self.send_message(event.user_id, "Сессия очищена", START_KB)
                self.send_message(message.user_id, "Привет! Я бот, который поможет тебе найти пару. Начнем?", START_KB)
                self.state_machine.set_state(event.user_id, State.START)
            elif message.text.startswith("Нет"):
                self.send_message(message.user_id, "Отмена поиска", START_KB)
                self.state_machine.clear_state(message.user_id)
            else:
                method = getattr(self, f"state_{state}")
                method(message, user)

    def next_state(self, message: Message, user: User):
        if not user.city_id:
            self.send_message(message.user_id, "Какой город тебя интересует?")
            self.state_machine.set_state(message.user_id, State.CITY)
        elif not user.age:
            self.send_message(message.user_id, "Какой возраст тебя интересует?")
            self.state_machine.set_state(message.user_id, State.AGE)
        elif not user.sex:
            self.send_message(message.user_id, "Какого пола тебе нужна пара?")
            self.state_machine.set_state(message.user_id, State.SEX)
        else:
            self.send_message(message.user_id, f"Поиск пары для тебя:\n{user}")
            self.state_machine.set_state(message.user_id, State.SEARCH)
            self.send_message(message.user_id, "Нажми 'Да' чтобы начать поиск", START_KB)
            search_generator = self.searching(user)
            self.users_searching_generators[user.user_id] = search_generator

    def state_begin(self, message: Message, user: User):
        self.send_message(message.user_id, "Привет! Я бот, который поможет тебе найти пару. Начнем?", START_KB)
        self.state_machine.set_state(message.user_id, State.START)

    def state_start(self, message: Message, user: User):
        if message.text.lower() == "да":
            self.next_state(message, user)
        elif message.text.lower() == "нет":
            self.send_message(message.user_id, "Пока!")
            self.state_machine.clear_state(message.user_id)
        else:
            self.send_message(message.user_id, "Не понял тебя. Нажми 'Да' или 'Нет'")

    def state_city(self, message: Message, user: User):
        if message.text.lower() == "пропустить":
            self.state_machine.set_state(message.user_id, State.AGE)
            self.send_message(message.user_id, "Какой возраст тебя интересует?", START_KB)
            return
        city_id = self.get_city_id(message.text)
        if city_id is None:
            self.send_message(message.user_id, "Не удалось найти город. Попробуйте еще раз...")
            return
        user.city_id = city_id
        user.city_title = self.get_city_title(city_id)
        self.db.save_user(user)
        self.next_state(message, user)

    def state_age(self, message: Message, user: User):
        if message.text.lower() == "пропустить":
            self.state_machine.set_state(message.user_id, State.SEX)
            self.send_message(message.user_id, "Какой пол тебя интересует?", START_KB)
            return
        try:
            age = int(message.text)
        except ValueError:
            self.send_message(message.user_id, "Некорректный формат возраста. Попробуйте еще раз...")
            return
        user.age = age
        self.db.save_user(user)
        self.next_state(message, user)

    def state_sex(self, message: Message, user: User):
        if message.text.lower() == "пропустить":
            self.state_machine.set_state(message.user_id, State.SEARCH)
            self.send_message(message.user_id, "Начинаю поиск. Это может занять некоторое время...")
            return
        sex = message.text.lower()
        if sex not in {"м", "ж"}:
            self.send_message(message.user_id, "Некорректный пол. Попробуйте еще раз...")
            return
        user.sex = sex
        self.db.save_user(user)
        self.state_machine.set_state(message.user_id, State.SEARCH)
        self.send_message(message.user_id, f"Поиск пары для тебя:\n{user}")
        self.send_message(message.user_id, "Нажми 'Да' чтобы начать поиск", START_KB)
        search_generator = self.searching(user)
        self.users_searching_generators[user.user_id] = search_generator

    def state_search(self, message: Message, user: User):
        search_generator = self.users_searching_generators.get(user.user_id)
        if search_generator is None:
            self.send_message(message.user_id, "Поиск не был запущен. Попробуйте еще раз...")
            self.state_machine.set_state(message.user_id, State.START)
            return

        if message.text.lower() == "да":
            self.send_message(message.user_id, "Поиск...")
        else:
            self.send_message(message.user_id, "Поиск завершен. Попробуйте еще раз...")
            self.state_machine.clear_state(message.user_id)
            return
        try:
            partner = next(search_generator)
            while (db.exist_partner(partner.user_id)) or not (
                    attachment := self.get_partner_popular_photos_attachment(partner)
            ):
                partner = next(search_generator)

            text = (
                f"Новая пара для тебя:\n"
                f"{partner.first_name} {partner.last_name}\n"
                f"Профиль: https://vk.com/id{partner.user_id}\n\n\n"
            )

            self.send_message(user.user_id, text, attachment=attachment, )
            self.send_message(user.user_id, f"Продолжить поиск?", reply_markup=START_KB)
            db.create_partner(partner.user_id)
        except StopIteration:
            self.send_message(message.user_id, "Поиск завершен. Попробуйте еще раз...")
            self.users_searching_generators.pop(user.user_id)
            self.state_machine.clear_state(message.user_id)

    def searching(self, user: User) -> Generator[Partner, None, None]:
        partner_sex = 2 if user.sex == 1 else 1  # выбираем противоположный пол
        age = int(user.age)
        age_from = age - 1
        age_to = age + 1
        params = {
            "sex": partner_sex,
            "count": 5,
            "offset": 0,
            "city": user.city_id,
            "status": 6,
            "age_from": age_from,
            "age_to": age_to,
            "has_photo": 1,
            "fields": {
                "first_name",
                "last_name",
                "city",
                "bdate",
            },
        }

        while True:
            data = self.user_api.method("users.search", params)
            if not data.get("items"):
                break
            items = data.get("items")
            partners = (Partner(item["id"], item["first_name"], item["last_name"]) for item in items)
            yield from partners
            params["offset"] += 5

    def get_partner_popular_photos_attachment(self, partner: Partner) -> AttachmentType | None:
        try:
            photos = self.user_api.method("photos.getAll", {
                "type": "album",
                "owner_id": partner.user_id,
                "extended": 1,
                "count": 30,
                "skip_hidden": 1
            })['items']
            photos = sorted(photos, key=lambda d: d['likes']['count'], reverse=True)[:3]
            attachments = [f"photo{partner.user_id}_{photo['id']}" for photo in photos]
            return ",".join(attachments)
        except Exception:
            return None
