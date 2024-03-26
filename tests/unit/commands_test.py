import pytest

import app.commands
from app.usecases.performance import ScoreParams

@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            # covers all parameters
            {"mode": 0, "args": "+hddtezfl 600x 99.37% 5x100 4x50 3xgeki 1xkatu 7m "},
            ScoreParams(mode=0, mods=4206, combo=600, acc=99.37, n100=5, n50=4, ngeki=3, nkatu=1, nmiss=7)
        ),
        
        (
            # specifically covers different mode & mods without "+" prefix
            {"mode": 1, "args": "hdhr"},
            ScoreParams(mode=1, mods=30)
        ),
        (
            # accuracy out of range
            {"mode": 0, "args": "100.0001%"},
            app.commands.ParsingError("Invalid accuracy.")
        )
    ]
)
def test_parse__with__args(test_input, expected):
    assert app.commands.parse__with__args(**test_input) == expected