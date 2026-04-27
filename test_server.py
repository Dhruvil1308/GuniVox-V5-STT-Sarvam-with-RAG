import pytest
from fastapi.testclient import TestClient
from server import app, sessions

client = TestClient(app)

def test_vobiz_answer_xml_format():
    """Test if the /vobiz-answer endpoint returns correctly formatted TwiML/XML."""
    response = client.post("/vobiz-answer", data={"CallSid": "test-1234"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/xml; charset=utf-8"
    
    xml_content = response.text
    
    # Check for correct Twilio attributes
    assert '<Gather inputType="speech"' in xml_content, "Missing correct inputType attribute"
    assert 'executionTimeout="20"' in xml_content, "Missing correct executionTimeout attribute"
    assert 'speechEndTimeout="3"' in xml_content, "Missing correct speechEndTimeout attribute"
    assert 'voice="WOMAN"' in xml_content, "Missing correct voice attribute (WOMAN)"

def test_vobiz_silent_fallback():
    """Test if the fallback loop gracefully handles silence and hangs up after 2 attempts."""
    # First silence hit
    response1 = client.post("/vobiz-silent", data={"CallSid": "test-silence"})
    assert response1.status_code == 200
    assert "Are you still there" in response1.text
    assert "<Gather" in response1.text
    
    # Second silence hit
    response2 = client.post("/vobiz-silent", data={"CallSid": "test-silence"})
    assert response2.status_code == 200
    assert "not available right now" in response2.text
    assert "<Hangup/>" in response2.text
    
def test_vobiz_status_cleanup():
    """Test if call termination properly cleans up sessions."""
    # Inject a fake session
    sessions["test-cleanup"] = [{"role": "system", "content": "test"}]
    
    # Send terminal status
    response = client.post("/status", data={"CallSid": "test-cleanup", "CallStatus": "completed"})
    assert response.status_code == 200
    
    # Session should be removed
    assert "test-cleanup" not in sessions
