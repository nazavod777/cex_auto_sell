from json import loads

from utils import logger


async def bypass_bybit_errors(current_function,
                              **kwargs) -> any:
    response = None

    try:
        response = await current_function(**kwargs)

        if loads(await response.text())['retMsg'] != 'OK':
            logger.error(f'Wrong Response: {await response.text()}')

            return await bypass_bybit_errors(current_function=current_function,
                                             **kwargs)

        return await response.text()

    except Exception as error:
        if response:
            logger.error(f'Unexpected Error: {error}, response text: {await response.text()}')

        else:
            logger.error(f'Unexpected Error: {error}')

        return await bypass_bybit_errors(current_function=current_function,
                                         **kwargs)
