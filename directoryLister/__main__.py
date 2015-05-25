from argparse import ArgumentParser, FileType
from inspect import getargspec
import os.path
from os import getcwd

from .directory_lister import main, InvalidConfigurationArgument, ListDirectory, json

if __name__ == '__main__':
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
    parser.add_argument('--single-thread', dest='singlethread', action='store_true', default=False,
                        help='If we should only use a single thread server or not and then process to requests '
                             'one after one.')
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
    main(**args_.__dict__)
