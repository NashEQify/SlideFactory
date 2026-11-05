"""Presenter timer: popup-side ticking and per-slide / target-position timing."""
import re

import pytest
from playwright.sync_api import expect
from test_editor_e2e import browser_factory, PACKAGE

pytestmark = pytest.mark.e2e

SECONDS = r"(\d\d):(\d\d)"


def _seconds(text, label):
    match = re.search(label + r" " + SECONDS, text)
    assert match, (label, text)
    return int(match[1]) * 60 + int(match[2])


def _deck(tmp_path, intro='data-sf-duration="60"', approach='data-sf-duration="90"', outlook=''):
    source = (PACKAGE / 'assets/consulting.html').read_text()
    for slide, extra in (('intro', intro), ('approach', approach), ('outlook', outlook)):
        if extra:
            source = source.replace(f'data-sf-slide="{slide}"', f'data-sf-slide="{slide}" {extra}', 1)
    path = tmp_path / 'timed.html'
    path.write_text(source)
    return path


def _presenter(page):
    with page.expect_popup() as opened:
        page.get_by_role('button', name='Referentenansicht', exact=True).click()
    popup = opened.value
    expect(popup.get_by_role('timer')).to_be_visible()
    return popup


def test_popup_timer_counts_without_owner_ticks(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path))
    popup = _presenter(page)
    timer = popup.get_by_role('timer')
    popup.get_by_role('button', name='Start', exact=True).click()
    expect(popup.get_by_role('button', name='Pause', exact=True)).to_be_enabled()
    # A background owner window is throttled by the browser. Model the worst
    # case: no further clock messages reach the popup at all.
    popup.evaluate("(() => { const post = window.postMessage.bind(window); window.postMessage = (message, ...rest) => message?.type === 'clock' ? undefined : post(message, ...rest); })()")
    popup.wait_for_timeout(2600)
    assert _seconds('Gesamt ' + timer.text_content(), 'Gesamt') >= 2, 'popup must keep counting on its own tick'
    assert _seconds(popup.locator('#slide-time').text_content(), 'Folie') >= 2


def test_whole_deck_pace_slide_time_and_revisit(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path))
    popup = _presenter(page)
    slide, plan, pace = popup.locator('#slide-time'), popup.locator('#target'), popup.locator('#pace')
    expect(slide).to_have_text('Folie 00:00 / 01:00')
    expect(plan).to_have_text('Gesamt 00:00 / Plan 00:00 · Ziel 02:30')
    expect(pace).to_have_text('im Plan')
    popup.get_by_role('button', name='Start', exact=True).click()
    popup.wait_for_timeout(2200)
    first = _seconds(slide.text_content(), 'Folie')
    assert first >= 2
    expect(pace).to_have_text('im Plan')  # plan grows with time on the slide up to its duration
    popup.get_by_role('button', name='Nächste Folie', exact=True).click()
    expect(slide).to_contain_text('/ 01:30')
    expect(plan).to_contain_text('/ Plan 01:0')
    expect(pace).to_have_text(re.compile(r'^−00:5\d vor Plan$'))
    assert pace.get_attribute('data-state') == 'ahead'
    assert _seconds(slide.text_content(), 'Folie') <= 1, 'a new slide starts its own time'
    popup.wait_for_timeout(1200)
    popup.get_by_role('button', name='Nächste Folie', exact=True).click()
    expect(slide).to_have_text(re.compile(r'^Folie \d\d:\d\d$'))  # no duration: 0 target
    expect(plan).to_contain_text('/ Plan 02:30')
    popup.get_by_role('combobox', name='Folie', exact=True).select_option('intro')
    expect(slide).to_contain_text('/ 01:00')
    assert _seconds(slide.text_content(), 'Folie') >= first, 'revisits continue the slide time'
    popup.get_by_role('button', name='Pause', exact=True).click()
    paused = slide.text_content()
    popup.wait_for_timeout(1300)
    assert slide.text_content() == paused
    popup.get_by_role('button', name='Stopp', exact=True).click()
    expect(slide).to_have_text('Folie 00:00 / 01:00')
    expect(popup.get_by_role('timer')).to_have_text('00:00')


def test_part_pace_behind_plan_and_frozen_backup(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path,
        intro='data-sf-duration="1" data-sf-part="Teil A" data-sf-part-duration="1200"',
        approach='data-sf-duration="90" data-sf-part="Teil B"'))
    popup = _presenter(page)
    plan, pace = popup.locator('#target'), popup.locator('#pace')
    expect(plan).to_have_text('Teil A 00:00 / Plan 00:00 · Budget 20:00')
    popup.get_by_role('button', name='Start', exact=True).click()
    # Staying beyond the slide's 1 s lets the deficit grow continuously.
    expect(pace).to_have_text(re.compile(r'^\+00:0[2-9] hinter Plan$'), timeout=6000)
    assert pace.get_attribute('data-state') == 'behind'
    popup.get_by_role('button', name='Nächste Folie', exact=True).click()
    expect(plan).to_have_text(re.compile(r'^Teil B 00:0[01] / Plan 00:0[01] · Budget 01:30$'))
    popup.wait_for_timeout(1300)
    popup.get_by_role('button', name='Nächste Folie', exact=True).click()
    # Backup slide without part: its time counts for Teil B, the plan holds still.
    expect(plan).to_contain_text('Teil B ')
    before = plan.text_content()
    popup.wait_for_timeout(2300)
    after = plan.text_content()
    assert _seconds(after, 'Teil B') >= _seconds(before, 'Teil B') + 2
    assert _seconds(after, 'Plan') == _seconds(before, 'Plan')


def _delta(pace):
    text = pace.text_content()
    if text == 'im Plan':
        return 0
    sign = 1 if text.startswith('+') else -1
    return sign * _seconds('x ' + text[1:], 'x')


def test_pace_is_continuous_across_back_jump_and_return(tmp_path, browser_factory):
    # User report: going back made the plan drop and "hinter Plan" jump.
    page = browser_factory(_deck(tmp_path,
        intro='data-sf-duration="30" data-sf-part="Teil A"',
        approach='data-sf-duration="30" data-sf-part="Teil A"'))
    popup = _presenter(page)
    pace, plan, choose = popup.locator('#pace'), popup.locator('#target'), popup.get_by_role('combobox', name='Folie', exact=True)
    popup.get_by_role('button', name='Start', exact=True).click()
    popup.wait_for_timeout(1500)
    popup.get_by_role('button', name='Nächste Folie', exact=True).click()  # leaving early forward: the one allowed drop
    expect(pace).to_have_text(re.compile(r'^−00:2[89] vor Plan$'))
    popup.wait_for_timeout(1200)
    for step, target in (('back', 'intro'), ('backup', 'outlook'), ('return', 'approach'), ('back again', 'intro')):
        before = _delta(pace)
        choose.select_option(target)
        popup.wait_for_timeout(300)
        assert abs(_delta(pace) - before) <= 1, f'{step}: pace jumped from {before} to {_delta(pace)}'
        frozen_plan = _seconds(plan.text_content(), 'Plan')
        popup.wait_for_timeout(1300)
        if target != 'approach':
            assert _seconds(plan.text_content(), 'Plan') == frozen_plan, f'{step}: plan must not move'
            assert _delta(pace) >= before + 1, f'{step}: time away from the furthest slide counts as delay'
    # Back on the furthest slide the plan continues; forward from there is normal.
    choose.select_option('approach')
    popup.wait_for_timeout(1300)
    assert _seconds(plan.text_content(), 'Plan') > 30
    # Reset clears the furthest-slide mark too.
    popup.get_by_role('button', name='Stopp', exact=True).click()
    choose.select_option('intro')
    expect(plan).to_have_text('Teil A 00:00 / Plan 00:00 · Budget 01:00')


def test_part_attributes_are_validated_and_inspected(tmp_path):
    import json, subprocess, sys
    cli = PACKAGE / 'scripts/deck.py'
    good = _deck(tmp_path, intro='data-sf-duration="60" data-sf-part="Teil A" data-sf-part-duration="1200"')
    info = json.loads(subprocess.run([sys.executable, str(cli), 'inspect', str(good), '--slide', 'intro'], capture_output=True, text=True).stdout)['slide']
    assert (info['part'], info['partDuration'], info['duration']) == ('Teil A', 1200.0, 60.0)
    for bad in ('data-sf-part=""', 'data-sf-part-duration="60"', 'data-sf-part="A" data-sf-part-duration="x"'):
        path = _deck(tmp_path, intro=bad)
        result = subprocess.run([sys.executable, str(cli), 'validate', str(path)], capture_output=True, text=True)
        assert result.returncode == 2 and 'part' in result.stderr, bad


def test_deck_without_durations_shows_only_slide_time(tmp_path, browser_factory):
    page = browser_factory(PACKAGE / 'assets/consulting.html')
    popup = _presenter(page)
    expect(popup.locator('#slide-time')).to_have_text('Folie 00:00')
    expect(popup.locator('#target')).to_have_text('')


def test_stop_clears_all_timing_and_legacy_reset_is_accepted(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path,
        intro='data-sf-duration="30" data-sf-part="Teil A"', approach='data-sf-duration="30" data-sf-part="Teil A"'))
    popup = _presenter(page)
    timer, state, slide, plan = popup.get_by_role('timer'), popup.locator('#timer-state'), popup.locator('#slide-time'), popup.locator('#target')
    expect(state).to_have_text('gestoppt')
    expect(popup.get_by_role('button', name='Stopp', exact=True)).to_be_disabled()
    popup.get_by_role('button', name='Start', exact=True).click()
    expect(state).to_have_text('läuft')
    popup.wait_for_timeout(1300)
    popup.get_by_role('button', name='Nächste Folie', exact=True).click()
    popup.wait_for_timeout(1300)
    # Since 1.3.4 Stop is the only reset control; a legacy 'reset' command
    # from an older popup still clears times and keeps the timer running.
    expect(popup.get_by_role('button', name='Zurücksetzen', exact=True)).to_have_count(0)
    popup.evaluate("""(() => { const config = JSON.parse(document.scripts[0].textContent.match(/\\)\\((\\{.*\\})\\);?$/s)[1]);
      window.opener.postMessage({...config, type: 'command', command: 'timer', payload: {action: 'reset'}}, '*'); })()""")
    expect(timer).to_have_text(re.compile(r'^00:0[01]$'))
    expect(state).to_have_text('läuft')
    popup.wait_for_timeout(1300)
    assert _seconds('t ' + timer.text_content(), 't') >= 1, 'legacy reset keeps the timer running'
    # Stop: halts and clears total, slide, part times and the furthest-slide mark.
    popup.get_by_role('button', name='Stopp', exact=True).click()
    expect(state).to_have_text('gestoppt')
    expect(timer).to_have_text('00:00')
    expect(slide).to_have_text('Folie 00:00 / 00:30')
    popup.get_by_role('combobox', name='Folie', exact=True).select_option('intro')
    expect(plan).to_have_text('Teil A 00:00 / Plan 00:00 · Budget 01:00')
    popup.wait_for_timeout(1200)
    expect(timer).to_have_text('00:00')
    expect(popup.get_by_role('button', name='Start', exact=True)).to_be_enabled()


def test_end_time_countdown_states_persistence_and_local_ticking(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path))
    popup = _presenter(page)
    countdown, field = popup.locator('#countdown'), popup.get_by_label('Zieluhrzeit', exact=True)
    expect(countdown).to_be_hidden()
    at = lambda minutes: popup.evaluate(f"(() => {{ const d = new Date(Date.now() + {minutes} * 60000); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); }})()")
    end = at(21)
    field.fill(end)
    expect(countdown).to_have_text(re.compile(rf'^noch (19|20|21):\d\d bis {end}$'))
    assert countdown.get_attribute('data-state') == 'ok'
    # Independent of the (stopped) presentation timer and of owner messages.
    popup.evaluate("(() => { const post = window.postMessage.bind(window); window.postMessage = (message, ...rest) => message?.type === 'clock' ? undefined : post(message, ...rest); })()")
    first = countdown.text_content()
    popup.wait_for_timeout(1300)
    assert countdown.text_content() != first, 'countdown ticks in the popup'
    popup.close()
    popup = _presenter(page)  # persists for the deck (localStorage), not in slide content
    countdown, field = popup.locator('#countdown'), popup.get_by_label('Zieluhrzeit', exact=True)
    expect(field).to_have_value(end)
    field.fill(at(6))
    expect(countdown).to_have_attribute('data-state', 'soon')
    field.fill(at(-3))
    expect(countdown).to_have_text(re.compile(r'^\+0[23]:\d\d über \d\d:\d\d$'))
    assert countdown.get_attribute('data-state') == 'over'
    popup.get_by_role('button', name='Zieluhrzeit löschen', exact=True).click()
    expect(countdown).to_be_hidden()
    expect(field).to_have_value('')
    assert 'presenter-end' not in page.evaluate("document.getElementById('sf-deck').outerHTML")
