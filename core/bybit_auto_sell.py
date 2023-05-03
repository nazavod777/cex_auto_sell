import asyncio
import hashlib
import hmac
from json import dumps, loads
from time import time

import aiohttp
from aiohttp_proxy import ProxyConnector

from utils import bypass_bybit_errors
from utils import logger


class ByBitAutoSell:
    def __init__(self,
                 api_key: str,
                 api_secret: str,
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
        self.token_from: str = token_from
        self.token_to: str = token_to
        self.start_sale_time: int = start_sale_time
        self.sale_price: float = sale_price
        self.threads: int = threads
        self.requests_count: int = requests_count
        self.endpoint_url: str = endpoint_url
        self.proxy_str: str | None = proxy_str

    async def make_auth(self,
                        request_data: dict | str | None = None) -> dict:
        current_timestamp: int = int(time() * 10 ** 3)
        str_to_sign: str = str(current_timestamp) + str(self.api_key) + '5000'

        if request_data:
            if type(request_data) == dict:
                str_to_sign += dumps(request_data)

            elif type(request_data) == str:
                str_to_sign += request_data

        signature: bytes = hmac.new(
            bytes(self.api_secret, "utf-8"),
            str_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        headers: dict = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": str(current_timestamp),
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-RECV-WINDOW": str(5000),
            "Content-Type": "application/json"
        }

        return headers

    async def get_target_coin_balance(self,
                                      session: aiohttp.client.ClientSession) -> float | None:
        current_headers: dict = await self.make_auth(request_data=f'accountType=SPOT&coin={self.token_from}')
        session.headers.update(current_headers)

        response_text: str = await bypass_bybit_errors(current_function=session.get,
                                                       url=f'{self.endpoint_url}/v5/account/wallet-balance',
                                                       params={
                                                           'accountType': 'SPOT',
                                                           'coin': self.token_from
                                                       })

        for current_balance in loads(response_text)['result']['list']:
            if current_balance['accountType'] == 'SPOT':
                if current_balance['coin']:
                    return float(current_balance['coin'][0]['free'])

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
        current_headers: dict = await self.make_auth(request_data={
            'category': 'spot',
            'symbol': f'{self.token_from.upper()}{self.token_to.upper()}',
            'side': 'Sell',
            'orderType': 'Limit',
            'qty': str(token_from_balance),
            'price': str(self.sale_price)
        })
        session.headers.update(current_headers)

        response_text: str = await bypass_bybit_errors(current_function=session.post,
                                                       url=f'{self.endpoint_url}/v5/order/create',
                                                       json={
                                                           'category': 'spot',
                                                           'symbol': f'{self.token_from.upper()}{self.token_to.upper()}',
                                                           'side': 'Sell',
                                                           'orderType': 'Limit',
                                                           'qty': str(token_from_balance),
                                                           'price': str(self.sale_price)
                                                       })

        logger.success(f'Order Id: {loads(response_text)["result"]["orderId"]}')

    async def wait_start_sale_time(self,
                                   session: aiohttp.client.ClientSession) -> None:

        while True:
            response_text: str = await bypass_bybit_errors(current_function=session.get,
                                                           url=f'{self.endpoint_url}/v3/public/time')

            if int(str(loads(response_text)['result']['timeSecond'])[:10]) >= self.start_sale_time:
                return

            logger.info(
                str(self.start_sale_time - int(str(loads(response_text)['result']['timeSecond'])[:10])) + ' sec.')

    async def get_token_base_precision(self,
                                       session: aiohttp.client.ClientSession) -> float | None:
        current_headers: dict = await self.make_auth()
        session.headers.update(current_headers)

        response_text: str = await bypass_bybit_errors(current_function=session.get,
                                                       url=f'{self.endpoint_url}/spot/v3/public/symbols')

        for current_token in loads(response_text)['result']['list']:
            if current_token['baseCoin'].upper() == self.token_from.upper() \
                    and current_token['quoteCoin'].upper() == self.token_to.upper():
                return float(current_token['basePrecision'])

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

            token_base_precision: float = await self.get_token_base_precision(session=session)

            if not token_base_precision:
                logger.error(f'Error When Getting Base Precision: {self.token_from.upper()}, Using 0.1')
                token_base_precision: float = 0.1

            token_from_balance: float = round(token_from_balance, len(str(token_base_precision).split('.')[-1]))
            logger.info(f'{self.token_from.upper()} - {token_from_balance}')

            await self.run_tasks(session=session,
                                 token_from_balance=token_from_balance)


def bybit_auto_sell(api_key: str,
                    api_secret: str,
                    token_from: str,
                    token_to: str,
                    start_sale_time: int,
                    sale_price: float,
                    threads: int,
                    requests_count: int,
                    endpoint_url: str,
                    proxy_str: str | None) -> None:
    asyncio.run(ByBitAutoSell(api_key=api_key,
                              api_secret=api_secret,
                              token_from=token_from,
                              token_to=token_to,
                              start_sale_time=start_sale_time,
                              sale_price=sale_price,
                              threads=threads,
                              requests_count=requests_count,
                              endpoint_url=endpoint_url,
                              proxy_str=proxy_str).main_work())
