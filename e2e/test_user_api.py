import requests
import json
import pytest

BASE_URL = "http://localhost:8080/api"

class TestUserManagement:
    
    def setup_class(self):
        """Setup: Login as admin to get token (if needed in future)"""
        self.admin_username = "Admin"
        self.admin_password = "password"
        self.test_user = {
            "username": "e2e_inspector",
            "password": "password123",
            "role": "INSPECTOR",
            "projectPermissions": []
        }
        
    def test_01_admin_login(self):
        """Test admin login functionality"""
        url = f"{BASE_URL}/auth/login"
        payload = {
            "username": self.admin_username,
            "password": self.admin_password
        }
        response = requests.post(url, json=payload)
        
        print(f"\nAdmin Login Response: {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert data["Code"] == 200
        assert data["Data"]["username"] == self.admin_username
        assert "token" in data["Data"]
        
    def test_02_create_user(self):
        """Test creating a new user"""
        url = f"{BASE_URL}/users"
        response = requests.post(url, json=self.test_user)
        
        print(f"\nCreate User Response: {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert data["Code"] == 200
        user_data = data["Data"]
        assert user_data["username"] == self.test_user["username"]
        assert user_data["role"] == self.test_user["role"]
        
        # Store user_id for later tests
        TestUserManagement.user_id = user_data["userId"]

    def test_03_get_user_list(self):
        """Test fetching user list"""
        url = f"{BASE_URL}/users"
        response = requests.get(url)
        
        assert response.status_code == 200
        data = response.json()
        assert data["Code"] == 200
        users = data["Data"]["content"] # Page object uses 'content'
        
        # Verify our created user is in the list
        found = False
        for user in users:
            if user["username"] == self.test_user["username"]:
                found = True
                break
        assert found, "Created user not found in user list"

    def test_04_update_user(self):
        """Test updating user password"""
        if not hasattr(TestUserManagement, 'user_id'):
            pytest.skip("Skipping update test because creation failed")
            
        url = f"{BASE_URL}/users/{TestUserManagement.user_id}"
        new_password = "new_password_456"
        payload = {
            "password": new_password
        }
        
        response = requests.put(url, json=payload)
        print(f"\nUpdate User Response: {response.text}")
        
        assert response.status_code == 200
        assert response.json()["Code"] == 200
        
        # Verify login with new password
        login_url = f"{BASE_URL}/auth/login"
        login_payload = {
            "username": self.test_user["username"],
            "password": new_password
        }
        login_response = requests.post(login_url, json=login_payload)
        assert login_response.status_code == 200
        assert login_response.json()["Code"] == 200

    def test_05_delete_user(self):
        """Test deleting the user"""
        if not hasattr(TestUserManagement, 'user_id'):
            pytest.skip("Skipping delete test because creation failed")
            
        url = f"{BASE_URL}/users/{TestUserManagement.user_id}"
        response = requests.delete(url)
        
        assert response.status_code == 200
        
        # Verify user is gone
        get_response = requests.get(url)
        # Assuming get returns 400 or valid error wrapper when not found
        # Based on controller: catch IllegalArgument -> 400
        assert get_response.status_code == 400

if __name__ == "__main__":
    # Allow running directly with python
    t = TestUserManagement()
    t.setup_class()
    t.test_01_admin_login()
    t.test_02_create_user()
    t.test_03_get_user_list()
    t.test_04_update_user()
    t.test_05_delete_user()
    print("\nAll E2E tests passed!")


