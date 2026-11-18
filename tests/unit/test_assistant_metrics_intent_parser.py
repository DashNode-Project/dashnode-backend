from app.modules.ai.application.assistant.intent_models import IntentType, MetricsPeriodKey
from app.modules.ai.application.assistant.intent_parser import parse_intent


def test_metrics_summary_intent() -> None:
    for text in (
        "resumen de métricas de ia",
        "cuántas interacciones de ia hubo",
        "promedio de latencia de ia",
        "total de tokens de ia",
    ):
        intent = parse_intent(text, open_project_name=None, last_project_names=[])
        assert intent.intent == IntentType.METRICS_SUMMARY, text


def test_metrics_by_user_intent() -> None:
    for text in (
        "métricas de ia por usuario",
        "interacciones de ia por usuarios",
        "desglose por usuario de interacciones de ia",
    ):
        intent = parse_intent(text, open_project_name=None, last_project_names=[])
        assert intent.intent == IntentType.METRICS_BY_USER, text


def test_metrics_list_intent() -> None:
    for text in (
        "lista el registro de ia",
        "historial de interacciones de ia",
        "últimas interacciones de ia",
    ):
        intent = parse_intent(text, open_project_name=None, last_project_names=[])
        assert intent.intent == IntentType.METRICS_LIST, text


def test_metrics_period_parsing() -> None:
    intent = parse_intent("métricas de ia de hoy", open_project_name=None, last_project_names=[])
    assert intent.intent == IntentType.METRICS_SUMMARY
    assert intent.metrics_period == MetricsPeriodKey.TODAY

    intent = parse_intent(
        "resumen métricas ia últimos 7 días", open_project_name=None, last_project_names=[]
    )
    assert intent.metrics_period == MetricsPeriodKey.SEVEN_D
