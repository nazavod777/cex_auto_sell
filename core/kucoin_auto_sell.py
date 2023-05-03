import asyncio
import base64
import hashlib
import hmac
import math
from json import dumps, loads
from time import time
from uuid import uuid4

import aiohttp
from aiohttp_proxy import ProxyConnector

from exceptions import InvalidRequestIp
from utils import bypass_kucoin_errors
from utils import logger


class KuCoinAutoSell:
    def __init__(self,
                 api_key: str,
                 api_secret: str,
                 api_pass_phrase: str,
                 token_from: str,
                 token_to: str,
                 start_sale_time: int,
                 sale_price: float,
                 threads: int,
                 requests_count: int,
                 endpoint_url: str,
                 proxy_str: str | None):
        self.api_key: str = api_key
        self.api_secret: str = api_secret
        self.api_pass_phrase: str = api_pass_phrase
        self.token_from: str = token_from
        self.token_to: str = token_to
        self.start_sale_time: int = start_sale_time
        self.sale_price: float = sale_price
        self.threads: int = threads
        self.requests_count: int = requests_count
        self.endpoint_url: str = endpoint_url
        self.proxy_str: str | None = proxy_str

    async def make_auth(self,
                        request_url: str,
                        request_type: str,
                        request_data: dict | None = None) -> dict:
        request_type: str = request_type.upper()
        current_timestamp: int = int(time() * 1000)
        str_to_sign: str = str(current_timestamp) + request_type + request_url

        if request_data:
            str_to_sign += dumps(request_data)

        signature: bytes = base64.b64encode(
            hmac.new(self.api_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
        passphrase: bytes = base64.b64encode(
            hmac.new(self.api_secret.encode('utf-8'), self.api_pass_phrase.encode('utf-8'), hashlib.sha256).digest())

        headers: dict = {
            "KC-API-SIGN": signature.decode(),
            "KC-API-TIMESTAMP": str(current_timestamp),
            "KC-API-KEY": self.api_key,
            "KC-API-PASSPHRASE": passphrase.decode(),
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }

        return headers

    async def bypass_invalid_request_ip(self,
                                        target_function,
                                        session: aiohttp.client.ClientSession,
                                        request_url: str,
                                        request_type: str,
                                        request_data: dict | None = None) -> dict:
        try:
            current_headers: dict = await self.make_auth(request_url=request_url,
                                                         request_type=request_type,
                                                         request_data=request_data)
            session.headers.update(current_headers)

            response_text: str = await bypass_kucoin_errors(current_function=target_function,
                                                            url=f'{self.endpoint_url}{request_url}',
                                                            json=request_data)

            return loads(response_text)

        except InvalidRequestIp:
            return await self.bypass_invalid_request_ip(session=session,
                                                        target_function=target_function,
                                                        request_url=request_url,
                                                        request_type=request_type,
                                                        request_data=request_data)

    async def get_target_coin_balance(self,
                                      session: aiohttp.client.ClientSession) -> float | None:
        account_balances: dict = await self.bypass_invalid_request_ip(target_function=session.get,
                                                                      session=session,
                                                                      request_url='/api/v1/accounts',
                                                                      request_type='GET')

        for current_balance in account_balances['data']:
            if current_balance['currency'].lower() == self.token_from and current_balance['type'] == 'trade':
                return float(current_balance['balance'])

        return None

    @staticmethod
    async def worker(semaphore, current_task) -> None:
        async with semaphore:
            await current_task

    async def run_tasks(self,
                        session: aiohttp.client.ClientSession,
                        token_from_balance: float) -> None:
        semaphore = asyncio.Semaphore(value=self.threads)

        tasks = [
            self.worker(semaphore=semaphore,
                        current_task=self.send_sell_request(
                            session=session,
                            token_from_balance=token_from_balance))
            for _ in range(self.requests_count)
        ]

        await self.wait_start_sale_time(session=session)

        await asyncio.gather(*tasks)

    async def send_sell_request(self,
                                session: aiohttp.client.ClientSession,
                                token_from_balance: float) -> None:
        response_text: dict = await self.bypass_invalid_request_ip(session=session,
                                                                   target_function=session.post,
                                                                   request_url='/api/v1/orders',
                                                                   request_type='POST',
                                                                   request_data={
                                                                       'side': 'sell',
                                                                       'symbol': f'{self.token_from.upper()}-{self.token_to.upper()}',
                                                                       'type': 'limit',
                                                                       'size': f'{token_from_balance:.9f}',
                                                                       'clientOid': str(uuid4()),
                                                                       'price': str(self.sale_price)
                                                                   })

        logger.success(f'Order Id: {response_text["data"]["orderId"]}')

    async def wait_start_sale_time(self,
                                   session: aiohttp.client.ClientSession) -> None:

        while True:
            response_text: dict = await bypass_kucoin_errors(current_function=session.get,
                                                             url=f'{self.endpoint_url}/api/v1/timestamp')
            if int(str(loads(response_text)['data'])[:10]) >= self.start_sale_time:
                return

            logger.info(str(self.start_sale_time - int(str(loads(response_text)['data'])[:10])) + ' sec.')

    async def get_token_base_increment(self,
                                       session: aiohttp.client.ClientSession) -> float | None:
        response_text: dict = await self.bypass_invalid_request_ip(target_function=session.get,
                                                                   request_url='/api/v2/symbols',
                                                                   session=session,
                                                                   request_type='GET')

        for current_token in response_text['data']:
            if current_token['baseCurrency'].upper() == self.token_from.upper() \
                    and current_token['quoteCurrency'].upper() == self.token_to.upper():
                return float(current_token['baseIncrement'])

        return None

    async def main_work(self) -> None:
        if self.proxy_str:
            connector = ProxyConnector.from_url(self.proxy_str)

        else:
            connector = None

        async with aiohttp.ClientSession(connector=connector) as session:
            token_from_balance: float | None = await self.get_target_coin_balance(session=session)

            if not token_from_balance:
                logger.error(f'Zero Token Balance: {self.token_from.upper()}')
                return

            token_base_precision: float = await self.get_token_base_increment(session=session)

            if not token_base_precision:
                logger.error(f'Error When Getting Base Precision: {self.token_from.upper()}, Using 0.1')
                token_base_precision: float = 0.1

            token_from_balance: float = math.floor(
                token_from_balance * 10 ** len(str(token_base_precision).split('.')[1])) / 10 ** len(
                str(token_base_precision).split('.')[1])

            logger.info(f'{self.token_from.upper()} - {token_from_balance}')

            await self.run_tasks(session=session,
                                 token_from_balance=token_from_balance)


def kucoin_auto_sell(api_key: str,
                     api_secret: str,
                     api_pass_phrase: str,
                     token_from: str,
                     token_to: str,
                     start_sale_time: int,
                     sale_price: float,
                     threads: int,
                     requests_count: int,
                     endpoint_url: str,
                     proxy_str: str | None) -> None:
    asyncio.run(KuCoinAutoSell(api_key=api_key,
                               api_secret=api_secret,
                               api_pass_phrase=api_pass_phrase,
                               token_from=token_from,
                               token_to=token_to,
                               start_sale_time=start_sale_time,
                               sale_price=sale_price,
                               threads=threads,
                               requests_count=requests_count,
                               endpoint_url=endpoint_url,
                               proxy_str=proxy_str).main_work())
