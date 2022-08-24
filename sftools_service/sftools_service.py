import logging

import falcon

from sftools_service.api.test_resource import TestResource


class SftoolsService:
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        # self._resources = resources
        self._entry_point = falcon.App()
        # for uri, resource in self._resources.items():
        #     self.entry_point.add_route(uri, resource)

        self._entry_point.add_route('/test', TestResource())

    @property
    def entry_point(self):
        return self._entry_point

    # # not sure if this is needed
    # def serve(self, port, host='127.0.0.1'):
    #     return self._entry_point

    def __call__(self, *args, **kwargs):
        if args:
            return self._entry_point(*args, **kwargs)

        return self._entry_point
