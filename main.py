"""Entry point for the File Management Utility.

Usage:
    python main.py --make-demo demo_folder        # create a messy sample folder
    python main.py --root demo_folder             # interactive menu
    python main.py --root demo_folder --report folder_report.txt --csv file_list.csv
"""

import argparse
import logging
import sys

from filemanager import reports
from filemanager.cli import FileManagerCLI
from filemanager.demo import create_demo
from filemanager.exceptions import FileManagerError
from filemanager.scanner import scan
from filemanager.validators import validate_directory


def main(argv=None):
    parser = argparse.ArgumentParser(description="File Management Utility")
    parser.add_argument("--root", help="folder to manage")
    parser.add_argument("--make-demo", metavar="FOLDER", help="create a sample folder to practise on")
    parser.add_argument("--report", metavar="PATH", help="write a folder report and exit (needs --root)")
    parser.add_argument("--csv", metavar="PATH", help="also export the file list as CSV (with --report)")
    args = parser.parse_args(argv)

    logging.basicConfig(filename="filemanager.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    try:
        if args.make_demo:
            folder = create_demo(args.make_demo)
            print(f"Demo folder created: {folder}")
            print(f"Try: python main.py --root {args.make_demo}")
            return 0

        if args.report:
            if not args.root:
                parser.error("--report requires --root")
            result = scan(validate_directory(args.root))
            print(reports.build_text_report(result))
            reports.save_text_report(result, args.report)
            print(f"\nReport saved to {args.report}")
            if args.csv:
                reports.export_inventory_csv(result, args.csv)
                print(f"File list saved to {args.csv}")
            return 0

        FileManagerCLI(args.root).run()
    except FileManagerError as exc:
        print(f"Error: {exc}")
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
