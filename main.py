from json import load

from core import kucoin_auto_sell, bybit_auto_sell
from utils import logger

if __name__ == '__main__':
    print('Donate (any evm) - 0xDEADf12DE9A24b47Da0a43E1bA70B8972F5296F2\n')

    with open('settings.json', 'r', encoding='utf-8-sig') as file:
        settings_json: dict = load(file)

    API_KEY: str = settings_json['api_key']
    API_SECRET: str = settings_json['api_secret']
    API_PASS_PHRASE: str = settings_json['api_pass_phrase']
    START_SALE_TIME: int = int(str(settings_json['start_sale_time'])[:10])
    SALE_PRICE: float = float(settings_json['sale_price'])
    THREADS: int = int(settings_json['threads'])
    REQUESTS_COUNT: int = int(settings_json['requests_count'])
    ENDPOINT_URL: str = settings_json['endpoint_url']
    PROXY_STR: str | None = settings_json['proxy']

    if not PROXY_STR:
        PROXY_STR: None = None

    cex_type: int = int(input('1. KuCoin\n'
                              '2. ByBit\n'
                              'Enter Your CEX Type: '))

    token_from: str = input('Enter Token From Name: ').lower()
    token_to: str = input('Enter Token To Name: ').lower()
    print('')

    if cex_type == 1:
        kucoin_auto_sell(api_key=API_KEY,
                         api_secret=API_SECRET,
                         api_pass_phrase=API_PASS_PHRASE,
                         token_from=token_from,
                         token_to=token_to,
                         start_sale_time=START_SALE_TIME,
                         sale_price=SALE_PRICE,
                         threads=THREADS,
                         requests_count=REQUESTS_COUNT,
                         endpoint_url=ENDPOINT_URL,
                         proxy_str=PROXY_STR)

    elif cex_type == 2:
        bybit_auto_sell(api_key=API_KEY,
                        api_secret=API_SECRET,
                        token_from=token_from,
                        token_to=token_to,
                        start_sale_time=START_SALE_TIME,
                        sale_price=SALE_PRICE,
                        threads=THREADS,
                        requests_count=REQUESTS_COUNT,
                        endpoint_url=ENDPOINT_URL,
                        proxy_str=PROXY_STR)

    logger.success(f'The Work Was Successfully Completed')
    input('\nPress Enter To Exit..')
