# from service.service_builder import ServiceBuilder
from sftools_service.sftools_service import SftoolsService


def create_middleware():
    return []

# this is for gunicorn
def get_app():
    # sftools_service = ServiceBuilder.build(
    #     SftoolsService,
    #     'sftools_service.configuration',
    #     middleware=create_middleware(),
    #     options={}
    # )

    sftools_service = SftoolsService()

    return sftools_service


# this is for waitress
app = get_app()
