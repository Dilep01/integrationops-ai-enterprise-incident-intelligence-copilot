from integrationops.checkpoints import create_sqlite_checkpointer
from integrationops.models import IncidentRequest
from integrationops.workflow import InvestigationWorkflow


def test_langgraph_state_is_durably_checkpointed(tmp_path) -> None:
    checkpointer = create_sqlite_checkpointer(tmp_path / "checkpoints.sqlite3")
    workflow = InvestigationWorkflow(checkpointer=checkpointer)

    report = workflow.investigate(
        IncidentRequest(message="Payment integration failed with HTTP 401 after token rotation.")
    )

    checkpoint = checkpointer.get_tuple({"configurable": {"thread_id": report.run_id}})
    assert checkpoint is not None
    assert checkpoint.checkpoint["channel_values"]["report"].run_id == report.run_id
