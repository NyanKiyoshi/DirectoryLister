# This script from http://github.com/NyanKiyoshi/directory-lister/ is under MIT license with the following terms:
#
# The MIT License (MIT)
#
# Copyright (c) 2015 NyanKiyoshi - https://github.com/NyanKiyoshi
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# Email:  wibberry@gmail.com
# URL:    https://github.com/NyanKiyoshi
# Author: NyanKiyoshi
#
#
# This script also uses a script by Ron Rothman under the MIT license:
#    https://github.com/RonRothman/mtwsgi/blob/master/LICENSE
# from https://github.com/RonRothman/mtwsgi/blob/master/mtwsgi.py


from sys import version_info

if version_info <= (2, 6) or version_info.major > 2:
    class VersionError(BaseException):
        pass
    raise VersionError('this script requires a Python2 version greater or equal than 2.7.')

import sqlite3
import socket
import re
import os.path
import multiprocessing.pool
import mimetypes
import json
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
from urlparse import parse_qs
from urllib import quote, unquote
from time import gmtime, strftime
from string import Template
from stat import *
from os import listdir, getcwd, stat, fstat
from operator import itemgetter
from math import log, floor
from inspect import getargspec
from hashlib import md5, sha1
from fnmatch import fnmatch
from Cookie import SimpleCookie
from cgi import escape
from argparse import ArgumentParser, FileType


DEFAULT_BODY = """\
<!DOCTYPE HTML>
<html>
    <head>
        <meta charset="UTF-8" />
        <title>$CURRENT_DIRECTORY</title>
        $CSS
        $JS
    </head>
    <body>
        <div id="content" class="container">
            {{ if error }}
                $ERROR_MESSAGE
            {{ endif }}
            {{ if no error }}
                <table>
                    <thead>
                        <tr>
                            <th colspan="4" class="th-title">
                                <h2>$CURRENT_DIRECTORY</h2>
                            </th>
                        </tr>
                        <tr>
                            <!-- TODO: arrows -->
                            <th class=""><a href="$TOGGLE_SORTING_NAME">File</a></th>
                            <th><a href="$TOGGLE_SORTING_SIZE">Size</a></th>
                            <th class="nowrap"><a href="$TOGGLE_SORTING_MODIFICATION">Date Modified</a></th>
                            <th></th>
                        </tr>
                        </tr>
                    </thead>
                    <tbody>
                        {{ loop }}
                            <tr>
                                <td class="full-width"><a href="$FILE_LINK">
                                    {{ if not file }}
                                        $FILE_NAME/
                                    {{ endif not file }}
                                    {{ if file }}
                                        $FILE_NAME
                                    {{ endif file }}
                                </a></td>
                                <td>$FILE_SIZE</td>
                                <td class="nowrap">$FILE_MODIFICATION</td>
                                {{ if file }}
                                    <td class="nowrap">
                                        <a class="more" href="$FILE_LINK?hashes" target="_blank">
                                            (+)
                                        </a>
                                    </td>
                                {{ endif file }}
                                {{ if not file }}
                                    <td class="nowrap"></td>
                                {{ endif not file }}
                                <!-- TODO -->
                            </tr>
                        {{ endloop }}
                    </tbody>
                </table>
            {{ endif }}
        </div>
    </body>
</html>
"""

DEFAULT_CSS = """\
h2 {
    font-size: 150%;
    margin-top: 0px;
    font-weight: 700;
    font-family: "Roboto Slab","ff-tisa-web-pro","Georgia",Arial,sans-serif;
}
#content {
    padding-bottom: 100px;
    max-width: 1080px;
    margin: 0 auto;
}
.th-title {
    background: rgba(0, 0, 0, 0.1) none repeat scroll 0% 0%;
}
.full-width { width: 100% }
.nowrap { white-space: nowrap}
.more { color: #787878 }
tr {
    /* border-top: 1px solid #CCC;*/
    border: 1px solid #DDD;
}
tbody tr:hover {
    background-color: rgba(0,0,0,0.1);
}
td {
    vertical-align: top;
}
.th-line-title {
    background: none repeat scroll 0% 0% rgba(0, 0, 0, 0.1);
}
table {
    margin: 0 auto;
    border-collapse: collapse;
    border-spacing: 0;
}
table th {
    font-weight: bold;
}
table th, table td {
    padding: 6px 13px;
}
h2 {
    font-size: 150%;
    margin: 0;
}
a { text-decoration: none; color: #0063c6 }
a:hover { color: #02417f }
"""
DEFAULT_JAVASCRIPT = ''
ERRORS = dict(
    NOT_FOUND='Invalid file or directory',
    HASHING_DISABLED='Hashing disabled.',
    FILE_TOO_LARGE='File is too large.'
)


class ThreadPoolWSGIServer(WSGIServer):
    """
    This class from https://github.com/RonRothman/mtwsgi/blob/master/mtwsgi.py is under MIT License and belongs
        to Ron Rothman, full license available here: https://github.com/RonRothman/mtwsgi/blob/master/LICENSE.
    ----
    WSGI-compliant HTTP server. Dispatches requests to a pool of threads.
    """
    def __init__(self, thread_count=None, *args, **kwargs):
        """If 'thread_count' == None, we'll use multiprocessing.cpu_count() threads."""
        WSGIServer.__init__(self, *args, **kwargs)
        self.pool = multiprocessing.pool.ThreadPool(thread_count)

    # Inspired by SocketServer.ThreadingMixIn.
    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
            self.shutdown_request(request)
        except socket.error:
            self.handle_error(request, client_address)
            self.shutdown_request(request)

    def process_request(self, request, client_address):
        self.pool.apply_async(self.process_request_thread, args=(request, client_address))


def make_multithread_server(host, port, app, thread_count=None, handler_class=WSGIRequestHandler):
    """
    This function from https://github.com/RonRothman/mtwsgi/blob/master/mtwsgi.py is under MIT License and
        belongs to Ron Rothman, full license available here: https://github.com/RonRothman/mtwsgi/blob/master/LICENSE.
    ----
    Creates a new WSGI server listening on `host` and `port` for `app`
    """
    h = ThreadPoolWSGIServer(thread_count, (host, port), handler_class)
    h.set_app(app)
    return h


class InvalidStatusCode(BaseException):
    pass


class InvalidConfigurationArgument(BaseException):
    pass


class PrepareResponse:
    def __init__(self, start_response, response_code=200, headers=None, body=None):
        """
        :param start_response:
        `start_response` must be an instance from `wsgiref.simple_server.ServerHandler`
            (wsgiref.handlers.BaseHandler.start_response).
        :param headers:
        :param response_code:
        :return:
        """
        self.headers = headers or {}
        self.status_code = response_code
        self.start_response = start_response
        self.content = body

    def status(self):
        """
        Sets the good status code from an integer code (e.g. 200 will be '200 OK).
        :return:
        """
        # https://tools.ietf.org/html/rfc7231#page-49
        response_code = {
            100: '100 Continue',
            101: '101 Switching Protocols',
            200: '200 OK',
            201: '201 Created',
            202: '202 Accepted',
            203: '203 Non-Authoritative Information',
            204: '204 No Content',
            205: '205 Reset Content',
            206: '206 Partial Content',
            300: '300 Multiple Choices',
            301: '301 Moved Permanently',
            302: '302 Found',
            303: '303 See Other',
            304: '304 Not Modified',
            305: '305 Use Proxy',
            307: '307 Temporary Redirect',
            400: '400 Bad Request',
            401: '401 Unauthorized',
            402: '402 Payment Required',
            403: '403 Forbidden',
            404: '404 Not Found',
            405: '405 Method Not Allowed',
            406: '406 Not Acceptable',
            407: '407 Proxy Authentication Required',
            408: '408 Request Timeout',
            409: '409 Conflict',
            410: '410 Gone',
            411: '411 Length Required',
            412: '412 Precondition Failed',
            413: '413 Payload Too Large',
            414: '414 URI Too Long',
            415: '415 Unsupported Media Type',
            416: '416 Range Not Satisfiable',
            417: '417 Expectation Failed',
            426: '426 Upgrade Required',
            500: '500 Internal Server Error',
            501: '501 Not Implemented',
            502: '502 Bad Gateway',
            503: '503 Service Unavailable',
            504: '504 Gateway Timeout',
            505: '505 HTTP Version Not Supported',
        }.get(self.status_code)
        if not response_code:
            raise InvalidStatusCode
        return response_code

    def add_headers(self, headers):
        """
        Add the given headers.
        :param headers:
        :return:
        """
        self.headers.update(headers)

    def remove_headers(self, *args):
        """
        Remove the headers key given.
        :param args:
        :return:
        """
        [self.headers.pop(h) for h in args]

    def get_headers(self):
        """
        Returns headers ready to be used as a list of tuples (key, value).
        :return:
        """
        return self.headers.items()

    def send_response(self):
        status = self.status()
        if not self.content:
            self.content = status  # if no content, we return the HTTP status
        self.start_response(self.status(), self.get_headers())
        return self.content


class ListDirectory(object):
    def __init__(
            self,
            path=getcwd(),
            body=DEFAULT_BODY,
            css=DEFAULT_CSS,
            js=DEFAULT_JAVASCRIPT,
            date_format='%Y-%m-%d %H:%M:%S',
            binary_prefix=False,
            allow_access_to_hidden=False,
            hidden_files=None,
            database=':memory:',
            must_hash_files=True,
            max_file_size_to_hash=2.1 * 10**8,  # 200MiB
            keep_hashes_cache=True,
            hide_parent=False,
            resources_directory=None,
    ):
        self.error_regex = re.compile(r'{{\s*if error\s*}}(?P<CONTENT>.*?){{\s*endif\s*}}', re.S)
        self.no_error_regex = re.compile(r'{{\s*if no error\s*}}(?P<CONTENT>.*?){{\s*endif\s*}}', re.S)
        self.loop_regex = re.compile(r'{{\s*loop\s*}}(?P<CONTENT>.*?){{\s*endloop\s*}}', re.S)
        self.if_file = re.compile(r'{{\s*if file\s*}}(?P<CONTENT>.*?){{\s*endif file\s*}}', re.S)
        self.if_not_file = re.compile(r'{{\s*if not file\s*}}(?P<CONTENT>.*?){{\s*endif not file\s*}}', re.S)

        self.css_invalid_chars = re.compile('[^_a-zA-Z\-]+[^_a-zA-Z0-9-]*')

        self.working_path = [path + '/', path][path.endswith('/')]
        self.body = body
        self.date_format = date_format
        self.binary_prefix = binary_prefix

        self.resources_directory = resources_directory

        self.hidden = hidden_files or []
        self.allow_access_to_hidden = allow_access_to_hidden

        self.hide_parent = hide_parent

        self.must_hash, self.keep_hashes_cache = must_hash_files, keep_hashes_cache
        self.max_file_size_to_hash = max_file_size_to_hash

        self.css = css
        self.js = js

        if self.must_hash and self.keep_hashes_cache:
            self.sqlite_connection = sqlite3.connect(database, check_same_thread=False)
            self.sqlite_connection.text_factory = str
            self.cursor = self.sqlite_connection.cursor()
            self.cursor.executescript(
                """
                    drop table if exists files;
                    CREATE TABLE if not exists files (
                        path TEXT NOT NULL,
                        st_mtime INTEGER NOT NULL,
                        hashes VARCHAR NOT NULL,
                        PRIMARY KEY (path)
                    );
                """
            )

        self.is_hidden = lambda file_name: True if filter(None, [fnmatch(file_name, pat) for pat in self.hidden]) \
            else False  # returns True if must be hidden or False if not.

        mimetypes.init()
        self.mimetypes_list = mimetypes.types_map.copy()

    def __call__(self, environ, start_response):
        # plain text by default.
        response = PrepareResponse(
            start_response,
            response_code=200,
            headers={'Content-Type': 'text/plain', 'Access-Control-Allow-Origin': '*'})

        # if request method is not GET or HEAD we returns a 405 HTTP error.
        if environ['REQUEST_METHOD'] not in ('GET', 'HEAD'):
            response.status_code = 405
            response.headers['Content-Type'] = 'text/plain'
            return response.send_response()

        parsed_qs = parse_qs(environ['QUERY_STRING'], True)

        # We escape and quote by security.
        for q in parsed_qs.copy():
            query = []
            for i in parsed_qs[q]:
                query.append(quote(escape(i)))
            parsed_qs[quote(escape(q))] = query

        # if cookies allowed (more "beautiful"), we read them
        cookies_allowed = not parsed_qs.get('no-cookies')
        if cookies_allowed:
            cookies = SimpleCookie(environ.get('HTTP_COOKIE'))
        else:
            cookies = None

        if environ['PATH_INFO'] == '/':
            # /?css
            if 'css' in parsed_qs:
                response.add_headers(
                    {'Content-Type': 'text/css', 'Cache-Control': 'max-age=172800, proxy-revalidate'})
                response.content = self.css
                return response.send_response()
            # /?js
            elif 'js' in parsed_qs:
                response.add_headers(
                    {'Content-Type': 'text/javascript', 'Cache-Control': 'max-age=172800, proxy-revalidate'})
                response.content = self.js
                return response.send_response()
            # /?get
            elif 'get' in parsed_qs and self.resources_directory:
                # %2F
                file_name = unquote(parsed_qs['get'][0])
                # prevent access to parent directories
                if file_name.find('../') != -1 or file_name.startswith('/'):
                    response.status_code = 400
                    return response.send_response()
                path = self.resources_directory + file_name
                try:
                    f = open(path, 'rb')
                except IOError:
                    pass
                else:
                    try:
                        stats = fstat(f.fileno())
                        response.add_headers(
                            {
                                "Content-Type": self.mimetypes_list.get(os.path.splitext(path)[1]) or 'application/octet-stream',
                                "Content-Length": str(stats[ST_SIZE]),
                                "Last-Modified": str(stats[ST_MTIME]),
                            }
                        )
                        response.content = f
                        return response.send_response()
                    except IOError:
                        f.close()

        path = self.working_path + environ['PATH_INFO'][1:]
        response.add_headers({'Content-Type': 'text/html; charset=UTF-8'})
        template = dict(
            CURRENT_DIRECTORY=environ['PATH_INFO'],
            CSS='<link rel="stylesheet" href="/?css" type="text/css">',
            JS='<script type="text/javascript" src="/?js"></script>',
            SORTING_MODIFICATION='asc',
            SORTING_CREATION='asc',
            SORTING_SIZE='asc',
            SORTING_NAME='asc',
        )
        if cookies_allowed:
            template.update(
                dict(
                    TOGGLE_SORTING_MODIFICATION='?sort=ST_MTIME.ASC',
                    TOGGLE_SORTING_CREATION='?sort=ST_CTIME.ASC',
                    TOGGLE_SORTING_SIZE='?sort=ST_SIZE.ASC',
                    TOGGLE_SORTING_NAME='?sort=NAME.ASC',
                )
            )
        else:
            template.update(
                dict(
                    TOGGLE_SORTING_MODIFICATION='?sort=ST_MTIME.ASC&no-cookies',
                    TOGGLE_SORTING_CREATION='?sort=ST_CTIME.ASC&no-cookies',
                    TOGGLE_SORTING_SIZE='?sort=ST_SIZE.ASC&no-cookies',
                    TOGGLE_SORTING_NAME='?sort=NAME.ASC&no-cookies',
                )
            )

        # searching the sorting link to toggle
        current_sorting = parsed_qs.get('sort')  # (NAME|ST_MTIME|ST_CTIME|ST_SIZE)(.DESC|.ASC)?
        if not current_sorting:  # if None
            if cookies_allowed:
                current_sorting = cookies['sort'].value if 'sort' in cookies else 'NAME'
            else:
                current_sorting = 'NAME'
        # If user has asked to change the sorting and allows the cookie usage instead of the query strings we save the
        #   chose sorting
        else:
            current_sorting = escape(current_sorting[0])
            if cookies_allowed:
                cookies['sort'] = current_sorting
                response.headers['Set-Cookie'] = cookies['sort'].OutputString()
        _sorting = current_sorting.upper().split('.', 2)  # e.g. [ST_MTIME, ASC]
        if _sorting and _sorting[0]:
            if not len(_sorting) > 1:
                _sorting.append('DESC')
            _available_sorting = dict(
                ST_MTIME=('TOGGLE_SORTING_MODIFICATION', 'SORTING_MODIFICATION'),
                ST_CTIME=('TOGGLE_SORTING_CREATION', 'SORTING_CREATION'),
                ST_SIZE=('TOGGLE_SORTING_SIZE', 'SORTING_SIZE'),
                NAME=('TOGGLE_SORTING_NAME', 'SORTING_NAME'),
            )
            template[_available_sorting.get(_sorting[0])[0]] = '?sort=%s.%s%s' % (
                _sorting[0] if _sorting[0] in _available_sorting.keys() else 'NAME',
                ((_sorting[1] == 'DESC') and 'ASC' or 'DESC'),  # if sorting = desc -> asc else -> desc
                '&no-cookies' if not cookies_allowed else ''
            )
            template[_available_sorting.get(_sorting[0])[1]] = (_sorting[1] == 'DESC' and 'DESC' or 'ASC')
            del _available_sorting
        del _sorting

        template['END_URL'] = (not cookies_allowed and ('?' + environ['QUERY_STRING']) or '')

        if os.path.isdir(path):
            if not path.endswith('/'):
                response.status_code = 301
                response.add_headers(
                    {
                        'Content-Type': 'text/plain',
                        'Location': environ['PATH_INFO'] + '/%s' % template['END_URL']
                    }
                )
                return response.send_response()

            # If directory is hidden and if the direct access is not allowed,
            #   we return Forbidden but we don't show, we just say "Invalid file or directory"
            if not self.allow_access_to_hidden:
                f = filter(None, environ['PATH_INFO'].split('/'))
                if f and self.is_hidden(f[-1]):
                    response.status_code = 404
                    response.content = Template(
                        self.rendering_error(ERROR_MESSAGE=ERRORS['NOT_FOUND'])).safe_substitute(**template)
                    return response.send_response()
            response.content = Template(
                self.list_dir(path=path, sorting=current_sorting, end_url=template['END_URL'])
            ).safe_substitute(**template)
            return response.send_response()

        # If file is hidden and if the direct access is not allowed,
        #   we return Forbidden but we don't show, we just say "Invalid file or directory"
        if not self.allow_access_to_hidden:
            _path = os.path.split(path)
            if _path and self.is_hidden(_path[-1]):
                response.status_code = 404
                response.content = Template(
                    self.rendering_error(ERROR_MESSAGE=ERRORS['NOT_FOUND'])).safe_substitute(**template)
                return response.send_response()
        try:
            f = open(path, 'rb')
        except IOError:
            response.status_code = 404
            response.content = Template(
                self.rendering_error(ERROR_MESSAGE=ERRORS['NOT_FOUND'])).safe_substitute(**template)
            return response.send_response()

        if 'hashes' in parsed_qs:
            # returns:
            #    - a 403 if hashing is disabled with as json:
            #       - {'message': 'Hashing disabled.',  'code': 0}
            #       - {'message': 'File is too large.', 'code': 1}
            #    - a 404 if the file is not found (returned in the above code)
            #    - a 200 with a JSON content if the file exists and if hashing is authorized
            response.add_headers({'Content-Type': 'application/json'})
            if not self.must_hash:
                response.status_code = 403
                response.content = '{"message": "%s",  "code": 0}' % ERRORS['HASHING_DISABLED']
                return response.send_response()

            content = self.hash_file(path, f)
            if not content:
                response.status_code = 403
                response.content = '{"message": "%s",  "code": 1}' % ERRORS['FILE_TOO_LARGE']
            else:
                response.content = content
            return response.send_response()
        try:
            stats = fstat(f.fileno())
            response.add_headers(
                {
                    "Content-Type": self.mimetypes_list.get(os.path.splitext(path)[1]) or 'application/octet-stream',
                    "Content-Length": str(stats[ST_SIZE]),
                    "Last-Modified": str(stats[ST_MTIME]),
                }
            )
            response.content = f
        except:
            f.close()
            raise
        return response.send_response()

    def convert_size(self, n_bytes):
        """
        Converts bytes into human readable using the binary or decimal prefix. It returns a result with the following
        format: "{NEW_VALUE}{UNIT_VALUE}". If the number of bytes is null (0), it returns `-`.

        :param n_bytes: The number of bytes.
        :type n_bytes int:
        :return:
        """
        if not n_bytes:
            return '0B'
        # using the binary prefix or the decimal one
        prefix, units = (1024, ['B', 'kiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']) \
            if self.binary_prefix else (1000, ['B', 'kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'])
        exponent = min(floor(log(n_bytes) / log(prefix)), len(units) - 1)
        return '%.2f%s' % ((n_bytes / prefix ** exponent), units[int(exponent)])

    def hash_file(self, path, opened_file):
        stats = fstat(opened_file.fileno())
        if stats[ST_SIZE] > self.max_file_size_to_hash:
            return

        st_mtime = stats[ST_MTIME]
        del stats

        if self.keep_hashes_cache:
            r = self.cursor.execute("SELECT hashes FROM files WHERE path=? AND st_mtime=?", (path, st_mtime)).fetchone()
            # we already hashed it! Then we just return the old results
            if r:
                return r[0]

        b_lines = opened_file.readlines()
        hashes = dict(md5=self.get_hash(b_lines, md5), sha1=self.get_hash(b_lines, sha1))
        if self.keep_hashes_cache:
            # We insert the hashes or we update them if the path already exists (if the modification time has changed)
            self.cursor.execute(
                "INSERT or REPLACE INTO files(path, st_mtime, hashes) VALUES"
                "(?, ?, ?)", (path, st_mtime, json.dumps(hashes)))
        return json.dumps(hashes)

    @staticmethod
    def get_hash(file_, algorithm_function):
        h = algorithm_function()
        [h.update(l) for l in file_]
        return h.hexdigest()

    def rendering_error(self, **keys):
        def r(obj):
            return Template(obj.group('CONTENT')).safe_substitute(**keys)
        # replacing error blocs by substituted and removing the no error blocs
        return re.sub(self.no_error_regex, '', re.sub(self.error_regex, r, self.body))

    def rendering_no_error(self, directory_content, descending, end_url, **keys):
        def r(obj):
            def loop(l_obj):
                def get_content_match(match_obj):
                    return match_obj.group('CONTENT')
                content_template = l_obj.group('CONTENT')
                if not self.hide_parent:
                    _t = Template(content_template).safe_substitute(
                        FILE_NAME='..', FILE_LINK='../' + end_url,
                        FILE_MODIFICATION='', FILE_CREATION='', FILE_TYPE='parent', FILE_SIZE='', FILE_MIMETYPE='')
                    _t = re.sub(self.if_not_file, get_content_match, _t)
                    _t = re.sub(self.if_file, '', _t)
                    formatted_content = _t
                else:
                    formatted_content = ''
                for key in directory_content:  # for each key into `directory_content`
                    # for each item sorted...
                    for i in sorted(directory_content[key], key=itemgetter(0), reverse=descending):
                        # getting the dict in previously loop created as `r` to format the `list_dir_bloc` template
                        _t = Template(content_template).safe_substitute(**i[1])
                        # replacing the blocs if file.../ if not file...
                        if key == 'dirs':
                            _t = re.sub(self.if_not_file, get_content_match, _t)
                            _t = re.sub(self.if_file, '', _t)
                        else:
                            _t = re.sub(self.if_file, get_content_match, _t)
                            _t = re.sub(self.if_not_file, '', _t)
                        formatted_content += _t
                return formatted_content
            return Template(re.sub(self.loop_regex, loop, obj.group('CONTENT'))).safe_substitute(**keys)
        return re.sub(self.error_regex, '', re.sub(self.no_error_regex, r, self.body))

    def list_dir(self, path, sorting='ST_MTIME.ASC', end_url=''):
        """
        Returns String if error.
        Sorting possibilities ([+]`.ASC|.DESC`):
            - ST_MTIME -> sorts by modification date.
            - ST_CTIME -> sorts by creation date.
            - ST_SIZE  -> sorts by size.
            - NAME     -> sorts by name.
        :param path:
        :return:
        """
        try:
            dir_ = listdir(path)
        except OSError:
            return self.rendering_error(ERROR_MESSAGE='Invalid file or directory.')

        path = [path + '/', path][path.endswith('/')]
        sorting = sorting.lower().split('.', 2)

        # We separate directories and files to always keep directories on top
        directory_content = {'dirs': [], 'files': []}
        for file_name in dir_:
            is_dir = os.path.isdir(path + file_name)
            # If is a directory we add a "/" at the end of the filename before check if hidden
            #   (to separate dirs of the files/ links).
            if self.is_hidden(file_name + '/' if is_dir else ''):
                continue
            stats = stat(os.path.join(path, file_name))
            r = dict(
                FILE_NAME=escape(file_name),
                # we keep the current query string on directories link
                FILE_LINK='%s%s' %
                          (quote(file_name), is_dir and ('/' + end_url) or ''),
                FILE_MODIFICATION=strftime(self.date_format, gmtime(stats[ST_MTIME])),
                FILE_CREATION=strftime(self.date_format, gmtime(stats[ST_CTIME])),
            )
            if is_dir:
                r['FILE_TYPE'], r['FILE_SIZE'], r['FILE_MIMETYPE'], r['DASHED_FILE_MIMETYPE'] = ('dir', '-', '-', '-')
            else:  # if file or link
                mime = self.mimetypes_list.get(os.path.splitext(file_name)[1]) or 'application/octet-stream'
                r['FILE_TYPE'], r['FILE_SIZE'], r['FILE_MIMETYPE'], r['DASHED_FILE_MIMETYPE'] = (
                    'file %s' % filter(None, mime.split('/'))[0], self.convert_size(stats[ST_SIZE]),
                    mime,
                    # Replacing special chars (excluding the dash), by a dash. Useful for the CSS class selector.
                    re.sub(self.css_invalid_chars, '-', mime)
                )

            # append into 'dirs' if is a directory, else we append into 'files'
            directory_content['dirs' if is_dir else 'files'].append(
                # if sorting[0] is in ['st_mtime', 'st_ctime', 'st_size'] we get the attribute `sorting[0]`
                # of the `stat_result` object else it gets by name (default).
                (stats.__getattribute__(sorting[0]), r) if sorting[0] in ['st_mtime', 'st_ctime', 'st_size']
                else (file_name, r)
            )
        return self.rendering_no_error(
            directory_content,
            # if sorting[1] is as descending; else, it stays as ascending.
            True if len(sorting) > 1 and sorting[1] == 'desc' else False,
            end_url=end_url,
        )


def parse_arguments():
    parser = ArgumentParser(prog='directoryLister')

    # --config=PATH
    parser.add_argument('-c', '--config', dest='configuration_file', type=FileType('r'), metavar='PATH',
                        help='The configuration file, useful if you don\'t want parse each parameters '
                             '(will overwrite the others arguments).')
    # --directory=DIRECTORY
    parser.add_argument('-d', '--directory', dest='path', metavar='DIRECTORY', default=getcwd(),
                        help='The root directory for listing (current working directory by default).')
    # --port=INT
    parser.add_argument('-p', '--port', metavar='INT', dest='port', type=int, default=8080, help='The port number.')
    # --body=PATH
    parser.add_argument('--body', metavar='PATH', dest='body', type=FileType('r'),
                        help='Path to a desired content body.',)
    # --CSS=PATH
    parser.add_argument('--style', metavar='PATH', dest='css', type=FileType('r'),
                        help='Path to the style file.')
    # --js=PATH
    parser.add_argument('--js', metavar='PATH', dest='js', type=FileType('r'),
                        help='Path to the Javascript file.')
    # --data=FORMAT
    parser.add_argument('--date', metavar='FORMAT', dest='date_format', default='%Y-%m-%d %H:%M:%S',
                        help='The date format to use. '
                             'Example: %%Y-%%m-%%d %%H:%%M:%%S will show something like: 2015-05-09 23:25:03 '
                             '(see here for more information: '
                             'https://docs.python.org/2.7/library/datetime.html#strftime-and-strptime-behavior).')
    # --binary=True/ False
    parser.add_argument('--binary', dest='binary_prefix', action='store_true', default=False,
                        help='Using the binary or decimal units.')
    # --hashing=True/ False
    parser.add_argument('--hashing', dest='must_hash_files', action='store_false', default=True,
                        help='Must provide the hash file on demand or not.')
    # --max-hash-size=INT
    parser.add_argument('--max-hash-size', dest='max_file_size_to_hash', type=int, default=int(2.5 * 10**8),
                        help='The maximal file size allowed to hash (in bytes).')
    # --store-hashes=True/ False
    parser.add_argument('--store-hashes', dest='keep_hashes_cache', action='store_true', default=False,
                        help='Must keep the hashes in cache into a database or not.')
    # --allow-hidden=True/ False
    parser.add_argument('--allow-hidden', dest='allow_access_to_hidden', action='store_true', default=False,
                        help='Allow the direct access to hidden files.')
    # --hidden=PATTERN
    parser.add_argument('--hidden', dest='hidden_files', action='append', default=[],
                        help='Add an UNIX filename pattern to hide on match '
                             '(this argument can be given as much you want).')
    # --database=PATH
    parser.add_argument('--database', metavar='PATH', dest='database', default=':memory:',
                        help='A path to a new sqlite database (in memory by default).')
    # --single-thread
    parser.add_argument('--single-thread', dest='single_thread', action='store_true', default=False,
                        help='If we should only use a single thread server or not and then process to requests '
                             'one after one.')
    # --thread-count
    parser.add_argument('--thread-count', dest='thread_count', default=10, type=int,
                        help='Sets the limit of threads.')
    # --hide-parent
    parser.add_argument('--hide-parent', dest='hide_parent', action='store_true', default=False,
                        help='Must hide the parent double dots (..) or not.')
    # --resources-directory
    parser.add_argument('--resources-directory', dest='resources_directory', metavar='DIRECTORY',
                        help='The resources directory. Useful to add resources on pages by using `?get=filename`.')
    args_ = parser.parse_args()

    # reading content of path and replacing the attribute with the output
    for a in ('body', 'css', 'js'):
        if getattr(args_, a):
            setattr(args_, a, getattr(args_, a).read())
        else:
            delattr(args_, a)

    if args_.configuration_file:
        conf_path = os.path.split(args_.configuration_file.name)[0]
        args_.configuration_file = json.loads(args_.configuration_file.read())
        # same as before but the files are not already opens, so we open them and read the content
        for k in ('body', 'css', 'js'):
            if args_.configuration_file.get(k):
                # replacing './' by the directory of the configuration file
                if args_.configuration_file[k].startswith('./'):
                    args_.configuration_file[k] = os.path.join(conf_path, args_.configuration_file[k][2:])
                with open(args_.configuration_file[k], mode='r') as o:
                    args_.configuration_file[k] = o.read()
        for k in args_.configuration_file:
            if k in getargspec(ListDirectory.__init__).args:  # if is an available argument in ListDirectory
                setattr(args_, k, args_.configuration_file[k])
        if args_.resources_directory and args_.resources_directory.startswith('./'):
            args_.resources_directory = os.path.join(conf_path, args_.resources_directory[2:]) + '/' \
                if not args_.resources_directory.endswith('/') else ''
    del args_.configuration_file

    # Verifies the resources directory
    if args_.resources_directory and not os.path.isdir(args_.resources_directory):
        raise InvalidConfigurationArgument('"%s" is not a valid directory.' % args_.resources_directory)

    # verifying the port range
    if not 1 <= args_.port <= 25555:
        raise AssertionError('Port must be between 1 and 25555 (%s).' % args_.port)
    return args_


def main(host='0.0.0.0', port=8000, single_thread=False, thread_count=10, **kwargs):
    # if the configuration file have an invalid item -> exception (we don't check)
    if single_thread:
        s = make_server(host=host, port=port, app=ListDirectory(**kwargs))
    else:
        s = make_multithread_server(thread_count=thread_count, host=host, port=port, app=ListDirectory(**kwargs))

    try:
        print('Starting the server at http://%s:%d' % (host, port))
        s.serve_forever()
    except KeyboardInterrupt:
        print('Closing the server...')
        s.server_close()


if __name__ == '__main__':
    main(**parse_arguments().__dict__)
