import time
import uuid
from pathlib import Path

import pytest
from aiohttp import ClientSession, ClientConnectorError
import run_sensor


class MockResponse:
    def __init__(self, json, status):
        self._json = json
        self.status = status

    async def json(self):
        return self.json

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __aenter__(self):
        return self


@pytest.fixture(autouse=True)
def override_queue_file_name(file_name_for_test):
    run_sensor.QUEUE_FILE_NAME = file_name_for_test


@pytest.fixture
def file_name_for_test():
    return "test_dead_letter_queue.pkl"


@pytest.fixture(autouse=True)
def cleanup_files(file_name_for_test):
    """Clean up temp files after each test."""
    yield
    run_sensor.delete_file(file_name_for_test)


@pytest.fixture
def mocked_endpoint(mocker):
    data = {}
    resp = MockResponse(data, 200)
    return mocker.patch("aiohttp.ClientSession.post", return_value=resp)


@pytest.fixture
def mocked_endpoint_no_internet(mocker):
    return mocker.patch(
        "aiohttp.ClientSession.post", side_effect=ClientConnectorError(None, OSError())
    )


@pytest.fixture
def queue_data():
    return [
        {
            "id": "2b1f5982-0382-49e2-9817-a54d77a47265",
            "event": {"type": "nominal", "readings": [50, 96, 25]},
            "timestamp": 1634720018,
        },
        {
            "id": "2b1f5982-0382-49e2-9817-a54d77a47265",
            "event": {"type": "nominal", "readings": [78, 83, 100]},
            "timestamp": 1634720023,
        },
    ]


@pytest.fixture
def populated_queue(queue_data):
    run_sensor.DEAD_LETTER_QUEUE.extend(queue_data)


@pytest.fixture
def blank_queue():
    run_sensor.DEAD_LETTER_QUEUE = []


@pytest.fixture
async def session():
    async with ClientSession(raise_for_status=True) as session:
        yield session


@pytest.fixture
def state():
    return {
        "id": uuid.uuid4(),
        "event": {
            "type": "nominal",
            "readings": [
                10,
                20,
                30,
            ],
        },
        "timestamp": int(time.time()),
    }


@pytest.fixture
def saved_state_file(queue_data):
    run_sensor.save_object_to_file(
        path=run_sensor.QUEUE_FILE_NAME, python_object=queue_data
    )


@pytest.mark.asyncio
async def test_send_state_with_queue(
    mocked_endpoint, session, state, populated_queue, queue_data
):
    """Test all items in the queue are sent to the API, as well as the current state."""
    # given ...
    # ... a client session
    # ... a populated queue
    # ... a mocked API endpoint

    # when ... we send the state to the API
    await run_sensor.send_state(session=session, state=state)

    # then ...
    # ... three separate calls are made to the API (two from the queue, one from current state)
    mock_calls = mocked_endpoint.call_args_list
    assert len(mock_calls) == 3

    # ... the data sent to the API is as expected
    assert mock_calls[0].args[0] == run_sensor.REQUEST_ENDPOINT
    assert mock_calls[0][1]["json"] == queue_data[0]

    assert mock_calls[1].args[0] == run_sensor.REQUEST_ENDPOINT
    assert mock_calls[1][1]["json"] == queue_data[1]

    assert mock_calls[2].args[0] == run_sensor.REQUEST_ENDPOINT
    assert mock_calls[2][1]["json"] == state

    # ... the queue is cleared
    assert len(run_sensor.DEAD_LETTER_QUEUE) == 0


@pytest.mark.asyncio
async def test_send_state_no_internet(
    mocked_endpoint_no_internet,
    session,
    state,
    populated_queue,
    queue_data,
):
    """Simulate a scenario where no internet is available."""
    # given ...
    # ... a client session
    # ... a populated queue
    # ... a mocked API endpoint that throws a ClientConnectorError exception
    assert len(run_sensor.DEAD_LETTER_QUEUE) == 2

    # when ... the state is attempted to be sent over the internet
    await run_sensor.send_state(session=session, state=state)

    # then ...
    # ... three separate calls are made to the API (two from the queue, one from current state)
    mock_calls = mocked_endpoint_no_internet.call_args_list
    assert len(mock_calls) == 3

    # ... the data sent to the API is as expected
    assert mock_calls[0].args[0] == run_sensor.REQUEST_ENDPOINT
    assert mock_calls[0][1]["json"] == queue_data[0]

    assert mock_calls[1].args[0] == run_sensor.REQUEST_ENDPOINT
    assert mock_calls[1][1]["json"] == queue_data[1]

    assert mock_calls[2].args[0] == run_sensor.REQUEST_ENDPOINT
    assert mock_calls[2][1]["json"] == state

    # ... the queue size has increased by one
    assert len(run_sensor.DEAD_LETTER_QUEUE) == 3
    # ... the new item in the queue is the latest state
    assert run_sensor.DEAD_LETTER_QUEUE[2] == state

    # ... the save file was created
    saved_file = Path(run_sensor.QUEUE_FILE_NAME)
    assert saved_file.is_file()


@pytest.mark.asyncio
async def test_load_state(blank_queue, queue_data, saved_state_file):
    """Simulate a scenario where the state needs to be loaded from a file."""
    # given ...
    # ... a saved state file with two states saved
    # ... an empty dead letter queue in memory
    assert len(run_sensor.DEAD_LETTER_QUEUE) == 0

    # when ... we load the state from file
    run_sensor.load_state(run_sensor.QUEUE_FILE_NAME)

    # then ...
    # ...the in memory queue is populated with the expected states
    assert len(run_sensor.DEAD_LETTER_QUEUE) == 2
    assert run_sensor.DEAD_LETTER_QUEUE == queue_data
