"""
Comprehensive unit tests for the Salesforce/NPA Lead API integration.

Tests cover:
1. Lead creation with all required fields
2. Lead creation with default values for optional fields
3. Error handling for missing credentials
4. Error handling for API failures
5. Field mapping and normalization
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from app.salesforce import create_lead, get_session_token


class TestGetSessionToken:
    """Tests for session token retrieval"""

    @pytest.mark.asyncio
    async def test_get_session_token_not_implemented(self):
        """Session token retrieval is currently not used"""
        # This function exists but returns None since we use username/password auth
        # Keep it for future use if API changes to require session token
        result = await get_session_token("user", "pass", "https://api.example.com")
        # Should return None since login endpoint doesn't work
        assert result is None


class TestCreateLead:
    """Tests for lead creation"""

    @pytest.mark.asyncio
    async def test_create_lead_missing_credentials(self):
        """Test that create_lead returns None when credentials are not configured"""
        with patch('app.salesforce.settings') as mock_settings:
            mock_settings.npa_api_username = None
            mock_settings.npa_api_password = None

            payload = {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "(555) 123-4567",
                "address": "California",
                "vehicle_make": "Harley-Davidson",
                "vehicle_model": "Street Glide",
                "vehicle_year": "2020",
            }

            result = await create_lead(payload)
            assert result is None

    @pytest.mark.asyncio
    async def test_create_lead_success(self):
        """Test successful lead creation with all required fields"""
        with patch('app.salesforce.settings') as mock_settings:
            mock_settings.npa_api_username = "testuser"
            mock_settings.npa_api_password = "testpass"
            mock_settings.npa_api_base_url = "https://api.example.com"
            mock_settings.npa_lead_source = "IVR"

            with patch('app.salesforce.httpx.AsyncClient') as mock_client:
                # Mock the HTTP response
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True,
                    "recordID": "00QOu00000Z4h3pMAB",
                    "message": "Lead created successfully"
                }
                mock_response.raise_for_status = Mock()

                # Setup async context manager
                mock_async_client = AsyncMock()
                mock_async_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_async_client

                payload = {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com",
                    "phone": "(555) 123-4567",
                    "address": "California",
                    "vehicle_make": "Harley-Davidson",
                    "vehicle_model": "Street Glide",
                    "vehicle_year": "2020",
                    "_channel": "sms",
                }

                result = await create_lead(payload)
                assert result == "00QOu00000Z4h3pMAB"

                # Verify the correct API endpoint was called
                post_call = mock_async_client.__aenter__.return_value.post
                assert post_call.called
                call_args = post_call.call_args
                assert call_args[0][0] == "https://api.example.com/api/Lead/LeadCreate"

                # Verify the payload structure
                sent_data = call_args[1]['json']
                assert sent_data['username'] == "testuser"
                assert sent_data['password'] == "testpass"
                assert sent_data['firstName'] == "John"
                assert sent_data['lastName'] == "Doe"
                assert sent_data['email'] == "john@example.com"
                assert sent_data['phone'] == "(555) 123-4567"
                assert sent_data['state'] == "California"
                assert sent_data['make'] == "Harley-Davidson"
                assert sent_data['model'] == "Street Glide"
                assert sent_data['year'] == 2020

    @pytest.mark.asyncio
    async def test_create_lead_with_defaults(self):
        """Test that optional fields have correct default values"""
        with patch('app.salesforce.settings') as mock_settings:
            mock_settings.npa_api_username = "testuser"
            mock_settings.npa_api_password = "testpass"
            mock_settings.npa_api_base_url = "https://api.example.com"
            mock_settings.npa_lead_source = "IVR"

            with patch('app.salesforce.httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True,
                    "recordID": "TEST123",
                    "message": "Lead created"
                }
                mock_response.raise_for_status = Mock()

                mock_async_client = AsyncMock()
                mock_async_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_async_client

                payload = {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "email": "jane@example.com",
                    "phone": "(555) 999-8888",
                    "address": "Texas",
                    "vehicle_make": "Yamaha",
                    "vehicle_model": "R1",
                    "vehicle_year": "2019",
                }

                result = await create_lead(payload)
                assert result == "TEST123"

                # Check that defaults were applied
                post_call = mock_async_client.__aenter__.return_value.post
                sent_data = post_call.call_args[1]['json']

                # Default values
                assert sent_data['zip'] == "00000"  # Default zipcode
                assert sent_data['vin'] == "N/A"  # Default VIN
                assert sent_data['milesHours'] == "1"  # Default miles/hours
                assert sent_data['askingPrice'] == 1  # Default asking price
                assert sent_data['sessionToken'] == ""
                assert sent_data['dataProviderDealerToken'] == ""
                assert sent_data['gclid'] == ""
                assert sent_data['resizeImages'] is False
                assert sent_data['isFinanced'] is False
                assert sent_data['okToText'] == "true"

                # Check default placeholder image
                assert len(sent_data['images']) == 1
                assert sent_data['images'][0]['name'] == "placeholder.png"
                assert 'base64' in sent_data['images'][0]

    @pytest.mark.asyncio
    async def test_create_lead_api_error(self):
        """Test handling of API errors"""
        with patch('app.salesforce.settings') as mock_settings:
            mock_settings.npa_api_username = "testuser"
            mock_settings.npa_api_password = "testpass"
            mock_settings.npa_api_base_url = "https://api.example.com"
            mock_settings.npa_lead_source = "IVR"

            with patch('app.salesforce.httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": False,
                    "recordID": None,
                    "message": "Invalid email format"
                }
                mock_response.raise_for_status = Mock()

                mock_async_client = AsyncMock()
                mock_async_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_async_client

                payload = {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "invalid-email",
                    "phone": "(555) 123-4567",
                    "address": "California",
                    "vehicle_make": "Honda",
                    "vehicle_model": "CBR",
                    "vehicle_year": "2021",
                }

                with pytest.raises(Exception) as exc_info:
                    await create_lead(payload)

                assert "NPA API error: Invalid email format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_lead_http_error(self):
        """Test handling of HTTP errors (4xx, 5xx)"""
        with patch('app.salesforce.settings') as mock_settings:
            mock_settings.npa_api_username = "testuser"
            mock_settings.npa_api_password = "testpass"
            mock_settings.npa_api_base_url = "https://api.example.com"
            mock_settings.npa_lead_source = "IVR"

            with patch('app.salesforce.httpx.AsyncClient') as mock_client:
                import httpx

                # Create a proper HTTP error response
                mock_response = Mock()
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"

                mock_async_client = AsyncMock()
                post_mock = AsyncMock(side_effect=httpx.HTTPStatusError(
                    "Server Error",
                    request=Mock(),
                    response=mock_response
                ))
                mock_async_client.__aenter__.return_value.post = post_mock
                mock_client.return_value = mock_async_client

                payload = {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com",
                    "phone": "(555) 123-4567",
                    "address": "California",
                    "vehicle_make": "Kawasaki",
                    "vehicle_model": "Ninja",
                    "vehicle_year": "2020",
                }

                with pytest.raises(httpx.HTTPStatusError):
                    await create_lead(payload)

    @pytest.mark.asyncio
    async def test_create_lead_field_mapping(self):
        """Test that all field mappings are correct (IVR fields -> API fields)"""
        with patch('app.salesforce.settings') as mock_settings:
            mock_settings.npa_api_username = "user"
            mock_settings.npa_api_password = "pass"
            mock_settings.npa_api_base_url = "https://api.example.com"
            mock_settings.npa_lead_source = "TestSource"

            with patch('app.salesforce.httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True,
                    "recordID": "TEST456"
                }
                mock_response.raise_for_status = Mock()

                mock_async_client = AsyncMock()
                mock_async_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_async_client

                payload = {
                    "first_name": "Alice",
                    "last_name": "Wonder",
                    "email": "alice@example.com",
                    "phone": "5551234567",
                    "address": "Nevada",
                    "zipcode": "90210",  # Optional, but should be used if provided
                    "vehicle_make": "Ducati",
                    "vehicle_model": "Panigale",
                    "vehicle_year": "2022",
                    "vin": "1234567890ABCDEFG",  # Optional
                    "miles_hours": "5000",  # Optional
                    "asking_price": "15000",  # Optional
                    "_channel": "voice",
                }

                result = await create_lead(payload)
                assert result == "TEST456"

                # Verify field mappings
                post_call = mock_async_client.__aenter__.return_value.post
                sent_data = post_call.call_args[1]['json']

                # IVR collected fields
                assert sent_data['firstName'] == "Alice"
                assert sent_data['lastName'] == "Wonder"
                assert sent_data['email'] == "alice@example.com"
                assert sent_data['phone'] == "5551234567"
                assert sent_data['state'] == "Nevada"
                assert sent_data['make'] == "Ducati"
                assert sent_data['model'] == "Panigale"
                assert sent_data['year'] == 2022

                # Optional fields that were provided
                assert sent_data['zip'] == "90210"
                assert sent_data['vin'] == "1234567890ABCDEFG"
                assert sent_data['milesHours'] == "5000"
                assert sent_data['askingPrice'] == 15000

                # Channel info
                assert "voice" in sent_data['additionalNotes']
                assert sent_data['leadSource'] == "TestSource"

    @pytest.mark.asyncio
    async def test_create_lead_year_conversion(self):
        """Test that vehicle year is properly converted to integer"""
        with patch('app.salesforce.settings') as mock_settings:
            mock_settings.npa_api_username = "user"
            mock_settings.npa_api_password = "pass"
            mock_settings.npa_api_base_url = "https://api.example.com"
            mock_settings.npa_lead_source = "IVR"

            with patch('app.salesforce.httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True,
                    "recordID": "TEST789"
                }
                mock_response.raise_for_status = Mock()

                mock_async_client = AsyncMock()
                mock_async_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_async_client

                # Test with string year
                payload = {
                    "first_name": "Bob",
                    "last_name": "Builder",
                    "email": "bob@example.com",
                    "phone": "(555) 111-2222",
                    "address": "Arizona",
                    "vehicle_make": "Polaris",
                    "vehicle_model": "RZR",
                    "vehicle_year": "2023",  # String
                }

                await create_lead(payload)

                post_call = mock_async_client.__aenter__.return_value.post
                sent_data = post_call.call_args[1]['json']
                assert sent_data['year'] == 2023
                assert isinstance(sent_data['year'], int)

    @pytest.mark.asyncio
    async def test_create_lead_empty_year(self):
        """Test handling of empty/missing vehicle year"""
        with patch('app.salesforce.settings') as mock_settings:
            mock_settings.npa_api_username = "user"
            mock_settings.npa_api_password = "pass"
            mock_settings.npa_api_base_url = "https://api.example.com"
            mock_settings.npa_lead_source = "IVR"

            with patch('app.salesforce.httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True,
                    "recordID": "TEST999"
                }
                mock_response.raise_for_status = Mock()

                mock_async_client = AsyncMock()
                mock_async_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_async_client

                payload = {
                    "first_name": "Charlie",
                    "last_name": "Brown",
                    "email": "charlie@example.com",
                    "phone": "(555) 333-4444",
                    "address": "Oregon",
                    "vehicle_make": "Can-Am",
                    "vehicle_model": "Spyder",
                    # No vehicle_year provided
                }

                await create_lead(payload)

                post_call = mock_async_client.__aenter__.return_value.post
                sent_data = post_call.call_args[1]['json']
                assert sent_data['year'] == 0  # Default for missing year

    @pytest.mark.asyncio
    async def test_create_lead_content_type_header(self):
        """Test that correct Content-Type header is sent"""
        with patch('app.salesforce.settings') as mock_settings:
            mock_settings.npa_api_username = "user"
            mock_settings.npa_api_password = "pass"
            mock_settings.npa_api_base_url = "https://api.example.com"
            mock_settings.npa_lead_source = "IVR"

            with patch('app.salesforce.httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True,
                    "recordID": "TESTCONTENT"
                }
                mock_response.raise_for_status = Mock()

                mock_async_client = AsyncMock()
                mock_async_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_async_client

                payload = {
                    "first_name": "Test",
                    "last_name": "User",
                    "email": "test@example.com",
                    "phone": "(555) 555-5555",
                    "address": "Utah",
                    "vehicle_make": "KTM",
                    "vehicle_model": "Duke",
                    "vehicle_year": "2021",
                }

                await create_lead(payload)

                post_call = mock_async_client.__aenter__.return_value.post
                headers = post_call.call_args[1]['headers']
                assert headers['Content-Type'] == "application/json-patch+json"
                assert headers['accept'] == "application/json"
