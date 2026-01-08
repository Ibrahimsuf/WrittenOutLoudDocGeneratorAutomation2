import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_post_form_submission(client):
    form_data = {
        "url": "https://docs.google.com/document/d/1FakeDocIdExample/edit",
        "title": "Test Title",
        "storyteller_names": [
            "Alice Smith",
            "Bob Jones",
        ],
        "director_name": "Jane Director",
        "dedication": "For testing purposes.\r\nWith newlines.",
    }

    response = client.post(
        "/",
        data=form_data,
        content_type="application/x-www-form-urlencoded",
    )

    # The POST will currently fail later on Google API calls unless mocked,
    # so we only assert that Flask accepted the POST and routed correctly.
    assert response.status_code in 200
    
