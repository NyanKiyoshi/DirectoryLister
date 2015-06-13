from .directory_lister import main, parse_arguments

if __name__ == '__main__':
    main(**parse_arguments().__dict__)
