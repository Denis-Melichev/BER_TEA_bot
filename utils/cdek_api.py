"""
Клиент для работы с API СДЭК (CDEK).

Предоставляет асинхронный клиент CDEKClient, который автоматически
управляет OAuth-аутентификацией: получает, кэширует и обновляет
access token при необходимости. Используется для интеграции с
сервисом СДЭК, например, для получения списка пунктов выдачи (ПВЗ).
"""

import os
import time
import httpx
from dotenv import load_dotenv
from config import CDEK_BASE_URL
from logger_config import setup_logger

load_dotenv()
logger = setup_logger()


class CDEKClient:
    """
    Клиент для взаимодействия с API СДЭК.

    Автоматически управляет получением и обновлением OAuth-токена,
    необходимого для аутентификации запросов к API СДЭК.
    """

    def __init__(self):
        """
        Инициализирует клиент СДЭК с данными из переменных окружения.

        Загружает client_id и client_secret из .env-файла,
        устанавливает базовый URL и сбрасывает токен.
        """
        self.client_id = os.getenv('CDEK_CLIENT_ID')
        self.client_secret = os.getenv('CDEK_CLIENT_SECRET')
        self.base_url = CDEK_BASE_URL
        self.access_token = None
        self.token_expires_at = 0

    async def _get_token(self) -> str:
        """
        Получает или возвращает действующий access token для API СДЭК.

        Если токен отсутствует или истёк, выполняется запрос к OAuth-эндпоинту
        для получения нового токена. Срок действия токена уменьшается на 60
        секунд для обеспечения запаса.

        Returns:
            str: Действующий access token.
        """
        now = time.time()
        if self.access_token and self.token_expires_at > now:
            return self.access_token

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f'{self.base_url}/oauth/token',
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data['access_token']
            self.token_expires_at = now + data['expires_in'] - 60
            logger.info('Логин обновлен.')
            return self.access_token

    async def get_city_code_by_name(self, city_name: str) -> int | None:
        """Получает city_code по названию города (через /location/cities)."""
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f'{self.base_url}/location/cities',
                params={'country_code': 'RU', 'city': city_name.strip()},
                headers={'Authorization': f'Bearer {token}'},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return data[0].get('code')
            return None

    async def get_pvz_by_city_code(self, city_code: int) -> list[dict]:
        """
        Получает список ПВЗ СДЭК по коду города.

        Args:
            city_code: Числовой код города из API СДЭК.

        Returns:
            Список словарей с ключами: code, name, address, address_comment.
            Пустой список при ошибке или отсутствии ПВЗ.
        """
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f'{self.base_url}/deliverypoints',
                params={
                    'city_code': city_code,
                    'country_code': 'RU',
                    'type': 'PVZ',
                    'lang': 'rus',
                    'size': 1000
                },
                headers={'Authorization': f'Bearer {token}'},
            )
            logger.info(f'Запрос ПВЗ, статус: {resp.status_code}')
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f'Получено ПВЗ: {len(data)}')
                return [
                    {
                        'code': pvz.get('code'),
                        'name': pvz.get('name'),
                        'address': pvz.get('address', '').strip(),
                        'address_comment': pvz.get('address_comment', ''),
                    }
                    for pvz in data
                ]
            else:
                logger.error(f'Ошибка API: {resp.text}')
            return []
