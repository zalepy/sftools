import logging

import falcon


class TestResource:
    def __init__(self, logger=None):
        self._logger = logger or logging.getLogger(__name__)

    def on_get(self, request, response):
        response.status = falcon.HTTP_OK
        response_json = {
            'links': {
                'self': request.uri
            },
            'data': 'This is a test'
        }

        response.media = response_json
