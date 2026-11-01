"""Light / dark theme: dark by default, a Light switch in the top bar."""
from datetime import date
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "static"


@pytest.fixture
def client(tmp_path):
    from companion.server import create_app
    vault = tmp_path / "vault"
    (vault / "01-daily").mkdir(parents=True)
    (vault / "30-habits").mkdir(parents=True)
    (vault / "01-daily" / f"{date.today().isoformat()}.md").write_text(
        "---\nstatus: active\n---\n## Morning Check-in\n### My Top 3\n1. [ ] Alpha\n")
    app = create_app(str(vault))
    app.config["TESTING"] = True
    return app.test_client()


def test_theme_script_runs_in_head_before_paint(client):
    html = client.get("/?mode=command").get_data(as_text=True)
    head = html[:html.index("</head>")]
    assert '<link rel="stylesheet" href="/static/theme.css">' in head
    # Not deferred, so <html data-theme> is set before the first paint
    assert '<script src="/static/theme.js"></script>' in head
    assert head.index("tailwind.css") < head.index("theme.css")


def test_top_bar_offers_light_and_dark(client):
    html = client.get("/?mode=command").get_data(as_text=True)
    nav = html[html.index('class="nsls-nav"'):html.index("</nav>")]
    assert "data-theme-toggle" in nav
    assert "nsls-theme-opt--light" in nav and ">Light" in nav
    assert "nsls-theme-opt--dark" in nav and ">Dark" in nav


def test_dark_is_the_default_unless_light_was_chosen():
    js = (STATIC / "theme.js").read_text(encoding="utf-8")
    assert 'theme === "light" ? "light" : "dark"' in js


def test_dark_palette_covers_the_task_lanes():
    css = (STATIC / "theme.css").read_text(encoding="utf-8")
    for selector in ('html[data-theme="dark"] {', ".nsls-shell", ".nsls-tcard",
                     ".nsls-lane--top3", ".nsls-lane--bonus", ".nsls-add-item input"):
        assert selector in css, selector



def test_dark_restates_the_states_its_base_rules_would_hide():
    """A dark rule on a base selector outranks the light rule for its state."""
    css = (STATIC / "theme.css").read_text(encoding="utf-8")
    for selector in ('html[data-theme="dark"] .nsls-habit-box.is-done',
                     'html[data-theme="dark"] .nsls-habit-box.is-partial',
                     ".nsls-pills button:hover:not(:disabled):not(.is-active)",
                     ".nsls-energy-btn:hover:not(.is-selected)",
                     'html[data-theme="dark"] .nsls-textarea:focus',
                     'html[data-theme="dark"] input.border:focus'):
        assert selector in css, selector
