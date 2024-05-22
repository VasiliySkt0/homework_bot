import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Dict

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
CHECK_PERIOD = 259200 * 3
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

HISTORY: Dict[str, str] = {}

logger = logging.getLogger('telegram-bot-logger')
logger.setLevel(logging.DEBUG)

log_format = '%(asctime)s - %(levelname)s - %(message)s'
log_formatter = logging.Formatter(log_format, style='%')

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setFormatter(log_formatter)

logger.addHandler(stream_handler)


def check_tokens():
    """Проверяет доступность токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = []
    for token in tokens:
        if not tokens.get(token):
            missing_tokens.append(token)
    if missing_tokens:
        logger.critical(f'Отсутствующие токены: {missing_tokens}')
        #Не получается отправить задание без лога в этой функции
    return missing_tokens


def send_message(bot: Bot, message) -> None:
    """Отправка сообщения."""
    try:
        logging.info('Начало отправки сообщения')
        bot.send_message(
            text=message,
            chat_id=TELEGRAM_CHAT_ID)
        logger.debug('Message sent')
    except telegram.error.TelegramError as error:
        raise exceptions.FailedToSendMessageError(error)


def get_api_answer(timestamp) -> Dict:
    """Запрос к серверу Яндекс."""
    payload = {'from_date': timestamp}
    try:
        logging.info('Начало запроса к API')
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code == HTTPStatus.OK:
            logger.debug('Response: OK')
            return response.json()
        raise exceptions.EmptyAPIResponseError
    except requests.RequestException as error:
        logger.error('get_api_answer() error %s', error.args)


def check_response(response) -> None:
    """Проверка ответа от сервера."""
    if not isinstance(response, dict):
        raise TypeError('response is not Dict type')
    if not response.get('homeworks'):
        raise KeyError('В ответе API домашки нет ключа "homeworks".')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('"homeworks" in response is not List type')
    if 'current_date' not in response:
        raise KeyError('key "current_date" not in response')


def parse_status(homework: Dict) -> str:
    """Поиск статуса отдельной работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        message = ('Отсутствие ключей в ответе API.')
        raise KeyError(message)
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise KeyError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens():
        logger.critical('Tokens not found')
        raise exceptions.TokenNotFoundError()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - CHECK_PERIOD
    sent_message = ''
    sent_error = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            if homeworks:
                message = parse_status(homeworks[0])
                if message != sent_message:
                    send_message(bot, message)
                sent_message = message
            else:
                logger.debug('Статус домашней работы не изменился')
        except Exception as error:
            message_error = f'Сбой в работе программы: {error}'
            send_message(bot, message_error)
            logger.error(message_error)
            if message_error != sent_error:
                send_message(bot, message_error)
                sent_message = message_error
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
