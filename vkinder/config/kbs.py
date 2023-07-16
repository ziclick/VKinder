import json


def create_button(text: str, color: str) -> dict:
    """Создает кнопку с заданным текстом и цветом."""
    return {
        "action": {
            "type": "text",
            "payload": "",
            "label": f"{text}"
        },
        "color": f"{color}"
    }


# Создаем клавиатуру
keyboard_data = {
    "one_time": False,
    "buttons": [
        [create_button('Да', 'positive')],
        [create_button('Нет', 'negative')],
        [create_button("Очистить и начать заново", "primary")]
    ]
}

# Преобразуем данные клавиатуры в json
START_KB = json.dumps(keyboard_data, ensure_ascii=False)
