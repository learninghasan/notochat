"""Run a persistent worker process beside the API: python worker.py [--once]."""
import argparse
import asyncio
import logging
from sqlalchemy import select
from server import app as gateway,registry


async def tick():
    apps=[gateway.legacy]
    with gateway.engine.connect() as c:
        organizations=list(c.execute(select(registry.c.organization_id)).scalars())
    for org in organizations:
        try:apps.append(await asyncio.to_thread(gateway.workspace,org))
        except Exception:logging.exception('Business workspace initialization failed')
    total=0
    for app in apps:
        try:total+=len(await app.state.run_jobs())
        except Exception:logging.exception('Workspace job processing failed')
    return total


async def main(once=False):
    while True:
        count=await tick()
        if once:
            print(f'Processed {count} draft jobs. No customer messages sent.');return
        await asyncio.sleep(5)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true')
    asyncio.run(main(parser.parse_args().once))
