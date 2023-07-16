from vkinder.bot import Bot
from vkinder.config import USER_TOKEN, GROUP_TOKEN, setup_db


def main():
    setup_db()
    bot = Bot(USER_TOKEN, GROUP_TOKEN)
    bot.start_worker()


if __name__ == '__main__':
    main()
