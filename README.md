# settings.json  
**api_key** - api_key аккаунта KuCoin/ByBit (_выдается после создания API_)  
**api_secret** - api_secret аккаунта KuCoin/ByBit (_выдается после создания API_)  
**api_pass_phrase** - api_pass_phrase аккаунта KuCoin (_создается перед созданием API_). При использовании ByBit оставлять пустым  

**start_sale_time** - время, в которое начинать отправлять запросы на продажу монет (_UNIX-формат_)  

**sale_price** - цена, по которой будут выставляться ордера на продажу

**threads** - количество потоков, с которых одновременно будут начинать слаться запросы на продажу  
**requests_count** - общее количество запросов для отправки  

**endpoint_url** - https://api.kucoin.com для Kucoin // https://api.bybit.com для ByBit


**proxy** - прокси (_при необходимости_). Формат загрузки - **_type://user:pass@ip:port_**, либо **_type://ip:port_**. Можно оставить пустым