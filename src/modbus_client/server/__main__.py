import argparse
import logging

from modbus_client.server.server import run_server

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


def main() -> None:
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--config", type=str, required=True)
    argparser.add_argument("-v", "--verbose", action='store_true')
    argparser.add_argument('--base-href', type=str, default="/")
    argparser.add_argument('--dark-mode', action='store_true')

    args = argparser.parse_args()

    logging.basicConfig()
    log = logging.getLogger()
    if args.verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    run_server(args)


if __name__ == "__main__":
    main()
