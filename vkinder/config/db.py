import psycopg2

from vkinder.config import HOST, USER, PASSWORD, DATABASE
from vkinder.users.user import User


class Database:
    def __init__(self, host, user, password, database):
        self.connection = psycopg2.connect(
            host=host, user=user, password=password, dbname=database, port=5432
        )
        self.connection.autocommit = True

    def get_user(self, vk_id: int) -> User | None:
        with self.connection.cursor() as cursor:
            try:
                query = "SELECT * FROM users WHERE vk_id = %s"
                cursor.execute(query, (vk_id,))
                user_data = cursor.fetchone()
            except psycopg2.Error as e:
                print(e)
                return None
            cursor.close()

            if user_data is None:
                # User not found
                return None

            user = User(user_data[1])
            user.db_id = user_data[0]
            user.city_id = user_data[2]
            user.city_title = user_data[3]
            user.age = user_data[4]
            user.sex = user_data[5]
            return user

    def create_user(self, vk_id: int, city_id: int = 0, city_title='', age: int = 0, sex: int = 1) -> User:
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO users (vk_id, city_id,city_title, age, sex) VALUES (%s, %s,%s, %s, %s) RETURNING id",
                (vk_id, city_id, city_title, age, sex))
            user_id = cur.fetchone()[0]
        user = User(vk_id)
        user.db_id = user_id
        user.city_id = city_id
        user.city_title = city_title
        user.age = age
        user.sex = sex
        return user

    def delete_user(self, vk_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute(
                '''
                DELETE FROM users WHERE vk_id = %s
                ''', (vk_id,)
            )

    def delete_all_partners(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                '''
                DELETE FROM partners
                '''
            )

    def create_user_from_model(self, user: User):
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO users (vk_id, city_id, city_title, age, sex) VALUES (%s, %s,%s, %s, %s) RETURNING id",
                (user.user_id, user.city_id, user.city_title, user.age, user.sex))
            user_id = cur.fetchone()[0]
            user.db_id = user_id
        return user

    def get_or_create_user(self, vk_id: int, city: int = 0, city_title='', age: int = 0, sex: int = 1) -> User:
        user = self.get_user(vk_id)
        if user is not None:
            return user
        return self.create_user(vk_id, city, city_title, age, sex)

    def save_user(self, user: User):
        with self.connection.cursor() as cursor:
            cursor.execute(
                '''
                 INSERT INTO users (vk_id, city_id,city_title, age, sex)
                 VALUES (%s, %s,%s, %s, %s)
                 ON CONFLICT (vk_id) DO UPDATE SET
                 city_id = excluded.city_id,
                 city_title = excluded.city_title,
                 age = excluded.age,
                 sex = excluded.sex
                 ''', (user.user_id, user.city_id, user.city_title, user.age, user.sex)
            )

    def create_table(self, table_name, fields):
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {table_name} ({fields});"
            )

    def insert_row(self, table_name, values):
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {table_name} VALUES ({values});"
            )

    def check_existence(self, user_vk_id, partner_vk_id):
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT EXISTS(SELECT 1 FROM users_partners WHERE user_vk_id = %s AND partner_vk_id = %s)", (
                    user_vk_id, partner_vk_id)
            )
            return cursor.fetchone()[0]

    def delete_rows(self, table_name, column_name, value):
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {table_name} WHERE {column_name} = %s", (value,)
            )

    def check_is_new_partner(self, user_id, partner_id) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT EXISTS(SELECT 1 FROM users_partners WHERE user_vk_id = %s AND partner_vk_id = %s)", (
                    user_id, partner_id)
            )
            return cursor.fetchone()[0]

    def create_partner(self, partner_id: int) -> None:
        with self.connection.cursor() as cursor:
            # Check if the partner already exists in the database
            if self.exist_partner(partner_id):
                print(f"Partner {partner_id} already exists in the database")
                return

            try:
                # Create a new partner record in the database
                cursor.execute(
                    "INSERT INTO partners (vk_id) VALUES (%s) RETURNING id",
                    (partner_id,),
                )
                partner_db_id = cursor.fetchone()[0]
                self.connection.commit()
                print(f"Partner {partner_id} created with id {partner_db_id}")
            except psycopg2.Error as e:
                self.connection.rollback()
                print(f"Failed to create partner {partner_id}: {e}")

    def exist_partner(self, partner_id) -> bool:
        with self.connection.cursor() as cursor:
            try:
                query = "SELECT COUNT(*) FROM partners WHERE vk_id = %s"
                cursor.execute(query, (partner_id,))
                count = cursor.fetchone()[0]
                return count > 0
            except psycopg2.Error as e:
                print(e)
                return False

    def new_partner(self, user_id: int, partner_id: int):
        if self.check_existence(user_id, partner_id):
            # Relationship already exists
            return
        with self.connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users_partners (user_vk_id, partner_vk_id) VALUES (%s, %s)", (user_id, partner_id)
            )

    def create_tables(self):
        self.create_table(
            "users",
            "id SERIAL PRIMARY KEY, "
            "vk_id BIGINT UNIQUE, "
            "city_id INTEGER, "
            "city_title VARCHAR(100), "
            "age INTEGER, "
            "sex INTEGER"
        )
        self.create_table("partners", "id SERIAL PRIMARY KEY, vk_id BIGINT UNIQUE")
        # self.create_table(
        #     "users_partners",
        #     "id SERIAL PRIMARY KEY, user_vk_id VARCHAR(30) REFERENCES users(vk_id), partner_vk_id VARCHAR(30) REFERENCES partners(vk_id)"
        # )
        self.create_table(
            "users_partners",
            "id SERIAL PRIMARY KEY, user_vk_id BIGINT REFERENCES users(vk_id), partner_vk_id BIGINT REFERENCES partners(vk_id)"
        )


db = Database(user=USER, password=PASSWORD, host=HOST, database=DATABASE)


def setup_db():
    db.create_tables()


if __name__ == "main":
    setup_db()
