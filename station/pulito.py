import sys
from desktop.app import main
if __name__ == "__main__":
    try:
        main("pulito")
    except Exception:
        if "--self-test" in sys.argv:
            sys.exit(1)
        raise
