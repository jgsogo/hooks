# coding=utf-8

from contextlib import contextmanager

from conans.client.command import Conan, CommandOutputer, Command


@contextmanager
def conan_command(output_stream):
    # This snippet reproduces code from conans.client.command.main, we cannot directly
    # use it because in case of error it is exiting the python interpreter :/
    conan_api, cache, user_io = Conan.factory()
    user_io.out._stream = output_stream
    outputer = CommandOutputer(user_io, cache)
    cmd = Command(conan_api, cache, user_io, outputer)
    try:
        yield cmd
    finally:
        conan_api._remote_manager._auth_manager._localdb.connection.close()  # Close sqlite3
