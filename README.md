## Instructions ##

1. Make sure you are in the root directory for the project.
2. Run `pip install -r requirements.txt`
3. Run the application via the command `python run_sensor.py`
4. Run tests via the command `pytest`


## Notes ##

1. This code was created with Python 3.8
2. The application can be run in online or offline mode automatically. 
3. You can test this functionality by turning off your wifi, starting the application, viewing the output for several seconds, and then turning your wifi back on.
4. While in offline mode, all states are stored in an in-memory queue (`DEAD_LETTER_QUEUE`) as well as on disk in case the system is shut down unexpectedly.
5. The application will automatically attempt to load the `dead_letter_queue.pkl` file into memory if it exists in the app root directory.
6. The use of aiohttp/asyncio is only beneficial while posting the dead letter queue to the API, since more than one request can be executed at the same time.  Asyncio/aiohttp doesn't provide much performance gain for single requests.

## Potential Improvements ##

1. Append to `dead_letter_queue.pkl` file instead of re-creating it every time.
2. (minor) Use `try` and `except` instead of if statements in the file loading functions.
3. Combine the POST of the queue with the POST of the current state so we have one POST, not two.
4. Add test for simulating internet connection returning while the application is running.
