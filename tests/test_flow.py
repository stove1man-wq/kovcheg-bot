from kovcheg_bot import texts as T
from kovcheg_bot.flow import Flow, User
from kovcheg_bot.storage import MemoryStore, SqliteStore

U = User(1, "ivan")
NOUSER = User(2, "")


def make(store=None):
    sent = []
    flow = Flow(store or MemoryStore(), notify=sent.append, policy_url="https://example.org/policy", testers_url="https://t.me/+x")
    return flow, sent


def labels(replies):
    return [b.label for r in replies for row in r.rows for b in row]


def test_start_asks_consent_and_saves_nothing():
    flow, _ = make()
    r = flow.start(U, "site_docs")
    assert T.CONSENT_BUTTON in labels(r)
    assert flow.store.get(1) is None


def test_buttons_before_consent_do_not_save():
    flow, _ = make()
    flow.start(U)
    r = flow.button(U, "seg:human")
    assert T.CONSENT_BUTTON in labels(r)
    assert flow.store.get(1) is None


def test_decline_saves_nothing():
    flow, _ = make()
    flow.start(U)
    flow.button(U, "no")
    assert flow.store.get(1) is None


def test_human_path_sets_tag_and_source():
    flow, _ = make()
    flow.start(U, "site_barabashka")
    flow.button(U, "ok")
    r = flow.button(U, "seg:human")
    assert T.PRODUCTS["barabashka"][0] in labels(r)
    flow.button(U, "p:barabashka")
    r = flow.button(U, "a:barabashka:1")
    p = flow.store.get(1)
    assert (p.segment, p.tag, p.source, p.answer) == ("human", "b2c_barabashka", "site_barabashka", T.PRODUCTS["barabashka"][4][1])
    assert T.FINAL_CALL in labels(r) and T.FINAL_ORDER not in labels(r)


def test_biz_gets_order_button_and_application_is_mailed():
    flow, sent = make()
    flow.start(U)
    flow.button(U, "ok")
    flow.button(U, "seg:biz")
    flow.button(U, "p:gateway")
    r = flow.button(U, "a:gateway:0")
    assert T.FINAL_ORDER in labels(r)
    assert flow.button(U, "f:order")[0].text == T.ASK_TASK
    done = flow.text(U, "Нужен единый API для трёх команд")
    assert done[0].text == T.APPLICATION_OK
    assert len(sent) == 1
    assert sent[0].tag == "b2b_gateway" and sent[0].contact == "@ivan" and sent[0].kind == "order"


def test_no_username_asks_contact():
    flow, sent = make()
    flow.start(NOUSER)
    flow.button(NOUSER, "ok")
    flow.button(NOUSER, "seg:biz")
    flow.button(NOUSER, "p:assistant")
    flow.button(NOUSER, "a:assistant:0")
    flow.button(NOUSER, "f:order")
    assert flow.text(NOUSER, "Нужен бот поддержки")[0].text == T.ASK_CONTACT
    assert flow.text(NOUSER, "mail@example.org")[0].text == T.APPLICATION_OK
    assert sent[0].contact == "mail@example.org"


def test_call_for_human_with_username_goes_straight():
    flow, sent = make()
    flow.start(U)
    flow.button(U, "ok")
    flow.button(U, "seg:human")
    flow.button(U, "p:memory")
    flow.button(U, "a:memory:0")
    r = flow.button(U, "f:call")
    assert r[0].text == T.CALL_OK
    assert sent[0].kind == "call"


def test_delete_removes_everything():
    flow, _ = make()
    flow.start(U)
    flow.button(U, "ok")
    flow.button(U, "seg:human")
    flow.button(U, "p:home")
    flow.button(U, "a:home:0")
    flow.button(U, "f:call")
    assert flow.delete(U)[0].text == T.DELETED
    assert flow.store.get(1) is None
    assert flow.store.applications == []
    assert flow.delete(U)[0].text == T.NOTHING_TO_DELETE


def test_bad_source_is_cleaned_and_bad_buttons_are_safe():
    flow, _ = make()
    flow.start(U, "a b;drop")
    flow.button(U, "ok")
    assert flow.store.get(1).source == "direct"
    assert flow.button(U, "p:zzz")[0].text == T.IDLE
    assert flow.button(U, "a:home:99")[0].text == T.IDLE


def test_idle_text_shows_menu():
    flow, _ = make()
    assert flow.text(U, "привет")[0].text == T.IDLE


def test_sqlite_roundtrip(tmp_path):
    store = SqliteStore(str(tmp_path / "bot.db"))
    flow, sent = make(store)
    flow.start(U, "site_docs")
    flow.button(U, "ok")
    flow.button(U, "seg:biz")
    flow.button(U, "p:docs")
    flow.button(U, "a:docs:2")
    flow.button(U, "f:order")
    flow.text(U, "Нужны шаблоны договоров")
    p = store.get(1)
    assert p.consent is True and p.tag == "pro_docs"
    assert store.stats() == {"pro_docs": 1}
    assert store.delete(1) is True and store.get(1) is None
