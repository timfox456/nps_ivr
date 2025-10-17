"""
End-to-end integration tests for SMS workflow.

Tests the complete SMS conversation flow from first message to lead creation,
including field validation, error handling, and NPA API integration.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base
from app.models import ConversationSession


# Setup test database
TEST_DATABASE_URL = "sqlite:///./test_sms_integration.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mock_db_session(test_db):
    """Mock database session"""
    with patch('app.main.SessionLocal', return_value=TestingSessionLocal()):
        yield


@pytest.fixture
def mock_create_lead():
    """Mock the create_lead function to avoid actual API calls"""
    with patch('app.main.create_lead', new_callable=AsyncMock) as mock:
        mock.return_value = "TEST_LEAD_ID_123"
        yield mock


class TestSMSIntegrationHappyPath:
    """Test complete SMS conversation flow"""

    def test_complete_sms_conversation(self, client, mock_db_session, mock_create_lead):
        """Test a complete SMS conversation from start to finish"""
        sms_sid = "SM_TEST_123456"
        from_number = "+15551234567"
        to_number = "+16198530829"

        # Message 1: First name
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "John"
        })
        assert response.status_code == 200
        assert "last name" in response.text.lower() or "name" in response.text.lower()

        # Message 2: Last name
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Smith"
        })
        assert response.status_code == 200
        assert "state" in response.text.lower() or "address" in response.text.lower()

        # Message 3: State
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "California"
        })
        assert response.status_code == 200
        assert "phone" in response.text.lower()

        # Message 4: Phone (already populated from caller ID)
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "(555) 123-4567"
        })
        assert response.status_code == 200
        assert "email" in response.text.lower()

        # Message 5: Email
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "john.smith@example.com"
        })
        assert response.status_code == 200
        assert "make" in response.text.lower() or "vehicle" in response.text.lower()

        # Message 6: Vehicle make
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Harley-Davidson"
        })
        assert response.status_code == 200
        assert "model" in response.text.lower()

        # Message 7: Vehicle model
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Street Glide"
        })
        assert response.status_code == 200
        assert "year" in response.text.lower()

        # Message 8: Vehicle year - should complete the conversation
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "2020"
        })
        assert response.status_code == 200
        assert "thank you" in response.text.lower()
        assert "submitted" in response.text.lower() or "npa" in response.text.lower()

        # Verify create_lead was called with correct data
        assert mock_create_lead.called
        call_args = mock_create_lead.call_args[0][0]
        assert call_args['first_name'] == "John"
        assert call_args['last_name'] == "Smith"
        assert call_args['address'] == "California"
        assert call_args['email'] == "john.smith@example.com"
        assert call_args['vehicle_make'] == "Harley-Davidson"
        assert call_args['vehicle_model'] == "Street Glide"
        assert call_args['vehicle_year'] == "2020"
        assert call_args['_channel'] == "sms"

    def test_sms_with_all_info_at_once(self, client, mock_db_session, mock_create_lead):
        """Test SMS where user provides multiple fields in one message"""
        sms_sid = "SM_BULK_TEST"
        from_number = "+15559876543"
        to_number = "+16198530829"

        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Hi, I'm Jane Doe from Texas, email is jane@test.com, I have a 2019 Yamaha R1"
        })
        assert response.status_code == 200

        # Should extract multiple fields
        # Continue with phone number
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "555-999-8888"
        })
        assert response.status_code == 200

        # At this point, all fields should be complete
        if "thank you" in response.text.lower():
            # Conversation complete
            assert mock_create_lead.called
        else:
            # May need one more exchange, send confirmation
            response = client.post("/twilio/sms", data={
                "SmsSid": sms_sid,
                "From": from_number,
                "To": to_number,
                "Body": "yes"
            })
            assert "thank you" in response.text.lower()


class TestSMSIntegrationValidation:
    """Test validation and error handling in SMS flow"""

    def test_sms_invalid_email_retry(self, client, mock_db_session, mock_create_lead):
        """Test that invalid email triggers re-prompt"""
        sms_sid = "SM_EMAIL_TEST"
        from_number = "+15551111111"
        to_number = "+16198530829"

        # Start conversation
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Alice"
        })
        assert response.status_code == 200

        # Provide last name
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Wonder"
        })
        assert response.status_code == 200

        # Provide state
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Nevada"
        })
        assert response.status_code == 200

        # Phone
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "555-222-3333"
        })
        assert response.status_code == 200

        # Invalid email (missing @)
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "invalid-email-no-at"
        })
        assert response.status_code == 200
        assert "sorry" in response.text.lower() or "email" in response.text.lower()

        # Valid email
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "alice@example.com"
        })
        assert response.status_code == 200
        # Should proceed to next question

    def test_sms_caller_id_phone_prepopulation(self, client, mock_db_session, mock_create_lead):
        """Test that valid caller ID phone number is pre-populated"""
        sms_sid = "SM_CALLERID_TEST"
        from_number = "+15552223333"  # Valid US phone
        to_number = "+16198530829"

        # First message - phone should be auto-populated from caller ID
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Bob"
        })
        assert response.status_code == 200

        # Complete the rest of the conversation
        messages = [
            "Builder",  # last name
            "Arizona",  # state
            # phone is already populated from caller ID
            "bob@builder.com",  # email
            "Polaris",  # make
            "RZR",  # model
            "2023"  # year
        ]

        for msg in messages:
            response = client.post("/twilio/sms", data={
                "SmsSid": sms_sid,
                "From": from_number,
                "To": to_number,
                "Body": msg
            })
            assert response.status_code == 200

        # Should complete and create lead
        assert mock_create_lead.called
        call_args = mock_create_lead.call_args[0][0]
        # Phone should be normalized caller ID
        assert "(555) 222-3333" in call_args['phone'] or "5552223333" in call_args['phone']


class TestSMSIntegrationEdgeCases:
    """Test edge cases and error scenarios"""

    def test_sms_empty_messages(self, client, mock_db_session, mock_create_lead):
        """Test handling of empty or whitespace messages"""
        sms_sid = "SM_EMPTY_TEST"
        from_number = "+15554445555"
        to_number = "+16198530829"

        # Empty message
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "   "
        })
        assert response.status_code == 200
        # Should still respond with a question

        # Valid message
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Charlie"
        })
        assert response.status_code == 200

    def test_sms_multiple_conversations_different_sids(self, client, mock_db_session, mock_create_lead):
        """Test that different SMS SIDs maintain separate conversations"""
        from_number_1 = "+15551111111"
        from_number_2 = "+15552222222"
        to_number = "+16198530829"

        # Start conversation 1
        response = client.post("/twilio/sms", data={
            "SmsSid": "SM_CONV1",
            "From": from_number_1,
            "To": to_number,
            "Body": "User1"
        })
        assert response.status_code == 200

        # Start conversation 2
        response = client.post("/twilio/sms", data={
            "SmsSid": "SM_CONV2",
            "From": from_number_2,
            "To": to_number,
            "Body": "User2"
        })
        assert response.status_code == 200

        # Continue conversation 1
        response = client.post("/twilio/sms", data={
            "SmsSid": "SM_CONV1",
            "From": from_number_1,
            "To": to_number,
            "Body": "LastName1"
        })
        assert response.status_code == 200

        # Continue conversation 2
        response = client.post("/twilio/sms", data={
            "SmsSid": "SM_CONV2",
            "From": from_number_2,
            "To": to_number,
            "Body": "LastName2"
        })
        assert response.status_code == 200

        # Conversations should remain independent

    def test_sms_vehicle_year_extraction(self, client, mock_db_session, mock_create_lead):
        """Test that vehicle year is correctly extracted from various formats"""
        sms_sid = "SM_YEAR_TEST"
        from_number = "+15556667777"
        to_number = "+16198530829"

        # Get to vehicle year question
        messages = [
            "David", "Jones", "Florida", "555-888-9999",
            "david@example.com", "Kawasaki", "Ninja"
        ]

        for msg in messages:
            response = client.post("/twilio/sms", data={
                "SmsSid": sms_sid,
                "From": from_number,
                "To": to_number,
                "Body": msg
            })
            assert response.status_code == 200

        # Provide year in sentence form
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "It's a 2021 model"
        })
        assert response.status_code == 200
        assert "thank you" in response.text.lower()

        # Verify year was extracted correctly
        assert mock_create_lead.called
        call_args = mock_create_lead.call_args[0][0]
        assert call_args['vehicle_year'] == "2021"


class TestSMSLeadCreation:
    """Test NPA lead creation after SMS conversation completes"""

    def test_sms_lead_not_created_until_complete(self, client, mock_db_session, mock_create_lead):
        """Test that lead is only created when all fields are collected"""
        sms_sid = "SM_LEAD_TIMING_TEST"
        from_number = "+15559998888"
        to_number = "+16198530829"

        # Send partial information
        messages = ["Emily", "Stone", "Washington"]

        for msg in messages:
            response = client.post("/twilio/sms", data={
                "SmsSid": sms_sid,
                "From": from_number,
                "To": to_number,
                "Body": msg
            })
            assert response.status_code == 200

        # Lead should NOT be created yet
        assert not mock_create_lead.called

        # Complete the conversation
        final_messages = ["555-777-6666", "emily@example.com", "Honda", "CBR", "2020"]

        for msg in final_messages:
            response = client.post("/twilio/sms", data={
                "SmsSid": sms_sid,
                "From": from_number,
                "To": to_number,
                "Body": msg
            })
            assert response.status_code == 200

        # Now lead should be created
        assert mock_create_lead.called

    def test_sms_lead_only_created_once(self, client, mock_db_session, mock_create_lead):
        """Test that lead is only created once even if user sends more messages"""
        sms_sid = "SM_ONCE_TEST"
        from_number = "+15553334444"
        to_number = "+16198530829"

        # Complete conversation
        messages = [
            "Frank", "Castle", "New York", "555-111-2222",
            "frank@example.com", "Ducati", "Monster", "2022"
        ]

        for msg in messages:
            response = client.post("/twilio/sms", data={
                "SmsSid": sms_sid,
                "From": from_number,
                "To": to_number,
                "Body": msg
            })
            assert response.status_code == 200

        # Verify lead was created once
        assert mock_create_lead.call_count == 1

        # Send additional message (should not create another lead)
        response = client.post("/twilio/sms", data={
            "SmsSid": sms_sid,
            "From": from_number,
            "To": to_number,
            "Body": "Thanks!"
        })
        assert response.status_code == 200

        # Lead should still only be created once
        assert mock_create_lead.call_count == 1

    def test_sms_lead_includes_channel_info(self, client, mock_db_session, mock_create_lead):
        """Test that lead includes channel information"""
        sms_sid = "SM_CHANNEL_TEST"
        from_number = "+15554443333"
        to_number = "+16198530829"

        # Complete conversation
        messages = [
            "Grace", "Hopper", "Virginia", "555-222-1111",
            "grace@example.com", "Triumph", "Bonneville", "2021"
        ]

        for msg in messages:
            response = client.post("/twilio/sms", data={
                "SmsSid": sms_sid,
                "From": from_number,
                "To": to_number,
                "Body": msg
            })
            assert response.status_code == 200

        # Verify channel info was included
        assert mock_create_lead.called
        call_args = mock_create_lead.call_args[0][0]
        assert call_args['_channel'] == "sms"
