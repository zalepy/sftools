import os

output_directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")


def set_output_directory(output_dir: str) -> None:
    global output_directory
    output_directory = output_dir

def get_output_directory() -> str:
    global output_directory
    return output_directory

