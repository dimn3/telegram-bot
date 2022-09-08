import logging
import os
import telegram
import requests
import sys
import exceptions

import time
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = 'y0_AgAAAAABUx_7AAYckQAAAADOMWD6rCeRx7c8R16qZXjwySDAz-qo1fU'
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = 903772427

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
FROM_DATE = {'from_date': 0}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Сообщение успешно отправлено в чат')
    except telegram.error.TelegramError:
        logger.error('Сбой при отправке сообщения в чат')
        raise Exception


def get_api_answer(current_timestamp):
    """Получает ответ API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        raise requests.ConnectionError(response.status_code)
    try:
        return response.json()
    except exceptions.WrongFormat:
        logger.error('Сервер вернул неправильный json')


def check_response(response):
    """Проверяет ответ API на корректность."""
    homeworks = response['homeworks']
    if len(homeworks) == 0:
        logger.error('Пустой словарь')
    if 'current_date' not in response:
        logger.error('Ключ "current_date" отсутсвует')
    if type(response) is not dict:
        message = ('Некорректный тип ответа API')
        logger.error(message)
    if type(homeworks) is not list:
        message = ('Объект homeworks не является словарем')
        logger.error(message)
    else:
        return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'status' not in homework:
        raise KeyError(
            logger.error('Ошибка при обращении к статусу домашней работы')
        )
    elif 'homework_name' not in homework:
        raise KeyError(
            logger.error('Ошибка при обращении к названию работы')
        )
    elif homework['status'] not in HOMEWORK_STATUSES:
        raise KeyError(
            logger.error('Неверный статус')
        )
    homework_name = homework['homework_name']
    homework_status = homework['status']
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except exceptions.UnregisteredStatus:
        KeyError(
            logger.error('Передан неизвестный статус работы')
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет наличие обязательных токенов."""
    if not PRACTICUM_TOKEN:
        logging.critical('Отсутствует переменная PRACTIKUM_TOKEN')
        return False
    if not TELEGRAM_CHAT_ID:
        logging.critical('Отсутствует переменная TELEGRAM_CHAT_ID')
        return False
    if not TELEGRAM_TOKEN:
        logging.critical('Отсутствует переменная TELEGRAM_TOKEN')
        return False
    else:
        return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time() - 12000000)
    message_cache = None
    status_cache = {}
    if not check_tokens():
        message = ('Отсутсвуют необходимые переменные')
        logger.error(message)
        send_message(bot, message)
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            homework_status = parse_status(homeworks[0])
            homework_name = homeworks[0].get('homework_name')
            if status_cache.get(homework_name) != homework_status:
                status_cache[homework_name] = homework_status
            send_message(bot, homework_status)
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message_cache != message:
                send_message(bot, message)
                message_cache = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
