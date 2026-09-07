from langgraph.graph import END

from app.ai.graph import route_triage


def _state(action):
    return {"triage_action": action}


def test_auto_pr_routes_to_fix():
    assert route_triage(_state("AUTO_PR")) == "fix"


def test_jira_ticket_routes_to_jira_node():
    assert route_triage(_state("JIRA_TICKET")) == "jira"


def test_user_error_routes_to_notify_user():
    assert route_triage(_state("USER_ERROR")) == "notify_user"


def test_unknown_action_falls_back_to_end():
    assert route_triage(_state("SOMETHING_UNEXPECTED")) == END
    assert route_triage({}) == END
