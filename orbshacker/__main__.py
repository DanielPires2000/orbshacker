"""Entry point for `python -m orbshacker`."""

import sys

from .timer import parse_timer_args

if "--timer-mode" in sys.argv:
    from .timer import run_timer
    run_timer(parse_timer_args(sys.argv))
else:
    from .main import main
    main()
