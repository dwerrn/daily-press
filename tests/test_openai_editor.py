from types import SimpleNamespace

from daily_press.models import ContentItem
from daily_press.openai_editor import EditorialResponse, OpenAIEditor


def _candidates() -> list[ContentItem]:
    return [
        ContentItem(
            source="Reuters",
            title="First story",
            url="https://example.test/first?utm_source=feed",
            summary="First source excerpt.",
            section="top",
        ),
        ContentItem(
            source="NASA",
            title="Second story",
            url="https://example.test/second",
            summary="Second source excerpt.",
            section="aerospace-defense",
        ),
        ContentItem(
            source="IEEE Spectrum",
            title="Third story",
            url="https://example.test/third",
            summary="Third source excerpt.",
            section="engineering-technology",
        ),
        ContentItem(
            source="The Register",
            title="Radar story",
            url="https://example.test/radar",
            summary="Radar source excerpt.",
            section="engineering-technology",
        ),
    ]


class FakeResponses:
    def __init__(self, parsed: object) -> None:
        self.parsed = parsed
        self.kwargs: dict[str, object] | None = None

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(output_parsed=self.parsed)


def test_editor_returns_source_attributed_stories_and_sends_bounded_fields() -> None:
    responses = FakeResponses(
        EditorialResponse(
            top_stories=[
                {"candidate_index": 0, "source": "Reuters", "summary": "A concise lead."},
                {"candidate_index": 1, "source": "NASA", "summary": "A concise second."},
                {"candidate_index": 2, "source": "IEEE Spectrum", "summary": "A concise third."},
            ],
            radar_stories=[
                {"candidate_index": 3, "source": "The Register", "summary": "A concise radar item."}
            ],
        )
    )
    editor = OpenAIEditor(SimpleNamespace(responses=responses))

    edition = editor.select(_candidates())

    assert len(edition.top_stories) == 3
    assert edition.top_stories[0].source == "Reuters"
    assert edition.radar_stories[0].source == "The Register"
    assert edition.mode == "openai"
    assert responses.kwargs is not None
    assert responses.kwargs["model"] == "gpt-5-mini"
    assert '"excerpt": "First source excerpt."' in str(responses.kwargs["input"])
    assert '"candidate_index"' not in str(responses.kwargs["input"])


def test_editor_falls_back_without_an_api_key() -> None:
    edition = OpenAIEditor().select(_candidates())

    assert edition.degraded
    assert edition.degraded_reason == "OpenAI API key not configured"
    assert [story.source for story in edition.top_stories] == ["Reuters", "NASA", "IEEE Spectrum"]
    assert edition.top_stories[0].summary == "First source excerpt."


def test_editor_falls_back_when_provider_returns_wrong_source() -> None:
    responses = FakeResponses(
        EditorialResponse(
            top_stories=[
                {"candidate_index": 0, "source": "Not Reuters", "summary": "Bad attribution."},
                {"candidate_index": 1, "source": "NASA", "summary": "Second."},
                {"candidate_index": 2, "source": "IEEE Spectrum", "summary": "Third."},
            ],
            radar_stories=[],
        )
    )

    edition = OpenAIEditor(SimpleNamespace(responses=responses)).select(_candidates())

    assert edition.degraded
    assert edition.degraded_reason == "OpenAI response was invalid"


def test_editor_falls_back_when_provider_request_fails() -> None:
    class FailingResponses:
        def parse(self, **kwargs: object) -> None:
            del kwargs
            raise RuntimeError("provider failure")

    edition = OpenAIEditor(SimpleNamespace(responses=FailingResponses())).select(_candidates())

    assert edition.degraded_reason == "OpenAI request failed"
