import logging
import asyncio
import time

import requests

from aiohttp import web, ClientSession

import requests.packages.urllib3

# Enable logging an INFO level so can see requests.

logging.basicConfig(level=logging.INFO)

# Disable all the noisy logging that request module outputs, including
# complaints about self signed certificates, which is what REST API for
# OpenShift when used internally has.

logging.getLogger('requests').setLevel(logging.CRITICAL)
requests.packages.urllib3.disable_warnings()

# The aiohttp application.

app = web.Application()

loop = asyncio.get_event_loop()

# Our REST API endpoints.

siege_running = False
siege_end_time = None
siege_engines = 0

async def battering_ram(url, delay):
    global siege_running
    global siege_end_time
    global siege_engines

    siege_engines += 1

    logging.info('Start battering ram %d.', siege_engines)

    while siege_running and time.time() < siege_end_time: 
        await asyncio.sleep(delay)

        try:
            async with ClientSession() as session:
                async with session.get(url, timeout=15.0) as response:
                    data = await response.read()
        except Exception:
            logging.exception('Request failed.')

    logging.info('Stop battering ram %d.', siege_engines)

    siege_engines -= 1

    if siege_engines == 0:
        siege_end_time = None

async def lay_siege(wait, url, delay):
    global siege_running

    asyncio.ensure_future(battering_ram(url, delay), loop=loop)

    while siege_running and siege_end_time and time.time() < siege_end_time:
        await asyncio.sleep(wait)
        asyncio.ensure_future(battering_ram(url, delay), loop=loop)

    siege_running = False

async def siege_start(request):
    global siege_running
    global siege_end_time

    if siege_running or siege_end_time:
        return web.json_response('Siege already running.')

    service = request.rel_url.query['service']

    duration = float(request.rel_url.query.get('duration', '600'))
    clients = int(request.rel_url.query.get('clients', '3'))
    delay = float(request.rel_url.query.get('delay', '0.25'))

    siege_end_time = time.time() + duration

    siege_running = True

    url = 'http://%s:8080/ws/siege/' % service

    logging.info('Laying siege to %s.', service)

    wait = duration / clients

    asyncio.ensure_future(lay_siege(wait, url, delay), loop=loop)

    return web.json_response('OK')

app.router.add_get('/ws/siege/start', siege_start)

async def siege_stop(request):
    global siege_running

    if not siege_running:
        return web.json_response('Siege is not running.')

    siege_running = False

    return web.json_response('OK')

app.router.add_get('/ws/siege/stop', siege_stop)

async def healthz(request):
    return web.json_response('OK')

app.router.add_get('/ws/healthz', healthz)

async def index(request):
    return web.HTTPFound('/index.html')

app.router.add_get('/', index)

app.router.add_static('/', 'static')

# Main application startup.

if __name__ == '__main__':
    # Run the aiohttpd server.

    web.run_app(app)
