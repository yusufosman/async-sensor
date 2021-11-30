import asyncio
import pickle
import random
import time
import uuid
from asyncio.exceptions import TimeoutError
from pathlib import Path
from typing import Dict

from aiohttp import ClientConnectorError, ClientSession

REQUEST_ENDPOINT = "https://en6msadu8lecg.x.pipedream.net/states"
QUEUE_FILE_NAME = "dead_letter_queue.pkl"
REQUEST_TIMEOUT = 1
DEAD_LETTER_QUEUE = []


def save_object_to_file(path: str, python_object: object):
    """Save a python object to disk so that it can be retrieved later."""
    with open(path, "wb") as output:
        pickle.dump(python_object, output, pickle.HIGHEST_PROTOCOL)
        print("Successfully saved queue to file")


def load_state(path: str):
    """Load a pickle file from disk and populate the in-memory queue"""
    saved_state = Path(path)
    if saved_state.is_file():
        with open(path, "rb") as input:
            global DEAD_LETTER_QUEUE
            DEAD_LETTER_QUEUE = pickle.load(input)
            print("Successfully loaded queue from file")


def delete_file(path: str):
    """Delete a locally stored file."""
    saved_state = Path(path)
    if saved_state.is_file():
        saved_state.unlink()
        print(f"File {path} deleted")


class Sensor:
    def __init__(self):
        self.sensor_id = str(uuid.uuid4())
        print(f"Created sensor: {self.sensor_id}")

    def _event_type(self):
        event_types = ["nominal", "info", "warning", "error", "critical"]
        return random.choices(event_types, cum_weights=[60, 24, 10, 5, 1], k=1)[0]

    def do_work(self):
        time.sleep(random.uniform(0.1, 1.5))

    @property
    def state(self):
        return {
            "id": self.sensor_id,
            "event": {
                "type": self._event_type(),
                "readings": [
                    random.randint(0, 100),
                    random.randint(0, 100),
                    random.randint(0, 100),
                ],
            },
            "timestamp": int(time.time()),
        }


async def post(session: ClientSession, state: Dict):
    """Make a POST request.  Can be used asynchronously with multiple requests via asyncio.gather()"""
    async with session.post(
        REQUEST_ENDPOINT, json=state, timeout=REQUEST_TIMEOUT
    ) as response:
        return await response.json()


async def send_state(session: ClientSession, state: Dict):
    if DEAD_LETTER_QUEUE:
        tasks = []
        for old_state in DEAD_LETTER_QUEUE:
            task = asyncio.ensure_future(post(session=session, state=old_state))
            tasks.append(task)
        try:
            # send all post requests in parallel
            await asyncio.gather(*tasks)
        except (ClientConnectorError, TimeoutError):
            pass
        else:
            print("Queue sent to API")
            DEAD_LETTER_QUEUE.clear()
            print("Queue cleared")
            delete_file(QUEUE_FILE_NAME)
    try:
        await post(session=session, state=state)
    except (ClientConnectorError, TimeoutError):
        # add state to dead letter queue if there is no internet connection or if there is a timeout
        DEAD_LETTER_QUEUE.append(state.copy())
        save_object_to_file(path=QUEUE_FILE_NAME, python_object=DEAD_LETTER_QUEUE)
    else:
        print(f"State {state} sent to API")


async def main():
    sensor = Sensor()
    load_state(QUEUE_FILE_NAME)

    async with ClientSession() as session:
        while True:
            sensor.do_work()
            await send_state(session=session, state=sensor.state)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
