#!/usr/bin/env python3
"""
WhatsApp CRM Backend API Testing Suite
Tests P2 File Upload and core backend functionality
"""

import requests
import json
import os
import tempfile
from typing import Dict, Any, Optional

# Configuration
BACKEND_URL = "https://easy-wapp.preview.emergentagent.com/api"
TEST_CREDENTIALS = {
    "email": "admin@minhaempresa.com",
    "password": "123456"
}

class BackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.tenant_id = None
        self.conversation_id = None
        self.test_results = []
        
    def log_result(self, test_name: str, success: bool, message: str, details: Any = None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details
        })
        
    def test_health_check(self) -> bool:
        """Test health check endpoint"""
        try:
            response = self.session.get(f"{BACKEND_URL}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log_result("Health Check", True, "API is healthy")
                    return True
                else:
                    self.log_result("Health Check", False, f"Unhealthy status: {data}")
                    return False
            else:
                self.log_result("Health Check", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Health Check", False, f"Connection error: {str(e)}")
            return False
    
    def test_authentication(self) -> bool:
        """Test authentication endpoint"""
        try:
            response = self.session.post(
                f"{BACKEND_URL}/auth/login",
                json=TEST_CREDENTIALS,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "token" in data and "user" in data:
                    self.token = data["token"]
                    self.tenant_id = data["user"].get("tenantId")
                    
                    # Set authorization header for future requests
                    self.session.headers.update({
                        "Authorization": f"Bearer {self.token}"
                    })
                    
                    self.log_result("Authentication", True, 
                                  f"Login successful. User: {data['user'].get('name')}, Tenant: {self.tenant_id}")
                    return True
                else:
                    self.log_result("Authentication", False, f"Missing token or user in response: {data}")
                    return False
            else:
                self.log_result("Authentication", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Authentication", False, f"Request error: {str(e)}")
            return False
    
    def test_conversations_api(self) -> bool:
        """Test conversations API"""
        if not self.token or not self.tenant_id:
            self.log_result("Conversations API", False, "No authentication token or tenant_id")
            return False
            
        try:
            response = self.session.get(
                f"{BACKEND_URL}/conversations",
                params={"tenant_id": self.tenant_id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    # Store first conversation ID for message testing
                    if data and len(data) > 0:
                        self.conversation_id = data[0].get("id")
                    
                    self.log_result("Conversations API", True, 
                                  f"Retrieved {len(data)} conversations. First conv ID: {self.conversation_id}")
                    return True
                else:
                    self.log_result("Conversations API", False, f"Expected list, got: {type(data)}")
                    return False
            else:
                self.log_result("Conversations API", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Conversations API", False, f"Request error: {str(e)}")
            return False
    
    def test_messages_api(self) -> bool:
        """Test messages API"""
        if not self.token or not self.conversation_id:
            self.log_result("Messages API", False, "No authentication token or conversation_id")
            return False
            
        try:
            response = self.session.get(
                f"{BACKEND_URL}/messages",
                params={"conversation_id": self.conversation_id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    self.log_result("Messages API", True, 
                                  f"Retrieved {len(data)} messages for conversation {self.conversation_id}")
                    return True
                else:
                    self.log_result("Messages API", False, f"Expected list, got: {type(data)}")
                    return False
            else:
                self.log_result("Messages API", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Messages API", False, f"Request error: {str(e)}")
            return False
    
    def test_file_upload(self) -> bool:
        """Test P2 file upload endpoint"""
        if not self.token or not self.conversation_id:
            self.log_result("File Upload (P2)", False, "No authentication token or conversation_id")
            return False
            
        try:
            # Create a test file
            test_content = "This is a test file for WhatsApp CRM file upload feature.\nTesting P2 functionality."
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(test_content)
                temp_file_path = temp_file.name
            
            try:
                # Prepare multipart form data
                with open(temp_file_path, 'rb') as f:
                    files = {
                        'file': ('test_document.txt', f, 'text/plain')
                    }
                    data = {
                        'conversation_id': self.conversation_id
                    }
                    
                    response = self.session.post(
                        f"{BACKEND_URL}/upload",
                        files=files,
                        data=data,
                        timeout=30
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    required_fields = ['id', 'url', 'name', 'type', 'size']
                    if all(field in result for field in required_fields):
                        self.log_result("File Upload (P2)", True, 
                                      f"File uploaded successfully. URL: {result['url'][:50]}..., Type: {result['type']}, Size: {result['size']} bytes")
                        return True
                    else:
                        missing = [f for f in required_fields if f not in result]
                        self.log_result("File Upload (P2)", False, f"Missing fields in response: {missing}")
                        return False
                else:
                    self.log_result("File Upload (P2)", False, f"HTTP {response.status_code}: {response.text}")
                    return False
                    
            finally:
                # Clean up temp file
                os.unlink(temp_file_path)
                
        except Exception as e:
            self.log_result("File Upload (P2)", False, f"Request error: {str(e)}")
            return False
    
    def test_media_message(self) -> bool:
        """Test P2 media message endpoint"""
        if not self.token or not self.conversation_id:
            self.log_result("Media Message (P2)", False, "No authentication token or conversation_id")
            return False
            
        try:
            # Test with a sample media URL (using a data URL for testing)
            test_media_url = "data:text/plain;base64,VGVzdCBtZWRpYSBjb250ZW50IGZvciBXaGF0c0FwcCBDUk0="
            
            data = {
                'conversation_id': self.conversation_id,
                'content': 'Test media message from backend testing',
                'media_type': 'document',
                'media_url': test_media_url,
                'media_name': 'test_media.txt'
            }
            
            response = self.session.post(
                f"{BACKEND_URL}/messages/media",
                data=data,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                
                required_fields = ['id', 'conversationId', 'content', 'type', 'direction', 'status']
                if all(field in result for field in required_fields):
                    self.log_result("Media Message (P2)", True, 
                                  f"Media message sent successfully. ID: {result['id']}, Type: {result['type']}")
                    return True
                else:
                    missing = [f for f in required_fields if f not in result]
                    self.log_result("Media Message (P2)", False, f"Missing fields in response: {missing}")
                    return False
            else:
                self.log_result("Media Message (P2)", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Media Message (P2)", False, f"Request error: {str(e)}")
            return False
    
    def test_current_user(self) -> bool:
        """Test current user endpoint"""
        if not self.token:
            self.log_result("Current User", False, "No authentication token")
            return False
            
        try:
            response = self.session.get(f"{BACKEND_URL}/auth/me", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                required_fields = ['id', 'email', 'name', 'role', 'tenantId']
                if all(field in data for field in required_fields):
                    self.log_result("Current User", True, 
                                  f"User info retrieved. Name: {data['name']}, Role: {data['role']}")
                    return True
                else:
                    missing = [f for f in required_fields if f not in data]
                    self.log_result("Current User", False, f"Missing fields: {missing}")
                    return False
            else:
                self.log_result("Current User", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Current User", False, f"Request error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all backend tests"""
        print("=" * 60)
        print("WhatsApp CRM Backend API Testing Suite")
        print("=" * 60)
        print(f"Backend URL: {BACKEND_URL}")
        print(f"Test Credentials: {TEST_CREDENTIALS['email']}")
        print("=" * 60)
        
        # Test sequence
        tests = [
            ("Health Check", self.test_health_check),
            ("Authentication", self.test_authentication),
            ("Current User", self.test_current_user),
            ("Conversations API", self.test_conversations_api),
            ("Messages API", self.test_messages_api),
            ("File Upload (P2)", self.test_file_upload),
            ("Media Message (P2)", self.test_media_message),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n--- Testing {test_name} ---")
            if test_func():
                passed += 1
        
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        # Show failed tests
        failed_tests = [r for r in self.test_results if not r['success']]
        if failed_tests:
            print("\nFAILED TESTS:")
            for test in failed_tests:
                print(f"❌ {test['test']}: {test['message']}")
        
        print("=" * 60)
        
        return passed, total, self.test_results

if __name__ == "__main__":
    tester = BackendTester()
    passed, total, results = tester.run_all_tests()
    
    # Exit with error code if any tests failed
    exit(0 if passed == total else 1)