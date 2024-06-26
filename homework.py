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

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
FROM_DATE = {'from_date': 0}

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Сообщение успешно отправлено в чат')
        return True
    except exceptions.UnrealToSendMessage:
        logger.error('Сбой при отправке сообщения в чат')
        return False


def get_api_answer(current_timestamp):
    """Получает ответ API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except exceptions.ConnectionLost as error:
        err_message = 'Сбой при подключении к API'
        logger.error(err_message)
        raise error(err_message)
    if response.status_code != HTTPStatus.OK:
        raise requests.ConnectionError(response.status_code)
    try:
        return response.json()
    except exceptions.WrongFormat as error:
        err_message = 'Сервер вернул неправильный json'
        logger.error(err_message)
        raise error(err_message)


def check_response(response):
    """Проверяет ответ API на корректность."""
    try:
        homeworks = response['homeworks']
    except KeyError:
        error_msg = 'Ошибка ключа homeworks'
        logger.error(error_msg)
        raise KeyError(error_msg)
    if 'current_date' not in response:
        error_msg = 'Не передана дата в ответе API'
        logger.error(error_msg)
        raise KeyError(error_msg)
    if not isinstance(response, dict):
        message = 'Некорректный тип ответа API'
        logger.error(message)
        raise exceptions.WrongFormat(message)
    if not isinstance(homeworks, list):
        message = 'Объект homeworks не является словарем'
        logger.error(message)
        raise exceptions.WrongFormat(message)
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'status' not in homework:
        err_message = 'Ошибка при обращении к статусу домашней работы'
        logger.error(err_message)
        raise KeyError(err_message)
    if 'homework_name' not in homework:
        err_message = 'Ошибка при обращении к названию домашней работы'
        logger.error(err_message)
        raise KeyError(err_message)
    if homework['status'] not in VERDICTS:
        err_message = 'Неверный статус работы'
        logger.error(err_message)
        raise KeyError(err_message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    try:
        verdict = VERDICTS[homework_status]
    except exceptions.UnregisteredStatus:
        err_message = 'Передан неизвестный статус работы'
        logger.error(err_message)
        raise KeyError(err_message)
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
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time() - 12000000)
    message_cache = None
    status_cache = {}
    if not check_tokens():
        message = 'Отсутсвуют необходимые переменные'
        logger.error(message)
        exit()
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) != 0:
                homework_status = parse_status(homeworks[0])
                homework_name = homeworks[0].get('homework_name')
                if status_cache.get(homework_name) != homework_status:
                    status_cache[homework_name] = homework_status
                    send_message(bot, homework_status)
                current_timestamp = response.get(
                    'current_date', current_timestamp
                )
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message_cache != message and send_message(bot, message):
                message_cache = message
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
